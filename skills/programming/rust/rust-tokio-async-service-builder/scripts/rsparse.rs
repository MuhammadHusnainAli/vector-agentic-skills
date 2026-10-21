//! Lightweight Rust source scanner shared by the tokio scripts: blanks comments and
//! string/char literals (keeping offsets and line numbers), then finds fn signatures,
//! struct/enum definitions and impl blocks. Not a full parser: it reads the shapes that
//! lifetime rules need. Not an entry point; pulled in with `mod rsparse;`.
#![allow(dead_code)]

pub struct Src {
    pub orig: String,
    /// Same length as `orig`; comments and literal contents replaced by spaces.
    pub code: String,
    line_starts: Vec<usize>,
}

pub struct FnSig {
    pub off: usize,
    pub name: String,
    pub generics: String,
    pub params: String,
    pub ret: String,
    pub where_: String,
    pub body: String,
    pub impl_idx: Option<usize>,
}

pub struct TypeDef {
    pub off: usize,
    pub kind: &'static str,
    pub name: String,
    pub generics: String,
    pub body: String,
}

pub struct ImplBlock {
    pub off: usize,
    pub generics: String,
    /// Text between the generics and `{`, e.g. `fmt::Display for Token<'a>`.
    pub header: String,
    pub where_: String,
    pub body: String,
    span: (usize, usize),
}

impl Src {
    pub fn new(orig: String) -> Src {
        let code = blank(&orig);
        let mut line_starts = vec![0];
        line_starts.extend(orig.match_indices('\n').map(|(i, _)| i + 1));
        Src { orig, code, line_starts }
    }

    pub fn line_of(&self, off: usize) -> usize {
        self.line_starts.partition_point(|&s| s <= off)
    }

    /// `// noqa: LT008` (or bare `// noqa`) on the item's line silences it.
    pub fn noqa(&self, line: usize, id: &str) -> bool {
        let start = self.line_starts[line - 1];
        let end = self.line_starts.get(line).copied().unwrap_or(self.orig.len());
        match self.orig[start..end].find("// noqa") {
            Some(i) => {
                let rest = &self.orig[start + i + 7..end];
                !rest.trim_start().starts_with(':') || rest.contains(id)
            }
            None => false,
        }
    }
}

/// Replace comments and the contents of string/char literals with spaces.
fn blank(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = b.to_vec();
    let mut i = 0;
    let wipe = |out: &mut Vec<u8>, from: usize, to: usize| {
        for c in &mut out[from..to.min(b.len())] {
            if *c != b'\n' {
                *c = b' ';
            }
        }
    };
    while i < b.len() {
        match b[i] {
            b'/' if b.get(i + 1) == Some(&b'/') => {
                let end = s[i..].find('\n').map_or(b.len(), |n| i + n);
                wipe(&mut out, i, end);
                i = end;
            }
            b'/' if b.get(i + 1) == Some(&b'*') => {
                let (mut depth, mut j) = (1, i + 2);
                while j < b.len() && depth > 0 {
                    if b[j] == b'/' && b.get(j + 1) == Some(&b'*') { depth += 1; j += 1; }
                    else if b[j] == b'*' && b.get(j + 1) == Some(&b'/') { depth -= 1; j += 1; }
                    j += 1;
                }
                wipe(&mut out, i, j);
                i = j;
            }
            b'r' if (b.get(i + 1) == Some(&b'"') || b.get(i + 1) == Some(&b'#')) && !ident_before(b, i) => {
                let hashes = b[i + 1..].iter().take_while(|&&c| c == b'#').count();
                if b.get(i + 1 + hashes) != Some(&b'"') { i += 1; continue; }
                let close = format!("\"{}", "#".repeat(hashes));
                let start = i + 2 + hashes;
                let end = s[start..].find(&close).map_or(b.len(), |n| start + n);
                wipe(&mut out, start, end);
                i = end + close.len();
            }
            b'"' => {
                let mut j = i + 1;
                while j < b.len() && b[j] != b'"' {
                    j += if b[j] == b'\\' { 2 } else { 1 };
                }
                wipe(&mut out, i + 1, j);
                i = j + 1;
            }
            b'\'' => {
                // char literal ('x', '\n', '\u{1F600}') vs lifetime ('a): a char closes with a quote.
                let len = if b.get(i + 1) == Some(&b'\\') {
                    s[i + 2..].find('\'').map(|n| n + 2)
                } else {
                    s[i + 1..].chars().next().map(char::len_utf8).filter(|&w| b.get(i + 1 + w) == Some(&b'\''))
                };
                match len {
                    Some(n) => { wipe(&mut out, i + 1, i + 1 + n); i += n + 2; }
                    None => i += 1,
                }
            }
            _ => i += 1,
        }
    }
    String::from_utf8(out).unwrap_or_default()
}

