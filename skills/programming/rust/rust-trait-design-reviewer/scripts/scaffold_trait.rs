//! Print a ready-to-adapt template for a common trait design. Every template compiles on
//! stable Rust (std only) and passes this skill's reviewers clean.
//!
//! Build: rustc -O --edition 2021 scripts/scaffold_trait.rs -o /tmp/scaffold_trait
//! Usage: scaffold_trait <KIND> [--name Name]    KIND: sealed | extension | typestate |
//!        newtype | dyn-compatible | async-send       scaffold_trait --list

use std::process::exit;

const USAGE: &str = "usage: scaffold_trait <KIND> [--name Name]
       scaffold_trait --list

Print a template for a common trait design, with Name substituted (CamelCase):
  sealed          public trait only this crate can implement (private supertrait)
  extension       extension trait adding methods to a foreign type (str)
  typestate       builder whose build() exists only after required fields are set
  newtype         validated newtype with TryFrom, FromStr, AsRef, Display and an error type
  dyn-compatible  trait usable as Box<dyn Name>: Sized-gated constructors, box_clone
  async-send      async trait whose futures are Send (RPITIT, Rust 1.75+), no macros

Exit: 0 printed, 2 unknown kind or invalid name.";

const SEALED: &str = r#"mod private {
    pub trait Sealed {}
}

/// Implemented only inside this crate (private supertrait), so adding methods later
/// is not a breaking change for downstream users.
pub trait {N}: private::Sealed {
    fn name(&self) -> &'static str;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct Default{N};

impl private::Sealed for Default{N} {}

impl {N} for Default{N} {
    fn name(&self) -> &'static str {
        "default"
    }
}
"#;

const EXTENSION: &str = r#"/// Extension methods for `str`. Callers `use` this trait to get the methods.
pub trait {N} {
    fn first_word(&self) -> &str;
    fn is_blank(&self) -> bool;
}

impl {N} for str {
    fn first_word(&self) -> &str {
        self.split_whitespace().next().unwrap_or("")
    }

    fn is_blank(&self) -> bool {
        self.trim().is_empty()
    }
}
"#;

const TYPESTATE: &str = r#"use std::marker::PhantomData;
use std::time::Duration;

#[derive(Debug, Clone, Copy, Default)]
pub struct Missing;
#[derive(Debug, Clone, Copy, Default)]
pub struct Present;

/// `build()` only exists once `url()` was called: forgetting it is a compile error.
#[derive(Debug, Clone)]
#[must_use = "builders do nothing until .build() is called"]
pub struct {N}Builder<U> {
    url: Option<String>,
    timeout: Duration,
    _url: PhantomData<U>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct {N} {
    pub url: String,
    pub timeout: Duration,
}

impl {N} {
    pub fn builder() -> {N}Builder<Missing> {
        {N}Builder { url: None, timeout: Duration::from_secs(30), _url: PhantomData }
    }
}

impl<U> {N}Builder<U> {
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }
}

impl {N}Builder<Missing> {
    pub fn url(self, url: impl Into<String>) -> {N}Builder<Present> {
        {N}Builder { url: Some(url.into()), timeout: self.timeout, _url: PhantomData }
    }
}

impl {N}Builder<Present> {
    pub fn build(self) -> {N} {
        {N} { url: self.url.unwrap_or_default(), timeout: self.timeout }
    }
}
"#;

const NEWTYPE: &str = r#"use std::fmt;
use std::str::FromStr;

/// A validated, non-empty identifier. Build it with `{N}::try_from(s)` or `s.parse()`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct {N}(String);

#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum {N}Error {
    Empty,
}

impl fmt::Display for {N}Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Empty => f.write_str("identifier must not be empty"),
        }
    }
}

impl std::error::Error for {N}Error {}

impl TryFrom<String> for {N} {
    type Error = {N}Error;

    fn try_from(s: String) -> Result<Self, Self::Error> {
        if s.trim().is_empty() { Err({N}Error::Empty) } else { Ok(Self(s)) }
    }
}

impl FromStr for {N} {
    type Err = {N}Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::try_from(s.to_owned())
    }
}

