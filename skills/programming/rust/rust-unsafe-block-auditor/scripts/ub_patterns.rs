//! Find unsafe patterns that are undefined behaviour or almost always unsound.
//!   US003 transmute            any transmute; high when it extends a lifetime to 'static
//!   US004 mem-uninitialized    mem::uninitialized() (UB for nearly every type)
//!   US005 zeroed-invalid-type  mem::zeroed for references, Box, Vec, String, NonNull, fn pointers
//!   US006 uninit-assume-init   MaybeUninit::uninit().assume_init()
//!   US007 set-len-before-init  Vec::set_len(n) with no visible write of the new elements first
//!   US010 cstring-temp-ptr     CString::new(..).unwrap().as_ptr(): pointer to a dropped temporary
//!   US024 mut-from-ref         fn f(&self) -> &mut T built with unsafe (aliasing &mut)
//!
//! Build: rustc -O --edition 2021 scripts/ub_patterns.rs -o /tmp/ub_patterns
//! Usage: ub_patterns <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;
mod unsafe_items;

use cli::{Finding, Rule};
use rsparse::{close_of, items, one_line, split_top, Src};
use unsafe_items::unsafe_items;

const RULES: &[Rule] = &[
    Rule { id: "US003", name: "transmute", severity: "high",
           why: "transmute reinterprets bits with no checks: invalid values, size/layout and lifetime extension are UB",
           fix: "to_bits/from_bits, from_ne_bytes, as casts, bytemuck/zerocopy; never transmute lifetimes (own the data)" },
    Rule { id: "US004", name: "mem-uninitialized", severity: "high",
           why: "mem::uninitialized is UB for almost every type (deprecated since 1.39)",
           fix: "MaybeUninit<T>: write every field, then assume_init" },
    Rule { id: "US005", name: "zeroed-invalid-type", severity: "high",
           why: "all-zero bits are not a valid reference, Box, Vec, String, NonNull or fn pointer",
           fix: "Default::default(), Option<NonNull<T>>/Option<&T> for nullable pointers, or MaybeUninit" },
    Rule { id: "US006", name: "uninit-assume-init", severity: "high",
           why: "assume_init on memory nothing wrote is UB (even for integers: uninit bytes are not values)",
           fix: "initialise first ([0u64; 64], MaybeUninit::write), or keep it as MaybeUninit<T>" },
    Rule { id: "US007", name: "set-len-before-init", severity: "high",
           why: "set_len exposes uninitialised elements; reading or dropping them is UB",
           fix: "write the elements (spare_capacity_mut + write, ptr::write, FFI fill) first, then set_len to the count actually written" },
    Rule { id: "US010", name: "cstring-temp-ptr", severity: "high",
           why: "the CString is dropped at the end of the statement, so the pointer dangles when C reads it",
           fix: "let c = CString::new(s)?; call(c.as_ptr()); // c lives across the call" },
    Rule { id: "US024", name: "mut-from-ref", severity: "high",
           why: "two calls through &self give two aliasing &mut to the same data: UB",
           fix: "take &mut self, or return a guard (RefCell::borrow_mut, Mutex::lock); UnsafeCell needs a uniqueness argument" },
];

const USAGE: &str = "usage: ub_patterns <FILES|DIRS|-> [options]

Report transmute (US003), mem::uninitialized (US004), mem::zeroed of types with invalid
all-zero values (US005), uninit().assume_init() (US006), set_len before the elements are
written (US007), pointers to temporary CStrings (US010) and &self -> &mut T (US024).";

/// Types for which all-zero bytes are not a valid value.
const NOT_ZEROABLE: &[&str] = &["&", "Box", "Vec", "String", "NonNull", "fn(", "Rc", "Arc", "HashMap", "char", "bool"];

