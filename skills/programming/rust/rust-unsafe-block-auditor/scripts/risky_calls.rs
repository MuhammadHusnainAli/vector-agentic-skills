//! Find unsafe operations that are sound only under conditions someone must write down.
//! Quiet inside an unsafe block/fn that already has its `// SAFETY:` / `# Safety` text.
//!   US012 unchecked-call          get_unchecked, unwrap_unchecked, from_utf8_unchecked, new_unchecked ...
//!   US013 slice-from-raw-parts    slice::from_raw_parts(_mut): validity, alignment, length, lifetime
//!   US014 owned-from-raw          Vec/String::from_raw_parts, Box/Arc/Rc/CString::from_raw
//!   US015 unreachable-unchecked   hint::unreachable_unchecked()
//!   US016 pin-unchecked           Pin::new_unchecked, map_unchecked(_mut), get_unchecked_mut()
//!   US022 int-to-ptr-cast         0x1000 as *const T, (p as usize | 1) as *const T (always reported)
//!   US025 inline-asm              asm!, global_asm!, naked_asm!
//!
//! Build: rustc -O --edition 2021 scripts/risky_calls.rs -o /tmp/risky_calls
//! Usage: risky_calls <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod cli;
mod rsparse;
mod unsafe_items;

use cli::{Finding, Rule};
use rsparse::{items, one_line, Src};
use unsafe_items::{justified, unsafe_items};

const RULES: &[Rule] = &[
    Rule { id: "US012", name: "unchecked-call", severity: "low",
           why: "the *_unchecked variant skips the check the safe version does; UB if the condition does not hold",
           fix: "use the checked version unless profiling proves the check matters; otherwise state why the condition holds" },
    Rule { id: "US013", name: "slice-from-raw-parts", severity: "low",
           why: "needs non-null, aligned, initialised, single-allocation memory valid for the chosen lifetime, len*size <= isize::MAX",
           fix: "// SAFETY: covering each requirement; prefer taking &[T] from the caller instead of (ptr, len)" },
    Rule { id: "US014", name: "owned-from-raw", severity: "medium",
           why: "the pointer must come from the matching into_raw/allocation with the same layout and allocator, exactly once",
           fix: "pair each from_raw with one into_raw/forget; for C buffers copy into a Vec and free with the C deallocator" },
    Rule { id: "US015", name: "unreachable-unchecked", severity: "medium",
           why: "if the path is reachable after all, the optimiser has already deleted the code that would have caught it",
           fix: "unreachable!() (checked) unless a benchmark proves the branch matters; document why it cannot be reached" },
    Rule { id: "US016", name: "pin-unchecked", severity: "medium",
           why: "Pin projection/creation by hand must uphold the pinning guarantees (no moves, Drop rules)",
           fix: "pin-project-lite or pin!(); Box::pin; keep unchecked pin APIs with a documented argument" },
    Rule { id: "US022", name: "int-to-ptr-cast", severity: "low",
           why: "integer-to-pointer casts lose provenance; dereferencing the result is UB under strict provenance",
           fix: "ptr.map_addr(|a| a | 1) / with_addr (1.84) to keep provenance; ptr::with_exposed_provenance for MMIO" },
    Rule { id: "US025", name: "inline-asm", severity: "low",
           why: "inline assembly is outside the Rust abstract machine: registers, memory and flags rules are on you",
           fix: "document clobbers and memory effects (options(nomem, nostack) etc.) and test on every target" },
];

const USAGE: &str = "usage: risky_calls <FILES|DIRS|-> [options]

Report operations whose soundness depends on conditions someone must write down:
unchecked calls (US012), slice::from_raw_parts (US013), owned-from-raw constructors (US014),
unreachable_unchecked (US015), unchecked Pin APIs (US016), integer-to-pointer casts (US022)
and inline asm (US025). Items inside an unsafe block or fn that already carries its
SAFETY comment / # Safety doc are not reported, except US022.";

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, _, _) = items(&src);
        let list = unsafe_items(&src, &fns);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, msg: String| {
            if id == "US022" || !justified(&list, off) {
                found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg, fix: String::new() });
            }
        };
        let path_before = |off: usize| {
            let start = code[..off].rfind(|c: char| !(c.is_alphanumeric() || c == '_' || c == ':')).map_or(0, |i| i + 1);
            code[start..off].to_string()
        };

        for (off, _) in code.match_indices("_unchecked") {
            let name_start = code[..off].rfind(|c: char| !(c.is_alphanumeric() || c == '_')).map_or(0, |i| i + 1);
            let name = &code[name_start..off + "_unchecked".len()];
            let rest = &code[off + "_unchecked".len()..];
            let full = format!("{}{}", path_before(name_start), name);
            let id = if name == "unreachable_unchecked" {
                "US015"
            } else if full.ends_with("Pin::new_unchecked") || name.starts_with("map_unchecked") || name == "get_unchecked_mut" && rest.starts_with("()") {
                "US016"
            } else if rest.starts_with('(') || rest.starts_with("_mut(") {
                "US012"
            } else {
                continue; // a definition such as `fn get_unchecked`
            };
            if code[..name_start].trim_end().ends_with("fn") {
                continue;
            }
            push(off, id, format!("`{full}` relies on an unchecked precondition"));
        }
        for (off, _) in code.match_indices("from_raw_parts") {
            let owner = path_before(off);
            if code[..off].trim_end().ends_with("fn") {
                continue;
            }
            if owner.ends_with("Vec::") || owner.ends_with("String::") {
                push(off, "US014", format!("`{owner}from_raw_parts` takes ownership of a raw allocation"));
            } else {
                push(off, "US013", format!("`{owner}from_raw_parts` builds a slice from a raw pointer"));
            }
        }
        for (off, _) in code.match_indices("::from_raw(") {
            let owner = path_before(off + 2);
            if ["Box::", "Arc::", "Rc::", "CString::"].iter().any(|o| owner.ends_with(o)) {
                push(off, "US014", format!("`{owner}from_raw` takes ownership of a raw pointer"));
            }
        }
        for pat in [" as *const", " as *mut"] {
            for (off, _) in code.match_indices(pat) {
                let stmt_start = code[..off].rfind([';', '{', '=', ',']).map_or(0, |i| i + 1);
                let operand = code[stmt_start..off].trim();
                let literal = operand.trim_start_matches('(').starts_with("0x")
                    || operand.chars().next().is_some_and(|c| c.is_ascii_digit());
                if literal || operand.contains("as usize") || operand.contains("as u64") {
                    push(off, "US022", format!("`{}{}` casts an integer to a pointer", one_line(operand), pat));
                }
            }
        }
        for mac in ["asm!(", "global_asm!(", "naked_asm!("] {
            for (off, _) in code.match_indices(mac) {
                let word_start = off == 0 || !code.as_bytes()[off - 1].is_ascii_alphanumeric() && code.as_bytes()[off - 1] != b'_';
                if word_start {
                    push(off, "US025", format!("`{}` inline assembly", &mac[..mac.len() - 1]));
                }
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    let findings: Vec<Finding> = findings
        .into_iter()
        .map(|mut f| {
            f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.to_string());
            f
        })
        .collect();
    cli::finish(&opts, RULES, findings, inputs.len(), "risky-call")
}
