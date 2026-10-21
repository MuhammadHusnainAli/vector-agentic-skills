//! Inventory every `unsafe` item, like a small cargo-geiger: kind, location, size, whether it
//! carries its justification (SAFETY comment / `# Safety` doc) and the risky operations inside.
//! Start every unsafe review here; the other scripts explain individual findings.
//!
//! Build: rustc -O --edition 2021 scripts/unsafe_inventory.rs -o /tmp/unsafe_inventory
//! Usage: unsafe_inventory <FILES|DIRS|-> [--json] [--strict]
//! Exit:  0 listed, 1 with --strict when an item lacks its justification, 2 usage error.

mod cli;
mod rsparse;
mod unsafe_items;

use rsparse::{items, Src};
use unsafe_items::{unsafe_items, UnsafeItem};

const USAGE: &str = "usage: unsafe_inventory <FILES|DIRS|-> [--json] [--strict]

List every unsafe block, unsafe fn, unsafe impl, unsafe trait and unsafe extern block with
its location, size in lines, justification status and the risky operations it contains,
then totals per file. Status: documented (SAFETY comment or # Safety doc), undocumented,
or undocumented+risky (no justification and it transmutes, zeroes, sets lengths, builds
owners from raw parts or assumes initialisation).";

/// (pattern in code, label, high risk?)
const OPS: &[(&str, &str, bool)] = &[
    ("transmute", "transmute", true),
    ("uninitialized(", "mem::uninitialized", true),
    ("zeroed", "mem::zeroed", true),
    (".assume_init()", "assume_init", true),
    ("set_len(", "set_len", true),
    ("from_raw_parts", "from_raw_parts", true),
    ("from_raw(", "from_raw", true),
    ("_unchecked", "unchecked call", false),
    ("read_volatile", "volatile read", false),
    ("write_volatile", "volatile write", false),
    (".read()", "ptr read", false),
    (".write(", "ptr write", false),
    (".add(", "ptr add", false),
    (".offset(", "ptr offset", false),
    ("from_ptr(", "CStr::from_ptr", false),
    ("asm!", "inline asm", false),
    ("&mut *", "&mut from raw", false),
];

fn ops(item: &UnsafeItem) -> (Vec<&'static str>, bool) {
    let mut found = Vec::new();
    let mut risky = false;
    for (pat, label, high) in OPS {
        if item.body.contains(pat) && !found.contains(label) {
            found.push(*label);
            risky |= *high;
        }
    }
    (found, risky)
}

fn status(item: &UnsafeItem, risky: bool) -> &'static str {
    match (item.documented, risky) {
        (true, _) => "documented",
        (false, true) => "undocumented+risky",
        (false, false) => "undocumented",
    }
}

fn json_str(s: &str) -> String {
    format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\""))
}

fn main() {
    let opts = cli::parse(USAGE, &[], &[]);
    let inputs = opts.inputs();
    let mut undocumented = 0;
    let mut totals = [0usize; 5]; // block, fn, impl, trait, extern
    let kinds = ["block", "fn", "impl", "trait", "extern"];
    let mut json_files = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let (fns, _, _) = items(&src);
        let list = unsafe_items(&src, &fns);
        let mut counts = [0usize; 5];
        let mut rows = Vec::new();
        for it in &list {
            let k = kinds.iter().position(|k| *k == it.kind).unwrap_or(0);
            counts[k] += 1;
            let (found, risky) = ops(it);
            let st = status(it, risky);
            undocumented += usize::from(!it.documented);
            let lines = src.line_of(it.end) - src.line_of(it.off) + 1;
            rows.push((src.line_of(it.off), it.kind, it.name.clone(), lines, st, found));
        }
        for (t, c) in totals.iter_mut().zip(counts) {
            *t += c;
        }
        if opts.json {
            let items: Vec<String> = rows
                .iter()
                .map(|(l, k, n, lines, st, ops)| {
                    let ops: Vec<String> = ops.iter().map(|o| json_str(o)).collect();
                    format!("{{\"line\":{l},\"kind\":{},\"name\":{},\"lines\":{lines},\"status\":{},\"ops\":[{}]}}",
                            json_str(k), json_str(n), json_str(st), ops.join(","))
                })
                .collect();
            let c: Vec<String> = kinds.iter().zip(counts).map(|(k, n)| format!("\"{k}\":{n}")).collect();
            json_files.push(format!("{{\"file\":{},\"counts\":{{{}}},\"items\":[{}]}}", json_str(&input.name), c.join(","), items.join(",")));
            continue;
        }
        let summary: Vec<String> = kinds.iter().zip(counts).filter(|(_, n)| *n > 0).map(|(k, n)| format!("{n} {k}")).collect();
        println!("{}  ({})", input.name, if summary.is_empty() { "no unsafe".to_string() } else { summary.join(", ") });
        for (l, k, n, lines, st, ops) in &rows {
            println!("  L{l:<5} {k:<6} {:<28} {lines:>3} line(s)  {st:<19} {}", truncate(n, 28), ops.join(", "));
        }
    }
    if opts.json {
        let t: Vec<String> = kinds.iter().zip(totals).map(|(k, n)| format!("\"{k}\":{n}")).collect();
        println!("{{\"files\":[{}],\"totals\":{{{}}},\"undocumented\":{undocumented}}}", json_files.join(","), t.join(","));
    } else {
        let total: usize = totals.iter().sum();
        println!("\n{total} unsafe item(s) in {} file(s): {} undocumented.", inputs.len(), undocumented);
    }
    std::process::exit(if opts.strict && undocumented > 0 { 1 } else { 0 });
}

fn truncate(s: &str, n: usize) -> String {
    if s.chars().count() <= n { s.to_string() } else { format!("{}...", s.chars().take(n - 3).collect::<String>()) }
}
