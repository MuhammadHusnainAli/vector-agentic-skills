//! Find unsafety at FFI boundaries and in global state, plus edition-2024 unsafe changes.
//!   US008 static-mut               `static mut` items
//!   US009 static-mut-ref           &X, &mut X or X.method() on a static mut (denied in edition 2024)
//!   US011 unsafe-impl-send-sync    unsafe impl Send/Sync without a SAFETY argument; unbounded impl<T>
//!   US017 extern-c-may-panic       extern "C" fn that can panic (unwrap, expect, panic!, indexing) without catch_unwind
//!   US019 extern-block-not-unsafe  extern "C" { .. } without `unsafe` (required in edition 2024)
//!   US020 unsafe-attr-2024         #[no_mangle] / #[export_name] / #[link_section] not written #[unsafe(..)]
//!   US021 env-set-var              std::env::set_var / remove_var (unsafe in edition 2024: racy with C getenv)
//!   US023 safe-fn-derefs-raw-ptr   safe pub fn that dereferences a raw-pointer parameter
//!
//! Build: rustc -O --edition 2021 scripts/ffi_and_globals.rs -o /tmp/ffi_and_globals
//! Usage: ffi_and_globals <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;
mod unsafe_items;

use cli::{Finding, Rule};
use rsparse::{is_pub, items, one_line, split_top, word_positions, Src};
use unsafe_items::{unsafe_items, UnsafeItem};

const RULES: &[Rule] = &[
    Rule { id: "US008", name: "static-mut", severity: "medium",
           why: "every access to a static mut is unsafe and racy; edition 2024 denies taking references to it",
           fix: "atomics (AtomicUsize, AtomicPtr), Mutex/RwLock, OnceLock/LazyLock, or thread_local!" },
    Rule { id: "US009", name: "static-mut-ref", severity: "high",
           why: "a reference to a static mut aliases every other access: UB unless nothing else touches it (static_mut_refs)",
           fix: "replace the static (US008); if it must stay, use &raw const X / &raw mut X (1.82) and copy values out" },
    Rule { id: "US011", name: "unsafe-impl-send-sync", severity: "medium",
           why: "Send/Sync impls assert thread safety the compiler could not prove; an unbounded impl<T> makes any T Send",
           fix: "// SAFETY: argument naming the synchronisation; bound generics (impl<T: Send> Send); never Sync with RefCell/Cell inside" },
    Rule { id: "US017", name: "extern-c-may-panic", severity: "low",
           why: "a panic unwinding out of extern \"C\" aborts the process (since 1.81); C callers get no error",
           fix: "wrap the body in std::panic::catch_unwind and return an error code, or use extern \"C-unwind\" deliberately" },
    Rule { id: "US019", name: "extern-block-not-unsafe", severity: "low",
           why: "edition 2024 requires `unsafe extern` blocks: declaring foreign items is an unchecked promise",
           fix: "unsafe extern \"C\" { .. } (1.82+), marking functions that are safe to call as `pub safe fn`" },
    Rule { id: "US020", name: "unsafe-attr-2024", severity: "low",
           why: "edition 2024 requires unsafe(..) around attributes that can cause UB through symbol clashes or layout",
           fix: "#[unsafe(no_mangle)], #[unsafe(export_name = \"..\")], #[unsafe(link_section = \"..\")] (1.82+)" },
    Rule { id: "US021", name: "env-set-var", severity: "low",
           why: "set_var/remove_var race with getenv in C code and other threads; unsafe fn in edition 2024",
           fix: "pass configuration explicitly; set env vars only for child processes (Command::env) or before threads start" },
    Rule { id: "US023", name: "safe-fn-derefs-raw-ptr", severity: "high",
           why: "a safe fn taking *const T and dereferencing it lets safe callers cause UB with any pointer",
           fix: "make it `unsafe fn` with a # Safety section, or take &T / &[T] / &CStr instead of raw pointers" },
];

const USAGE: &str = "usage: ffi_and_globals <FILES|DIRS|-> [options]

Report static mut items and references to them (US008, US009), unsafe Send/Sync impls
without an argument (US011), extern \"C\" fns that may unwind (US017), edition-2024
unsafe syntax not yet adopted (US019, US020, US021) and safe pub fns that dereference
raw-pointer parameters (US023).";

