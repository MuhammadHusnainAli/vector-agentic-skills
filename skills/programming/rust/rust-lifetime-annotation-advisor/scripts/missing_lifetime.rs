//! Find lifetimes the compiler will demand (E0106) or reject as unused (E0392), with a fix.
//!   LT003 missing-lifetime-return  fn longer(a: &str, b: &str) -> &str      (E0106)
//!   LT004 missing-lifetime-field   struct Line { raw: &str }                (E0106)
//!   LT006 unused-type-lifetime     struct Settings<'a> { name: String }     (E0392)
//!
//! Build: rustc -O --edition 2021 scripts/missing_lifetime.rs -o /tmp/missing_lifetime
//! Usage: missing_lifetime <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{count_lifetime, declared_lifetimes, elided_refs, items, lifetimes_in, one_line, split_top, strip_fn_sugar, FnSig, Src, TypeDef};

const RULES: &[Rule] = &[
    Rule { id: "LT003", name: "missing-lifetime-return", severity: "high",
           why: "a returned reference needs exactly one input lifetime (or &self) to elide from; otherwise E0106",
           fix: "name the lifetime of the input the result borrows from, or return owned data" },
    Rule { id: "LT004", name: "missing-lifetime-field", severity: "high",
           why: "references in struct/enum fields never elide (E0106)",
           fix: "add a lifetime parameter (struct S<'a> { f: &'a T }) or store owned data (String, Vec<T>)" },
    Rule { id: "LT006", name: "unused-type-lifetime", severity: "high",
           why: "a type's lifetime parameter must be used by a field (E0392)",
           fix: "remove it, or mark it with PhantomData<&'a ()>" },
];

const USAGE: &str = "usage: missing_lifetime <FILES|DIRS|-> [options]

Report missing lifetimes rustc would reject with E0106 (returned references with no
or several input lifetimes, reference fields without a lifetime) and unused lifetime
parameters on types (E0392). Reads source text only; `cargo check` is the final word.";

/// Types that cannot hide a lifetime, so a fn taking only these has nothing to borrow from.
const OWNED: &[&str] = &[
    "u8", "u16", "u32", "u64", "u128", "usize", "i8", "i16", "i32", "i64", "i128", "isize", "f32", "f64",
    "bool", "char", "String", "Vec", "Option", "Result", "Box", "HashMap", "HashSet", "BTreeMap", "BTreeSet",
    "PathBuf", "mut",
];

fn first_free_lifetime(sig: &str) -> String {
    let used = lifetimes_in(sig);
    ["'a", "'b", "'r", "'s", "'x"].iter().find(|l| !used.iter().any(|u| u == *l)).unwrap_or(&"'a").to_string()
}

/// Give every elided `&` in `s` the lifetime `lt` (`&T` -> `&'a T`, `&mut T` -> `&'a mut T`).
fn name_refs(s: &str, lt: &str) -> String {
    let b = s.as_bytes();
    let mut out = String::new();
    for (i, ch) in s.char_indices() {
        out.push(ch);
        let next = s[i + 1..].trim_start();
        if ch == '&' && b.get(i + 1) != Some(&b'&') && (i == 0 || b[i - 1] != b'&') && !next.starts_with('\'') {
            out.push_str(lt);
            out.push(' ');
        }
    }
    out
}

fn input_lifetimes(params: &str) -> usize {
    let lts = lifetimes_in(params);
    let mut named: Vec<&String> = lts.iter().filter(|l| *l != "'_").collect();
    named.sort();
    named.dedup();
    elided_refs(params) + lts.iter().filter(|l| *l == "'_").count() + named.len()
}

fn only_owned(params: &str) -> bool {
    split_top(params).iter().all(|p| {
        let ty = p.split_once(':').map_or("", |(_, t)| t);
        ty.split(|c: char| !c.is_alphanumeric() && c != '_').filter(|w| !w.is_empty()).all(|w| OWNED.contains(&w))
    })
}

