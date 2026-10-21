//! Explain runtime borrow failures in test or program output: RefCell `already borrowed`
//! panics and Mutex `PoisonError`s, linking each poisoned lock to the panic that poisoned it.
//!
//! Build: rustc -O --edition 2021 scripts/runtime_panic.rs -o /tmp/runtime_panic
//! Usage: runtime_panic test-output.txt | -   [--json] [--strict]
//! Exit:  0 done, 1 --strict and a panic is neither borrow-related nor a poisoning root cause,
//!        2 usage error or empty input.

mod catalog;
mod common;

use catalog::{tier_name, Pattern, RUNTIME_PATTERNS};
use common::{die, json_str, read_input};

const USAGE: &str = "usage: runtime_panic <FILE|-> [--json] [--strict]

Find panics in `cargo test` / program output and explain the borrow-related ones:
  BCK024 refcell-double-borrow  already borrowed: BorrowMutError / already mutably borrowed: BorrowError
  BCK025 mutex-poisoned         PoisonError from lock().unwrap(), linked to the earlier panic that
                                poisoned the lock (the real bug)
Understands the `panicked at FILE:L:C:` format (Rust 1.73+) and the older
`panicked at 'MSG', FILE:L:C` format.

  cargo test 2>&1 | runtime_panic -

options:
  --json    machine-readable report
  --strict  exit 1 if a panic is unrelated to borrowing (not a poisoning root cause either)
  -h, --help";

struct Panic {
    thread: String,
    location: String,
    message: String,
    test: String,
    pattern: Option<&'static Pattern>,
    root_of: Option<usize>, // index of the poisoned panic this one caused
    root: Option<usize>,    // for a PoisonError: index of the panic that poisoned the lock
}

fn parse(text: &str) -> Vec<Panic> {
    let lines: Vec<&str> = text.lines().collect();
    let mut out: Vec<Panic> = Vec::new();
    let mut test = String::new();
    for (i, line) in lines.iter().enumerate() {
        if let Some(name) = line.strip_prefix("---- ").and_then(|l| l.strip_suffix(" stdout ----")) {
            test = name.to_string();
            continue;
        }
        let Some(rest) = line.trim_start().strip_prefix("thread '") else { continue };
        let Some((thread, after)) = rest.split_once("' panicked at ") else { continue };
        let (location, message) = if let Some(old) = after.strip_prefix('\'') {
            // old format: 'MSG', FILE:L:C
            match old.rsplit_once("', ") {
                Some((msg, loc)) => (loc.to_string(), msg.to_string()),
                None => continue,
            }
        } else {
            // 1.73+: FILE:L:C:  then the message on the following line(s)
            let msg: Vec<&str> = lines[i + 1..]
                .iter()
                .take_while(|l| !l.trim().is_empty() && !l.starts_with("note:") && !l.trim_start().starts_with("thread '"))
                .copied()
                .collect();
            (after.trim_end_matches(':').to_string(), msg.join("\n"))
        };
        let lower = message.to_lowercase();
        let pattern = RUNTIME_PATTERNS.iter().find(|p| p.any.iter().any(|n| lower.contains(n)));
        out.push(Panic { thread: thread.into(), location, message, test: test.clone(), pattern, root_of: None, root: None });
    }
    // Link each PoisonError to the closest earlier panic that is not itself a poisoning symptom.
    for i in 0..out.len() {
        if out[i].pattern.map(|p| p.id) == Some("BCK025") {
            if let Some(j) = (0..i).rev().find(|&j| out[j].pattern.map(|p| p.id) != Some("BCK025")) {
                out[i].root = Some(j);
                out[j].root_of = Some(i);
            }
        }
    }
    out
}

fn print_text(panics: &[Panic]) {
    for (i, p) in panics.iter().enumerate() {
        let test = if p.test.is_empty() { String::new() } else { format!(" (test {})", p.test) };
        println!("#{} panic in thread '{}' at {}{}", i + 1, p.thread, p.location, test);
        println!("  message : {}", p.message.replace('\n', "\n            "));
        if let Some(pat) = p.pattern {
            println!("  pattern : {} {}: {}", pat.id, pat.name, pat.why);
            if let Some(r) = p.root {
                let root = &panics[r];
                println!("  root    : #{} thread '{}' at {}: {}", r + 1, root.thread, root.location, root.message);
            }
            for (k, f) in pat.fixes.iter().enumerate() {
                let prefix = if k == 0 { "  fixes   :" } else { "           " };
                println!("{prefix} {}. [{}] {}", k + 1, tier_name(f.tier), f.text);
            }
        } else if let Some(v) = p.root_of {
            println!("  role    : root cause: this panic happened while a lock was held and poisoned it (see #{})", v + 1);
        } else {
            println!("  not a borrow/ownership panic");
        }
        println!();
    }
    let borrow = panics.iter().filter(|p| p.pattern.is_some()).count();
    let roots = panics.iter().filter(|p| p.root_of.is_some()).count();
    if panics.is_empty() {
        println!("No panics found.");
    } else {
        println!(
            "{} panic(s): {} borrow-related, {} poisoning root cause(s), {} other.",
            panics.len(), borrow, roots, panics.len() - borrow - roots
        );
    }
}

fn print_json(panics: &[Panic]) {
    let items: Vec<String> = panics
        .iter()
        .map(|p| {
            let opt = |v: Option<usize>| v.map_or("null".to_string(), |n| (n + 1).to_string());
            format!(
                "{{\"thread\":{},\"location\":{},\"message\":{},\"test\":{},\"pattern\":{},\"root\":{},\"root_of\":{}}}",
                json_str(&p.thread), json_str(&p.location), json_str(&p.message), json_str(&p.test),
                p.pattern.map_or("null".to_string(), |x| json_str(x.id)), opt(p.root), opt(p.root_of)
            )
        })
        .collect();
    println!("{{\"panics\":[{}]}}", items.join(","));
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
    let text = read_input(path);
    if text.trim().is_empty() {
        die("input is empty; capture it with `cargo test 2>&1 | tee test.txt`");
    }
    let panics = parse(&text);
    if json {
        print_json(&panics);
    } else {
        print_text(&panics);
    }
    let other = panics.iter().filter(|p| p.pattern.is_none() && p.root_of.is_none()).count();
    std::process::exit(if strict && other > 0 { 1 } else { 0 });
}
