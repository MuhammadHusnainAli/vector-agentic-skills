//! Find trait and impl shapes that fight Rust's conventions.
//!   TR002 impl-into-not-from   impl Into<DocumentId> for RawId   -> impl From<RawId> for DocumentId
//!   TR005 deref-inheritance    impl Deref<Target = Document> for VersionedDocument (multi-field struct)
//!   TR006 fat-trait            pub trait with more than --max-methods required methods (default 8)
//!   TR007 single-impl-trait    private trait, one impl for a local type, never dyn or a bound
//!
//! Build: rustc -O --edition 2021 scripts/trait_shape.rs -o /tmp/trait_shape
//! Usage: trait_shape <FILES|DIRS|-> [--max-methods N] [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{base_name, is_pub, items, one_line, split_top, traits, word_positions, ImplBlock, Src, TypeDef};

const RULES: &[Rule] = &[
    Rule { id: "TR002", name: "impl-into-not-from", severity: "medium",
           why: "implementing From gives Into for free (blanket impl); an Into impl gives nothing back",
           fix: "impl From<Source> for Target (and TryFrom instead of TryInto)" },
    Rule { id: "TR005", name: "deref-inheritance", severity: "medium",
           why: "Deref is for smart pointers; using it to inherit a struct's methods confuses method resolution and docs",
           fix: "delegate the needed methods explicitly, expose `fn inner(&self) -> &Inner`, or share a trait" },
    Rule { id: "TR006", name: "fat-trait", severity: "low",
           why: "every implementor must write every required method; large traits are hard to implement and to evolve",
           fix: "split into smaller traits, give methods default bodies, or move helpers to an extension trait" },
    Rule { id: "TR007", name: "single-impl-trait", severity: "low",
           why: "a private trait with one local implementor and no generic use is indirection without a second user",
           fix: "make the methods inherent (`impl Type { .. }`) until a second implementor or a test fake exists" },
];

const USAGE: &str = "usage: trait_shape <FILES|DIRS|-> [--max-methods N] [options]

Report Into impls that should be From (TR002), Deref used for inheritance (TR005), traits
with too many required methods (TR006) and private single-implementor traits (TR007).
Scan the whole crate: impls and uses in other files count.

  --max-methods N      TR006 threshold: required (body-less) methods allowed (default 8)";

fn deref_target(b: &ImplBlock) -> Option<String> {
    let i = b.body.find("type Target")?;
    let rest = &b.body[i + "type Target".len()..];
    let rest = rest.trim_start().strip_prefix('=')?;
    Some(rest.split(';').next()?.trim().to_string())
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &["--max-methods"]);
    let max: usize = opts.value("--max-methods").map_or(8, |v| v.parse().unwrap_or_else(|_| cli::die("--max-methods needs a number")));
    let inputs = opts.inputs();
    let srcs: Vec<Src> = inputs.iter().map(|i| Src::new(i.text.clone())).collect();
    let parsed: Vec<_> = srcs.iter().map(items).collect();

    // Crate-wide facts: local type definitions, every impl, every dyn use.
    let local_types: Vec<&TypeDef> = parsed.iter().flat_map(|(_, t, _)| t).collect();
    let all_impls: Vec<(String, String)> = parsed
        .iter()
        .flat_map(|(_, _, impls)| impls.iter().filter_map(|b| match b.trait_and_self() {
            (Some(t), s) => Some((base_name(&t), base_name(&s))),
            _ => None,
        }))
        .collect();
    let all_code: String = srcs.iter().map(|s| s.code.as_str()).collect::<Vec<_>>().join("\n");

    let mut findings = Vec::new();
    for ((input, src), (fns, _, impls)) in inputs.iter().zip(&srcs).zip(&parsed) {
        let mut found = Vec::new();
        for b in impls {
            let line = src.line_of(b.off);
            let (Some(tr), self_ty) = b.trait_and_self() else { continue };
            let name = base_name(&tr);
            if name == "Into" || name == "TryInto" {
                let target = tr.split_once('<').map_or("T", |(_, r)| r.trim_end_matches('>')).trim();
                let from = if name == "Into" { "From" } else { "TryFrom" };
                found.push(Finding { file: input.name.clone(), line, id: "TR002",
                                     msg: format!("`impl {}` for {}: implement {from} instead", one_line(&tr), one_line(&self_ty)),
                                     fix: format!("impl {from}<{}> for {target}", one_line(&self_ty)) });
            }
            if name == "Deref" {
                let target = deref_target(b).unwrap_or_default();
                let fields: Vec<String> = local_types
                    .iter()
                    .find(|t| t.name == base_name(&self_ty))
                    .map_or(vec![], |t| split_top(&t.body));
                let target_local = local_types.iter().any(|t| t.name == base_name(&target) && t.kind == "struct");
                if target_local && fields.len() > 1 {
                    // The field that holds the target, for the delegation example.
                    let inner = fields
                        .iter()
                        .find_map(|f| f.split_once(':').filter(|(_, ty)| base_name(ty) == base_name(&target)))
                        .map_or("inner".to_string(), |(n, _)| n.trim().trim_start_matches("pub ").to_string());
                    found.push(Finding { file: input.name.clone(), line, id: "TR005",
                                         msg: format!("{} derefs to {target}: Deref used as inheritance on a {}-field struct", one_line(&self_ty), fields.len()),
                                         fix: format!("delegate each method callers need (`fn x(&self) -> &T {{ &self.{inner}.x }}`) or expose `fn {inner}(&self) -> &{target}`") });
                }
            }
        }
        for t in traits(src) {
            let line = src.line_of(t.off);
            let required = fns.iter().filter(|f| t.span.0 < f.off && f.off < t.span.1 && f.body.is_empty()).count();
            if is_pub(&src.code, t.off) && required > max {
                found.push(Finding { file: input.name.clone(), line, id: "TR006",
                                     msg: format!("pub trait {} has {required} required methods (max {max})", t.name), fix: String::new() });
            }
            let impls_of: Vec<&(String, String)> = all_impls.iter().filter(|(tr, _)| *tr == t.name).collect();
            let used_generically = word_positions(&all_code, &t.name).iter().any(|&i| {
                let before = all_code[..i].trim_end();
                let header = all_code[i..].split(['{', ';', ',', ')']).next().unwrap_or("");
                before.ends_with("dyn") || before.ends_with("impl") && !header.contains(" for ")
                    || before.ends_with(':') || before.ends_with('+')
            });
            if !is_pub(&src.code, t.off) && impls_of.len() == 1 && !used_generically
                && local_types.iter().any(|ty| ty.name == impls_of[0].1) {
                found.push(Finding { file: input.name.clone(), line, id: "TR007",
                                     msg: format!("private trait {} has one implementor ({}) and no generic or dyn use", t.name, impls_of[0].1),
                                     fix: format!("move its methods into `impl {} {{ .. }}`", impls_of[0].1) });
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "trait-shape")
}
