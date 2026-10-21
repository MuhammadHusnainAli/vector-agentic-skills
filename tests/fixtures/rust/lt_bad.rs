//! Log-ingestion tokenizer with typical lifetime mistakes (fixture for the rust-lifetime-annotation-advisor scripts).
use std::collections::HashMap;
use std::fmt;

// LT004: borrowed field without a lifetime (E0106)
pub struct LogLine {
    pub raw: &str,
    pub level: u8,
}

// LT006: lifetime parameter never used (E0392)
pub struct Settings<'a> {
    pub name: String,
    pub retries: u32,
}

// LT008: &'static field only accepts literals
pub struct Source {
    pub label: &'static str,
    pub path: String,
}

// LT010 + LT011: three lifetimes, and a boxed callback that defaults to 'static
pub struct Pipeline<'src, 'cfg, 'out> {
    src: &'src str,
    cfg: &'cfg HashMap<String, String>,
    out: &'out mut Vec<String>,
    on_line: Box<dyn Fn(&str) -> bool>,
}

pub struct Tokenizer<'a> {
    src: &'a str,
    pos: usize,
}

impl<'a> Tokenizer<'a> {
    pub fn new(src: &'a str) -> Self {
        Self { src, pos: 0 }
    }

    // LT007: borrows the tokenizer mutably for all of 'a; a second call will not compile
    pub fn next_token(&'a mut self) -> Option<&'a str> {
        let rest = &self.src[self.pos..];
        let end = rest.find(' ').unwrap_or(rest.len());
        self.pos += end + 1;
        if end == 0 { None } else { Some(&rest[..end]) }
    }

    // LT001: &self's lifetime is assigned to the output anyway
    pub fn remaining<'b>(&'b self) -> &'b str {
        &self.src[self.pos..]
    }
}

// LT002: 'a used once in the header and never in the body
impl<'a> fmt::Display for Tokenizer<'a> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "Tokenizer at {}", self.pos)
    }
}

// LT001: single input lifetime goes to the output
pub fn first_word<'a>(line: &'a str) -> &'a str {
    line.split_whitespace().next().unwrap_or("")
}

// LT003: two input references, which one does the result borrow from? (E0106)
pub fn longer(a: &str, b: &str) -> &str {
    if a.len() >= b.len() { a } else { b }
}

// LT003: nothing to borrow from (E0106)
pub fn default_level() -> &str {
    "info"
}

// LT005: 'x declared but never used
pub fn count_fields<'x>(line: &str, sep: char) -> usize {
    line.split(sep).count()
}

// LT007: &'a mut Vec<&'a str> keeps `out` borrowed for as long as the words live
pub fn collect_words<'a>(out: &'a mut Vec<&'a str>, line: &'a str) {
    out.extend(line.split(' '));
}

// LT008: callers cannot pass a borrowed String
pub fn tag(label: &'static str, line: &str) -> String {
    format!("[{label}] {line}")
}

// LT009: T is only borrowed and printed; 'static rejects T = Wrapper<&str>
pub fn log_value<T: fmt::Debug + 'static>(value: &T) {
    eprintln!("{value:?}");
}

// LT012 (edition 2024 only): the iterator owns nothing borrowed, yet captures `line`
pub fn lengths(line: &str) -> impl Iterator<Item = usize> {
    let lens: Vec<usize> = line.split(' ').map(str::len).collect();
    lens.into_iter()
}