fn ident_before(b: &[u8], i: usize) -> bool {
    i > 0 && (b[i - 1].is_ascii_alphanumeric() || b[i - 1] == b'_')
}

fn is_ident(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}

/// Offsets of `word` as a whole word in `s`.
pub fn word_positions(s: &str, word: &str) -> Vec<usize> {
    let b = s.as_bytes();
    s.match_indices(word)
        .map(|(i, _)| i)
        .filter(|&i| !ident_before(b, i) && !b.get(i + word.len()).is_some_and(|&c| is_ident(c)))
        .collect()
}

/// Index just past the bracket that closes the one at `open` (`<`, `(`, `{`, `[`).
/// `->` is not treated as a closing angle bracket.
pub fn close_of(s: &str, open: usize) -> usize {
    let b = s.as_bytes();
    let (o, c) = match b[open] { b'<' => (b'<', b'>'), b'(' => (b'(', b')'), b'[' => (b'[', b']'), _ => (b'{', b'}') };
    let mut depth = 0i32;
    for (j, &ch) in b.iter().enumerate().skip(open) {
        if ch == o {
            depth += 1;
        } else if ch == c && !(c == b'>' && j > 0 && b[j - 1] == b'-') {
            depth -= 1;
            if depth == 0 {
                return j + 1;
            }
        }
    }
    b.len()
}

fn skip_ws(s: &str, mut i: usize) -> usize {
    let b = s.as_bytes();
    while i < b.len() && b[i].is_ascii_whitespace() { i += 1; }
    i
}

fn ident_at(s: &str, i: usize) -> (String, usize) {
    let b = s.as_bytes();
    let end = (i..b.len()).find(|&j| !is_ident(b[j])).unwrap_or(b.len());
    (s[i..end].to_string(), end)
}

/// Optional `<...>` at `i`: (contents, index after it).
fn generics_at(s: &str, i: usize) -> (String, usize) {
    if s.as_bytes().get(i) == Some(&b'<') {
        let end = close_of(s, i);
        (s[i + 1..end - 1].to_string(), end)
    } else {
        (String::new(), i)
    }
}

/// Position of the first top-level `{` or `;` at or after `i` (and of `where`, if any, before it).
fn header_end(s: &str, i: usize) -> (usize, Option<usize>) {
    let b = s.as_bytes();
    let mut depth = 0i32;
    let mut where_at = None;
    let mut j = i;
    while j < b.len() {
        match b[j] {
            b'(' | b'[' | b'<' => depth += 1,
            b')' | b']' => depth -= 1,
            b'>' if j == 0 || b[j - 1] != b'-' => depth -= 1,
            b'{' | b';' if depth <= 0 => return (j, where_at),
            b'w' if depth <= 0 && where_at.is_none() && s[j..].starts_with("where") && !ident_before(b, j)
                && !b.get(j + 5).is_some_and(|&c| is_ident(c)) => where_at = Some(j),
            _ => {}
        }
        j += 1;
    }
    (b.len(), where_at)
}

