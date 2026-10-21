//! Library-or-binary and test-code decisions shared by the error-handling audits.
//! Not an entry point; pulled in with `mod scope;` (needs `mod cli;` and `mod rsparse;`).
#![allow(dead_code)]

use crate::cli::{Input, Opts};
use crate::rsparse::{attrs_before, test_spans, word_positions, FnSig, Src};

pub const SWITCHES: &[&str] = &["--lib", "--app", "--include-tests"];

pub const SCOPE_HELP: &str = "  --lib / --app        treat every file as library / binary code (default: per file;
                       src/main.rs, src/bin/* and files with `fn main` are binary code)
  --include-tests      also audit #[cfg(test)] modules, #[test] fns and tests/ benches/ examples/";

pub struct Scope {
    /// Binary code: panics and anyhow are acceptable at the top level.
    pub app: bool,
    test_file: bool,
    spans: Vec<(usize, usize)>,
    include_tests: bool,
}

impl Scope {
    pub fn new(input: &Input, src: &Src, fns: &[FnSig], opts: &Opts) -> Scope {
        let name = input.name.replace('\\', "/");
        let looks_app = name.ends_with("main.rs") || name.contains("/bin/") || !word_positions(&src.code, "main")
            .iter()
            .filter(|&&i| src.code[..i].trim_end().ends_with("fn"))
            .collect::<Vec<_>>()
            .is_empty();
        let app = if opts.on("--lib") { false } else { opts.on("--app") || looks_app };
        // tests/, benches/ and examples/ only count when they sit next to a Cargo.toml (a crate's test dirs).
        let test_file = std::path::Path::new(&input.name).ancestors().any(|a| {
            let dir = a.file_name().and_then(|n| n.to_str()).unwrap_or("");
            ["tests", "benches", "examples"].contains(&dir) && a.parent().is_some_and(|p| p.join("Cargo.toml").exists())
        });
        let mut spans = test_spans(&src.code);
        for f in fns {
            let attrs = attrs_before(&src.code, f.off);
            if attrs.contains("#[test]") || attrs.contains("::test") {
                if let Some(open) = src.code[f.off..].find('{').map(|n| f.off + n) {
                    spans.push((f.off, open + f.body.len() + 2));
                }
            }
        }
        Scope { app, test_file, spans, include_tests: opts.on("--include-tests") }
    }

    /// Should the code at `off` be skipped as test code?
    pub fn skip(&self, off: usize) -> bool {
        !self.include_tests && (self.test_file || self.spans.iter().any(|&(a, b)| a <= off && off < b))
    }
}

/// Offsets of `needle` in `code` (plain substring search).
pub fn find_all(code: &str, needle: &str) -> Vec<usize> {
    code.match_indices(needle).map(|(i, _)| i).collect()
}

/// The fn whose body contains `off`, if any.
pub fn enclosing<'a>(fns: &'a [FnSig], src: &Src, off: usize) -> Option<&'a FnSig> {
    fns.iter()
        .filter(|f| {
            let start = src.code[f.off..].find('{').map(|n| f.off + n);
            start.is_some_and(|s| s < off && off <= s + f.body.len() + 1)
        })
        .min_by_key(|f| f.body.len())
}
