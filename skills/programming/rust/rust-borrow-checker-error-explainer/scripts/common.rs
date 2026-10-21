//! Shared helpers for the borrow-checker scripts: input, JSON output, cargo JSON lines.
//! Not an entry point; each script pulls it in with `mod common;`.
#![allow(dead_code)] // not every script uses every helper

use std::io::Read;
use std::process;

/// Print `msg` to stderr and exit with code 2 (usage or input error).
pub fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    process::exit(2);
}

/// Read a file, or stdin when `path` is "-".
pub fn read_input(path: &str) -> String {
    let mut text = String::new();
    let result = if path == "-" {
        std::io::stdin().read_to_string(&mut text).map(|_| ())
    } else {
        std::fs::read_to_string(path).map(|t| text = t)
    };
    if let Err(e) = result {
        die(&format!("cannot read {path}: {e}"));
    }
    text
}

/// Quote and escape a string for JSON output.
pub fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// `["a","b"]` from a list of strings.
pub fn json_list(items: &[String]) -> String {
    let parts: Vec<String> = items.iter().map(|s| json_str(s)).collect();
    format!("[{}]", parts.join(","))
}

/// Decode the JSON string value of the first `"key":"..."` in `line`.
/// Enough for cargo/rustc `--message-format=json`, whose `rendered` field holds the
/// exact text rustc prints, so one text parser handles both formats.
pub fn json_string_field(line: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":\"");
    let start = line.find(&needle)? + needle.len();
    let mut out = String::new();
    let mut chars = line[start..].chars();
    while let Some(c) = chars.next() {
        match c {
            '"' => return Some(out),
            '\\' => match chars.next()? {
                'n' => out.push('\n'),
                't' => out.push('\t'),
                'r' => out.push('\r'),
                'b' => out.push('\u{8}'),
                'f' => out.push('\u{c}'),
                'u' => {
                    let hi = hex4(&mut chars)?;
                    let code = if (0xD800..0xDC00).contains(&hi) {
                        // surrogate pair: 😀
                        if chars.next()? != '\\' || chars.next()? != 'u' {
                            return None;
                        }
                        let lo = hex4(&mut chars)?;
                        0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                    } else {
                        hi
                    };
                    out.push(char::from_u32(code).unwrap_or('\u{fffd}'));
                }
                other => out.push(other), // \" \\ \/
            },
            c => out.push(c),
        }
    }
    None
}

fn hex4(chars: &mut std::str::Chars) -> Option<u32> {
    let s: String = chars.by_ref().take(4).collect();
    u32::from_str_radix(&s, 16).ok()
}

/// Turn cargo/rustc JSON lines into the plain text rustc would print; plain text passes through.
pub fn normalize(input: &str) -> String {
    let mut out = String::new();
    for line in input.lines() {
        let t = line.trim_start();
        if t.starts_with('{') && t.contains("\"rendered\"") {
            if let Some(r) = json_string_field(t, "rendered") {
                out.push_str(&r);
                out.push('\n');
            }
        } else if !t.starts_with('{') {
            out.push_str(line);
            out.push('\n');
        }
    }
    out
}
