//! Command line, file walking, edition detection and reporting shared by the lifetime scripts.
//! Not an entry point; pulled in with `mod cli;`.
#![allow(dead_code)]

use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::exit;

pub struct Rule {
    pub id: &'static str,
    pub name: &'static str,
    pub severity: &'static str,
    pub why: &'static str,
    pub fix: &'static str,
}

pub struct Finding {
    pub file: String,
    pub line: usize,
    pub id: &'static str,
    pub msg: String,
    pub fix: String,
}

pub struct Input {
    pub name: String,
    pub text: String,
    pub edition: u32,
}

pub struct Opts {
    pub paths: Vec<String>,
    pub json: bool,
    pub strict: bool,
    select: Vec<String>,
    ignore: Vec<String>,
    edition: Option<u32>,
    values: Vec<(String, String)>,
}

pub fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    exit(2);
}

pub const COMMON_OPTIONS: &str = "options:
  --json               machine-readable findings
  --strict             exit 1 when there are findings (CI gate)
  --select IDS         only these rules (ids, id prefixes or names, comma separated)
  --ignore IDS         skip these rules
  --edition YEAR       2015|2018|2021|2024; default: from the nearest Cargo.toml (stdin: 2021)
  --list-rules         print every rule with why and fix
  -h, --help
Silence one line with `// noqa: LT001`. Exit: 0 clean (or findings without --strict),
1 findings with --strict, 2 usage error or unreadable file.";

/// Parse argv. `value_flags` are script-specific options that take a value (e.g. "--max-lifetimes").
pub fn parse(usage: &str, rules: &[Rule], value_flags: &[&str]) -> Opts {
    let mut o = Opts { paths: vec![], json: false, strict: false, select: vec![], ignore: vec![], edition: None, values: vec![] };
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        let mut value = |name: &str| args.next().unwrap_or_else(|| die(&format!("{name} needs a value")));
        match a.as_str() {
            "-h" | "--help" => { println!("{usage}\n\n{COMMON_OPTIONS}"); exit(0) }
            "--list-rules" => {
                for r in rules {
                    println!("{} {} [{}]\n  why: {}\n  fix: {}", r.id, r.name, r.severity, r.why, r.fix);
                }
                exit(0)
            }
            "--json" => o.json = true,
            "--strict" => o.strict = true,
            "--select" => o.select = list(&value("--select")),
            "--ignore" => o.ignore = list(&value("--ignore")),
            "--edition" => {
                let v = value("--edition");
                o.edition = match v.as_str() {
                    "auto" => None,
                    "2015" | "2018" | "2021" | "2024" => v.parse().ok(),
                    _ => die(&format!("unknown edition {v}")),
                }
            }
            f if value_flags.contains(&f) => { let v = value(f); o.values.push((f.to_string(), v)) }
            f if f.starts_with("--") => die(&format!("unknown option {f}\n\n{usage}")),
            _ => o.paths.push(a),
        }
    }
    if o.paths.is_empty() {
        die(&format!("no input; pass files, directories or - for stdin\n\n{usage}"));
    }
    for key in o.select.iter().chain(&o.ignore) {
        if !rules.iter().any(|r| matches(r, key)) {
            die(&format!("unknown rule {key}; see --list-rules"));
        }
    }
    o
}

fn list(s: &str) -> Vec<String> {
    s.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect()
}

fn matches(r: &Rule, key: &str) -> bool {
    r.id.starts_with(&key.to_uppercase()) || r.name == key
}

impl Opts {
    pub fn enabled(&self, r: &Rule) -> bool {
        (self.select.is_empty() || self.select.iter().any(|k| matches(r, k))) && !self.ignore.iter().any(|k| matches(r, k))
    }

    pub fn value(&self, flag: &str) -> Option<&str> {
        self.values.iter().rev().find(|(f, _)| f == flag).map(|(_, v)| v.as_str())
    }

    /// Read every input: `-` (stdin), files, and `.rs` files under directories (skips target/, .git/).
    pub fn inputs(&self) -> Vec<Input> {
        let mut files = Vec::new();
        for p in &self.paths {
            if p == "-" {
                let mut text = String::new();
                std::io::stdin().read_to_string(&mut text).unwrap_or_else(|e| die(&format!("cannot read stdin: {e}")));
                files.push(Input { name: "<stdin>".into(), text, edition: self.edition.unwrap_or(2021) });
                continue;
            }
            let path = PathBuf::from(p);
            let mut found = Vec::new();
            if path.is_dir() {
                walk(&path, &mut found);
                found.sort();
            } else {
                found.push(path);
            }
            for f in found {
                let text = std::fs::read_to_string(&f).unwrap_or_else(|e| die(&format!("cannot read {}: {e}", f.display())));
                let edition = self.edition.unwrap_or_else(|| edition_for(&f));
                files.push(Input { name: f.display().to_string(), text, edition });
            }
        }
        files
    }
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else { return };
    for e in entries.flatten() {
        let p = e.path();
        let name = e.file_name();
        if p.is_dir() {
            if name != "target" && name != ".git" {
                walk(&p, out);
            }
        } else if p.extension().is_some_and(|x| x == "rs") {
            out.push(p);
        }
    }
}

/// Edition from the nearest Cargo.toml that states one (follows `edition.workspace = true` upward).
pub fn edition_for(file: &Path) -> u32 {
    let mut dir = file.canonicalize().ok().and_then(|p| p.parent().map(Path::to_path_buf));
    while let Some(d) = dir {
        if let Ok(toml) = std::fs::read_to_string(d.join("Cargo.toml")) {
            for line in toml.lines() {
                let l = line.trim();
                if let Some(v) = l.strip_prefix("edition").map(str::trim).and_then(|r| r.strip_prefix('=')) {
                    if let Ok(year) = v.trim().trim_matches('"').parse() {
                        return year;
                    }
                }
            }
        }
        dir = d.parent().map(Path::to_path_buf);
    }
    2021
}

fn json_str(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// Print findings and exit with the documented code.
pub fn finish(opts: &Opts, rules: &[Rule], mut findings: Vec<Finding>, nfiles: usize, topic: &str) -> ! {
    findings.sort_by(|a, b| (&a.file, a.line, a.id).cmp(&(&b.file, b.line, b.id)));
    let rule = |id: &str| rules.iter().find(|r| r.id == id).expect("rule id");
    if opts.json {
        let items: Vec<String> = findings
            .iter()
            .map(|f| {
                let r = rule(f.id);
                format!(
                    "{{\"file\":{},\"line\":{},\"rule\":{},\"name\":{},\"severity\":{},\"message\":{},\"fix\":{}}}",
                    json_str(&f.file), f.line, json_str(r.id), json_str(r.name), json_str(r.severity), json_str(&f.msg), json_str(&f.fix)
                )
            })
            .collect();
        println!("{{\"files\":{},\"findings\":[{}]}}", nfiles, items.join(","));
    } else if findings.is_empty() {
        println!("No {topic} issues found in {nfiles} file(s).");
    } else {
        for f in &findings {
            let r = rule(f.id);
            println!("{}:{}: {} [{}] {}: {}", f.file, f.line, r.id, r.severity, r.name, f.msg);
            if !f.fix.is_empty() {
                println!("    fix: {}", f.fix);
            }
        }
        println!("\n{} finding(s) in {} file(s).", findings.len(), nfiles);
    }
    exit(if opts.strict && !findings.is_empty() { 1 } else { 0 })
}
