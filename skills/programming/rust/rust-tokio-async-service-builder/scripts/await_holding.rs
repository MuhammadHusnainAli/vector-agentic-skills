//! Find values alive across `.await` that make futures !Send or hold locks too long.
//!   TK006 sync-guard-across-await  std MutexGuard / RwLock guard / RefCell borrow alive at a later .await
//!   TK007 async-mutex-not-needed   tokio::sync::Mutex guard never held across an .await (std Mutex is cheaper)
//!   TK008 rc-in-async              Rc inside async code (!Send: cannot be spawned on the multi-thread runtime)
//!
//! Build: rustc -O --edition 2021 scripts/await_holding.rs -o /tmp/await_holding
//! Usage: await_holding <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod async_ctx;
mod cli;
mod rsparse;

use async_ctx::{fn_at, scope_end, AsyncCtx};
use cli::{Finding, Rule};
use rsparse::{items, word_positions, Src};

const RULES: &[Rule] = &[
    Rule { id: "TK006", name: "sync-guard-across-await", severity: "high",
           why: "a std guard alive at .await makes the future !Send (spawn fails) and blocks other tasks on the lock",
           fix: "scope the guard: let v = { let g = m.lock().unwrap(); g.get(..).cloned() }; then .await; or drop(g) first" },
    Rule { id: "TK007", name: "async-mutex-not-needed", severity: "low",
           why: "tokio::sync::Mutex is slower than std::sync::Mutex and only needed when the guard lives across .await",
           fix: "std::sync::Mutex (or parking_lot) for short critical sections without .await" },
    Rule { id: "TK008", name: "rc-in-async", severity: "medium",
           why: "Rc is !Send: a future holding it across .await cannot go to tokio::spawn on the multi-thread runtime",
           fix: "Arc (and Mutex/atomics for mutation), or keep the Rc out of the awaited section" },
];

const USAGE: &str = "usage: await_holding <FILES|DIRS|-> [options]

Report std lock guards and RefCell borrows that are still alive at a later .await (TK006),
tokio Mutex guards that never live across an .await (TK007) and Rc used in async code (TK008).
A guard is a `let` binding of .lock()/.read()/.write()/.borrow()/.borrow_mut(); it lives until
drop(name) or the end of its block.";

/// Offset of the `;` that ends the statement starting at `i` (ignoring `;` nested in blocks).
fn statement_end(code: &str, i: usize) -> usize {
    let mut depth = 0i32;
    for (j, c) in code[i..].char_indices() {
        match c {
            '(' | '[' | '{' => depth += 1,
            ')' | ']' | '}' => depth -= 1,
            ';' if depth == 0 => return i + j,
            _ => {}
        }
        if depth < 0 {
            return i + j;
        }
    }
    code.len()
}

/// (guard name, offset of the let, is it a tokio guard?) for `let [mut] g = ..lock()..;`
fn guards(code: &str, from: usize, to: usize) -> Vec<(String, usize, bool)> {
    let mut out = Vec::new();
    for i in word_positions(&code[from..to], "let").into_iter().map(|i| from + i) {
        let stmt = &code[i..statement_end(code, i).min(to)];
        let Some((lhs, rhs)) = stmt.split_once('=') else { continue };
        let name = lhs.trim_start_matches("let").trim().trim_start_matches("mut ").trim();
        if !name.chars().all(|c| c.is_alphanumeric() || c == '_') || name.is_empty() {
            continue;
        }
        let rhs = rhs.replace([' ', '\n'], "");
        let tokio = [".lock().await", ".read().await", ".write().await"].iter().any(|p| rhs.ends_with(p));
        let std = [".lock().unwrap()", ".read().unwrap()", ".write().unwrap()", ".borrow()", ".borrow_mut()"]
            .iter()
            .any(|p| rhs.ends_with(p))
            || [".lock().expect(", ".read().expect(", ".write().expect("].iter().any(|p| rhs.contains(p) && rhs.ends_with(')'));
        if tokio || std {
            out.push((name.to_string(), i, tokio));
        }
    }
    out
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, _, _) = items(&src);
        let ctx = AsyncCtx::new(&src, &fns);
        let mut found = Vec::new();
        let mut seen = Vec::new();
        for (name, off, tokio) in guards(code, 0, code.len()) {
            let Some(span) = ctx.innermost(off).filter(|_| ctx.contains(off)) else { continue };
            if seen.contains(&off) {
                continue;
            }
            seen.push(off);
            // The guard lives until drop(name) or the end of its block (whichever comes first).
            let end = scope_end(code, off).min(span.1);
            let dropped = code[off..end].find(&format!("drop({name})")).map(|n| off + n);
            let alive_until = dropped.unwrap_or(end);
            let stmt_end = statement_end(code, off);
            let await_at = code[stmt_end..alive_until].find(".await").map(|n| stmt_end + n);
            let place = fn_at(&src, &fns, off).map_or(String::new(), |f| format!(" in fn {}", f.name));
            match (tokio, await_at) {
                (false, Some(a)) => found.push(Finding {
                    file: input.name.clone(), line: src.line_of(off), id: "TK006",
                    msg: format!("std guard `{name}`{place} is still alive at the .await on line {}", src.line_of(a)),
                    fix: String::new() }),
                (true, None) => found.push(Finding {
                    file: input.name.clone(), line: src.line_of(off), id: "TK007",
                    msg: format!("tokio Mutex guard `{name}`{place} is never held across an .await"),
                    fix: String::new() }),
                _ => {}
            }
        }
        let mut rc_fns = Vec::new();
        for (off, _) in code.match_indices("Rc::") {
            let word_start = off == 0 || !code.as_bytes()[off - 1].is_ascii_alphanumeric();
            let f = fn_at(&src, &fns, off).map(|f| f.name.clone()).unwrap_or_default();
            if word_start && ctx.contains(off) && !rc_fns.contains(&f) {
                found.push(Finding { file: input.name.clone(), line: src.line_of(off), id: "TK008",
                                     msg: format!("`Rc` in async fn {f}: the future is !Send"), fix: String::new() });
                rc_fns.push(f);
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    let findings: Vec<Finding> = findings
        .into_iter()
        .map(|mut f| {
            f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.to_string());
            f
        })
        .collect();
    cli::finish(&opts, RULES, findings, inputs.len(), "await-holding")
}