impl AsRef<str> for {N} {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for {N} {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl From<{N}> for String {
    fn from(v: {N}) -> String {
        v.0
    }
}
"#;

const DYN_COMPATIBLE: &str = r#"use std::collections::HashMap;
use std::fmt;

/// Usable as `Box<dyn {N}>`: the constructor and the generic helper opt out of the
/// vtable with `where Self: Sized`, and cloning goes through `box_clone`.
pub trait {N}: fmt::Debug + Send + Sync {
    fn create() -> Self
    where
        Self: Sized;
    fn get(&self, key: &str) -> Option<Vec<u8>>;
    fn put(&mut self, key: &str, value: &[u8]);
    fn put_all<I>(&mut self, items: I)
    where
        I: IntoIterator<Item = (String, Vec<u8>)>,
        Self: Sized,
    {
        for (k, v) in items {
            self.put(&k, &v);
        }
    }
    fn box_clone(&self) -> Box<dyn {N}>;
}

impl Clone for Box<dyn {N}> {
    fn clone(&self) -> Self {
        self.box_clone()
    }
}

#[derive(Debug, Clone, Default)]
pub struct Memory{N} {
    data: HashMap<String, Vec<u8>>,
}

impl {N} for Memory{N} {
    fn create() -> Self {
        Self::default()
    }

    fn get(&self, key: &str) -> Option<Vec<u8>> {
        self.data.get(key).cloned()
    }

    fn put(&mut self, key: &str, value: &[u8]) {
        self.data.insert(key.to_owned(), value.to_vec());
    }

    fn box_clone(&self) -> Box<dyn {N}> {
        Box::new(self.clone())
    }
}

pub fn put_everywhere(backends: &mut [Box<dyn {N}>], key: &str, value: &[u8]) {
    for b in backends.iter_mut() {
        b.put(key, value);
    }
}
"#;

const ASYNC_SEND: &str = r#"use std::collections::HashMap;
use std::future::Future;

/// Async trait whose futures are always Send, so callers can `tokio::spawn` them
/// (Rust 1.75+, no macros). Implementors may still write `async fn` in their impls.
/// Alternative: `#[trait_variant::make(Send{N}: Send)]` on a trait with `async fn`.
pub trait {N}: Send + Sync {
    fn fetch(&self, key: &str) -> impl Future<Output = Option<Vec<u8>>> + Send;
}

#[derive(Debug, Default)]
pub struct Memory{N} {
    data: HashMap<String, Vec<u8>>,
}

impl {N} for Memory{N} {
    async fn fetch(&self, key: &str) -> Option<Vec<u8>> {
        self.data.get(key).cloned()
    }
}
"#;

const KINDS: &[(&str, &str)] = &[
    ("sealed", SEALED),
    ("extension", EXTENSION),
    ("typestate", TYPESTATE),
    ("newtype", NEWTYPE),
    ("dyn-compatible", DYN_COMPATIBLE),
    ("async-send", ASYNC_SEND),
];

fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    exit(2);
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        exit(if args.is_empty() { 2 } else { 0 });
    }
    if args.iter().any(|a| a == "--list") {
        KINDS.iter().for_each(|(k, _)| println!("{k}"));
        return;
    }
    let mut name = None;
    let mut kind = None;
    let mut it = args.iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--name" => name = Some(it.next().unwrap_or_else(|| die("--name needs a value")).clone()),
            f if f.starts_with("--") => die(&format!("unknown option {f}")),
            k => kind = Some(k.to_string()),
        }
    }
    let kind = kind.unwrap_or_else(|| die("missing KIND; see --list"));
    let Some((_, template)) = KINDS.iter().find(|(k, _)| *k == kind) else {
        die(&format!("unknown kind '{kind}'; choose one of: {}", KINDS.iter().map(|k| k.0).collect::<Vec<_>>().join(", ")))
    };
    let default = match kind.as_str() {
        "sealed" => "Codec", "extension" => "StrExt", "typestate" => "Client", "newtype" => "UserId",
        "dyn-compatible" => "Storage", _ => "RemoteStore",
    };
    let name = name.unwrap_or_else(|| default.to_string());
    let valid = name.chars().next().is_some_and(|c| c.is_ascii_uppercase()) && name.chars().all(|c| c.is_ascii_alphanumeric());
    if !valid {
        die(&format!("--name must be a CamelCase identifier, got '{name}'"));
    }
    print!("{}", template.replace("{N}", &name));
}
