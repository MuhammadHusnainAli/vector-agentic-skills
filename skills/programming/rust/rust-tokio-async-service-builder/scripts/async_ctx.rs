//! Where is code async, and which fns are axum handlers? Shared by the tokio scripts;
//! pulled in with `mod async_ctx;` (needs `mod rsparse;`).
//!
//! Async context = `async fn` bodies, `async {}` / `async move {}` blocks and async closures,
//! minus the arguments of spawn_blocking, block_in_place, thread::spawn and rayon::spawn
//! (code there runs on a blocking thread, where blocking is the point).
#![allow(dead_code)]

use crate::rsparse::{close_of, word_positions, FnSig, Src};

pub struct AsyncCtx {
    spans: Vec<(usize, usize)>,
    excluded: Vec<(usize, usize)>,
}

/// `{ .. }` body span of a fn, if it has one.
pub fn body_span(src: &Src, f: &FnSig) -> Option<(usize, usize)> {
    let open = f.off + src.code[f.off..].find(['{', ';'])?;
    (src.code.as_bytes()[open] == b'{').then(|| (open, close_of(&src.code, open)))
}

pub fn is_async_fn(src: &Src, f: &FnSig) -> bool {
    let before = src.code[..f.off].trim_end();
    before.ends_with("async") || before.ends_with("async unsafe")
}

/// Argument spans of every call to one of `names` (e.g. `spawn_blocking(`).
pub fn call_arg_spans(code: &str, names: &[&str]) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    for name in names {
        for (i, _) in code.match_indices(name) {
            let open = i + name.len() - 1; // names end with '('
            out.push((open, close_of(code, open)));
        }
    }
    out
}

/// Spans of `name! { .. }` / `name!( .. )` macro bodies, e.g. `select!`.
pub fn macro_spans(code: &str, name: &str) -> Vec<(usize, usize)> {
    code.match_indices(name)
        .filter_map(|(i, _)| {
            let rest = &code[i + name.len()..];
            let open = i + name.len() + rest.find(['{', '('])?;
            (rest[..open - i - name.len()].trim().is_empty()).then(|| (open, close_of(code, open)))
        })
        .collect()
}

impl AsyncCtx {
    pub fn new(src: &Src, fns: &[FnSig]) -> AsyncCtx {
        let code = &src.code;
        let mut spans: Vec<(usize, usize)> = fns.iter().filter(|f| is_async_fn(src, f)).filter_map(|f| body_span(src, f)).collect();
        for i in word_positions(code, "async") {
            let mut rest = code[i + 5..].trim_start();
            if let Some(r) = rest.strip_prefix("move") {
                rest = r.trim_start();
            }
            let at = code.len() - rest.len();
            if rest.starts_with('{') {
                spans.push((at, close_of(code, at)));
            } else if rest.starts_with('|') {
                // async closure: |args| { body }  or  |args| expr
                if let Some(end_args) = rest[1..].find('|') {
                    let body = rest[end_args + 2..].trim_start();
                    let b = code.len() - body.len();
                    if body.starts_with('{') {
                        spans.push((b, close_of(code, b)));
                    }
                }
            }
        }
        let excluded = call_arg_spans(code, &["spawn_blocking(", "block_in_place(", "thread::spawn(", "rayon::spawn(", "thread::scope("]);
        AsyncCtx { spans, excluded }
    }

    /// Is `off` in async code (and not inside a blocking-thread closure)?
    pub fn contains(&self, off: usize) -> bool {
        self.spans.iter().any(|&(a, b)| a < off && off < b) && !self.excluded.iter().any(|&(a, b)| a < off && off < b)
    }

    /// Innermost async span containing `off`.
    pub fn innermost(&self, off: usize) -> Option<(usize, usize)> {
        self.spans.iter().filter(|&&(a, b)| a < off && off < b).min_by_key(|&&(a, b)| b - a).copied()
    }
}

/// Names of fns routed with get(..)/post(..)/... or taking axum extractors.
pub fn handlers(src: &Src, fns: &[FnSig]) -> Vec<String> {
    let code = &src.code;
    let mut out: Vec<String> = Vec::new();
    for verb in ["get(", "post(", "put(", "delete(", "patch(", "head(", "options(", "any("] {
        for (i, _) in code.match_indices(verb) {
            let before_ok = i == 0 || !code.as_bytes()[i - 1].is_ascii_alphanumeric() && code.as_bytes()[i - 1] != b'_';
            if !before_ok {
                continue;
            }
            let open = i + verb.len() - 1;
            let arg = code[open + 1..close_of(code, open) - 1].trim();
            let name = arg.rsplit("::").next().unwrap_or("");
            if !name.is_empty() && name.chars().all(|c| c.is_alphanumeric() || c == '_') {
                out.push(name.to_string());
            }
        }
    }
    for f in fns {
        let extractor = ["State(", "Json(", "Path(", "Query(", "Extension(", "Form("].iter().any(|e| f.params.contains(e));
        if extractor && is_async_fn(src, f) {
            out.push(f.name.clone());
        }
    }
    out.sort();
    out.dedup();
    out
}

/// Innermost fn whose body contains `off`.
pub fn fn_at<'a>(src: &Src, fns: &'a [FnSig], off: usize) -> Option<&'a FnSig> {
    fns.iter()
        .filter(|f| body_span(src, f).is_some_and(|(a, b)| a < off && off < b))
        .min_by_key(|f| f.body.len())
}

/// End of the scope (block) that contains `off`: the first unmatched `}` after it.
pub fn scope_end(code: &str, off: usize) -> usize {
    let mut depth = 0i32;
    for (j, c) in code[off..].char_indices() {
        match c {
            '{' => depth += 1,
            '}' if depth == 0 => return off + j,
            '}' => depth -= 1,
            _ => {}
        }
    }
    code.len()
}