const DEREFS: &[&str] = &["from_raw_parts", "from_ptr", ".read()", ".read_volatile", "&*", "*", ".as_ref()", ".offset(", ".add("];

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, _, _) = items(&src);
        let list: Vec<UnsafeItem> = unsafe_items(&src, &fns);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String| {
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: String::new() });
        };

        // static mut and references to it
        let mut statics = Vec::new();
        for off in word_positions(code, "static") {
            let rest = code[off + 6..].trim_start();
            if let Some(r) = rest.strip_prefix("mut ") {
                let name: String = r.trim_start().chars().take_while(|c| c.is_alphanumeric() || *c == '_').collect();
                push(off, "US008", format!("`static mut {name}`"));
                statics.push(name);
            }
        }
        for name in &statics {
            for off in word_positions(code, name) {
                let before = code[..off].trim_end();
                let after = &code[off + name.len()..];
                if before.ends_with("static mut") {
                    continue; // the declaration itself
                }
                // `&X`, `&mut X` and `X.method()` (autoref) all create references; `&raw` does not.
                let borrowed = before.ends_with('&') || before.ends_with("&mut") || after.starts_with('.') && !after.starts_with("..");
                let raw = before.ends_with("&raw const") || before.ends_with("&raw mut") || before.ends_with("addr_of!(") || before.ends_with("addr_of_mut!(");
                if borrowed && !raw {
                    push(off, "US009", format!("reference to `static mut {name}` (`{}`)", one_line(code[off..].split([';', '\n']).next().unwrap_or(""))));
                }
            }
        }

        // unsafe impl Send / Sync
        for it in list.iter().filter(|i| i.kind == "impl") {
            let h = &it.name;
            let marker = if h.contains(" Send for ") { "Send" } else if h.contains(" Sync for ") { "Sync" } else { continue };
            let generic = h.strip_prefix("impl<").map(|g| g.split('>').next().unwrap_or(""));
            let unbounded = generic.is_some_and(|g| split_top(g).iter().any(|p| !p.starts_with('\'') && !p.contains(':')));
            if unbounded {
                push(it.off, "US011", format!("`unsafe {h}` has unbounded type parameters: every T becomes {marker}"));
            } else if !it.documented {
                push(it.off, "US011", format!("`unsafe {h}` has no SAFETY argument for why the type is {marker}"));
            }
        }

        // extern "C" fns: panics, attributes, raw pointer params
        for f in &fns {
            let before = code[..f.off].trim_end();
            let abi_c = before.ends_with('"') && code[..f.off].rfind("extern").is_some_and(|e| f.off - e < 20)
                && src.orig[code[..f.off].rfind("extern").unwrap_or(0)..f.off].contains("\"C\"");
            let may_panic = [".unwrap()", ".expect(", "panic!", "unreachable!", "todo!"].iter().any(|p| f.body.contains(p));
            if abi_c && !f.body.is_empty() && may_panic && !f.body.contains("catch_unwind") {
                push(f.off, "US017", format!("extern \"C\" fn {} can panic and has no catch_unwind", f.name));
            }
            let is_unsafe_fn = before.ends_with("unsafe") || before.ends_with('"') && before.contains("unsafe extern");
            let raw_params: Vec<String> = split_top(&f.params)
                .iter()
                .filter(|p| p.contains("*const") || p.contains("*mut"))
                .filter_map(|p| p.split(':').next().map(|n| n.trim().to_string()))
                .collect();
            if is_pub(code, f.off) || before.ends_with("pub extern") || abi_c && is_pub(code, code[..f.off].rfind("extern").unwrap_or(f.off)) {
                let unsafe_kw = code[..f.off].rsplit('\n').next().unwrap_or("").contains("unsafe");
                for p in raw_params.iter().filter(|_| !is_unsafe_fn && !unsafe_kw) {
                    let used = word_positions(&f.body, p).iter().any(|&i| {
                        let ctx = &f.body[i.saturating_sub(24)..(i + p.len() + 16).min(f.body.len())];
                        DEREFS.iter().any(|d| ctx.contains(d))
                    });
                    if used {
                        push(f.off, "US023", format!("safe {}fn {} dereferences raw-pointer parameter `{p}`{}",
                                                     if abi_c { "extern \"C\" " } else { "pub " }, f.name,
                                                     if abi_c { " (C callers only; still mark it unsafe or validate)" } else { "" }));
                    }
                }
            }
        }
        for off in word_positions(code, "extern") {
            let rest = code[off + 6..].trim_start();
            let rest = if rest.starts_with('"') { rest[1..].find('"').map_or(rest, |q| &rest[q + 2..]).trim_start() } else { rest };
            if rest.starts_with('{') && !code[..off].trim_end().ends_with("unsafe") {
                push(off, "US019", "`extern \"C\" { .. }` block is not declared `unsafe extern`".into());
            }
        }
        for attr in ["#[no_mangle]", "#[export_name", "#[link_section"] {
            for (off, _) in code.match_indices(attr) {
                push(off, "US020", format!("`{attr}{}` must be written `#[unsafe({})]` in edition 2024",
                                           if attr.ends_with(']') { "" } else { " = ..]" }, attr.trim_start_matches("#[").trim_end_matches(']')));
            }
        }
        for call in ["set_var(", "remove_var("] {
            for (off, _) in code.match_indices(call) {
                if code[..off].ends_with("env::") || code[..off].ends_with("std::env::") {
                    push(off, "US021", format!("`env::{}..)` mutates the process environment", call));
                }
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
    cli::finish(&opts, RULES, findings, inputs.len(), "FFI/global")
}
