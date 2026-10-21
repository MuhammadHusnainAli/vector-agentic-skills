//! Check the contents of every manifest in a Cargo workspace.
//!   CW001 resolver-missing             virtual manifest (or edition < 2021 root) without `resolver`
//!   CW002 root-only-section-in-member  [profile], [patch] or [replace] in a member (Cargo ignores them)
//!   CW004 package-field-not-inherited  a [workspace.package] key the member neither inherits nor sets
//!   CW005 inconsistent-edition         member edition differs from the workspace edition
//!   CW006 missing-rust-version         package without rust-version (MSRV)
//!   CW008 publish-not-set              publishable package without description/license and no publish = false
//!   CW012 lints-not-inherited          [workspace.lints] exists but the member has no [lints] workspace = true
//!   CW017 deprecated-underscore-key    dev_dependencies, build_dependencies, default_features, [project] ...
//!   CW019 virtual-manifest-section     [dependencies]/[features]/[lib]/[[bin]] in a virtual manifest
//!   CW020 msrv-below-manifest-feature  rust-version older than the manifest features in use
//!
//! Build: rustc -O --edition 2021 scripts/manifest_lint.rs -o /tmp/manifest_lint
//! Usage: manifest_lint <DIR|Cargo.toml|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod toml;
mod workspace;

use cli::{Finding, Rule};
use toml::{Table, Val};
use workspace::{Manifest, Workspace};

const RULES: &[Rule] = &[
    Rule { id: "CW001", name: "resolver-missing", severity: "high",
           why: "a virtual manifest has no edition, so Cargo falls back to resolver 1 (features unified across build/dev/target deps)",
           fix: "[workspace] resolver = \"2\" (or \"3\" for MSRV-aware resolution, Rust 1.84+)" },
    Rule { id: "CW002", name: "root-only-section-in-member", severity: "high",
           why: "[profile], [patch] and [replace] only take effect in the workspace root; in a member they are ignored with a warning",
           fix: "move the section to the root Cargo.toml (use [profile.release.package.NAME] for per-crate settings)" },
    Rule { id: "CW004", name: "package-field-not-inherited", severity: "low",
           why: "fields defined once in [workspace.package] drift when a member silently leaves them out",
           fix: "KEY.workspace = true in the member's [package]" },
    Rule { id: "CW005", name: "inconsistent-edition", severity: "medium",
           why: "mixed editions change language rules, prelude and RPIT capture between crates of one product",
           fix: "edition.workspace = true (migrate with cargo fix --edition first)" },
    Rule { id: "CW006", name: "missing-rust-version", severity: "low",
           why: "without rust-version, users on old compilers get confusing errors and the MSRV-aware resolver has nothing to use",
           fix: "rust-version = \"1.NN\" in [workspace.package] and rust-version.workspace = true in members" },
    Rule { id: "CW008", name: "publish-not-set", severity: "low",
           why: "a publishable crate without description/license fails cargo publish; internal crates should say so",
           fix: "publish = false for internal crates, or add description and license(-file)" },
    Rule { id: "CW012", name: "lints-not-inherited", severity: "medium",
           why: "[workspace.lints] only applies to members that opt in",
           fix: "[lints] workspace = true (Rust 1.74+)" },
    Rule { id: "CW017", name: "deprecated-underscore-key", severity: "medium",
           why: "underscore spellings and [project] are deprecated and rejected in edition 2024",
           fix: "dev-dependencies, build-dependencies, default-features, crate-type, proc-macro, [package]" },
    Rule { id: "CW019", name: "virtual-manifest-section", severity: "high",
           why: "a virtual manifest (no [package]) cannot have dependencies, features or targets; Cargo rejects or ignores them",
           fix: "move them to [workspace.dependencies] or into a member crate" },
    Rule { id: "CW020", name: "msrv-below-manifest-feature", severity: "medium",
           why: "the manifest uses a feature newer than its rust-version, so the declared MSRV cannot build it",
           fix: "raise rust-version to at least the listed version, or stop using the feature" },
];

const USAGE: &str = "usage: manifest_lint <DIR|Cargo.toml|-> [options]

Check every manifest of a Cargo workspace: resolver (CW001), root-only sections in members
(CW002), [workspace.package] inheritance (CW004), editions (CW005), rust-version (CW006),
publishability (CW008), lint inheritance (CW012), deprecated keys (CW017), virtual-manifest
sections (CW019) and MSRV vs manifest features (CW020).";

