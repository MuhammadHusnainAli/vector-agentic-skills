//! Find lifetime annotations that elision makes unnecessary, and print the elided form.
//!   LT001 needless-lifetime       fn first<'a>(s: &'a str) -> &'a str   ->  fn first(s: &str) -> &str
//!   LT002 elidable-impl-lifetime  impl<'a> Display for Token<'a>        ->  impl Display for Token<'_>
//!   LT005 unused-fn-lifetime      fn count<'x>(s: &str) -> usize        ->  fn count(s: &str) -> usize
//!
//! Build: rustc -O --edition 2021 scripts/elision_check.rs -o /tmp/elision_check
//! Usage: elision_check <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{count_lifetime, declared_lifetimes, elided_refs, items, lifetimes_in, one_line, strip_fn_sugar, word_positions, FnSig, Src};

const RULES: &[Rule] = &[
    Rule { id: "LT001", name: "needless-lifetime", severity: "low",
           why: "the elision rules already give this signature; named lifetimes add noise",
           fix: "delete the lifetime parameter and its uses (printed signature)" },
    Rule { id: "LT002", name: "elidable-impl-lifetime", severity: "low",
           why: "the impl's lifetime is used once in the header and never in the body",
           fix: "impl Trait for Type<'_> (impl-header elision, Rust 2018+)" },
    Rule { id: "LT005", name: "unused-fn-lifetime", severity: "medium",
           why: "a lifetime declared on a fn but used nowhere (clippy: extra_unused_lifetimes)",
           fix: "remove it from the generic list" },
];

const USAGE: &str = "usage: elision_check <FILES|DIRS|-> [options]

Report lifetime annotations that Rust's elision rules make unnecessary (LT001, LT002)
and fn lifetimes that are declared but never used (LT005), with the corrected
signature. Reads source text only; never compiles anything.";

/// Generic list without the given lifetimes; "" when nothing is left.
fn without(generics: &str, drop: &[String]) -> String {
    let kept: Vec<String> = rsparse::split_top(generics)
        .into_iter()
        .filter(|p| !drop.iter().any(|d| p == d || p.starts_with(&format!("{d}:"))))
        .collect();
    if kept.is_empty() { String::new() } else { format!("<{}>", kept.join(", ")) }
}

/// `&'a T` -> `&T`; other `'a` -> `'_`.
fn elide(s: &str, lts: &[String]) -> String {
    let mut out = s.to_string();
    for lt in lts {
        out = out.replace(&format!("&{lt} "), "&");
        for i in word_positions(&out.clone(), &lt[1..]).into_iter().rev() {
            if i > 0 && out.as_bytes()[i - 1] == b'\'' {
                out.replace_range(i - 1..i + lt.len() - 1, "'_");
            }
        }
    }
    out
}

/// Uses of `lt` outside its own declaration in the generic list (bounds like `'b: 'a`, `T: 'a`).
fn used_in_bounds(f: &FnSig, lt: &str) -> bool {
    count_lifetime(&f.generics, lt) > 1 || count_lifetime(&f.where_, lt) > 0
}

fn check_fn(f: &FnSig, src: &Src, file: &str, out: &mut Vec<Finding>) {
    let decl = declared_lifetimes(&f.generics);
    if decl.is_empty() {
        return;
    }
    let inputs = strip_fn_sugar(&f.params);
    let output = strip_fn_sugar(&f.ret);
    let line = src.line_of(f.off);
    let sig = |g: &str, p: &str, r: &str| {
        let ret = if r.is_empty() { String::new() } else { format!(" -> {r}") };
        one_line(&format!("fn {}{g}({p}){ret}", f.name))
    };

    let unused: Vec<String> = decl
        .iter()
        .filter(|lt| count_lifetime(&f.params, lt) + count_lifetime(&f.ret, lt) + count_lifetime(&f.body, lt) == 0 && !used_in_bounds(f, lt))
        .cloned()
        .collect();
    for lt in &unused {
        out.push(Finding { file: file.into(), line, id: "LT005", msg: format!("`{lt}` is declared on fn {} but never used", f.name),
                           fix: sig(&without(&f.generics, &unused), &f.params, &f.ret) });
    }
    if !unused.is_empty() || decl.iter().any(|lt| used_in_bounds(f, lt) || count_lifetime(&f.body, lt) > 0) {
        return;
    }

    // Every declared lifetime must be written exactly once among the inputs.
    if decl.iter().any(|lt| count_lifetime(&inputs, lt) != 1) {
        return;
    }
    let in_output: Vec<&String> = decl.iter().filter(|lt| count_lifetime(&output, lt) > 0).collect();
    let needless = match in_output.as_slice() {
        [] => true, // rule 1: each elided input gets its own lifetime anyway
        [lt] => {
            let receiver = inputs.trim_start();
            let by_ref_only = output.matches(&format!("&{lt}")).count() == count_lifetime(&output, lt);
            let rule3 = receiver.starts_with(&format!("&{lt} self")) || receiver.starts_with(&format!("&{lt} mut self"));
            let input_lifetimes = elided_refs(&inputs) + lifetimes_in(&inputs).len();
            by_ref_only && (rule3 || input_lifetimes == 1) // rule 3, or rule 2 (one input lifetime)
        }
        _ => false,
    };
    if needless {
        let names: Vec<String> = decl.iter().map(|l| format!("`{l}`")).collect();
        out.push(Finding { file: file.into(), line, id: "LT001",
                           msg: format!("{} on fn {} can be elided", names.join(", "), f.name),
                           fix: sig(&without(&f.generics, &decl), &elide(&f.params, &decl), &elide(&f.ret, &decl)) });
    }
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, _, impls) = items(&src);
        let mut found = Vec::new();
        for f in &fns {
            check_fn(f, &src, &input.name, &mut found);
        }
        for b in &impls {
            let decl = declared_lifetimes(&b.generics);
            let elidable: Vec<String> = decl
                .iter()
                .filter(|lt| count_lifetime(&b.header, lt) == 1 && count_lifetime(&b.generics, lt) == 1
                    && count_lifetime(&b.where_, lt) == 0 && count_lifetime(&b.body, lt) == 0)
                .cloned()
                .collect();
            if !elidable.is_empty() {
                let names: Vec<String> = elidable.iter().map(|l| format!("`{l}`")).collect();
                found.push(Finding { file: input.name.clone(), line: src.line_of(b.off), id: "LT002",
                                     msg: format!("{} is only used once in `impl {}`", names.join(", "), one_line(&b.header)),
                                     fix: one_line(&format!("impl{} {}", without(&b.generics, &elidable), elide(&b.header, &elidable))) });
            }
        }
        let rules_on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| rules_on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "elision")
}
