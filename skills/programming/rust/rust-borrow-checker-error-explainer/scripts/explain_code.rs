//! Explain one borrow-checker error code or pattern: meaning, ranked fixes, related patterns.
//!
//! Build: rustc -O --edition 2021 scripts/explain_code.rs -o /tmp/explain_code
//! Usage: explain_code E0502 | BCK002 | iterate-and-mutate | --list [--json]
//! Exit:  0 explained, 2 unknown code or usage error.

mod catalog;
mod common;

use catalog::{find_code, find_pattern, tier_name, Fix, Pattern, CODES, PATTERNS, RUNTIME_PATTERNS};
use common::{die, json_str};

const USAGE: &str = "usage: explain_code <CODE|PATTERN> [--json]
       explain_code --list [--json]

Explain a Rust borrow/ownership error code (E0382, E0499, E0502, E0505, E0507,
E0515, E0597, E0716, E0373, ...; `lifetime` and `not-send` for the uncoded
'lifetime may not live long enough' / 'future cannot be sent' errors) or a
pattern id/name from parse_diagnostics (BCK001..BCK030, iterate-and-mutate, ...).

Fixes are ranked by tier: restructure > std api > own the data > shared
ownership > last resort. unsafe is never offered as a fix.

options:
  --list    list every code and pattern
  --json    machine-readable output
  -h, --help";

fn fixes_text(fixes: &[Fix]) -> String {
    fixes
        .iter()
        .enumerate()
        .map(|(i, f)| format!("  {}. [{}] {}\n", i + 1, tier_name(f.tier), f.text))
        .collect()
}

fn fixes_json(fixes: &[Fix]) -> String {
    let items: Vec<String> = fixes
        .iter()
        .map(|f| format!("{{\"tier\":{},\"text\":{}}}", json_str(tier_name(f.tier)), json_str(f.text)))
        .collect();
    format!("[{}]", items.join(","))
}

fn pattern_json(p: &Pattern) -> String {
    let codes: Vec<String> = p.codes.iter().map(|c| c.to_string()).collect();
    format!(
        "{{\"id\":{},\"name\":{},\"codes\":{},\"why\":{},\"fixes\":{}}}",
        json_str(p.id), json_str(p.name), common::json_list(&codes), json_str(p.why), fixes_json(p.fixes)
    )
}

fn list(json: bool) {
    let all_patterns = PATTERNS.iter().chain(RUNTIME_PATTERNS);
    if json {
        let codes: Vec<String> = CODES
            .iter()
            .map(|c| format!("{{\"code\":{},\"title\":{}}}", json_str(c.code), json_str(c.title)))
            .collect();
        let pats: Vec<String> = all_patterns
            .map(|p| format!("{{\"id\":{},\"name\":{}}}", json_str(p.id), json_str(p.name)))
            .collect();
        println!("{{\"codes\":[{}],\"patterns\":[{}]}}", codes.join(","), pats.join(","));
        return;
    }
    println!("Error codes:");
    for c in CODES {
        println!("  {:<9} {}", c.code, c.title);
    }
    println!("\nPatterns:");
    let mut pats: Vec<&Pattern> = all_patterns.collect();
    pats.sort_by_key(|p| p.id);
    for p in pats {
        println!("  {}  {:<36} {}", p.id, p.name, p.codes.join(", "));
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let json = args.iter().any(|a| a == "--json");
    if args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        return;
    }
    if args.iter().any(|a| a == "--list") {
        return list(json);
    }
    let keys: Vec<&String> = args.iter().filter(|a| !a.starts_with("--")).collect();
    let [key] = keys.as_slice() else { die(&format!("expected one code or pattern\n\n{USAGE}")) };
    let key = key.trim().trim_start_matches("error[").trim_end_matches(']');

    if let Some(code) = find_code(key) {
        let related: Vec<&Pattern> = PATTERNS.iter().filter(|p| p.codes.contains(&code.code)).collect();
        if json {
            let rel: Vec<String> = related.iter().map(|p| pattern_json(p)).collect();
            println!(
                "{{\"code\":{},\"title\":{},\"meaning\":{},\"fixes\":{},\"patterns\":[{}]}}",
                json_str(code.code), json_str(code.title), json_str(code.meaning), fixes_json(code.fixes), rel.join(",")
            );
            return;
        }
        println!("{}: {}\n\n{}\n\nFixes, best first:\n{}", code.code, code.title, code.meaning, fixes_text(code.fixes));
        if !related.is_empty() {
            println!("Patterns that produce {}:", code.code);
            for p in related {
                println!("  {} {}: {}", p.id, p.name, p.why);
            }
        }
        if code.code.starts_with('E') {
            println!("\nFull compiler text: rustc --explain {}", code.code);
        }
    } else if let Some(p) = find_pattern(key) {
        if json {
            println!("{}", pattern_json(p));
            return;
        }
        println!("{} {} ({})\n\n{}\n\nFixes, best first:\n{}", p.id, p.name, p.codes.join(", "), p.why, fixes_text(p.fixes));
    } else {
        die(&format!("unknown code or pattern '{key}'; run with --list to see what is covered"));
    }
}
