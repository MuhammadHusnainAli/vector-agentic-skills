//! Storage client for a document service. Deliberately full of trait-design issues
//! for the rust-trait-design-reviewer scanners. Not meant to compile cleanly.

use std::collections::HashMap;
use std::error::Error;
use std::hash::{Hash, Hasher};
use std::ops::Deref;
use std::path::PathBuf;
use std::time::Duration;

/// A key-value backend. Used as `Box<dyn Storage>` below, but not dyn compatible.
pub trait Storage: Send + Sync {
    fn open(path: &str) -> Self;
    fn get(&self, key: &str) -> Option<Vec<u8>>;
    fn put<V: serde::Serialize>(&mut self, key: &str, value: &V);
    fn try_clone(&self) -> Self;
    fn delete(&mut self, key: &str) -> bool;
}

pub struct Registry {
    backends: HashMap<String, Box<dyn Storage>>,
}

impl Registry {
    pub fn new() -> Self {
        Registry { backends: HashMap::new() }
    }

    pub fn names(&self, filter: &Vec<String>) -> Vec<String> {
        self.backends.keys().filter(|k| filter.contains(k)).cloned().collect()
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DocumentId(pub String);

#[derive(Debug, Clone)]
pub struct RawId(pub String);

impl Into<DocumentId> for RawId {
    fn into(self) -> DocumentId {
        DocumentId(self.0)
    }
}

#[derive(Debug)]
pub enum StorageError {
    NotFound(String),
    Timeout(Duration),
}

#[derive(Debug, Clone)]
pub struct Document {
    pub id: String,
    pub title: String,
    pub body: String,
}

#[derive(Debug, Clone)]
pub struct VersionedDocument {
    pub doc: Document,
    pub version: u64,
    pub previous: Option<u64>,
}

impl Deref for VersionedDocument {
    type Target = Document;

    fn deref(&self) -> &Document {
        &self.doc
    }
}

#[derive(Debug, Clone, Eq, Hash)]
pub struct CaseInsensitiveKey {
    pub key: String,
}

impl PartialEq for CaseInsensitiveKey {
    fn eq(&self, other: &Self) -> bool {
        self.key.eq_ignore_ascii_case(&other.key)
    }
}

/// Async API exposed to downstream crates.
pub trait RemoteStore {
    async fn fetch(&self, id: &DocumentId) -> Result<Document, StorageError>;
    async fn store(&self, doc: Document) -> Result<(), StorageError>;
}

pub fn load_config(path: &PathBuf) -> Result<String, Box<dyn Error>> {
    Ok(std::fs::read_to_string(path)?)
}

#[derive(Debug, Clone, Default)]
pub struct ClientBuilder {
    timeout: Option<Duration>,
    retries: u32,
}

impl ClientBuilder {
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = Some(timeout);
        self
    }

    pub fn retries(mut self, retries: u32) -> Self {
        self.retries = retries;
        self
    }
}

trait Normalize {
    fn normalize(&self) -> String;
}

impl Normalize for Document {
    fn normalize(&self) -> String {
        self.title.trim().to_lowercase()
    }
}

fn index_key(doc: &Document) -> String {
    doc.normalize()
}

fn hash_key(k: &CaseInsensitiveKey) -> u64 {
    let mut h = std::collections::hash_map::DefaultHasher::new();
    k.hash(&mut h);
    h.finish()
}
