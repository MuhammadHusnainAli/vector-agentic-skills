//! Find places where errors lose information on their way up.
//!   ERR006 map-err-discards-source  .map_err(|_| ..)
//!   ERR007 stringly-map-err         .map_err(|e| e.to_string()) / format!("..{e}")
//!   ERR011 discarded-result         let _ = call(); / call().ok();
//!   ERR012 missing-context          bare `?` on fs/parse/serde calls in fns returning anyhow
//!   ERR013 exit-instead-of-return   eprintln! + std::process::exit instead of returning an error
//!
//! Build: rustc -O --edition 2021 scripts/error_flow.rs -o /tmp/error_flow
//! Usage: error_flow <FILES|DIRS|-> [--lib|--app] [--include-tests] [--json] [--strict]

mod cli;
mod rsparse;
mod scope;

use cli::{Finding, Rule};
use rsparse::{items, one_line, Src};
use scope::{enclosing, find_all, Scope};

const RULES: &[Rule] = &[
    Rule { id: "ERR006", name: "map-err-discards-source", severity: "medium",
           why: "`|_|` throws the original error away: no source(), no cause in logs",
           fix: "keep it: .map_err(|e| MyError::Parse { input, source: e }) or a #[from] conversion with `?`" },
    Rule { id: "ERR007", name: "stringly-map-err", severity: "medium",
           why: "turning an error into a String loses its type, its source chain and its backtrace",
           fix: "wrap it in a typed variant (#[source]/#[from]) or add anyhow context: .context(\"..\")" },
    Rule { id: "ERR011", name: "discarded-result", severity: "low",
           why: "a silently ignored Result hides failures (the #[must_use] warning was only silenced)",
           fix: "handle it, propagate with `?`, or log it: if let Err(e) = f() { tracing::warn!(error = %e, \"..\") }" },
    Rule { id: "ERR012", name: "missing-context", severity: "info",
           why: "a bare `?` on I/O or parsing in anyhow code produces 'No such file or directory' without saying which file",
           fix: ".with_context(|| format!(\"reading {}\", path.display()))?" },
    Rule { id: "ERR013", name: "exit-instead-of-return", severity: "medium",
           why: "process::exit skips destructors (buffered writers, temp files) and cannot be tested or reused",
           fix: "return the error to main; `fn main() -> anyhow::Result<()>` or ExitCode prints and exits for you" },
];

const USAGE: &str = "usage: error_flow <FILES|DIRS|-> [options]

Report errors that lose information: map_err(|_| ..) (ERR006), errors turned into Strings
(ERR007), ignored Results (ERR011), bare `?` on I/O or parsing in anyhow code without
context (ERR012) and eprintln! + process::exit instead of returning (ERR013).";

/// Calls whose errors say nothing about *which* input failed.
const NEEDS_CONTEXT: &[&str] = &["fs::", "File::open", "File::create", "read_to_string", ".parse", "from_str", "from_slice", "from_reader", "serde_json::", "toml::"];

/// The expression that ends at `q` (a `?`), back to the start of its statement.
fn statement_before(code: &str, q: usize) -> &str {
    let start = code[..q].rfind([';', '{', '}']).map_or(0, |i| i + 1);
    &code[start..q]
}

fn main() {
    let usage = format!("{USAGE}\n\n{}", scope::SCOPE_HELP);
    let opts = cli::parse(&usage, RULES, &[], scope::SWITCHES);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, _, _) = items(&src);
        let scope = Scope::new(input, &src, &fns, &opts);
        let code = &src.code;
        let in_fn = |off: usize| enclosing(&fns, &src, off).map_or(String::new(), |f| format!(" in fn {}", f.name));
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String| {
            if !scope.skip(off) {
                found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: String::new() });
            }
        };

        for off in find_all(code, ".map_err(") {
            let open = off + ".map_err".len();
            let close = rsparse::close_of(code, open);
            let (args, args_orig) = (code[open + 1..close - 1].trim(), src.orig[open + 1..close - 1].trim());
            let call = one_line(&src.orig[off..close]);
            if args.starts_with("|_|") {
                push(off, "ERR006", format!("`{call}`{} discards the original error", in_fn(off)));
            } else if let Some((var, body)) = args.strip_prefix('|').and_then(|a| a.split_once('|')) {
                let var = var.trim();
                let body_orig = &args_orig[args_orig.len() - body.len()..];
                let uses_var = !rsparse::word_positions(body_orig, var).is_empty();
                let stringly = body.contains(&format!("{var}.to_string()")) || body.contains("format!") && uses_var;
                if stringly && !var.is_empty() {
                    push(off, "ERR007", format!("`{call}`{} turns the error into a String", in_fn(off)));
                }
            }
        }

        for off in find_all(code, "let _ =") {
            let stmt = code[off..].split(';').next().unwrap_or("");
            if stmt.contains('(') && !stmt.contains("drop(") {
                push(off, "ERR011", format!("`{}`{} ignores a Result", one_line(stmt), in_fn(off)));
            }
        }
        for off in find_all(code, ".ok();") {
            let stmt_start = code[..off].rfind([';', '{', '}']).map_or(0, |i| i + 1);
            let stmt = code[stmt_start..off].trim();
            if !stmt.starts_with("let ") && !stmt.starts_with("return") && !stmt.contains('=') {
                push(off, "ERR011", format!("`{}.ok();`{} ignores a Result", one_line(stmt), in_fn(off)));
            }
        }

        for f in fns.iter().filter(|f| f.ret.contains("anyhow")) {
            let Some(open) = code[f.off..].find('{').map(|n| f.off + n + 1) else { continue };
            for (i, _) in f.body.match_indices('?') {
                let stmt = statement_before(&f.body, i);
                if NEEDS_CONTEXT.iter().any(|c| stmt.contains(c)) && !stmt.contains("context(") {
                    push(open + i, "ERR012", format!("bare `?` on `{}` in fn {} (anyhow): which input failed?", one_line(stmt.trim()), f.name));
                }
            }
        }

        for f in &fns {
            if f.body.contains("eprintln!") && (f.body.contains("process::exit") || f.body.contains(" exit(")) {
                push(f.off, "ERR013", format!("fn {} prints an error and calls process::exit", f.name));
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    let fixes: Vec<Finding> = findings
        .into_iter()
        .map(|mut f| {
            f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.to_string());
            f
        })
        .collect();
    cli::finish(&opts, RULES, fixes, inputs.len(), "error flow")
}
