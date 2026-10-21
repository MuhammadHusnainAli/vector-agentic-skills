//! Find `'static` requirements that are stricter than the code needs.
//!   LT008 static-borrow             struct S { label: &'static str } / fn f(x: &'static T)
//!   LT009 static-bound-borrow-only  fn log<T: Debug + 'static>(v: &T) that never stores or spawns
//!   LT011 boxed-dyn-default-static  struct F<'a> { cb: Box<dyn Fn(&str)> }  (= dyn Fn + 'static)
//!
//! Build: rustc -O --edition 2021 scripts/static_bounds.rs -o /tmp/static_bounds
//! Usage: static_bounds <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{close_of, declared_lifetimes, items, lifetimes_in, one_line, split_top, strip_fn_sugar, word_positions, FnSig, Src, TypeDef};

const RULES: &[Rule] = &[
    Rule { id: "LT008", name: "static-borrow", severity: "low",
           why: "&'static fields/params accept only literals and leaked data, never a borrowed String",
           fix: "String or Cow<'static, str> (literals and owned), Arc<str>, or a lifetime parameter" },
    Rule { id: "LT009", name: "static-bound-borrow-only", severity: "low",
           why: "T: 'static on a fn that only borrows T rejects T = Wrapper<&str> for no reason",
           fix: "drop 'static; require it only where T is stored, spawned, boxed as dyn Any or global" },
    Rule { id: "LT011", name: "boxed-dyn-default-static", severity: "low",
           why: "Box/Rc/Arc<dyn Trait> means dyn Trait + 'static, so closures borrowing 'a data will not fit",
           fix: "Box<dyn Trait + 'a> when the struct already borrows 'a data" },
];

const USAGE: &str = "usage: static_bounds <FILES|DIRS|-> [options]

Report 'static requirements stricter than needed: &'static fields and parameters (LT008),
T: 'static bounds on fns that only borrow T (LT009), and Box/Rc/Arc<dyn Trait> fields in
lifetime-generic structs, which silently mean dyn Trait + 'static (LT011).";

const PRIMITIVE: &[&str] = &["u8", "u16", "u32", "u64", "usize", "i8", "i16", "i32", "i64", "isize", "f32", "f64", "bool", "char"];

/// Words in a fn body that suggest a value really escapes (so 'static may be needed).
const ESCAPES: &[&str] = &["spawn", "Box", "Any", "TypeId", "thread", "static", "send", "insert", "push", "leak", "Arc", "Rc"];

fn static_bounded_params(f: &FnSig) -> Vec<String> {
    let mut out = Vec::new();
    for part in split_top(&f.generics).into_iter().chain(split_top(&f.where_)) {
        if let Some((name, bounds)) = part.split_once(':') {
            let name = name.trim();
            if !name.starts_with('\'') && !name.contains(' ') && bounds.split('+').any(|b| b.trim() == "'static") {
                out.push(name.to_string());
            }
        }
    }
    out
}

/// True when every mention of `t` in the parameters sits directly behind a reference.
fn only_borrowed(params: &str, t: &str) -> bool {
    let pos = word_positions(params, t);
    !pos.is_empty()
        && pos.iter().all(|&i| {
            let before = params[..i].trim_end();
            before.ends_with('&') || before.ends_with("&mut") || before.ends_with("&[") || before.ends_with("&mut [")
        })
}

fn check_fn(f: &FnSig, src: &Src, file: &str, out: &mut Vec<Finding>) {
    let line = src.line_of(f.off);
    // `const fn` builders of static tables take &'static by design.
    let is_const = src.code[..f.off].trim_end().ends_with("const");
    for p in split_top(&strip_fn_sugar(&f.params)).iter().filter(|_| !is_const) {
        if let Some((name, ty)) = p.split_once(':') {
            if ty.trim_start().starts_with("&'static") {
                out.push(Finding { file: file.into(), line, id: "LT008",
                                   msg: format!("fn {} parameter `{}` requires &'static: callers cannot pass borrowed data", f.name, one_line(p)),
                                   fix: format!("`{}: {}` (elided), or `impl Into<Cow<'static, str>>` if it is stored", name.trim(), ty.trim().replacen("&'static ", "&", 1)) });
            }
        }
    }
    let body_escapes = ESCAPES.iter().any(|w| !word_positions(&f.body, w).is_empty());
    if body_escapes || f.body.is_empty() {
        return; // a trait declaration, or the value may really escape
    }
    for t in static_bounded_params(f) {
        if only_borrowed(&f.params, &t) && word_positions(&f.ret, &t).is_empty() {
            out.push(Finding { file: file.into(), line, id: "LT009",
                               msg: format!("fn {} requires {t}: 'static but only borrows {t} and never stores or spawns it", f.name),
                               fix: format!("remove `'static` from the bounds of {t}") });
        }
    }
}

fn check_type(t: &TypeDef, src: &Src, file: &str, out: &mut Vec<Finding>) {
    let line = src.line_of(t.off);
    // A struct made only of &'static and primitive fields is a static data table: that is
    // exactly what &'static is for, so LT008 stays quiet.
    let fields = split_top(&t.body);
    let table = fields.iter().all(|f| {
        let ty = f.split_once(':').map_or(f.as_str(), |(_, ty)| ty).trim();
        ty.starts_with("&'static") || PRIMITIVE.contains(&ty)
    });
    for field in fields.iter().filter(|_| !table) {
        let ty = field.split_once(':').map_or(field.as_str(), |(_, ty)| ty).trim();
        if ty.starts_with("&'static") {
            out.push(Finding { file: file.into(), line, id: "LT008",
                               msg: format!("{} {} field `{}` only accepts literals or leaked data", t.kind, t.name, one_line(field)),
                               fix: "String, Cow<'static, str> (takes literals and owned strings) or Arc<str>; or a lifetime parameter if it borrows".into() });
        }
    }
    let lts = declared_lifetimes(&t.generics);
    if lts.is_empty() {
        return;
    }
    for ptr in ["Box", "Rc", "Arc"] {
        for i in word_positions(&t.body, ptr) {
            let open = i + ptr.len();
            if !t.body[open..].starts_with("<dyn ") {
                continue;
            }
            let inner = &t.body[open + 1..close_of(&t.body, open) - 1];
            if lifetimes_in(&strip_fn_sugar(inner)).is_empty() {
                out.push(Finding { file: file.into(), line, id: "LT011",
                                   msg: format!("{} {}<{}> has `{ptr}<{}>`, which is `+ 'static`: it cannot hold closures that borrow {}",
                                                t.kind, t.name, t.generics.trim(), one_line(inner), lts[0]),
                                   fix: format!("{ptr}<{} + {}>", one_line(inner), lts[0]) });
            }
        }
    }
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, types, _) = items(&src);
        let mut found = Vec::new();
        fns.iter().for_each(|f| check_fn(f, &src, &input.name, &mut found));
        types.iter().for_each(|t| check_type(t, &src, &input.name, &mut found));
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "'static")
}
