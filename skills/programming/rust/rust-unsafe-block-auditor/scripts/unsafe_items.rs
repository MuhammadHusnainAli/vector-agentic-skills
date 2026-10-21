//! Find every `unsafe` item (block, fn, impl, trait, extern block) and whether it carries
//! its justification: a `// SAFETY:` comment for blocks and impls, a `# Safety` doc section
//! for unsafe fns and traits. Shared by the unsafe-audit scripts; pulled in with
//! `mod unsafe_items;` (needs `mod rsparse;`).
#![allow(dead_code)]

use crate::rsparse::{close_of, word_positions, FnSig, Src};

#[derive(Clone)]
pub struct UnsafeItem {
    pub off: usize,
    pub end: usize,
    /// "block", "fn", "impl", "trait" or "extern".
    pub kind: &'static str,
    /// fn / impl / trait name, or for blocks the enclosing fn.
    pub name: String,
    /// SAFETY comment (blocks, impls) or `# Safety` doc (fns, traits).
    pub documented: bool,
    pub body: String,
}

/// Lines of the original text, 1-based access.
fn line_text(src: &Src, line: usize) -> &str {
    src.orig.lines().nth(line.saturating_sub(1)).unwrap_or("")
}

fn is_comment(l: &str) -> bool {
    let t = l.trim_start();
    t.starts_with("//") || t.starts_with("/*") || t.starts_with('*')
}

/// A `// SAFETY:` comment directly above the statement containing `off`, on its line,
/// or as the first line inside a block starting at `off`.
pub fn has_safety_comment(src: &Src, off: usize) -> bool {
    let says = |l: &str| l.to_ascii_uppercase().contains("SAFETY:");
    // Statement start: after the previous `;`, `{` or `}` (multi-line expressions).
    let stmt = src.code[..off].rfind([';', '{', '}']).map_or(0, |i| i + 1);
    let stmt = stmt + (src.code[stmt..off].len() - src.code[stmt..off].trim_start().len());
    for start in [src.line_of(off), src.line_of(stmt)] {
        if says(&line_text(src, start)[..]) && line_text(src, start).contains("//") {
            return true;
        }
        let mut l = start - 1;
        while l >= 1 {
            let text = line_text(src, l);
            if is_comment(text) {
                if says(text) {
                    return true;
                }
            } else if !text.trim_start().starts_with("#[") {
                break; // attributes may sit between the comment and the item
            }
            l -= 1;
        }
    }
    // `unsafe { // SAFETY: ..` or a comment on the first line inside the block
    let after = &src.orig[off..];
    after.find('{').is_some_and(|b| after[b..].lines().take(2).any(|l| says(l) && l.contains("//")))
}

/// A `# Safety` heading in the doc comment above the item at `off` (attributes skipped).
pub fn has_safety_doc(src: &Src, off: usize) -> bool {
    let mut l = src.line_of(off) - 1;
    while l >= 1 {
        let t = line_text(src, l).trim_start();
        if t.starts_with("///") || t.starts_with("//!") {
            if t.contains("# Safety") {
                return true;
            }
        } else if !t.starts_with("#[") && !t.starts_with("//") {
            return false;
        }
        l -= 1;
    }
    false
}

/// Every unsafe item in the file, in source order.
pub fn unsafe_items(src: &Src, fns: &[FnSig]) -> Vec<UnsafeItem> {
    let code = &src.code;
    let enclosing = |off: usize| {
        fns.iter()
            .filter(|f| code[f.off..].find('{').is_some_and(|b| f.off + b < off && off <= f.off + b + f.body.len() + 1))
            .min_by_key(|f| f.body.len())
            .map_or("<top level>".to_string(), |f| f.name.clone())
    };
    let mut out = Vec::new();
    for pos in word_positions(code, "unsafe") {
        let rest = &code[pos + 6..];
        let next = rest.trim_start();
        let at = pos + 6 + (rest.len() - next.len());
        // After `extern`, skip the ABI string (`"C"`, blanked to `" "`) to see `fn` or `{`.
        let after_extern = next.strip_prefix("extern").map(|r| {
            let r = r.trim_start();
            let r = if r.starts_with('"') { r[1..].find('"').map_or(r, |q| &r[q + 2..]) } else { r };
            r.trim_start()
        });
        let item = if next.starts_with('{') {
            let end = close_of(code, at);
            Some(UnsafeItem { off: pos, end, kind: "block", name: enclosing(pos), documented: has_safety_comment(src, pos),
                              body: code[at + 1..end - 1].to_string() })
        } else if next.starts_with("fn") || after_extern.is_some_and(|r| r.starts_with("fn")) {
            // `unsafe fn` / `unsafe extern "C" fn`
            fns.iter().find(|f| f.off > pos && f.off < pos + 40).map(|f| {
                let start = code[f.off..].find(['{', ';']).map_or(f.off, |n| f.off + n);
                let end = if code.as_bytes().get(start) == Some(&b'{') { close_of(code, start) } else { start + 1 };
                UnsafeItem { off: pos, end, kind: "fn", name: f.name.clone(), documented: has_safety_doc(src, pos), body: f.body.clone() }
            })
        } else if after_extern.is_some_and(|r| r.starts_with('{')) {
            let open = at + next.find('{').unwrap_or(0);
            let end = close_of(code, open);
            Some(UnsafeItem { off: pos, end, kind: "extern", name: "extern block".into(), documented: true, body: code[open + 1..end - 1].to_string() })
        } else if next.starts_with("impl") || next.starts_with("trait") {
            let kind = if next.starts_with("impl") { "impl" } else { "trait" };
            let open = at + next.find(['{', ';']).unwrap_or(0);
            let end = if code.as_bytes()[open] == b'{' { close_of(code, open) } else { open + 1 };
            let header = crate::rsparse::one_line(&code[at..open]);
            let documented = if kind == "impl" { has_safety_comment(src, pos) } else { has_safety_doc(src, pos) };
            Some(UnsafeItem { off: pos, end, kind, name: header, documented, body: code[open..end].to_string() })
        } else {
            None // `#[unsafe(no_mangle)]` and other attributes
        };
        out.extend(item);
    }
    out
}

/// Is `off` inside an unsafe block or unsafe fn that already carries its justification?
pub fn justified(items: &[UnsafeItem], off: usize) -> bool {
    items.iter().any(|i| (i.kind == "block" || i.kind == "fn") && i.documented && i.off <= off && off < i.end)
}

/// Is `off` inside any unsafe block or unsafe fn?
pub fn in_unsafe(items: &[UnsafeItem], off: usize) -> bool {
    items.iter().any(|i| (i.kind == "block" || i.kind == "fn") && i.off <= off && off < i.end)
}
