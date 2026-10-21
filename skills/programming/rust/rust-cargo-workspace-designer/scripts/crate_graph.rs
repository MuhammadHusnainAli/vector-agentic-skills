//! Print a Cargo workspace's internal crate graph by layer (layer 0 = no internal deps) and
//! check membership.
//!   CW009 member-missing          a `members` entry with no Cargo.toml / a glob matching nothing
//!   CW010 crate-not-in-workspace  a Cargo.toml under the root that no `members` entry covers
//!   CW011 dependency-cycle        internal crates depending on each other (normal/build edges)
//!   CW018 default-member-invalid  a `default-members` entry that is not a member
//!
//! Build: rustc -O --edition 2021 scripts/crate_graph.rs -o /tmp/crate_graph
//! Usage: crate_graph <DIR|Cargo.toml> [--dot | --json] [--strict]
//! Exit:  0 acyclic (findings listed), 1 a dependency cycle (or any finding with --strict), 2 usage error.

mod cli;
mod toml;
mod workspace;

use cli::{Finding, Rule};
use toml::Val;
use workspace::Workspace;

const RULES: &[Rule] = &[
    Rule { id: "CW009", name: "member-missing", severity: "high",
           why: "Cargo fails to load the workspace when a member path has no Cargo.toml",
           fix: "fix or remove the `members` entry (globs must match at least one crate directory)" },
    Rule { id: "CW010", name: "crate-not-in-workspace", severity: "medium",
           why: "a package under the workspace root that is not a member fails with 'current package believes it's in a workspace when it's not'",
           fix: "add it to `members`, list it in `exclude`, or give it its own [workspace]" },
    Rule { id: "CW011", name: "dependency-cycle", severity: "high",
           why: "Cargo rejects cycles between packages (dev-dependency cycles are allowed but make layering meaningless)",
           fix: "move the shared types into a lower crate both depend on, or invert one edge behind a trait" },
    Rule { id: "CW018", name: "default-member-invalid", severity: "high",
           why: "every `default-members` entry must also be a member; Cargo errors otherwise",
           fix: "point it at an existing member directory or drop it" },
];

const USAGE: &str = "usage: crate_graph <DIR|Cargo.toml> [--dot | --json] [--strict]

Print the internal dependency graph of a Cargo workspace by layer (layer 0 has no internal
dependencies; layer N depends only on lower layers), report dependency cycles (CW011) and
membership problems: missing members (CW009), crates under the root that are not members
(CW010) and invalid default-members (CW018). Dev-dependencies are not graph edges.

  --dot     Graphviz output (cycle edges in red):  crate_graph . --dot | dot -Tsvg > crates.svg";

/// Internal edges: crate -> internal crates it depends on (normal + build).
fn edges(ws: &Workspace) -> Vec<(String, Vec<String>)> {
    let pkgs = ws.packages();
    let names: Vec<String> = pkgs.iter().map(|m| m.name()).collect();
    let wdeps = ws.root.doc.path(&["workspace", "dependencies"]).and_then(Val::as_table);
    pkgs.iter()
        .map(|m| {
            let mut deps: Vec<String> = m
                .deps()
                .into_iter()
                .filter(|d| !d.section.ends_with("dev-dependencies") && !d.section.ends_with("dev_dependencies"))
                .filter(|d| d.path.is_some() || d.workspace && wdeps.and_then(|w| w.table(&d.key)).is_some_and(|t| t.get("path").is_some()))
                .map(|d| {
                    // a workspace dep may rename: `x = { path = .., package = "real" }`
                    wdeps.and_then(|w| w.table(&d.key)).and_then(|t| t.get("package")).and_then(Val::as_str).map_or(d.package.clone(), str::to_string)
                })
                .filter(|n| names.contains(n))
                .collect();
            deps.sort();
            deps.dedup();
            (m.name(), deps)
        })
        .collect()
}

/// Layer per crate (None for crates on or behind a cycle) and the cycles found.
fn layers(g: &[(String, Vec<String>)]) -> (Vec<(String, Option<usize>)>, Vec<Vec<String>>) {
    fn visit(n: &str, g: &[(String, Vec<String>)], stack: &mut Vec<String>, memo: &mut Vec<(String, Option<usize>)>, cycles: &mut Vec<Vec<String>>) -> Option<usize> {
        if let Some((_, l)) = memo.iter().find(|(m, _)| m == n) {
            return *l;
        }
        if let Some(pos) = stack.iter().position(|s| s == n) {
            let mut cyc = stack[pos..].to_vec();
            cyc.push(n.to_string());
            if !cycles.iter().any(|c| c.len() == cyc.len() && cyc.iter().all(|x| c.contains(x))) {
                cycles.push(cyc);
            }
            return None;
        }
        stack.push(n.to_string());
        let deps = g.iter().find(|(m, _)| m == n).map(|(_, d)| d.clone()).unwrap_or_default();
        let mut layer = Some(0);
        for d in &deps {
            match visit(d, g, stack, memo, cycles) {
                Some(l) => layer = layer.map(|x| x.max(l + 1)),
                None => layer = None,
            }
        }
        stack.pop();
        memo.push((n.to_string(), layer));
        layer
    }
    let (mut memo, mut cycles) = (Vec::new(), Vec::new());
    for (n, _) in g {
        visit(n, g, &mut Vec::new(), &mut memo, &mut cycles);
    }
    (memo, cycles)
}

