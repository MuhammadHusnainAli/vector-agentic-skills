//! Explain every borrow/ownership error in rustc or cargo output (text or --message-format=json).
//!
//! Build: rustc -O --edition 2021 scripts/parse_diagnostics.rs -o /tmp/parse_diagnostics
//! Usage: parse_diagnostics build.txt | -   [--json] [--strict]
//! Exit:  0 done (unclassified errors listed but tolerated), 1 --strict and an error is not a
//!        borrow/ownership error, 2 usage error or empty input.

mod catalog;
mod common;

use catalog::{classify, find_code, tier_name, Fix};
use common::{die, json_list, json_str, normalize, read_input};

const USAGE: &str = "usage: parse_diagnostics <FILE|-> [--json] [--strict]

Read `cargo check`/`cargo build`/`cargo test` output (plain text, or JSON lines from
--message-format=json) and, for every error: the code, location, the compiler's labels
(borrow created / conflicting use / used later) with line numbers, help lines, the
recurring pattern (BCK id) and fixes ranked best first. Warnings are counted, not shown.

  cargo check 2> build.txt; parse_diagnostics build.txt
  cargo check --message-format=json | parse_diagnostics -

options:
  --json    machine-readable report
  --strict  exit 1 if any error is not a borrow/ownership error
  -h, --help";

#[derive(Default)]
struct Diag {
    code: String,    // "E0502", a pseudo code ("lifetime", "not-send"), or "" when unknown
    message: String,
    location: String,
    labels: Vec<(String, String)>, // (source line number, label)
    help: Vec<String>,
    raw: String, // lower-cased text, for pattern matching
}

/// Header of a new diagnostic: `error[E0502]: msg`, `error: msg`, `warning: msg`.
fn header(line: &str) -> Option<(bool, String, String)> {
    let (is_error, rest) = if let Some(r) = line.strip_prefix("error") {
        (true, r)
    } else if let Some(r) = line.strip_prefix("warning") {
        (false, r)
    } else {
        return None;
    };
    let (code, msg) = if let Some(r) = rest.strip_prefix('[') {
        let end = r.find("]: ")?;
        (r[..end].to_string(), r[end + 3..].to_string())
    } else {
        (String::new(), rest.strip_prefix(": ")?.to_string())
    };
    Some((is_error, code, msg))
}

/// A line that belongs to the current diagnostic: indented gutter/arrow lines, numbered
/// source lines (`40 |`), `...` elisions and help/note lines.
fn is_body(line: &str) -> bool {
    let t = line.trim_start();
    if t.is_empty() {
        return false;
    }
    let digits = t.len() - t.trim_start_matches(|c: char| c.is_ascii_digit()).len();
    line.starts_with(' ')
        || t == "..."
        || ["help", "note", "|", "="].iter().any(|p| t.starts_with(p))
        || (digits > 0 && t[digits..].trim_start().starts_with('|'))
}

/// Cargo/rustc summary lines that look like errors but are not diagnostics.
fn is_summary(msg: &str) -> bool {
    ["could not compile", "aborting due to", "test failed", "build failed"].iter().any(|s| msg.starts_with(s))
}

fn pseudo_code(msg: &str) -> &'static str {
    if msg.starts_with("lifetime may not live long enough") {
        "lifetime"
    } else if msg.contains("cannot be sent between threads safely") {
        "not-send"
    } else {
        ""
    }
}

fn parse(text: &str) -> (Vec<Diag>, usize) {
    let mut diags = Vec::new();
    let mut warnings = 0;
    let mut cur: Option<Diag> = None;
    let mut in_help = false;
    let mut src_line = String::new();
    for line in text.lines() {
        if let Some((is_error, code, msg)) = header(line) {
            diags.extend(cur.take());
            in_help = false;
            if !is_error {
                warnings += usize::from(!msg.contains("generated") && !msg.contains("emitted"));
            } else if !is_summary(&msg) {
                let code = if code.is_empty() { pseudo_code(&msg).to_string() } else { code };
                cur = Some(Diag { code, message: msg, ..Default::default() });
            }
            continue;
        }
        let Some(d) = cur.as_mut() else { continue };
        let t = line.trim_start();
        if !is_body(line) {
            diags.extend(cur.take()); // blank line or unrelated output ends the diagnostic
            continue;
        }
        d.raw.push_str(&line.to_lowercase());
        d.raw.push('\n');
        if let Some(loc) = t.strip_prefix("--> ") {
            if d.location.is_empty() {
                d.location = loc.to_string();
            }
        } else if let Some(h) = t.strip_prefix("help: ").or_else(|| t.strip_prefix("= help: ")) {
            d.help.push(h.to_string());
            in_help = true;
        } else if t.starts_with("note:") || t.starts_with("= note:") {
            in_help = true; // notes point into other files; their labels are not ours
        } else if !in_help && t != "..." {
            // `40 |  code`  or  `   |  ---- label`
            let (num, rest) = t.split_once('|').unwrap_or(("", t));
            if !num.trim().is_empty() && num.trim().chars().all(|c| c.is_ascii_digit()) {
                src_line = num.trim().to_string();
            } else if num.trim().is_empty() {
                let label = rest.trim_start_matches(|c: char| " |_-^~+/\\".contains(c)).trim();
                if !label.is_empty() {
                    d.labels.push((src_line.clone(), label.to_string()));
                }
            }
        }
    }
    diags.extend(cur);
    (diags, warnings)
}