/// Is `impl` at `i` an item (`impl<T> X for Y {`) rather than `impl Trait` in a type?
fn item_position(code: &str, i: usize) -> bool {
    let before = code[..i].trim_end();
    before.is_empty()
        || before.ends_with(['}', ';', '{', ']'])
        || before.ends_with("unsafe")
        || before.ends_with("default")
}

pub fn items(src: &Src) -> (Vec<FnSig>, Vec<TypeDef>, Vec<ImplBlock>) {
    let code = &src.code;
    let mut impls = Vec::new();
    for i in word_positions(code, "impl") {
        if !item_position(code, i) { continue; }
        let (generics, after) = generics_at(code, skip_ws(code, i + 4));
        let (end, where_at) = header_end(code, after);
        if code.as_bytes().get(end) != Some(&b'{') { continue; }
        let close = close_of(code, end);
        impls.push(ImplBlock {
            off: i,
            generics,
            header: code[after..where_at.unwrap_or(end)].trim().to_string(),
            where_: where_at.map_or(String::new(), |w| code[w + 5..end].trim().to_string()),
            body: code[end + 1..close - 1].to_string(),
            span: (end, close),
        });
    }

    let mut fns = Vec::new();
    for i in word_positions(code, "fn") {
        let name_at = skip_ws(code, i + 2);
        let (name, after_name) = ident_at(code, name_at);
        if name.is_empty() { continue; } // `fn(` pointer type
        let (generics, after) = generics_at(code, skip_ws(code, after_name));
        let p = skip_ws(code, after);
        if code.as_bytes().get(p) != Some(&b'(') { continue; }
        let pend = close_of(code, p);
        let (end, where_at) = header_end(code, pend);
        let sig_end = where_at.unwrap_or(end);
        let between = code[pend..sig_end].trim();
        let ret = between.strip_prefix("->").map_or(String::new(), |r| r.trim().to_string());
        let body = if code.as_bytes().get(end) == Some(&b'{') {
            code[end + 1..close_of(code, end) - 1].to_string()
        } else {
            String::new()
        };
        fns.push(FnSig {
            off: i,
            name,
            generics,
            params: code[p + 1..pend - 1].to_string(),
            ret,
            where_: where_at.map_or(String::new(), |w| code[w + 5..end].trim().to_string()),
            body,
            impl_idx: impls.iter().position(|b: &ImplBlock| b.span.0 < i && i < b.span.1),
        });
    }

    let mut types = Vec::new();
    for kind in ["struct", "enum", "union"] {
        for i in word_positions(code, kind) {
            let (name, after_name) = ident_at(code, skip_ws(code, i + kind.len()));
            if name.is_empty() { continue; }
            let (generics, after) = generics_at(code, skip_ws(code, after_name));
            let j = skip_ws(code, after);
            let body = match code.as_bytes().get(j) {
                Some(b'(') => code[j + 1..close_of(code, j) - 1].to_string(),
                _ => {
                    let (end, _) = header_end(code, j);
                    if code.as_bytes().get(end) == Some(&b'{') { code[end + 1..close_of(code, end) - 1].to_string() } else { String::new() }
                }
            };
            let kind = match kind { "struct" => "struct", "enum" => "enum", _ => "union" };
            types.push(TypeDef { off: i, kind, name, generics, body });
        }
    }
    types.sort_by_key(|t| t.off);
    (fns, types, impls)
}

/// Split at top-level commas (ignoring commas nested in <>, (), [], {}).
pub fn split_top(s: &str) -> Vec<String> {
    let b = s.as_bytes();
    let (mut depth, mut start, mut out) = (0i32, 0, Vec::new());
    for (j, &c) in b.iter().enumerate() {
        match c {
            b'<' | b'(' | b'[' | b'{' => depth += 1,
            b')' | b']' | b'}' => depth -= 1,
            b'>' if j == 0 || b[j - 1] != b'-' => depth -= 1,
            b',' if depth == 0 => { out.push(s[start..j].trim().to_string()); start = j + 1; }
            _ => {}
        }
    }
    let last = s[start..].trim();
    if !last.is_empty() { out.push(last.to_string()); }
    out
}