fn json_str(s: &str) -> String {
    format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\""))
}

fn main() {
    let opts = cli::parse(USAGE, RULES, &[], &["--dot"]);
    let dot = opts.on("--dot");
    let paths: Vec<&String> = opts.paths.iter().collect();
    let [arg] = paths.as_slice() else { cli::die("pass one workspace directory or Cargo.toml") };
    if *arg == "-" {
        cli::die("crate_graph needs a workspace directory (it reads every member)");
    }
    let ws = workspace::load_arg(arg).unwrap_or_else(|e| cli::die(&e));
    for w in &ws.warnings {
        eprintln!("warning: {w}");
    }
    let g = edges(&ws);
    let (memo, cycles) = layers(&g);
    let layer_of = |n: &str| memo.iter().find(|(m, _)| m == n).and_then(|(_, l)| *l);
    let in_cycle = |a: &str, b: &str| cycles.iter().any(|c| c.windows(2).any(|w| w[0] == a && w[1] == b));

    // Membership findings.
    let mut findings = Vec::new();
    let root_rel = ws.root.rel.clone();
    for (pat, line) in &ws.missing {
        findings.push(Finding { file: root_rel.clone(), line: *line, id: "CW009", msg: format!("members entry \"{pat}\" matches no directory with a Cargo.toml"), fix: String::new() });
    }
    for s in &ws.strays {
        findings.push(Finding { file: s.clone(), line: 1, id: "CW010", msg: format!("{s} is under the workspace root but not a member"), fix: String::new() });
    }
    let wt = ws.root.doc.table("workspace");
    if let Some(dm) = wt.and_then(|w| w.get("default-members")).and_then(Val::as_array) {
        let root_dir = ws.root.dir.canonicalize().unwrap_or_else(|_| ws.root.dir.clone());
        for d in dm.iter().filter_map(Val::as_str) {
            let dir = root_dir.join(d);
            let is_member = ws.members.iter().any(|m| m.dir.canonicalize().map_or(false, |p| p == dir)) || dir == root_dir;
            if !is_member {
                findings.push(Finding { file: root_rel.clone(), line: wt.map_or(1, |w| w.line_of("default-members")), id: "CW018",
                                        msg: format!("default-members entry \"{d}\" is not a workspace member"), fix: String::new() });
            }
        }
    }
    for c in &cycles {
        findings.push(Finding { file: root_rel.clone(), line: 1, id: "CW011", msg: format!("cyclic dependency between workspace crates: {}", c.join(" -> ")), fix: String::new() });
    }
    findings.retain(|f| RULES.iter().any(|r| r.id == f.id && opts.enabled(r)));
    for f in &mut findings {
        f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.to_string());
    }

    if dot {
        println!("digraph workspace {{\n  rankdir=BT;\n  node [shape=box];");
        for (n, deps) in &g {
            println!("  {};", json_str(n));
            for d in deps {
                let red = if in_cycle(n, d) { " [color=red]" } else { "" };
                println!("  {} -> {}{red};", json_str(n), json_str(d));
            }
        }
        println!("}}");
    } else if opts.json {
        let crates: Vec<String> = g
            .iter()
            .map(|(n, deps)| {
                let d: Vec<String> = deps.iter().map(|x| json_str(x)).collect();
                format!("{{\"name\":{},\"layer\":{},\"deps\":[{}]}}", json_str(n), layer_of(n).map_or("null".into(), |l| l.to_string()), d.join(","))
            })
            .collect();
        let cyc: Vec<String> = cycles.iter().map(|c| format!("[{}]", c.iter().map(|x| json_str(x)).collect::<Vec<_>>().join(","))).collect();
        let fs: Vec<String> = findings.iter().map(|f| format!("{{\"file\":{},\"line\":{},\"rule\":{},\"message\":{}}}", json_str(&f.file), f.line, json_str(f.id), json_str(&f.msg))).collect();
        println!("{{\"crates\":[{}],\"cycles\":[{}],\"findings\":[{}]}}", crates.join(","), cyc.join(","), fs.join(","));
    } else {
        let max = memo.iter().filter_map(|(_, l)| *l).max();
        for layer in 0..=max.unwrap_or(0) {
            let mut at: Vec<&str> = g.iter().filter(|(n, _)| layer_of(n) == Some(layer)).map(|(n, _)| n.as_str()).collect();
            at.sort();
            if !at.is_empty() {
                println!("layer {layer}: {}", at.join(", "));
            }
        }
        let cyclic: Vec<&str> = g.iter().filter(|(n, _)| layer_of(n).is_none()).map(|(n, _)| n.as_str()).collect();
        if !cyclic.is_empty() {
            println!("no layer (in or depending on a cycle): {}", cyclic.join(", "));
        }
        let w = g.iter().map(|(n, _)| n.len()).max().unwrap_or(0);
        println!("\nedges:");
        for (n, deps) in g.iter().filter(|(_, d)| !d.is_empty()) {
            println!("  {n:<w$} -> {}", deps.join(", "));
        }
        for f in &findings {
            println!("\n{}:{}: {} {}\n    fix: {}", f.file, f.line, f.id, f.msg, f.fix);
        }
        println!("\n{} crate(s), {} cycle(s), {} finding(s).", g.len(), cycles.len(), findings.len());
    }
    let code = if !cycles.is_empty() || (opts.strict && !findings.is_empty()) { 1 } else { 0 };
    std::process::exit(code);
}