struct Explained<'a> {
    diag: &'a Diag,
    meaning: Option<&'static str>,
    pattern: Option<(&'static str, &'static str, &'static str)>,
    fixes: &'static [Fix],
}

fn explain(d: &Diag) -> Explained<'_> {
    let haystack = format!("{}\n{}", d.message.to_lowercase(), d.raw);
    let code = find_code(&d.code);
    let pattern = classify(&d.code, &haystack);
    let known = match code {
        Some(c) => !c.needs_pattern || pattern.is_some(),
        None => false,
    };
    Explained {
        diag: d,
        meaning: code.filter(|_| known).map(|c| c.meaning),
        pattern: pattern.filter(|_| known).map(|p| (p.id, p.name, p.why)),
        fixes: match (known, pattern) {
            (true, Some(p)) => p.fixes,
            (true, None) => code.map_or(&[][..], |c| c.fixes),
            _ => &[],
        },
    }
}

fn print_text(all: &[Explained], warnings: usize) {
    for e in all {
        let d = e.diag;
        let code = if d.code.is_empty() { "error".to_string() } else { format!("error[{}]", d.code) };
        println!("{code} {}  {}", d.location, d.message);
        let Some(meaning) = e.meaning else {
            println!("  not a borrow/ownership error; see `rustc --explain` or the compiler's help\n");
            continue;
        };
        println!("  meaning : {meaning}");
        for (i, (line, label)) in d.labels.iter().enumerate() {
            let prefix = if i == 0 { "  labels  :" } else { "           " };
            println!("{prefix} L{line:<4} {label}");
        }
        for h in &d.help {
            println!("  compiler: help: {h}");
        }
        if let Some((id, name, why)) = e.pattern {
            println!("  pattern : {id} {name}: {why}");
        }
        for (i, f) in e.fixes.iter().enumerate() {
            let prefix = if i == 0 { "  fixes   :" } else { "           " };
            println!("{prefix} {}. [{}] {}", i + 1, tier_name(f.tier), f.text);
        }
        println!();
    }
    let explained = all.iter().filter(|e| e.meaning.is_some()).count();
    if all.is_empty() {
        println!("No compiler errors found ({warnings} warning(s) ignored).");
    } else {
        println!(
            "{} error(s): {} borrow/ownership explained, {} other; {} warning(s) ignored.",
            all.len(), explained, all.len() - explained, warnings
        );
    }
}

fn print_json(all: &[Explained], warnings: usize) {
    let items: Vec<String> = all
        .iter()
        .map(|e| {
            let d = e.diag;
            let labels: Vec<String> = d
                .labels
                .iter()
                .map(|(l, t)| format!("{{\"line\":{},\"text\":{}}}", l.parse::<u32>().unwrap_or(0), json_str(t)))
                .collect();
            let fixes: Vec<String> = e
                .fixes
                .iter()
                .map(|f| format!("{{\"tier\":{},\"text\":{}}}", json_str(tier_name(f.tier)), json_str(f.text)))
                .collect();
            let pattern = e.pattern.map_or("null".into(), |(id, name, _)| {
                format!("{{\"id\":{},\"name\":{}}}", json_str(id), json_str(name))
            });
            format!(
                "{{\"code\":{},\"message\":{},\"location\":{},\"explained\":{},\"labels\":[{}],\"help\":{},\"pattern\":{},\"fixes\":[{}]}}",
                json_str(&d.code), json_str(&d.message), json_str(&d.location), e.meaning.is_some(),
                labels.join(","), json_list(&d.help), pattern, fixes.join(",")
            )
        })
        .collect();
    println!("{{\"errors\":[{}],\"warnings\":{}}}", items.join(","), warnings);
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        return;
    }
    let json = args.iter().any(|a| a == "--json");
    let strict = args.iter().any(|a| a == "--strict");
    if let Some(bad) = args.iter().find(|a| a.starts_with("--") && !["--json", "--strict"].contains(&a.as_str())) {
        die(&format!("unknown option {bad}\n\n{USAGE}"));
    }
    let paths: Vec<&String> = args.iter().filter(|a| !a.starts_with("--")).collect();
    let [path] = paths.as_slice() else { die(&format!("expected one input file or -\n\n{USAGE}")) };

    let text = normalize(&read_input(path));
    if text.trim().is_empty() {
        die("input is empty; capture it with `cargo check 2> build.txt` or --message-format=json");
    }
    let (diags, warnings) = parse(&text);
    let all: Vec<Explained> = diags.iter().map(explain).collect();
    if json {
        print_json(&all, warnings);
    } else {
        print_text(&all, warnings);
    }
    let other = all.iter().filter(|e| e.meaning.is_none()).count();
    std::process::exit(if strict && other > 0 { 1 } else { 0 });
}
