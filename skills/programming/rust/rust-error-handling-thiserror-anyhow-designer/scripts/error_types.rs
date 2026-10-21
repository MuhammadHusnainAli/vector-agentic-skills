//! Check how error types are declared and exposed.
//!   ERR004 box-dyn-error-not-send   Box<dyn Error> without Send + Sync (fn main is exempt)
//!   ERR005 anyhow-in-lib-api        pub fn in library code returning anyhow::Result / anyhow::Error
//!   ERR008 string-error-type        Result<T, String>, Result<T, &str>, Result<T, ()>
//!   ERR009 source-printed-twice     #[error("..{0}")] on a #[from]/#[source] field (chain prints it twice)
//!   ERR010 missing-non-exhaustive   pub error enum in library code without #[non_exhaustive]
//!
//! Build: rustc -O --edition 2021 scripts/error_types.rs -o /tmp/error_types
//! Usage: error_types <FILES|DIRS|-> [--lib|--app] [--include-tests] [--json] [--strict]

mod cli;
mod rsparse;
mod scope;

use cli::{Finding, Rule};
use rsparse::{attrs_before, base_name, is_pub, items, one_line, split_top, word_positions, Src, TypeDef};
use scope::Scope;

const RULES: &[Rule] = &[
    Rule { id: "ERR004", name: "box-dyn-error-not-send", severity: "medium",
           why: "Box<dyn Error> without Send + Sync cannot cross threads or tokio::spawn and does not convert into anyhow::Error",
           fix: "Box<dyn std::error::Error + Send + Sync + 'static>, or a concrete error type" },
    Rule { id: "ERR005", name: "anyhow-in-lib-api", severity: "high",
           why: "anyhow::Error in a library API forces callers to downcast to handle specific failures",
           fix: "a thiserror enum for the public API; keep anyhow for binaries and internal glue" },
    Rule { id: "ERR008", name: "string-error-type", severity: "medium",
           why: "String/&str/() errors cannot be matched, carry no source and do not implement Error",
           fix: "a typed error (thiserror enum), or anyhow::Error in application code" },
    Rule { id: "ERR009", name: "source-printed-twice", severity: "medium",
           why: "Display must not include the source if source() returns it: reports print the cause twice",
           fix: "describe only this layer in #[error(..)]; the reporter walks source() for the cause" },
    Rule { id: "ERR010", name: "missing-non-exhaustive", severity: "info",
           why: "adding a variant to an exhaustive public error enum is a breaking change",
           fix: "#[non_exhaustive] on public library error enums" },
];

const USAGE: &str = "usage: error_types <FILES|DIRS|-> [options]

Report Box<dyn Error> without Send + Sync (ERR004), anyhow in public library signatures
(ERR005), String/&str/() as error types (ERR008), thiserror messages that print their own
source (ERR009) and exhaustive public library error enums (ERR010).";

/// Error type of `Result<T, E>` in `ret` (None for one-argument aliases such as `Result<T>`).
fn result_error(ret: &str) -> Option<String> {
    let i = word_positions(ret, "Result").into_iter().find(|&i| ret[i + 6..].trim_start().starts_with('<'))?;
    let open = i + 6 + (ret[i + 6..].len() - ret[i + 6..].trim_start().len());
    let inner = &ret[open + 1..rsparse::close_of(ret, open) - 1];
    split_top(inner).get(1).cloned()
}

