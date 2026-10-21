//! Find lifetime designs that compile but hurt callers.
//!   LT007 mut-borrow-own-lifetime  &'a mut self in impl<'a> S<'a>; &'a mut Vec<&'a str>
//!   LT010 too-many-lifetimes       struct Pipeline<'src, 'cfg, 'out>  (more than --max-lifetimes)
//!   LT012 rpit-captures-2024       -> impl Trait with borrowed inputs and no use<..>, edition 2024
//!
//! Build: rustc -O --edition 2021 scripts/lifetime_smells.rs -o /tmp/lifetime_smells
//! Usage: lifetime_smells <FILES|DIRS|-> [--max-lifetimes N] [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{declared_lifetimes, elided_refs, items, lifetimes_in, one_line, split_top, strip_fn_sugar, FnSig, ImplBlock, Src};

const RULES: &[Rule] = &[
    Rule { id: "LT007", name: "mut-borrow-own-lifetime", severity: "medium",
           why: "&'a mut tied to the data's own lifetime borrows it mutably for all of 'a: the second call fails (E0499/E0502)",
           fix: "use a short &mut self / &mut Vec<&'a str>; keep 'a only on the data that is returned or stored" },
    Rule { id: "LT010", name: "too-many-lifetimes", severity: "low",
           why: "every lifetime parameter spreads to every user of the item",
           fix: "own some of the data (String, Arc<str>, indices) or merge lifetimes that never need to differ" },
    Rule { id: "LT012", name: "rpit-captures-2024", severity: "low",
           why: "in edition 2024 `-> impl Trait` captures every in-scope lifetime, so the result keeps the inputs borrowed",
           fix: "if the returned value owns its data, add `+ use<..>` listing only what it captures (Rust 1.82+)" },
];

const USAGE: &str = "usage: lifetime_smells <FILES|DIRS|-> [--max-lifetimes N] [options]

Report lifetime designs that compile but make callers suffer: `&'a mut` tied to the
data's own lifetime (LT007), items with more than N lifetime parameters (LT010, default
N=2), and edition-2024 `-> impl Trait` returns that capture borrowed inputs (LT012).

  --max-lifetimes N    LT010 threshold (default 2)";

/// `&'a mut X` whose X mentions 'a again: borrows X mutably for X's whole lifetime.
fn self_tied_mut(ty: &str) -> Option<String> {
    let ty = ty.trim();
    let rest = ty.strip_prefix('&')?.trim_start();
    let lt = lifetimes_in(rest).into_iter().next()?;
    let after = rest.strip_prefix(lt.as_str())?.trim_start().strip_prefix("mut")?;
    lifetimes_in(after).contains(&lt).then_some(lt)
}

fn check_fn(f: &FnSig, impls: &[ImplBlock], edition: u32, max: usize, src: &Src, file: &str, out: &mut Vec<Finding>) {
    let line = src.line_of(f.off);
    let params = split_top(&strip_fn_sugar(&f.params));
    let impl_lts = f.impl_idx.map(|i| declared_lifetimes(&impls[i].generics)).unwrap_or_default();
    for p in &params {
        let recv = p.replace(' ', "");
        if let Some(lt) = impl_lts.iter().find(|lt| recv == format!("&{lt}mutself")) {
            out.push(Finding { file: file.into(), line, id: "LT007",
                               msg: format!("fn {} takes `&{lt} mut self` with the impl's own lifetime: self stays mutably borrowed for all of {lt}", f.name),
                               fix: format!("`&mut self`, keeping {lt} only on the returned data (e.g. -> Option<&{lt} str>)") });
        } else if let Some((name, ty)) = p.split_once(':') {
            if let Some(lt) = self_tied_mut(ty) {
                out.push(Finding { file: file.into(), line, id: "LT007",
                                   msg: format!("fn {} parameter `{}` ties the mutable borrow to {lt}, the lifetime of the data inside it", f.name, one_line(p)),
                                   fix: format!("`{}: {}` (separate, short lifetime for the &mut)", name.trim(), ty.trim().replacen(&format!("&{lt} mut"), "&mut", 1)) });
            }
        }
    }
    let n = declared_lifetimes(&f.generics).len();
    if n > max {
        out.push(Finding { file: file.into(), line, id: "LT010",
                           msg: format!("fn {} has {n} lifetime parameters (max {max})", f.name), fix: String::new() });
    }
    let ret = f.ret.trim();
    let borrows = elided_refs(&f.params) > 0 || !lifetimes_in(&f.params).is_empty();
    // A return type that names a lifetime (`+ '_`, `Item = &'a str`) already says it borrows.
    if edition >= 2024 && ret.starts_with("impl ") && !ret.contains("use<") && lifetimes_in(ret).is_empty() && borrows {
        let types: Vec<String> = split_top(&f.generics)
            .iter()
            .filter(|g| !g.starts_with('\'') && !g.starts_with("const "))
            .map(|g| g.split(':').next().unwrap_or("").trim().to_string())
            .collect();
        out.push(Finding { file: file.into(), line, id: "LT012",
                           msg: format!("fn {} returns `{}`, which captures its borrowed inputs in edition 2024", f.name, one_line(ret)),
                           fix: format!("if the returned value owns its data: `-> {} + use<{}>`; keep as is if it borrows the inputs", one_line(ret), types.join(", ")) });
    }
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &["--max-lifetimes"]);
    let max: usize = opts.value("--max-lifetimes").map_or(2, |v| v.parse().unwrap_or_else(|_| cli::die("--max-lifetimes needs a number")));
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, types, impls) = items(&src);
        let mut found = Vec::new();
        for f in &fns {
            check_fn(f, &impls, input.edition, max, &src, &input.name, &mut found);
        }
        for t in &types {
            let line = src.line_of(t.off);
            let n = declared_lifetimes(&t.generics).len();
            if n > max {
                found.push(Finding { file: input.name.clone(), line, id: "LT010",
                                     msg: format!("{} {} has {n} lifetime parameters (max {max}); every user inherits them", t.kind, t.name),
                                     fix: "own the long-lived parts (String, Arc<str>, indices) and keep one lifetime for the borrowed input".into() });
            }
            for field in split_top(&strip_fn_sugar(&t.body)) {
                if let Some(lt) = field.split_once(':').and_then(|(_, ty)| self_tied_mut(ty)) {
                    found.push(Finding { file: input.name.clone(), line, id: "LT007",
                                         msg: format!("{} {} field `{}` ties the mutable borrow to {lt}", t.kind, t.name, one_line(&field)),
                                         fix: "use two lifetimes (&'m mut X<'a>) or own the inner data".into() });
                }
            }
        }
        for b in &impls {
            let n = declared_lifetimes(&b.generics).len();
            if n > max {
                found.push(Finding { file: input.name.clone(), line: src.line_of(b.off), id: "LT010",
                                     msg: format!("impl {} has {n} lifetime parameters (max {max})", one_line(&b.header)), fix: String::new() });
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "lifetime design")
}
