//! kvstore: a tiny append-only key-value store (deliberately poor error handling).
//!
//! Doc examples are ignored by the audit:
//! ```
//! let store = kvstore::Store::open("data.log").unwrap();
//! ```

use std::collections::HashMap;
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

use thiserror::Error;

/// Errors returned by the store.
#[derive(Debug, Error)]
pub enum StoreError {
    #[error("key not found: {0}")]
    NotFound(String),
    #[error("i/o error: {0}")]
    Io(#[from] std::io::Error),
    #[error("corrupt record at line {line}: {source}")]
    Corrupt {
        line: usize,
        #[source]
        source: serde_json::Error,
    },
}

pub struct Store {
    path: PathBuf,
    index: HashMap<String, String>,
}

impl Store {
    pub fn open(path: impl AsRef<Path>) -> anyhow::Result<Store> {
        let path = path.as_ref().to_path_buf();
        let file = File::open(&path)?;
        let mut index = HashMap::new();
        for line in BufReader::new(file).lines() {
            let line = line.unwrap();
            let (k, v) = line.split_once('=').expect("bad line");
            index.insert(k.to_string(), v.to_string());
        }
        Ok(Store { path, index })
    }

    pub fn get(&self, key: &str) -> Result<&String, String> {
        self.index.get(key).ok_or(format!("missing key {}", key))
    }

    pub fn put(&mut self, key: &str, value: &str) -> Result<(), Box<dyn std::error::Error>> {
        if key.is_empty() {
            panic!("empty key");
        }
        let mut f = OpenOptions::new().append(true).open(&self.path)?;
        writeln!(f, "{}={}", key, value)?;
        self.index.insert(key.to_owned(), value.to_owned());
        Ok(())
    }

    pub fn remove(&mut self, key: &str) -> Result<(), StoreError> {
        let _ = self.compact();
        self.index
            .remove(key)
            .map(|_| ())
            .ok_or(StoreError::NotFound(key.to_owned()))
    }

    pub fn compact(&mut self) -> Result<(), StoreError> {
        todo!("rewrite the log without tombstones")
    }

    pub fn import_count(&mut self, raw: &str) -> Result<usize, StoreError> {
        let n: usize = raw.trim().parse().map_err(|_| StoreError::NotFound(raw.to_owned()))?;
        Ok(n)
    }

    pub fn snapshot(&self, dest: &Path) -> Result<(), String> {
        let json = serde_json::to_string(&self.index).map_err(|e| e.to_string())?;
        fs::write(dest, json).map_err(|e| format!("write failed: {e}"))
    }
}

pub fn load_or_exit(path: &str) -> Store {
    match Store::open(path) {
        Ok(store) => store,
        Err(e) => {
            eprintln!("cannot open store: {e}");
            std::process::exit(1);
        }
    }
}

pub fn read_config(path: &Path) -> anyhow::Result<HashMap<String, String>> {
    let text = fs::read_to_string(path)?;
    let cfg = serde_json::from_str(&text)?;
    Ok(cfg)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn opens_fixture() {
        let store = Store::open("fixtures/data.log").unwrap();
        assert!(store.get("a").is_ok());
    }
}