/// (major, minor) of "1.85" / "1.85.0".
fn ver(s: &str) -> Option<(u32, u32)> {
    let mut it = s.split('.');
    Some((it.next()?.trim().parse().ok()?, it.next().unwrap_or("0").trim().parse().ok()?))
}

/// A package field: Some(Some(v)) set, Some(None) inherited (`x.workspace = true`), None absent.
fn field<'a>(pkg: &'a Table, key: &str) -> Option<Option<&'a Val>> {
    match pkg.get(key)? {
        Val::Tbl(t) if t.get("workspace").and_then(Val::as_bool) == Some(true) => Some(None),
        v => Some(Some(v)),
    }
}

fn check(ws: &Workspace, out: &mut Vec<Finding>) {
    let root = &ws.root;
    let wt = root.doc.table("workspace");
    let wpkg = wt.and_then(|w| w.table("package"));
    let virtual_root = wt.is_some() && root.package().is_none();
    let mut push = |m: &Manifest, line: usize, id: &'static str, msg: String| {
        out.push(Finding { file: m.rel.clone(), line, id, msg, fix: String::new() });
    };

    if let Some(w) = wt {
        let resolver = w.get("resolver").and_then(Val::as_str);
        let root_edition = root.package().and_then(|p| p.get("edition")).and_then(Val::as_str);
        if resolver.is_none() && (virtual_root || root_edition.is_none_or(|e| e < "2021")) {
            push(root, w.line, "CW001", if virtual_root { "virtual manifest without `resolver`: Cargo uses resolver 1".into() }
                 else { "root package on edition < 2021 without `resolver`".into() });
        }
    }
    if virtual_root {
        for sec in ["dependencies", "dev-dependencies", "build-dependencies", "features", "lib", "bin", "lints", "target"] {
            if let Some(v) = root.doc.get(sec) {
                let line = match v { Val::Tbl(t) => t.line, _ => root.doc.line_of(sec) };
                push(root, line, "CW019", format!("[{sec}] in a virtual manifest (no [package])"));
            }
        }
    }
    let manifests: Vec<&Manifest> = std::iter::once(root).chain(ws.members.iter().filter(|m| m.dir != root.dir)).collect();
    for m in &manifests {
        for key in ["dev_dependencies", "build_dependencies", "project"] {
            if let Some(t) = m.doc.table(key) {
                push(m, t.line, "CW017", format!("[{key}] is deprecated (use [{}])", key.replace('_', "-").replace("project", "package")));
            }
        }
        for d in m.deps() {
            let raw = m.doc.table(&d.section).or_else(|| None).and_then(|t| t.table(&d.key));
            if raw.is_some_and(|t| t.get("default_features").is_some()) {
                push(m, d.line, "CW017", format!("`default_features` on {} (use default-features)", d.key));
            }
        }
        if let Some(lib) = m.doc.table("lib") {
            for k in ["crate_type", "proc_macro"] {
                if lib.get(k).is_some() {
                    push(m, lib.line_of(k), "CW017", format!("[lib] {k} (use {})", k.replace('_', "-")));
                }
            }
        }
    }
    for m in ws.members.iter().filter(|m| m.dir != root.dir) {
        for sec in ["profile", "patch", "replace"] {
            if let Some(t) = m.doc.table(sec) {
                let line = t.entries.first().and_then(|(_, v, _)| v.as_table()).map_or(t.line, |s| s.line);
                push(m, line, "CW002", format!("[{sec}] in a member is ignored; it belongs in the root Cargo.toml"));
            }
        }
    }

    let w_edition = wpkg.and_then(|p| p.get("edition")).and_then(Val::as_str);
    let w_msrv = wpkg.and_then(|p| p.get("rust-version")).and_then(Val::as_str);
    for m in ws.packages() {
        let Some(pkg) = m.package() else { continue };
        if let Some(wp) = wpkg {
            let missing: Vec<&str> = wp.entries.iter().map(|(k, _, _)| k.as_str()).filter(|k| pkg.get(k).is_none()).collect();
            if !missing.is_empty() && m.dir != root.dir {
                push(m, pkg.line, "CW004", format!("{} does not inherit {}", m.name(), missing.iter().map(|k| format!("{k}.workspace = true")).collect::<Vec<_>>().join(", ")));
            }
        }
        if let (Some(Some(Val::Str(e))), Some(we)) = (field(pkg, "edition"), w_edition) {
            if e != we {
                push(m, pkg.line_of("edition"), "CW005", format!("{} uses edition {e}, the workspace uses {we}", m.name()));
            }
        }
        let msrv = match field(pkg, "rust-version") {
            Some(Some(Val::Str(v))) => Some(v.clone()),
            Some(None) => w_msrv.map(str::to_string),
            _ => None,
        };
        if field(pkg, "rust-version").is_none() {
            push(m, pkg.line, "CW006", format!("{} has no rust-version", m.name()));
        }
        let has = |k: &str| match field(pkg, k) {
            Some(Some(_)) => true,
            Some(None) => wpkg.is_some_and(|w| w.get(k).is_some()),
            None => false,
        };
        if m.publishable() && (!has("description") || !(has("license") || has("license-file"))) {
            let what: Vec<&str> = ["description", "license"].into_iter().filter(|k| !has(k) && !(*k == "license" && has("license-file"))).collect();
            push(m, pkg.line, "CW008", format!("{} is publishable but has no {}; internal crates should set publish = false", m.name(), what.join(" or ")));
        }
        if wt.and_then(|w| w.table("lints")).is_some() && m.doc.table("lints").and_then(|l| l.get("workspace")).and_then(Val::as_bool) != Some(true) {
            push(m, pkg.line, "CW012", format!("{} does not opt into [workspace.lints]", m.name()));
        }
        // CW020: features newer than the declared MSRV
        if let Some(v) = msrv.as_deref().and_then(ver) {
            let edition = match field(pkg, "edition") { Some(Some(Val::Str(e))) => Some(e.clone()), Some(None) => w_edition.map(str::to_string), _ => None };
            let mut needs: Vec<((u32, u32), String)> = Vec::new();
            match edition.as_deref() {
                Some("2024") => needs.push(((1, 85), "edition 2024".into())),
                Some("2021") => needs.push(((1, 56), "edition 2021".into())),
                _ => {}
            }
            if m.doc.table("lints").is_some() {
                needs.push(((1, 74), "[lints]".into()));
            }
            let inherits = pkg.entries.iter().any(|(_, v, _)| matches!(v, Val::Tbl(t) if t.get("workspace").is_some())) || m.deps().iter().any(|d| d.workspace);
            if inherits {
                needs.push(((1, 64), "workspace inheritance".into()));
            }
            let features = m.doc.table("features").map(|f| f.entries.iter().flat_map(|(_, v, _)| v.as_array().unwrap_or(&[]).to_vec()).filter_map(|v| v.as_str().map(str::to_string)).collect::<Vec<_>>()).unwrap_or_default();
            if features.iter().any(|f| f.starts_with("dep:") || f.contains("?/")) {
                needs.push(((1, 60), "dep:/weak (?/) feature syntax".into()));
            }
            if m.dir == root.dir && wt.and_then(|w| w.get("resolver")).and_then(Val::as_str) == Some("3") {
                needs.push(((1, 84), "resolver = \"3\"".into()));
            }
            for (need, what) in needs.into_iter().filter(|(n, _)| *n > v) {
                push(m, pkg.line_of("rust-version"), "CW020", format!("{} declares rust-version {} but uses {what} (needs {}.{})",
                                                                   m.name(), msrv.as_deref().unwrap_or("?"), need.0, need.1));
            }
        }
    }
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[], &[]);
    let [arg] = opts.paths.as_slice() else { cli::die("pass one workspace directory, Cargo.toml or -") };
    let ws = workspace::load_arg(arg).unwrap_or_else(|e| cli::die(&e));
    for w in &ws.warnings {
        eprintln!("warning: {w}");
    }
    let mut found = Vec::new();
    check(&ws, &mut found);
    let findings: Vec<Finding> = found
        .into_iter()
        .filter(|f| RULES.iter().any(|r| r.id == f.id && opts.enabled(r)))
        .map(|mut f| {
            f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.to_string());
            f
        })
        .collect();
    cli::finish(&opts, RULES, findings, 1 + ws.members.len(), "manifest")
}