fn zero_invalid(ty: &str, local: &[rsparse::TypeDef]) -> Option<String> {
    let ty = ty.trim();
    if let Some(bad) = NOT_ZEROABLE.iter().find(|b| ty.starts_with(*b) || ty.contains(&format!("<{b}")) || ty == **b) {
        return Some(format!("`{ty}` ({bad} has no all-zero value)"));
    }
    let def = local.iter().find(|t| t.name == rsparse::base_name(ty))?;
    split_top(&def.body).iter().find_map(|f| {
        let fty = f.split_once(':').map_or(f.as_str(), |(_, t)| t).trim();
        NOT_ZEROABLE.iter().any(|b| fty.starts_with(*b)).then(|| format!("`{ty}` (field `{}` cannot be zero)", one_line(f)))
    })
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, types, impls) = items(&src);
        let list = unsafe_items(&src, &fns);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String| {
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: String::new() });
        };

        for (off, _) in code.match_indices("transmute") {
            let call = one_line(code[off..].split([';', '\n']).next().unwrap_or("").trim_end_matches(['}', ' ']));
            let to_static = call.contains("'static") || src.code[..off].rsplit('\n').next().unwrap_or("").contains("'static");
            push(off, "US003", format!("`{call}`{}", if to_static { ": extends a lifetime to 'static (dangling reference)" } else { "" }));
        }
        for (off, _) in code.match_indices("uninitialized(") {
            push(off, "US004", "mem::uninitialized() creates invalid values".into());
        }
        for (off, _) in code.match_indices("zeroed") {
            let rest = &code[off + 6..];
            let ty = if let Some(t) = rest.strip_prefix("::<") {
                Some(t[..rsparse::close_of(&format!("<{t}"), 0) - 2].to_string())
            } else {
                // `let x: T = mem::zeroed();`
                let stmt = &code[code[..off].rfind([';', '{', '}']).map_or(0, |i| i + 1)..off];
                stmt.split_once(':').map(|(_, t)| t.split('=').next().unwrap_or("").to_string())
            };
            if let Some(why) = ty.as_deref().and_then(|t| zero_invalid(t, &types)) {
                push(off, "US005", format!("mem::zeroed for {why}"));
            }
        }
        for (off, _) in code.match_indices("uninit()") {
            let after = code[off + 8..].trim_start();
            let expr_start = code[..off].rfind([';', '{', '=', '(']).map_or(0, |i| i + 1);
            let nested = code[expr_start..off].contains("[MaybeUninit"); // MaybeUninit<[MaybeUninit<T>; N]> is fine
            if after.starts_with(".assume_init()") && !nested {
                push(off, "US006", "MaybeUninit::uninit().assume_init() reads memory nothing initialised".into());
            }
        }
        for (off, _) in code.match_indices(".set_len(") {
            let scope_start = list.iter().filter(|i| i.off < off && off < i.end).map(|i| i.off).max().unwrap_or(0);
            let before = &code[scope_start..off];
            let wrote = ["write(", "copy", "spare_capacity_mut", "fill(", "read_exact", "extend", "push"].iter().any(|w| before.contains(w));
            if !wrote {
                push(off, "US007", "set_len before any visible write of the new elements".into());
            }
        }
        for (off, _) in code.match_indices("CString::new(") {
            let open = off + "CString::new".len();
            let after = &code[close_of(code, open)..];
            let after = after.trim_start();
            let rest = if let Some(r) = after.strip_prefix(".unwrap()") { r } else if let Some(r) = after.strip_prefix('?') { r }
                       else if after.starts_with(".expect(") { &after[close_of(after, 7)..] } else { continue };
            if rest.trim_start().starts_with(".as_ptr()") {
                push(off, "US010", "`CString::new(..)..as_ptr()`: the CString is a temporary dropped at the end of the statement".into());
            }
        }
        for f in &fns {
            let recv = split_top(&f.params).first().map(|p| p.replace(' ', "")).unwrap_or_default();
            let in_trait_impl = f.impl_idx.is_some_and(|i| impls[i].trait_and_self().0.is_some());
            if (recv == "&self" || recv.starts_with("&'") && recv.ends_with("self") && !recv.contains("mut"))
                && f.ret.trim_start().starts_with("&mut") && f.body.contains("unsafe") && !in_trait_impl {
                push(f.off, "US024", format!("fn {} takes &self but returns `{}`", f.name, one_line(&f.ret)));
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
    cli::finish(&opts, RULES, findings, inputs.len(), "undefined-behaviour")
}
