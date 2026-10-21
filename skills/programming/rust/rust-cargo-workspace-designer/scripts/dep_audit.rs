//! Check how a Cargo workspace declares its dependencies.
//!   CW003 duplicated-dependency        versions set per member instead of once in [workspace.dependencies]
//!   CW007 unversioned-path-dependency  path/git dependency without `version` in a publishable crate
//!   CW013 wildcard-version             version = "*"
//!   CW014 git-dependency-unpinned      git dependency without `rev` or `tag`
//!   CW015 inherit-undefined            `x.workspace = true` with nothing in the workspace to inherit
//!   CW016 default-features-ignored     member sets default-features = false on a workspace dep that enables them
//!
//! Build: rustc -O --edition 2021 scripts/dep_audit.rs -o /tmp/dep_audit
//! Usage: dep_audit <DIR|Cargo.toml|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod toml;
mod workspace;

use cli::{Finding, Rule};
use toml::Val;
use workspace::{dep_of, Dep, Manifest, Workspace};

const RULES: &[Rule] = &[
    Rule { id: "CW003", name: "duplicated-dependency", severity: "medium",
           why: "versions repeated per member drift apart and duplicate the crate in the build",
           fix: "declare it once in [workspace.dependencies] and use NAME.workspace = true (members may add features)" },
    Rule { id: "CW007", name: "unversioned-path-dependency", severity: "high",
           why: "crates.io rejects path/git dependencies without a version, so `cargo publish` fails",
           fix: "dep = { path = \"../x\", version = \"0.3.0\" } (or publish = false for internal crates)" },
    Rule { id: "CW013", name: "wildcard-version", severity: "high",
           why: "\"*\" accepts any future major version; crates.io rejects it",
           fix: "a caret requirement such as \"0.9\" or \"1.2\"" },
    Rule { id: "CW014", name: "git-dependency-unpinned", severity: "medium",
           why: "a git dependency without rev/tag follows a moving branch: builds change without a code change",
           fix: "rev = \"<commit>\" or tag = \"v1.2.3\" (Cargo.lock pins it, but cargo update silently moves it)" },
    Rule { id: "CW015", name: "inherit-undefined", severity: "high",
           why: "`workspace = true` points at a key the workspace does not define: Cargo refuses to build",
           fix: "add it to [workspace.dependencies] / [workspace.package] / [workspace.lints], or set it in the member" },
    Rule { id: "CW016", name: "default-features-ignored", severity: "medium",
           why: "a member cannot turn default features off when the workspace dependency leaves them on (Cargo warns and ignores it)",
           fix: "default-features = false in [workspace.dependencies]; members then add the features they need" },
];

const USAGE: &str = "usage: dep_audit <DIR|Cargo.toml|-> [options]

Check dependency declarations across a Cargo workspace: per-member versions that belong in
[workspace.dependencies] (CW003), unversioned path/git deps in publishable crates (CW007),
\"*\" versions (CW013), unpinned git deps (CW014), workspace inheritance of undefined keys
(CW015) and member default-features = false that Cargo ignores (CW016).";

fn check(ws: &Workspace, out: &mut Vec<Finding>) {
    let wt = ws.root.doc.table("workspace");
    let wdeps: Vec<Dep> = wt
        .and_then(|w| w.table("dependencies"))
        .map(|t| t.entries.iter().map(|(k, v, l)| dep_of("workspace.dependencies", k, v, *l)).collect())
        .unwrap_or_default();
    let mut push = |m: &Manifest, line: usize, id: &'static str, msg: String| {
        out.push(Finding { file: m.rel.clone(), line, id, msg, fix: String::new() });
    };
    let manifests: Vec<&Manifest> = std::iter::once(&ws.root).chain(ws.members.iter().filter(|m| m.dir != ws.root.dir)).collect();

    for d in &wdeps {
        if d.version.as_deref() == Some("*") {
            push(&ws.root, d.line, "CW013", format!("[workspace.dependencies] {} = \"*\"", d.key));
        }
        if d.git.is_some() && !d.pinned {
            push(&ws.root, d.line, "CW014", format!("[workspace.dependencies] {} follows a git branch", d.key));
        }
    }
    // External crates declared directly (not inherited) in more than one manifest.
    let direct: Vec<(&Manifest, Dep)> = manifests
        .iter()
        .flat_map(|m| m.deps().into_iter().map(move |d| (*m, d)))
        .filter(|(_, d)| !d.workspace && d.path.is_none() && d.section != "workspace.dependencies")
        .collect();
    for (m, d) in &direct {
        if wdeps.iter().any(|w| w.key == d.key) {
            push(m, d.line, "CW003", format!("{} sets its own `{}` although [workspace.dependencies] has it", m.name(), d.key));
            continue;
        }
        let others: Vec<String> = direct
            .iter()
            .filter(|(o, od)| o.dir != m.dir && od.package == d.package)
            .map(|(o, od)| format!("{} {}", o.name(), od.version.as_deref().unwrap_or("git")))
            .collect();
        if !others.is_empty() {
            push(m, d.line, "CW003", format!("`{}` {} is also declared by {}", d.key, d.version.as_deref().unwrap_or("(git)"), others.join(", ")));
        }
    }

    for m in &manifests {
        let pkg = m.package();
        for d in m.deps() {
            if d.version.as_deref() == Some("*") {
                push(m, d.line, "CW013", format!("{} depends on {} = \"*\"", m.name(), d.key));
            }
            if d.git.is_some() && !d.pinned {
                push(m, d.line, "CW014", format!("{} depends on git {} without rev or tag", m.name(), d.key));
            }
            let dev = d.section.ends_with("dev-dependencies") || d.section.ends_with("dev_dependencies");
            if pkg.is_some() && m.publishable() && !dev && !d.workspace && (d.path.is_some() || d.git.is_some()) && d.version.is_none() {
                let kind = if d.path.is_some() { "path" } else { "git" };
                push(m, d.line, "CW007", format!("{} is publishable but its {kind} dependency `{}` has no version", m.name(), d.key));
            }
            if d.workspace {
                match wdeps.iter().find(|w| w.key == d.key) {
                    None => push(m, d.line, "CW015", format!("`{}.workspace = true` but [workspace.dependencies] has no `{}`", d.key, d.key)),
                    Some(w) if d.default_features == Some(false) && w.default_features != Some(false) => push(m, d.line, "CW016",
                        format!("`default-features = false` on {} is ignored: [workspace.dependencies] enables them", d.key)),
                    _ => {}
                }
            }
        }
        if let Some(p) = pkg {
            let wpkg = wt.and_then(|w| w.table("package"));
            for (k, v, line) in &p.entries {
                if matches!(v, Val::Tbl(t) if t.get("workspace").and_then(Val::as_bool) == Some(true)) && wpkg.is_none_or(|w| w.get(k).is_none()) {
                    push(m, *line, "CW015", format!("`{k}.workspace = true` but [workspace.package] has no `{k}`"));
                }
            }
            let wants_lints = m.doc.table("lints").and_then(|l| l.get("workspace")).and_then(Val::as_bool) == Some(true);
            if wants_lints && wt.and_then(|w| w.table("lints")).is_none() {
                push(m, m.doc.table("lints").map_or(1, |l| l.line), "CW015", "`[lints] workspace = true` but the workspace has no [workspace.lints]".into());
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
    cli::finish(&opts, RULES, findings, 1 + ws.members.len(), "dependency")
}