/// ERR009: thiserror variants whose message names their own source field.
fn twice_printed(t: &TypeDef, src: &Src) -> Vec<(usize, String)> {
    let mut out = Vec::new();
    let mut pos = 0;
    for v in split_top(&t.body) {
        let off = t.body_off + t.body[pos..].find(v.as_str()).map_or(0, |n| pos + n);
        pos = off - t.body_off + v.len();
        let orig = &src.orig[off..off + v.len()];
        let Some(e) = orig.find("#[error(") else { continue };
        let msg_end = orig[e..].find(")]").map_or(orig.len(), |n| e + n);
        let msg = &orig[e + 8..msg_end];
        if msg.trim() == "transparent" {
            continue;
        }
        // Fields after the variant name: (tuple) or {named}.
        let code_v = &src.code[off..off + v.len()];
        let fields_at = code_v.rfind(|c| c == '(' || c == '{').filter(|&i| !code_v[..i].trim_end().ends_with("error"));
        let Some(fa) = fields_at.or_else(|| code_v.find(['(', '{']).filter(|&i| i > msg_end - e)) else { continue };
        let named = code_v.as_bytes()[fa] == b'{';
        let variant = code_v[..fa].rsplit([']', ' ', '\n']).find(|w| !w.trim().is_empty()).unwrap_or("").trim().to_string();
        let body = &code_v[fa + 1..rsparse::close_of(code_v, fa) - 1];
        for (i, field) in split_top(body).iter().enumerate() {
            let is_source = field.contains("#[from]") || field.contains("#[source]")
                || (named && field.trim_start().starts_with("source") && field.contains(':'));
            if !is_source {
                continue;
            }
            let name = if named {
                field.rsplit(']').next().unwrap_or(field).split(':').next().unwrap_or("").trim().to_string()
            } else {
                i.to_string()
            };
            if msg.contains(&format!("{{{name}}}")) || msg.contains(&format!("{{{name}:")) {
                out.push((off, format!("{variant}: message {} prints `{{{name}}}`, which is also the error's source()", one_line(msg))));
            }
        }
    }
    out
}

fn main() {
    let usage = format!("{USAGE}\n\n{}", scope::SCOPE_HELP);
    let opts = cli::parse(&usage, RULES, &[], scope::SWITCHES);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, types, impls) = items(&src);
        let scope = Scope::new(input, &src, &fns, &opts);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String, fix: &str| {
            if !scope.skip(off) {
                found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: fix.into() });
            }
        };
        let anyhow_result = src.code.contains("use anyhow::Result") || src.code.contains("use anyhow::{") && src.code.contains("Result");
        for f in &fns {
            let sig = format!("{} {}", f.params, f.ret);
            for i in word_positions(&sig, "dyn") {
                let obj = one_line(sig[i..].split(['>', ')', ',']).next().unwrap_or(""));
                if base_name(obj.trim_start_matches("dyn ").split('+').next().unwrap_or("")) == "Error"
                    && sig[..i].trim_end().ends_with("Box<") && !obj.contains("Send") && f.name != "main" {
                    push(f.off, "ERR004", format!("fn {} uses `Box<{obj}>` without Send + Sync", f.name),
                         "Box<dyn std::error::Error + Send + Sync + 'static>");
                }
            }
            let in_trait_impl = f.impl_idx.is_some_and(|i| impls[i].trait_and_self().0.is_some());
            if !scope.app && is_pub(&src.code, f.off) && !in_trait_impl
                && (f.ret.contains("anyhow::") || anyhow_result && result_error(&f.ret).is_none() && f.ret.contains("Result<")) {
                push(f.off, "ERR005", format!("pub fn {} returns anyhow in library code: `{}`", f.name, one_line(&f.ret)),
                     "return a thiserror enum; convert to anyhow in the binary");
            }
            if let Some(e) = result_error(&f.ret) {
                let e = e.replace(' ', "");
                if ["String", "&str", "&'staticstr", "()"].contains(&e.as_str()) {
                    push(f.off, "ERR008", format!("fn {} returns `{}`: the error is a {}", f.name, one_line(&f.ret), if e == "()" { "unit" } else { "string" }),
                         "a thiserror enum (library) or anyhow::Result (application)");
                }
            }
        }
        for t in types.iter().filter(|t| t.kind == "enum") {
            let attrs = attrs_before(&src.code, t.off);
            let is_error = t.name.ends_with("Error") || attrs.contains("Error");
            if !is_error {
                continue;
            }
            for (off, msg) in twice_printed(t, &src) {
                push(off, "ERR009", format!("{}::{msg}", t.name), "drop the placeholder: #[error(\"failed to ..\")]");
            }
            if !scope.app && is_pub(&src.code, t.off) && !attrs.contains("non_exhaustive") {
                push(t.off, "ERR010", format!("pub enum {} can never gain a variant without a major release", t.name), "#[non_exhaustive]");
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "error type")
}
