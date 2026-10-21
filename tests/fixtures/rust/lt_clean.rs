//! Idiomatic lifetimes: every annotation here is required or deliberate (fixture for the rust-lifetime-annotation-advisor scripts).
use std::borrow::Cow;
use std::collections::HashMap;
use std::fmt;
use std::marker::PhantomData;
use std::sync::Arc;
use std::thread;

/// Borrows the input text; tokens point into it, not into the parser.
pub struct Parser<'a> {
    src: &'a str,
    pos: usize,
}

impl<'a> Parser<'a> {
    pub fn new(src: &'a str) -> Self {
        Self { src, pos: 0 }
    }

    /// Short `&mut self` borrow, result tied to the source text ('a), not to the parser.
    pub fn next_token(&mut self) -> Option<&'a str> {
        let rest = self.src[self.pos..].trim_start();
        if rest.is_empty() {
            return None;
        }
        let start = self.src.len() - rest.len();
        let end = rest.find(char::is_whitespace).unwrap_or(rest.len());
        self.pos = start + end;
        Some(&rest[..end])
    }

    pub fn remaining(&self) -> &str {
        &self.src[self.pos..]
    }
}

impl fmt::Display for Parser<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Parser at byte {}", self.pos)
    }
}

/// Iterator yielding sub-slices of the borrowed input.
pub struct Words<'a> {
    rest: &'a str,
}

impl<'a> Iterator for Words<'a> {
    type Item = &'a str;

    fn next(&mut self) -> Option<&'a str> {
        let s = self.rest.trim_start();
        if s.is_empty() {
            return None;
        }
        let end = s.find(char::is_whitespace).unwrap_or(s.len());
        let (word, rest) = s.split_at(end);
        self.rest = rest;
        Some(word)
    }
}

/// Owned configuration: no lifetime parameter anywhere, cheap to clone and share.
#[derive(Clone, Debug)]
pub struct Config {
    pub name: Arc<str>,
    pub labels: HashMap<String, String>,
}

/// A filter that may borrow from the caller's data: object lifetime is spelled out.
pub struct Filter<'a> {
    pattern: &'a str,
    predicate: Box<dyn Fn(&str) -> bool + 'a>,
}

impl<'a> Filter<'a> {
    pub fn new(pattern: &'a str) -> Self {
        Self { pattern, predicate: Box::new(move |line: &str| line.contains(pattern)) }
    }

    pub fn matches(&self, line: &str) -> bool {
        (self.predicate)(line) && !self.pattern.is_empty()
    }
}

/// Typed handle into an arena: borrows nothing, but remembers what it indexes.
pub struct Handle<T> {
    index: usize,
    _marker: PhantomData<fn() -> T>,
}

/// GAT lending iterator (Rust 1.65+): each item borrows the iterator itself.
pub trait LendingIterator {
    type Item<'a>
    where
        Self: 'a;

    fn next<'a>(&'a mut self) -> Option<Self::Item<'a>>;
}

/// Result may come from either input: one shared lifetime is the honest signature.
pub fn longest<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() >= b.len() { a } else { b }
}

/// Result only ever borrows from `text`; `sep` has its own elided lifetime.
pub fn before<'a>(text: &'a str, sep: &str) -> &'a str {
    text.split(sep).next().unwrap_or(text)
}

/// Borrow when possible, allocate only when the input must change.
pub fn normalize(input: &str) -> Cow<'_, str> {
    if input.contains('\t') {
        Cow::Owned(input.replace('\t', "    "))
    } else {
        Cow::Borrowed(input)
    }
}

/// Returned iterator borrows `xs`, and says so.
pub fn evens(xs: &[u32]) -> impl Iterator<Item = u32> + '_ {
    xs.iter().copied().filter(|x| x % 2 == 0)
}

/// Higher-ranked bound: the closure must accept a borrow of any lifetime.
pub fn total_len<F>(items: &[String], f: F) -> usize
where
    F: for<'s> Fn(&'s str) -> usize,
{
    items.iter().map(|s| f(s.as_str())).sum()
}

/// 'static is required here: the value moves to another thread.
pub fn run_in_background<T: Send + fmt::Debug + 'static>(value: T) -> thread::JoinHandle<()> {
    thread::spawn(move || println!("{value:?}"))
}

pub fn handle_index<T>(h: &Handle<T>) -> usize {
    h.index
}