/// Every lifetime token (`'a`, `'_`, `'static`) in `s`, in order.
pub fn lifetimes_in(s: &str) -> Vec<String> {
    let b = s.as_bytes();
    let mut out = Vec::new();
    for (i, _) in s.match_indices('\'') {
        let (name, _) = ident_at(s, i + 1);
        if !name.is_empty() && !ident_before(b, i) {
            out.push(format!("'{name}"));
        }
    }
    out
}

/// Lifetime parameters declared in a generics list: `'a, 'b: 'a, T` -> ["'a", "'b"].
pub fn declared_lifetimes(generics: &str) -> Vec<String> {
    split_top(generics)
        .iter()
        .filter(|p| p.starts_with('\''))
        .map(|p| p.split(':').next().unwrap_or("").trim().to_string())
        .collect()
}

pub fn count_lifetime(s: &str, lt: &str) -> usize {
    lifetimes_in(s).iter().filter(|l| *l == lt).count()
}

/// Blank out closure-trait sugar `Fn(..) -> T` / `fn(..) -> T`, whose references are
/// higher-ranked and never need a named lifetime. Keeps offsets.
pub fn strip_fn_sugar(s: &str) -> String {
    let mut out = s.to_string();
    for kw in ["FnOnce", "FnMut", "Fn", "fn"] {
        for i in word_positions(&out.clone(), kw) {
            let p = skip_ws(&out, i + kw.len());
            if out.as_bytes().get(p) != Some(&b'(') { continue; }
            let mut end = close_of(&out, p);
            let rest = &out[end..];
            if rest.trim_start().starts_with("->") {
                // the return type runs to the next top-level `,`, `+`, `>` or `)`
                let r = end + rest.find("->").unwrap() + 2;
                let b = out.as_bytes();
                let mut depth = 0i32;
                end = b.len();
                for (j, &c) in b.iter().enumerate().skip(r) {
                    match c {
                        b'<' | b'(' | b'[' => depth += 1,
                        b'>' | b')' | b']' | b',' | b'+' if depth == 0 => { end = j; break; }
                        b'>' | b')' | b']' => depth -= 1,
                        _ => {}
                    }
                }
            }
            let blanked: String = out[p..end].bytes().map(|c| if c == b'\n' { '\n' } else { ' ' }).collect();
            out.replace_range(p..end, &blanked);
        }
    }
    out
}

/// Number of `&` references without a written lifetime (`&T`, `&mut T`, but not `&'a T`).
pub fn elided_refs(s: &str) -> usize {
    let b = s.as_bytes();
    (0..b.len())
        .filter(|&i| b[i] == b'&' && b.get(i + 1) != Some(&b'&') && (i == 0 || b[i - 1] != b'&'))
        .filter(|&i| b.get(skip_ws(s, i + 1)) != Some(&b'\''))
        .count()
}

