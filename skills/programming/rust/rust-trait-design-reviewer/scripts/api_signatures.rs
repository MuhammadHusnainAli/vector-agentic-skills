//! Find function signatures that make APIs harder to use than they need to be.
//!   TR009 box-dyn-error-not-send   Result<T, Box<dyn Error>> (not Send + Sync), except in fn main
//!   TR010 borrowed-owned-param     &Vec<T>, &String, &Box<T>, &PathBuf, &OsString parameters
//!   TR013 builder-missing-must-use pub fn x(self, ..) -> Self without #[must_use] on it or its type
//!
//! Build: rustc -O --edition 2021 scripts/api_signatures.rs -o /tmp/api_signatures
//! Usage: api_signatures <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;

use cli::{Finding, Rule};
use rsparse::{attrs_before, base_name, is_pub, items, one_line, split_top, test_spans, word_positions, Src};

const RULES: &[Rule] = &[
    Rule { id: "TR009", name: "box-dyn-error-not-send", severity: "medium",
           why: "Box<dyn Error> without Send + Sync cannot cross threads or tokio::spawn, and anyhow cannot wrap it cheaply",
           fix: "Box<dyn std::error::Error + Send + Sync + 'static> (a `BoxError` alias), or a concrete error type" },
    Rule { id: "TR010", name: "borrowed-owned-param", severity: "low",
           why: "&Vec<T>/&String/&Box<T>/&PathBuf/&OsString force callers to own that exact container (clippy::ptr_arg)",
           fix: "&[T], &str, &T, &Path, &OsStr: strictly more callers, same body" },
    Rule { id: "TR013", name: "builder-missing-must-use", severity: "low",
           why: "a by-value builder method whose result is dropped silently does nothing",
           fix: "#[must_use] on the builder type (covers every method) or on each method" },
];

const USAGE: &str = "usage: api_signatures <FILES|DIRS|-> [options]

Report Box<dyn Error> without Send + Sync (TR009, fn main is exempt), parameters that
borrow an owned container instead of its slice/view type (TR010, trait impls exempt since
the trait fixes the signature) and by-value builder methods without #[must_use] (TR013).
#[cfg(test)] modules are skipped.";

const OWNED: &[(&str, &str)] = &[("Vec", "&[T]"), ("String", "&str"), ("Box", "&T"), ("PathBuf", "&Path"), ("OsString", "&OsStr")];

/// Every `Box<dyn ...Error>` in `s` that lacks `Send` (borrowed `&dyn Error`, as in
/// `Error::source`, is fine and required by std).
fn non_send_dyn_errors(s: &str) -> Vec<String> {
    word_positions(s, "dyn")
        .into_iter()
        .filter(|&i| s[..i].trim_end().ends_with("Box<"))
        .filter_map(|i| {
            let rest = &s[i..];
            let end = rest.find(['>', ')', ',', ';', '{', '=']).unwrap_or(rest.len());
            let obj = one_line(&rest[..end]);
            let is_error = base_name(obj.trim_start_matches("dyn ").split('+').next().unwrap_or("")) == "Error";
            (is_error && !obj.contains("Send")).then_some(obj)
        })
        .collect()
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, types, impls) = items(&src);
        let tests = test_spans(&src.code);
        let in_test = |off: usize| tests.iter().any(|&(a, b)| a < off && off < b);
        let mut found = Vec::new();
        for f in fns.iter().filter(|f| !in_test(f.off)) {
            let line = src.line_of(f.off);
            let block = f.impl_idx.map(|i| &impls[i]);
            let trait_impl = block.is_some_and(|b| b.trait_and_self().0.is_some());

            if f.name != "main" && !trait_impl {
                for obj in non_send_dyn_errors(&format!("{} {}", f.params, f.ret)) {
                    found.push(Finding { file: input.name.clone(), line, id: "TR009",
                                         msg: format!("fn {} uses `{obj}` without Send + Sync", f.name),
                                         fix: format!("{} + Send + Sync + 'static", obj.trim_end_matches(" + 'static")) });
                }
            }
            if !trait_impl {
                for p in split_top(&f.params) {
                    let Some((name, ty)) = p.split_once(':') else { continue };
                    let ty = ty.trim();
                    let Some(inner) = ty.strip_prefix('&').map(str::trim_start) else { continue };
                    if inner.starts_with("mut ") || inner.starts_with('\'') {
                        continue; // &mut Vec<T> can grow the Vec; explicit lifetimes are deliberate
                    }
                    if let Some((owned, better)) = OWNED.iter().find(|(o, _)| base_name(inner) == *o && !inner.contains("dyn ")) {
                        // Name the concrete view type: &Vec<String> -> &[String], &Box<Node> -> &Node.
                        let arg = inner.split_once('<').map(|(_, r)| r.trim_end().trim_end_matches('>').trim());
                        let better = match (*owned, arg) {
                            ("Vec", Some(a)) => format!("&[{a}]"),
                            ("Box", Some(a)) => format!("&{a}"),
                            _ => better.to_string(),
                        };
                        found.push(Finding { file: input.name.clone(), line, id: "TR010",
                                             msg: format!("fn {} parameter `{}: {ty}` borrows a {owned}", f.name, name.trim()),
                                             fix: format!("`{}: {better}` accepts {owned} and more without changing the body", name.trim()) });
                    }
                }
            }
            // By-value builder method in an inherent impl.
            let receiver = split_top(&f.params).first().map(|p| p.replace(' ', "")).unwrap_or_default();
            if let Some(b) = block.filter(|_| !trait_impl) {
                let self_ty = base_name(&b.trait_and_self().1);
                let type_must_use = types.iter().any(|t| t.name == self_ty && attrs_before(&src.code, t.off).contains("must_use"));
                let by_value = receiver == "self" || receiver == "mutself";
                if by_value && f.ret.trim() == "Self" && is_pub(&src.code, f.off)
                    && !type_must_use && !attrs_before(&src.code, f.off).contains("must_use") {
                    found.push(Finding { file: input.name.clone(), line, id: "TR013",
                                         msg: format!("builder method {self_ty}::{} returns Self by value without #[must_use]", f.name),
                                         fix: format!("#[must_use] on struct {self_ty} (covers all its builder methods)") });
                }
            }
        }
        // Type aliases are a common home for Box<dyn Error>.
        for i in word_positions(&src.code, "type") {
            let stmt = src.code[i..].split(';').next().unwrap_or("");
            if stmt.contains('=') && !in_test(i) {
                for obj in non_send_dyn_errors(stmt) {
                    found.push(Finding { file: input.name.clone(), line: src.line_of(i), id: "TR009",
                                         msg: format!("type alias uses `{obj}` without Send + Sync"),
                                         fix: format!("{} + Send + Sync + 'static", obj.trim_end_matches(" + 'static")) });
                }
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    cli::finish(&opts, RULES, findings, inputs.len(), "API signature")
}
