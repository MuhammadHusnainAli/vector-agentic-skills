//! Check that every unsafe item carries its justification, and that the crate turns on the
//! lints that keep it that way.
//!   US001 missing-safety-comment  unsafe block / unsafe impl without `// SAFETY:`
//!   US002 missing-safety-doc      unsafe fn / unsafe trait without a `# Safety` doc section
//!   US018 large-unsafe-block      block longer than --max-block-lines (default 15)
//!   US026 forbid-unsafe-code      crate root with no unsafe and no #![forbid(unsafe_code)]
//!   US027 unsafe-op-lint          unsafe fns but no unsafe_op_in_unsafe_fn lint (default in 2024)
//!   US028 safety-comment-lint     unsafe blocks but no clippy::undocumented_unsafe_blocks
//!
//! Build: rustc -O --edition 2021 scripts/safety_comments.rs -o /tmp/safety_comments
//! Usage: safety_comments <FILES|DIRS|-> [--max-block-lines N] [--json] [--strict]

mod cli;
mod rsparse;
mod unsafe_items;

use cli::{Finding, Rule};
use rsparse::{items, Src};
use unsafe_items::unsafe_items;

const RULES: &[Rule] = &[
    Rule { id: "US001", name: "missing-safety-comment", severity: "medium",
           why: "every unsafe block/impl must say which invariants make it sound (clippy::undocumented_unsafe_blocks)",
           fix: "// SAFETY: <why each precondition of every unsafe operation holds here>" },
    Rule { id: "US002", name: "missing-safety-doc", severity: "medium",
           why: "an unsafe fn/trait must document the contract callers or implementors uphold (clippy::missing_safety_doc)",
           fix: "/// # Safety\\n/// <every precondition: validity, alignment, aliasing, lifetimes, thread rules>" },
    Rule { id: "US018", name: "large-unsafe-block", severity: "low",
           why: "a long unsafe block hides which operation needs which invariant and unsafe-checks safe code too",
           fix: "shrink the block to the unsafe operations; one block (and one SAFETY comment) per operation" },
    Rule { id: "US026", name: "forbid-unsafe-code", severity: "info",
           why: "a crate without unsafe can promise it stays that way",
           fix: "#![forbid(unsafe_code)] at the crate root, or [lints.rust] unsafe_code = \"forbid\"" },
    Rule { id: "US027", name: "unsafe-op-lint", severity: "info",
           why: "without it, an unsafe fn body is one big implicit unsafe block (edition 2024 warns by default)",
           fix: "#![deny(unsafe_op_in_unsafe_fn)] (or [lints.rust]) and explicit unsafe blocks inside unsafe fns" },
    Rule { id: "US028", name: "safety-comment-lint", severity: "info",
           why: "the lint keeps new unsafe blocks documented",
           fix: "#![warn(clippy::undocumented_unsafe_blocks, clippy::missing_safety_doc)] or [lints.clippy]" },
];

const USAGE: &str = "usage: safety_comments <FILES|DIRS|-> [--max-block-lines N] [options]

Report unsafe blocks and impls without a `// SAFETY:` comment (US001), unsafe fns and
traits without a `# Safety` doc section (US002), oversized unsafe blocks (US018) and
missing crate-level safety lints (US026-US028, read from the crate root file and the
[lints] tables of ancestor Cargo.toml files).

  --max-block-lines N  US018 threshold (default 15)";

/// Text of every Cargo.toml above `file`, for [lints] lookups.
fn cargo_lints(file: &str) -> String {
    let mut out = String::new();
    let mut dir = std::path::Path::new(file).canonicalize().ok().and_then(|p| p.parent().map(|d| d.to_path_buf()));
    while let Some(d) = dir {
        if let Ok(t) = std::fs::read_to_string(d.join("Cargo.toml")) {
            out.push_str(&t);
        }
        dir = d.parent().map(|p| p.to_path_buf());
    }
    out
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &["--max-block-lines"]);
    let max: usize = opts.value("--max-block-lines").map_or(15, |v| v.parse().unwrap_or_else(|_| cli::die("--max-block-lines needs a number")));
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, _, _) = items(&src);
        let list = unsafe_items(&src, &fns);
        let traits = rsparse::traits(&src);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String| {
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: String::new() });
        };
        for it in &list {
            match it.kind {
                "block" | "impl" if !it.documented => {
                    let what = if it.kind == "block" { format!("unsafe block in fn {}", it.name) } else { format!("`unsafe {}`", it.name) };
                    push(it.off, "US001", format!("{what} has no // SAFETY: comment"));
                }
                "fn" | "trait" if !it.documented => {
                    // Methods of a pub trait are public even without `pub`.
                    let in_pub_trait = traits.iter().any(|t| t.span.0 < it.off && it.off < t.span.1 && rsparse::is_pub(&src.code, t.off));
                    let public = in_pub_trait || src.code[..it.off].trim_end().ends_with("pub") || src.code[..it.off].trim_end().ends_with(')');
                    let what = if it.kind == "fn" { format!("unsafe fn {}", it.name) } else { format!("`unsafe {}`", it.name) };
                    push(it.off, "US002", format!("{what}{} has no # Safety section in its docs", if public { "" } else { " (private)" }));
                }
                _ => {}
            }
            if it.kind == "block" {
                let lines = src.line_of(it.end) - src.line_of(it.off) + 1;
                if lines > max {
                    push(it.off, "US018", format!("unsafe block in fn {} spans {lines} lines (max {max})", it.name));
                }
            }
        }
        // Crate-level lint checks: only on files that look like a crate root.
        let base = std::path::Path::new(&input.name).file_name().and_then(|n| n.to_str()).unwrap_or("");
        let root = base == "lib.rs" || base == "main.rs" || src.code.contains("#![") || input.name == "<stdin>";
        if root {
            let lints = format!("{}\n{}", src.code, if input.name == "<stdin>" { String::new() } else { cargo_lints(&input.name) });
            let has = |name: &str| lints.contains(name);
            if list.is_empty() && !has("unsafe_code") {
                push(0, "US026", "crate root has no unsafe code but does not forbid it".into());
            }
            if list.iter().any(|i| i.kind == "fn") && !has("unsafe_op_in_unsafe_fn") && input.edition < 2024 {
                push(0, "US027", "crate has unsafe fns but no unsafe_op_in_unsafe_fn lint".into());
            }
            if list.iter().any(|i| i.kind == "block") && !has("undocumented_unsafe_blocks") {
                push(0, "US028", "crate has unsafe blocks but does not enable clippy::undocumented_unsafe_blocks".into());
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line.max(1), f.id)));
    }
    let findings: Vec<Finding> = findings
        .into_iter()
        .map(|mut f| {
            f.line = f.line.max(1);
            f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.replace("\\n", " ").to_string());
            f
        })
        .collect();
    cli::finish(&opts, RULES, findings, inputs.len(), "safety-documentation")
}