/// Collapse whitespace runs for one-line display.
pub fn one_line(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

// ---------------------------------------------------------------- trait-review additions

pub struct TraitDef {
    pub off: usize,
    pub name: String,
    pub generics: String,
    /// Supertrait list after `:` (may be empty).
    pub supers: String,
    pub body: String,
    pub span: (usize, usize),
}

pub fn traits(src: &Src) -> Vec<TraitDef> {
    let code = &src.code;
    let mut out = Vec::new();
    for i in word_positions(code, "trait") {
        let (name, after_name) = ident_at(code, skip_ws(code, i + 5));
        if name.is_empty() { continue; }
        let (generics, after) = generics_at(code, skip_ws(code, after_name));
        let (end, where_at) = header_end(code, after);
        if code.as_bytes().get(end) != Some(&b'{') { continue; } // trait alias or parse miss
        let head = code[after..where_at.unwrap_or(end)].trim();
        let close = close_of(code, end);
        out.push(TraitDef {
            off: i,
            name,
            generics,
            supers: head.strip_prefix(':').unwrap_or("").trim().to_string(),
            body: code[end + 1..close - 1].to_string(),
            span: (end, close),
        });
    }
    out
}

impl ImplBlock {
    /// (`Some(trait path)` for `impl Trait for Type`, self type).
    pub fn trait_and_self(&self) -> (Option<String>, String) {
        let h = &self.header;
        let b = h.as_bytes();
        let mut depth = 0i32;
        for (j, &c) in b.iter().enumerate() {
            match c {
                b'<' | b'(' | b'[' => depth += 1,
                b'>' if j == 0 || b[j - 1] != b'-' => depth -= 1,
                b')' | b']' => depth -= 1,
                b'f' if depth == 0 && h[j..].starts_with("for ") && j > 0 && b[j - 1] == b' ' => {
                    return (Some(h[..j].trim().to_string()), h[j + 4..].trim().to_string());
                }
                _ => {}
            }
        }
        (None, h.trim().to_string())
    }

    pub fn contains(&self, off: usize) -> bool {
        self.span.0 < off && off < self.span.1
    }
}

/// Last path segment without generics: `std::fmt::Display` -> `Display`, `Vec<T>` -> `Vec`.
pub fn base_name(path: &str) -> String {
    let p = path.trim().trim_start_matches('&').trim_start_matches("mut ").trim();
    let p = p.split('<').next().unwrap_or("");
    p.rsplit("::").next().unwrap_or("").trim().to_string()
}

/// Attribute text (`#[...]` blocks) directly above the item starting at `off`, skipping
/// visibility and qualifiers. Doc comments are already blanked.
pub fn attrs_before(code: &str, off: usize) -> String {
    let mut end = off;
    let mut out = String::new();
    loop {
        let before = code[..end].trim_end();
        let stripped = ["pub(crate)", "pub(super)", "pub", "unsafe", "async", "const", "default", "auto"]
            .iter()
            .find_map(|q| before.strip_suffix(q).filter(|r| r.is_empty() || r.ends_with(|c: char| !c.is_alphanumeric() && c != '_')));
        if let Some(rest) = stripped {
            end = rest.len();
            continue;
        }
        if before.ends_with(']') {
            if let Some(start) = before.rfind("#[") {
                out.insert_str(0, &before[start..]);
                end = start;
                continue;
            }
        }
        return out;
    }
}

/// Is the item at `off` declared plain `pub` (not `pub(crate)`)?
pub fn is_pub(code: &str, off: usize) -> bool {
    let before = code[..off].trim_end();
    let before = before.strip_suffix("unsafe").map_or(before, str::trim_end);
    before.ends_with("pub") && !before[..before.len() - 3].ends_with(|c: char| c.is_alphanumeric() || c == '_')
}

/// Spans of `#[cfg(test)] mod name { ... }` bodies.
pub fn test_spans(code: &str) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    for (i, _) in code.match_indices("#[cfg(test)]") {
        let rest = &code[i..];
        if let Some(m) = word_positions(rest, "mod").first() {
            if let Some(open) = rest[*m..].find('{') {
                let at = i + m + open;
                out.push((at, close_of(code, at)));
            }
        }
    }
    out
}

/// Names that appear as `dyn Name` anywhere in the code.
pub fn dyn_uses(code: &str) -> Vec<String> {
    word_positions(code, "dyn")
        .into_iter()
        .map(|i| {
            let start = skip_ws(code, i + 3);
            let end = code[start..].find(|c: char| !(c.is_alphanumeric() || c == '_' || c == ':')).map_or(code.len(), |n| start + n);
            base_name(&code[start..end])
        })
        .filter(|n| !n.is_empty())
        .collect()
}
