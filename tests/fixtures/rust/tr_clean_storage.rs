//! Storage client written to the Rust API Guidelines. the rust-trait-design-reviewer scanners should report nothing.
//! Comments and strings mention `impl Into<X> for Y` and `Box<dyn Error>` on purpose.

use std::collections::HashMap;
use std::fmt;
use std::marker::PhantomData;
use std::path::Path;
use std::time::Duration;

pub type BoxError = Box<dyn std::error::Error + Send + Sync + 'static>;

/// Dyn-compatible: constructors and generic helpers opt out with `where Self: Sized`.
pub trait Storage: fmt::Debug + Send + Sync {
    fn open(path: &Path) -> Result<Self, StorageError>
    where
        Self: Sized;
    fn get(&self, key: &str) -> Option<Vec<u8>>;
    fn put_bytes(&mut self, key: &str, value: &[u8]);
    fn put_all<I>(&mut self, items: I)
    where
        I: IntoIterator<Item = (String, Vec<u8>)>,
        Self: Sized,
    {
        for (k, v) in items {
            self.put_bytes(&k, &v);
        }
    }
    fn box_clone(&self) -> Box<dyn Storage>;
}

impl Clone for Box<dyn Storage> {
    fn clone(&self) -> Self {
        self.box_clone()
    }
}

#[derive(Debug, Clone, Default)]
pub struct MemoryStorage {
    data: HashMap<String, Vec<u8>>,
}

impl Storage for MemoryStorage {
    fn open(_path: &Path) -> Result<Self, StorageError> {
        Ok(Self::default())
    }

    fn get(&self, key: &str) -> Option<Vec<u8>> {
        self.data.get(key).cloned()
    }

    fn put_bytes(&mut self, key: &str, value: &[u8]) {
        self.data.insert(key.to_owned(), value.to_vec());
    }

    fn box_clone(&self) -> Box<dyn Storage> {
        Box::new(self.clone())
    }
}

#[derive(Debug, Default)]
pub struct Registry {
    backends: HashMap<String, Box<dyn Storage>>,
}

impl Registry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn names(&self, filter: &[String]) -> Vec<String> {
        self.backends.keys().filter(|k| filter.contains(k)).cloned().collect()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct DocumentId(String);

impl From<String> for DocumentId {
    fn from(s: String) -> Self {
        DocumentId(s)
    }
}

impl AsRef<str> for DocumentId {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

#[derive(Debug)]
#[non_exhaustive]
pub enum StorageError {
    NotFound(DocumentId),
    Timeout(Duration),
    Io(std::io::Error),
}

impl fmt::Display for StorageError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound(id) => write!(f, "document {} not found {{", id.as_ref()),
            Self::Timeout(d) => write!(f, "timed out after {d:?}"),
            Self::Io(_) => f.write_str(r#"i/o error: "dyn Storage" { "#),
        }
    }
}

impl std::error::Error for StorageError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for StorageError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}

/// Async API with an explicit Send variant for multi-threaded runtimes (Rust 1.75+).
#[trait_variant::make(RemoteStore: Send)]
pub trait LocalRemoteStore {
    async fn fetch(&self, id: &DocumentId) -> Result<Vec<u8>, StorageError>;
}

pub fn load_config(path: &Path) -> Result<String, BoxError> {
    Ok(std::fs::read_to_string(path)?)
}

#[derive(Debug, Clone, Copy, Default)]
pub struct NoUrl;
#[derive(Debug, Clone, Copy, Default)]
pub struct HasUrl;

#[derive(Debug, Clone)]
#[must_use = "builders do nothing until .build() is called"]
pub struct ClientBuilder<S> {
    url: Option<String>,
    timeout: Duration,
    _state: PhantomData<S>,
}

impl<S> ClientBuilder<S> {
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }
}

impl ClientBuilder<NoUrl> {
    pub fn url(self, url: impl Into<String>) -> ClientBuilder<HasUrl> {
        ClientBuilder { url: Some(url.into()), timeout: self.timeout, _state: PhantomData }
    }
}

/// Extension trait on a foreign type: single impl is the point.
trait StrExt {
    fn first_char_or(&self, fallback: char) -> char;
}

impl StrExt for str {
    fn first_char_or(&self, fallback: char) -> char {
        self.chars().next().unwrap_or(fallback)
    }
}

pub fn initial(name: &str) -> char {
    name.first_char_or('?')
}

mod private {
    pub trait Sealed {}
}

pub trait Codec: private::Sealed {
    fn name(&self) -> &'static str;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct Json;

impl private::Sealed for Json {}

impl Codec for Json {
    fn name(&self) -> &'static str {
        "json"
    }
}

pub struct Pages<'a> {
    items: &'a [u8],
    size: usize,
}

impl fmt::Debug for Pages<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Pages").field("size", &self.size).finish_non_exhaustive()
    }
}

impl<'a> Iterator for Pages<'a> {
    type Item = &'a [u8];

    fn next(&mut self) -> Option<Self::Item> {
        if self.items.is_empty() {
            return None;
        }
        let (head, tail) = self.items.split_at(self.size.min(self.items.len()));
        self.items = tail;
        Some(head)
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let quote = '"';
    let brace = '{';
    println!("{quote}{brace} {}", initial("ada"));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    pub struct FakeStorage {
        calls: Vec<String>,
    }

    fn assert_dyn(_s: &dyn Storage) {}

    #[test]
    fn registry_starts_empty() {
        assert!(Registry::new().names(&[]).is_empty());
        assert_dyn(&MemoryStorage::default());
    }
}
