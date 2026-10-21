//! kvstore: an append-only key-value store with typed, chain-friendly errors.
//!
//! ```no_run
//! let store = kvstore::Store::open("data.log").expect("store should open in docs");
//! ```

use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

/// Errors returned by [`Store`].
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum StoreError {
    /// The key does not exist.
    #[error("key {key:?} not found")]
    NotFound { key: String },

    /// Keys must be non-empty.
    #[error("key must not be empty")]
    EmptyKey,

    /// The log file could not be opened.
    #[error("failed to open store log {path:?}")]
    Open {
        path: PathBuf,
        #[source]
        source: io::Error,
    },

    /// Reading or appending to the log failed.
    #[error("i/o error on store log")]
    Io(#[from] io::Error),

    /// A line in the log is not `key=value`.
    #[error("corrupt record at line {line}")]
    Corrupt { line: usize },
}

impl StoreError {
    /// True when retrying the same call may succeed.
    pub fn is_retryable(&self) -> bool {
        match self {
            Self::Io(e) | Self::Open { source: e, .. } => matches!(
                e.kind(),
                io::ErrorKind::Interrupted | io::ErrorKind::TimedOut | io::ErrorKind::WouldBlock
            ),
            Self::NotFound { .. } | Self::EmptyKey | Self::Corrupt { .. } => false,
        }
    }
}

/// Result alias used throughout the crate.
pub type Result<T, E = StoreError> = std::result::Result<T, E>;

/// An append-only key-value store backed by a text log.
pub struct Store {
    path: PathBuf,
    index: HashMap<String, String>,
}

impl Store {
    /// Open the log at `path` and rebuild the in-memory index.
    ///
    /// # Errors
    ///
    /// [`StoreError::Open`] if the file cannot be opened, [`StoreError::Io`] if a read fails and
    /// [`StoreError::Corrupt`] if a line is not `key=value`.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref().to_path_buf();
        let file = File::open(&path).map_err(|source| StoreError::Open { path: path.clone(), source })?;
        let mut index = HashMap::new();
        for (n, line) in BufReader::new(file).lines().enumerate() {
            let line = line?;
            let (k, v) = line.split_once('=').ok_or(StoreError::Corrupt { line: n + 1 })?;
            index.insert(k.to_owned(), v.to_owned());
        }
        Ok(Self { path, index })
    }

    /// Look up a key.
    ///
    /// # Errors
    ///
    /// [`StoreError::NotFound`] when the key is absent.
    pub fn get(&self, key: &str) -> Result<&str> {
        self.index
            .get(key)
            .map(String::as_str)
            .ok_or_else(|| StoreError::NotFound { key: key.to_owned() })
    }

    /// Append `key=value` to the log.
    ///
    /// # Errors
    ///
    /// [`StoreError::EmptyKey`] for an empty key, [`StoreError::Io`] when the append fails.
    pub fn put(&mut self, key: &str, value: &str) -> Result<()> {
        if key.is_empty() {
            return Err(StoreError::EmptyKey);
        }
        let mut file = OpenOptions::new().append(true).open(&self.path)?;
        writeln!(file, "{key}={value}")?;
        self.index.insert(key.to_owned(), value.to_owned());
        Ok(())
    }

    /// Parse several values, failing on the first bad one.
    ///
    /// # Errors
    ///
    /// [`StoreError::NotFound`] for the first missing key.
    pub fn get_many(&self, keys: &[&str]) -> Result<Vec<&str>> {
        keys.iter().map(|k| self.get(k)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_key_is_not_found() {
        let dir = std::env::temp_dir().join("kvstore-clean-test.log");
        std::fs::write(&dir, "a=1\n").unwrap();
        let store = Store::open(&dir).unwrap();
        let err = store.get("b").unwrap_err();
        assert!(matches!(err, StoreError::NotFound { ref key } if key == "b"));
        assert!(!err.is_retryable());
    }
}
