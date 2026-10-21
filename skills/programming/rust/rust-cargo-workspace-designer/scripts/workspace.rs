//! Load a Cargo workspace the way Cargo finds it: the root manifest, `members` globs minus
//! `exclude`, implicit path-dependency members, and every dependency entry with its line.
//! Shared by the workspace scripts; pulled in with `mod workspace;` (needs `mod toml;`).
#![allow(dead_code)]

use crate::toml::{self, Table, Val};
use std::path::{Path, PathBuf};

pub struct Manifest {
    /// Directory holding the Cargo.toml.
    pub dir: PathBuf,
    /// Display path relative to the workspace root, e.g. `crates/core/Cargo.toml`.
    pub rel: String,
    pub doc: Table,
}

pub struct Dep {
    pub section: String, // "dependencies", "dev-dependencies", "build-dependencies", or a target section
    pub key: String,     // the name used in the manifest
    pub package: String, // `package = ".."` rename target, else key
    pub version: Option<String>,
    pub path: Option<String>,
    pub git: Option<String>,
    pub pinned: bool, // git with rev or tag
    pub workspace: bool,
    pub default_features: Option<bool>,
    pub line: usize,
}

pub struct Workspace {
    pub root: Manifest,
    pub members: Vec<Manifest>,
    /// (`members` entry, line) that matched nothing or has no Cargo.toml.
    pub missing: Vec<(String, usize)>,
    /// Cargo.toml files under the root that belong to no member.
    pub strays: Vec<String>,
    pub warnings: Vec<String>,
}

impl Manifest {
    pub fn read(path: &Path, root_dir: &Path) -> Result<Manifest, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
        let doc = toml::parse(&text).map_err(|e| format!("{}: {e}", path.display()))?;
        let rel = path.strip_prefix(root_dir).unwrap_or(path).display().to_string();
        Ok(Manifest { dir: path.parent().unwrap_or(Path::new(".")).to_path_buf(), rel, doc })
    }

    pub fn from_text(text: &str, name: &str) -> Result<Manifest, String> {
        let doc = toml::parse(text).map_err(|e| format!("{name}: {e}"))?;
        Ok(Manifest { dir: PathBuf::from("."), rel: name.to_string(), doc })
    }

    pub fn package(&self) -> Option<&Table> {
        self.doc.table("package")
    }

    pub fn name(&self) -> String {
        self.package().and_then(|p| p.get("name")).and_then(Val::as_str).unwrap_or("?").to_string()
    }

    /// `publish = false` (or an empty registry list) marks an internal crate.
    pub fn publishable(&self) -> bool {
        match self.package().and_then(|p| p.get("publish")) {
            Some(Val::Bool(b)) => *b,
            Some(Val::Arr(a)) => !a.is_empty(),
            _ => true,
        }
    }

    /// Every dependency in [dependencies], [dev-dependencies], [build-dependencies] (also the
    /// deprecated underscore spellings) and their [target.'..'.*] variants.
    pub fn deps(&self) -> Vec<Dep> {
        let mut out = Vec::new();
        let mut scan = |prefix: &str, t: &Table| {
            for sec in ["dependencies", "dev-dependencies", "build-dependencies", "dev_dependencies", "build_dependencies"] {
                let Some(deps) = t.table(sec) else { continue };
                for (key, val, line) in &deps.entries {
                    out.push(dep_of(&format!("{prefix}{sec}"), key, val, *line));
                }
            }
        };
        scan("", &self.doc);
        if let Some(targets) = self.doc.table("target") {
            for (cfg, t, _) in &targets.entries {
                if let Some(t) = t.as_table() {
                    scan(&format!("target.{cfg}."), t);
                }
            }
        }
        out
    }
}

pub fn dep_of(section: &str, key: &str, val: &Val, line: usize) -> Dep {
    let mut d = Dep { section: section.to_string(), key: key.to_string(), package: key.to_string(), version: None, path: None,
                      git: None, pinned: false, workspace: false, default_features: None, line };
    match val {
        Val::Str(v) => d.version = Some(v.clone()),
        Val::Tbl(t) => {
            let s = |k: &str| t.get(k).and_then(Val::as_str).map(str::to_string);
            d.version = s("version");
            d.path = s("path");
            d.git = s("git");
            d.pinned = t.get("rev").is_some() || t.get("tag").is_some();
            d.workspace = t.get("workspace").and_then(Val::as_bool).unwrap_or(false);
            d.default_features = t.get("default-features").or_else(|| t.get("default_features")).and_then(Val::as_bool);
            if let Some(p) = s("package") {
                d.package = p;
            }
        }
        _ => {}
    }
    d
}

/// Match one path component against a glob with `*` and `?`.
fn glob_match(pat: &str, name: &str) -> bool {
    let (p, n): (Vec<char>, Vec<char>) = (pat.chars().collect(), name.chars().collect());
    fn rec(p: &[char], n: &[char]) -> bool {
        match (p.first(), n.first()) {
            (None, None) => true,
            (Some('*'), _) => rec(&p[1..], n) || (!n.is_empty() && rec(p, &n[1..])),
            (Some('?'), Some(_)) => rec(&p[1..], &n[1..]),
            (Some(a), Some(b)) if a == b => rec(&p[1..], &n[1..]),
            _ => false,
        }
    }
    rec(&p, &n)
}

