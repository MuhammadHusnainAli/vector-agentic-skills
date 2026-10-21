//! Check public types against the std-trait expectations of the Rust API Guidelines.
//!   TR003 missing-debug             pub struct/enum without Debug (derive or impl, any scanned file)
//!   TR004 error-without-error-impl  pub *Error type without Display and std::error::Error
//!   TR011 hash-with-manual-eq       #[derive(Hash)] with a hand-written PartialEq
//!   TR012 new-without-default       pub fn new() -> Self with no arguments and no Default
//!   TR014 error-enum-exhaustive     pub enum *Error without #[non_exhaustive]
//!
//! Build: rustc -O --edition 2021 scripts/api_traits.rs -o /tmp/api_traits
//! Usage: api_traits <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{attrs_before, base_name, is_pub, items, split_top, test_spans, Src};

const RULES: &[Rule] = &[
    Rule { id: "TR003", name: "missing-debug", severity: "medium",
           why: "C-DEBUG: every public type should implement Debug so users can log and assert on it",
           fix: "#[derive(Debug)], or a manual impl that hides secrets / uses finish_non_exhaustive()" },
    Rule { id: "TR004", name: "error-without-error-impl", severity: "high",
           why: "C-GOOD-ERR: error types must implement Display and std::error::Error to work with ?, Box<dyn Error> and anyhow",
           fix: "#[derive(thiserror::Error)] with #[error(\"..\")] per variant, or impl Display + impl std::error::Error" },
    Rule { id: "TR011", name: "hash-with-manual-eq", severity: "medium",
           why: "k1 == k2 must imply hash(k1) == hash(k2); a derived Hash next to a custom PartialEq usually breaks it",
           fix: "implement Hash by hand over the same normalized data PartialEq compares" },
    Rule { id: "TR012", name: "new-without-default", severity: "low",
           why: "a no-argument constructor should also be Default (clippy::new_without_default)",
           fix: "#[derive(Default)] or impl Default { fn default() -> Self { Self::new() } }" },
    Rule { id: "TR014", name: "error-enum-exhaustive", severity: "low",
           why: "adding a variant to an exhaustive public error enum is a breaking change",
           fix: "#[non_exhaustive] on the enum (callers then need a `_ =>` arm)" },
];

const USAGE: &str = "usage: api_traits <FILES|DIRS|-> [options]

Check public structs and enums for the std traits the Rust API Guidelines expect: Debug
(TR003), Display + Error on error types (TR004), Hash consistent with PartialEq (TR011),
Default next to new() (TR012) and #[non_exhaustive] error enums (TR014). Impls anywhere in
the scanned files count, so scan the whole crate. #[cfg(test)] modules are skipped.";

fn derives(attrs: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut rest = attrs;
    while let Some(i) = rest.find("derive(") {
        let inner = &rest[i + 7..];
        let end = inner.find(')').unwrap_or(inner.len());
        out.extend(inner[..end].split(',').map(|d| base_name(d)));
        rest = &inner[end..];
    }
    out
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let srcs: Vec<Src> = inputs.iter().map(|i| Src::new(i.text.clone())).collect();
    let parsed: Vec<_> = srcs.iter().map(items).collect();
    // (trait, self type) for every impl in the crate, e.g. ("Display", "StorageError").
    let impls: Vec<(String, String)> = parsed
        .iter()
        .flat_map(|(_, _, bs)| bs.iter().map(|b| {
            let (t, s) = b.trait_and_self();
            (t.map(|t| base_name(&t)).unwrap_or_default(), base_name(&s))
        }))
        .collect();
    let has_impl = |tr: &str, ty: &str| impls.iter().any(|(t, s)| t == tr && s == ty);

    let mut findings = Vec::new();
    for ((input, src), (fns, types, blocks)) in inputs.iter().zip(&srcs).zip(&parsed) {
        let tests = test_spans(&src.code);
        let in_test = |off: usize| tests.iter().any(|&(a, b)| a < off && off < b);
        let mut found = Vec::new();
        let push = |found: &mut Vec<Finding>, off: usize, id: &'static str, msg: String, fix: &str| {
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: fix.to_string() });
        };
        for t in types.iter().filter(|t| !in_test(t.off)) {
            let attrs = attrs_before(&src.code, t.off);
            let d = derives(&attrs);
            let public = is_pub(&src.code, t.off);
            let derived = |x: &str| d.iter().any(|n| n == x);
            if public && !derived("Debug") && !has_impl("Debug", &t.name) {
                push(&mut found, t.off, "TR003", format!("pub {} {} implements neither derive(Debug) nor Debug", t.kind, t.name),
                     "#[derive(Debug)] (manual impl if a field must stay hidden)");
            }
            if public && t.name.ends_with("Error") {
                let derive_err = derived("Error") || derived("Snafu"); // thiserror / snafu
                let missing: Vec<&str> = [("Display", "Display"), ("Error", "std::error::Error")]
                    .iter()
                    .filter(|(tr, _)| !derive_err && !has_impl(tr, &t.name))
                    .map(|(_, shown)| *shown)
                    .collect();
                if !missing.is_empty() {
                    push(&mut found, t.off, "TR004", format!("pub {} {} is missing {}", t.kind, t.name, missing.join(" and ")),
                         "#[derive(thiserror::Error, Debug)] with #[error(\"..\")] messages, or impl Display + std::error::Error");
                }
                if t.kind == "enum" && !attrs.contains("non_exhaustive") {
                    push(&mut found, t.off, "TR014", format!("pub enum {} is exhaustive: adding a variant breaks callers", t.name),
                         "#[non_exhaustive] above the enum");
                }
            }
            if derived("Hash") && has_impl("PartialEq", &t.name) {
                push(&mut found, t.off, "TR011", format!("{} derives Hash but implements PartialEq by hand", t.name),
                     "impl Hash manually over the same (normalized) fields PartialEq compares");
            }
        }
        for f in fns.iter().filter(|f| f.name == "new" && f.params.trim().is_empty() && !in_test(f.off)) {
            let Some(b) = f.impl_idx.map(|i| &blocks[i]) else { continue };
            let (tr, self_ty) = b.trait_and_self();
            let ty = base_name(&self_ty);
            let derives_default = types.iter().any(|t| t.name == ty && derives(&attrs_before(&src.code, t.off)).iter().any(|d| d == "Default"));
            let returns_self = matches!(f.ret.trim(), "Self") || base_name(&f.ret) == ty;
            if tr.is_none() && is_pub(&src.code, f.off) && returns_self && !derives_default && !has_impl("Default", &ty)
                && split_top(&b.generics).is_empty() {
                push(&mut found, f.off, "TR012", format!("{ty}::new() takes no arguments but {ty} has no Default"),
                     "#[derive(Default)] if field defaults match, else impl Default calling Self::new()");
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "API trait")
}