fn check_fn(f: &FnSig, src: &Src, file: &str, out: &mut Vec<Finding>) {
    let ret = strip_fn_sugar(&f.ret);
    if elided_refs(&ret) == 0 {
        return;
    }
    let params = strip_fn_sugar(&f.params);
    let first = params.trim_start();
    let by_ref_self = first.starts_with('&') && first.split(',').next().is_some_and(|p| p.trim_end().ends_with("self"));
    if by_ref_self || first.starts_with("self:") || first.starts_with("mut self") || first == "self" || first.starts_with("self,") {
        return; // rule 3, or a by-value self whose type may carry the lifetime
    }
    let n = input_lifetimes(&params);
    let line = src.line_of(f.off);
    let gen = |lt: &str| if f.generics.trim().is_empty() { format!("<{lt}>") } else { format!("<{lt}, {}>", f.generics.trim()) };
    // Only rewrite simple signatures: no named lifetimes and no closure sugar to keep apart.
    if n >= 2 && lifetimes_in(&params).iter().all(|l| l == "'_") && params == f.params && ret == f.ret {
        let lt = first_free_lifetime(&format!("{} {}", f.generics, f.params));
        out.push(Finding {
            file: file.into(), line, id: "LT003",
            msg: format!("fn {} returns a reference but has {n} input lifetimes and no &self: which one does it borrow from? (E0106)", f.name),
            fix: one_line(&format!("fn {}{}({}) -> {}   (then remove {lt} from inputs the result never borrows from)",
                                   f.name, gen(&lt), name_refs(&f.params, &lt), name_refs(&f.ret, &lt))),
        });
    } else if n >= 2 {
        out.push(Finding { file: file.into(), line, id: "LT003",
                           msg: format!("fn {} returns an elided reference but has {n} input lifetimes (E0106)", f.name),
                           fix: "write the lifetime of the input the result borrows from on the return type".into() });
    } else if n == 0 && only_owned(&params) {
        out.push(Finding {
            file: file.into(), line, id: "LT003",
            msg: format!("fn {} returns a reference but borrows from no input (E0106)", f.name),
            fix: one_line(&format!("return owned data (String, Vec<T>), or for literals: fn {}{}({}) -> {}",
                                   f.name, if f.generics.is_empty() { String::new() } else { format!("<{}>", f.generics) },
                                   f.params, name_refs(&f.ret, "'static"))),
        });
    }
}

fn check_type(t: &TypeDef, src: &Src, file: &str, out: &mut Vec<Finding>) {
    let line = src.line_of(t.off);
    let body = strip_fn_sugar(&t.body);
    if elided_refs(&body) > 0 {
        // Field name (`raw: &str`), variant name (`A(&str)`, `B { x: &u8 }`) or tuple index.
        let fields: Vec<String> = split_top(&body)
            .iter()
            .enumerate()
            .filter(|(_, f)| elided_refs(f) > 0)
            .map(|(i, f)| {
                let f = f.trim();
                let f = match f.strip_prefix("pub") {
                    Some(r) if r.starts_with('(') => r.split_once(')').map_or(r, |(_, rest)| rest),
                    Some(r) if r.starts_with(' ') => r,
                    _ => f,
                };
                let head = f.split([':', '(', '{']).next().unwrap_or("").trim();
                let name = head.rsplit(' ').next().unwrap_or("");
                if name.is_empty() || name.starts_with('&') { i.to_string() } else { name.to_string() }
            })
            .collect();
        let lt = first_free_lifetime(&t.generics);
        let gen = if t.generics.trim().is_empty() { format!("<{lt}>") } else { format!("<{lt}, {}>", t.generics.trim()) };
        out.push(Finding {
            file: file.into(), line, id: "LT004",
            msg: format!("{} {} has reference field(s) without a lifetime: {} (E0106)", t.kind, t.name, fields.join(", ")),
            fix: format!("{} {}{gen} with `&{lt}` in those fields, or own the data (String / Vec<T> / Arc<str>)", t.kind, t.name),
        });
    }
    for lt in declared_lifetimes(&t.generics) {
        if count_lifetime(&t.body, &lt) == 0 && count_lifetime(&t.generics, &lt) == 1 {
            out.push(Finding { file: file.into(), line, id: "LT006",
                               msg: format!("{} {} declares `{lt}` but no field uses it (E0392)", t.kind, t.name),
                               fix: format!("remove `{lt}`, or add `_marker: PhantomData<&{lt} ()>` if it must stay") });
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
    cli::finish(&opts, RULES, findings, inputs.len(), "missing-lifetime")
}
