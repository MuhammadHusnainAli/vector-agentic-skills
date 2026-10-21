//! Find code that panics instead of returning an error in library code.
//!   ERR001 unwrap-in-lib   .unwrap() outside tests and binaries
//!   ERR002 expect-in-lib   .expect("..") outside tests and binaries
//!   ERR003 panic-in-lib    todo!/unimplemented! (unfinished code), panic! (documented invariant?)
//!
//! Build: rustc -O --edition 2021 scripts/unwrap_audit.rs -o /tmp/unwrap_audit
//! Usage: unwrap_audit <FILES|DIRS|-> [--lib|--app] [--include-tests] [--json] [--strict]

mod cli;
mod rsparse;
mod scope;

use cli::{Finding, Rule};
use rsparse::{items, Src};
use scope::{enclosing, find_all, Scope};

const RULES: &[Rule] = &[
    Rule { id: "ERR001", name: "unwrap-in-lib", severity: "medium",
           why: "a library that panics takes the decision away from the caller and loses the error",
           fix: "return the error with `?` (add a variant or `.ok_or(..)`), or use `expect(\"invariant: ..\")` if it truly cannot fail" },
    Rule { id: "ERR002", name: "expect-in-lib", severity: "low",
           why: "expect is fine for real invariants, but often hides a recoverable error",
           fix: "propagate with `?`; keep expect only for invariants and phrase the message as the invariant" },
    Rule { id: "ERR003", name: "panic-in-lib", severity: "high",
           why: "todo!/unimplemented! ship unfinished paths; panic! on bad input should be an Err",
           fix: "return Err(..) for input errors; finish or remove todo!; keep panic! only for broken invariants (document under # Panics)" },
];

const USAGE: &str = "usage: unwrap_audit <FILES|DIRS|-> [options]

Report .unwrap(), .expect(..), panic!, todo! and unimplemented! in library code. Binary
code (main.rs, src/bin/, files with fn main), tests, benches and examples are skipped.";

fn main() {
    let usage = format!("{USAGE}\n\n{}", scope::SCOPE_HELP);
    let opts = cli::parse(&usage, RULES, &[], scope::SWITCHES);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, _, _) = items(&src);
        let scope = Scope::new(input, &src, &fns, &opts);
        if scope.app {
            continue;
        }
        let in_fn = |off: usize| enclosing(&fns, &src, off).map_or(String::new(), |f| format!(" in fn {}", f.name));
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String| {
            if !scope.skip(off) {
                found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: String::new() });
            }
        };
        for off in find_all(&src.code, ".unwrap()") {
            push(off, "ERR001", format!("`.unwrap()`{}", in_fn(off)));
        }
        for off in find_all(&src.code, ".expect(") {
            let msg = src.orig[off..].split(')').next().unwrap_or("").trim_start_matches(".expect(").to_string();
            push(off, "ERR002", format!("`.expect({msg})`{}", in_fn(off)));
        }
        for (mac, why) in [("todo!", "unfinished code path"), ("unimplemented!", "unfinished code path"), ("panic!", "panics on a recoverable condition?")] {
            for off in find_all(&src.code, mac) {
                let word_start = off == 0 || !src.code.as_bytes()[off - 1].is_ascii_alphanumeric() && src.code.as_bytes()[off - 1] != b'_';
                if word_start {
                    push(off, "ERR003", format!("`{mac}`{}: {why}", in_fn(off)));
                }
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "panic")
}
