//! Find traits used as `dyn Trait` that are not dyn compatible (E0038), and public traits
//! with `async fn` whose futures callers cannot require to be `Send`.
//!   TR001 dyn-incompatible-trait  pub trait Storage { fn open(p: &str) -> Self; .. }  +  Box<dyn Storage>
//!   TR008 async-fn-public-trait   pub trait RemoteStore { async fn fetch(&self) -> T; }
//!
//! Build: rustc -O --edition 2021 scripts/dyn_compat.rs -o /tmp/dyn_compat
//! Usage: dyn_compat <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{attrs_before, dyn_uses, is_pub, items, split_top, traits, word_positions, FnSig, Src, TraitDef};

const RULES: &[Rule] = &[
    Rule { id: "TR001", name: "dyn-incompatible-trait", severity: "high",
           why: "the trait is used as `dyn Trait` but a method or item breaks dyn compatibility (E0038)",
           fix: "add `where Self: Sized` to the offending methods, move them to an extension trait, or return Box<dyn ..> / boxed futures" },
    Rule { id: "TR008", name: "async-fn-public-trait", severity: "medium",
           why: "callers cannot require the future of a public trait's `async fn` to be Send (tokio::spawn needs it)",
           fix: "#[trait_variant::make(SendX: Send)], or declare `fn f(..) -> impl Future<Output = T> + Send`" },
];

const USAGE: &str = "usage: dyn_compat <FILES|DIRS|-> [options]

For every local trait used as `dyn Trait` in the scanned files, list what breaks dyn
compatibility (E0038): Sized supertrait, associated consts, generic associated types,
methods without a receiver, generic methods, Self in parameters or return types,
async fn and -> impl Trait. Also flag `async fn` in public traits without a Send story.
Scan the whole crate: the `dyn` use may live in another file.";

/// Why one trait method is not dispatchable through `dyn`, or None.
fn method_problem(f: &FnSig) -> Option<String> {
    if f.where_.replace(' ', "").contains("Self:Sized") {
        return None; // explicitly opted out of the vtable
    }
    let params = split_top(&f.params);
    let receiver = params.first().is_some_and(|p| {
        let p = p.replace(' ', "");
        p == "self" || p == "mutself" || p.starts_with("&self") || p.starts_with("&mutself") || p.starts_with("&'")
            && p.ends_with("self") || p.starts_with("self:")
    });
    let others = if receiver { &params[1..] } else { &params[..] };
    let mentions_self = |s: &str| word_positions(s, "Self").iter().any(|&i| !s[i..].starts_with("Self::"));
    if !receiver {
        Some(format!("`{}` has no self receiver", f.name))
    } else if f.generics.split(',').any(|g| !g.trim().is_empty() && !g.trim().starts_with('\'')) {
        Some(format!("`{}` has type parameters", f.name))
    } else if others.iter().any(|p| p.contains("impl ")) {
        Some(format!("`{}` takes `impl Trait` (a hidden type parameter)", f.name))
    } else if mentions_self(&f.ret) || others.iter().any(|p| mentions_self(p.split_once(':').map_or("", |x| x.1))) {
        Some(format!("`{}` uses `Self` outside the receiver", f.name))
    } else if f.ret.trim_start().starts_with("impl ") {
        Some(format!("`{}` returns `impl Trait`", f.name))
    } else {
        None
    }
}

fn check_trait(t: &TraitDef, fns: &[FnSig], src: &Src, used_as_dyn: bool, file: &str, out: &mut Vec<Finding>) {
    let line = src.line_of(t.off);
    let methods: Vec<&FnSig> = fns.iter().filter(|f| t.span.0 < f.off && f.off < t.span.1).collect();
    let is_async = |f: &FnSig| src.code[..f.off].trim_end().ends_with("async");

    if used_as_dyn {
        let mut why = Vec::new();
        if t.supers.split('+').any(|s| s.trim() == "Sized") {
            why.push("it has a `Sized` supertrait".to_string());
        }
        if !word_positions(&t.body, "const").is_empty() {
            why.push("it has associated consts".to_string());
        }
        if word_positions(&t.body, "type").iter().any(|&i| {
            let rest = t.body[i + 4..].trim_start();
            let name_end = rest.find(|c: char| !(c.is_alphanumeric() || c == '_')).unwrap_or(rest.len());
            rest[name_end..].trim_start().starts_with('<')
        }) {
            why.push("it has a generic associated type".to_string());
        }
        for f in &methods {
            if is_async(f) && !f.where_.replace(' ', "").contains("Self:Sized") {
                why.push(format!("`{}` is an async fn", f.name));
            } else if let Some(p) = method_problem(f) {
                why.push(p);
            }
        }
        if !why.is_empty() {
            out.push(Finding { file: file.into(), line, id: "TR001",
                               msg: format!("trait {} is used as `dyn {}` but is not dyn compatible: {} (E0038)", t.name, t.name, why.join("; ")),
                               fix: "add `where Self: Sized` to constructors/generic helpers (they stay callable on concrete types), \
                                     split them into an extension trait, or box: `-> Box<dyn Trait>`, `Pin<Box<dyn Future<..> + Send + '_>>`".into() });
        }
    }

    let attrs = attrs_before(&src.code, t.off);
    let has_send_story = attrs.contains("trait_variant") || attrs.contains("async_trait");
    let async_methods: Vec<&str> = methods.iter().filter(|f| is_async(f)).map(|f| f.name.as_str()).collect();
    if is_pub(&src.code, t.off) && !has_send_story && !async_methods.is_empty() {
        out.push(Finding { file: file.into(), line, id: "TR008",
                           msg: format!("pub trait {} has async fn {}: callers cannot require the returned futures to be Send", t.name, async_methods.join(", ")),
                           fix: format!("#[trait_variant::make(Send{}: Send)] above the trait, or `fn {}(..) -> impl Future<Output = ..> + Send`",
                                        t.name, async_methods[0]) });
    }
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let parsed: Vec<Src> = inputs.iter().map(|i| Src::new(i.text.clone())).collect();
    let dyn_names: Vec<String> = parsed.iter().flat_map(|s| dyn_uses(&s.code)).collect(); // crate-wide
    let mut findings = Vec::new();
    for (input, src) in inputs.iter().zip(&parsed) {
        let (fns, _, _) = items(src);
        let mut found = Vec::new();
        for t in traits(src) {
            check_trait(&t, &fns, src, dyn_names.contains(&t.name), &input.name, &mut found);
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "dyn-compatibility")
}