/// Directories matching a members pattern such as `crates/*` (relative to `root`).
fn expand(root: &Path, pattern: &str) -> Vec<PathBuf> {
    let mut dirs = vec![root.to_path_buf()];
    for comp in pattern.trim_end_matches('/').split('/') {
        let mut next = Vec::new();
        for d in &dirs {
            if comp.contains(['*', '?']) {
                if let Ok(rd) = std::fs::read_dir(d) {
                    let mut found: Vec<PathBuf> = rd
                        .flatten()
                        .filter(|e| e.path().is_dir() && glob_match(comp, &e.file_name().to_string_lossy()))
                        .map(|e| e.path())
                        .collect();
                    found.sort();
                    next.extend(found);
                }
            } else {
                next.push(d.join(comp));
            }
        }
        dirs = next;
    }
    dirs
}

fn is_workspace_root(manifest: &Path) -> bool {
    std::fs::read_to_string(manifest).is_ok_and(|t| t.lines().any(|l| l.trim() == "[workspace]"))
}

/// Find the workspace root for a directory or Cargo.toml path.
pub fn find_root(arg: &Path) -> Result<PathBuf, String> {
    let start = if arg.is_dir() { arg.join("Cargo.toml") } else { arg.to_path_buf() };
    if !start.exists() {
        return Err(format!("no Cargo.toml at {}", start.display()));
    }
    let mut dir = start.canonicalize().map_err(|e| e.to_string())?.parent().map(Path::to_path_buf);
    while let Some(d) = dir {
        if is_workspace_root(&d.join("Cargo.toml")) {
            return Ok(d.join("Cargo.toml"));
        }
        dir = d.parent().map(Path::to_path_buf);
    }
    Ok(start) // a single package without a workspace
}

pub fn load(arg: &Path) -> Result<Workspace, String> {
    let root_path = find_root(arg)?;
    let root_dir = root_path.parent().unwrap_or(Path::new(".")).to_path_buf();
    let root = Manifest::read(&root_path, &root_dir)?;
    let mut ws = Workspace { root, members: vec![], missing: vec![], strays: vec![], warnings: vec![] };
    let wt = ws.root.doc.table("workspace").cloned().unwrap_or_default();
    let list = |key: &str| -> Vec<(String, usize)> {
        wt.get(key).and_then(Val::as_array).unwrap_or(&[]).iter().filter_map(|v| v.as_str().map(|s| (s.to_string(), wt.line_of(key)))).collect()
    };
    let exclude: Vec<PathBuf> = list("exclude").iter().map(|(p, _)| root_dir.join(p)).collect();
    let mut dirs: Vec<PathBuf> = Vec::new();
    for (pat, line) in list("members") {
        let found: Vec<PathBuf> = expand(&root_dir, &pat).into_iter().filter(|d| d.join("Cargo.toml").exists()).collect();
        if found.is_empty() {
            ws.missing.push((pat, line));
        }
        dirs.extend(found.into_iter().filter(|d| !exclude.iter().any(|e| d.starts_with(e))));
    }
    // Implicit members: path dependencies of the root package that live under the root.
    if ws.root.package().is_some() {
        for d in ws.root.deps() {
            if let Some(p) = d.path {
                let dir = root_dir.join(p);
                if dir.starts_with(&root_dir) && dir.join("Cargo.toml").exists() {
                    dirs.push(dir);
                }
            }
        }
    }
    dirs.sort();
    dirs.dedup();
    for d in &dirs {
        match Manifest::read(&d.join("Cargo.toml"), &root_dir) {
            Ok(m) => ws.members.push(m),
            Err(e) => ws.warnings.push(format!("skipped unparsable member: {e}")),
        }
    }
    // Cargo.toml files under the root that are neither the root nor a member.
    let mut all = Vec::new();
    walk(&root_dir, &root_dir, &mut all);
    for p in all {
        let dir = p.parent().unwrap_or(Path::new(".")).to_path_buf();
        if dir != root_dir && !dirs.contains(&dir) && !exclude.iter().any(|e| dir.starts_with(e)) {
            ws.strays.push(p.strip_prefix(&root_dir).unwrap_or(&p).display().to_string());
        }
    }
    Ok(ws)
}

fn walk(dir: &Path, root: &Path, out: &mut Vec<PathBuf>) {
    let Ok(rd) = std::fs::read_dir(dir) else { return };
    let mut entries: Vec<_> = rd.flatten().collect();
    entries.sort_by_key(|e| e.path());
    for e in entries {
        let p = e.path();
        let name = e.file_name().to_string_lossy().into_owned();
        if p.is_dir() {
            if name == "target" || name.starts_with('.') || (p.join("Cargo.toml").exists() && is_workspace_root(&p.join("Cargo.toml"))) {
                continue; // build output, hidden dirs, nested workspaces
            }
            walk(&p, root, out);
        } else if name == "Cargo.toml" && dir != root {
            out.push(p);
        }
    }
}

/// Load from the command-line argument: a directory, a Cargo.toml, or `-` (one manifest on stdin).
pub fn load_arg(arg: &str) -> Result<Workspace, String> {
    if arg != "-" {
        return load(Path::new(arg));
    }
    let mut text = String::new();
    std::io::Read::read_to_string(&mut std::io::stdin(), &mut text).map_err(|e| format!("cannot read stdin: {e}"))?;
    let root = Manifest::from_text(&text, "<stdin>")?;
    Ok(Workspace { root, members: vec![], missing: vec![], strays: vec![], warnings: vec![] })
}

impl Workspace {
    /// Root (if it is a package) followed by the members.
    pub fn packages(&self) -> Vec<&Manifest> {
        let mut v: Vec<&Manifest> = Vec::new();
        if self.root.package().is_some() {
            v.push(&self.root);
        }
        v.extend(self.members.iter().filter(|m| m.dir != self.root.dir));
        v
    }
}
