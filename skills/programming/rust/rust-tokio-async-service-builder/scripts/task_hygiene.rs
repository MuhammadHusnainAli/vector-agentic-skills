//! Find task and channel patterns that lose errors, memory or data.
//!   TK009 detached-spawn               tokio::spawn(..); with the JoinHandle dropped
//!   TK010 unbounded-channel            mpsc::unbounded_channel(): no backpressure
//!   TK016 select-loop-not-cancel-safe  select! in a loop racing read_exact/read_line/write_all or a fresh sleep(..)
//!   TK019 spawn-without-move           tokio::spawn(async { .. }) / .spawn(async { .. }) without `move`
//!
//! Build: rustc -O --edition 2021 scripts/task_hygiene.rs -o /tmp/task_hygiene
//! Usage: task_hygiene <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod async_ctx;
mod cli;
mod rsparse;

use async_ctx::{fn_at, macro_spans};
use cli::{Finding, Rule};
use rsparse::{close_of, items, word_positions, Src};

const RULES: &[Rule] = &[
    Rule { id: "TK009", name: "detached-spawn", severity: "medium",
           why: "a dropped JoinHandle loses the task's panic and result, and shutdown cannot wait for it",
           fix: "keep it: JoinSet / TaskTracker (tokio-util) or store the JoinHandle and await it; log errors inside the task" },
    Rule { id: "TK010", name: "unbounded-channel", severity: "medium",
           why: "an unbounded channel has no backpressure: a slow consumer turns into unbounded memory growth",
           fix: "mpsc::channel(capacity) and send().await (or try_send for drop-on-full)" },
    Rule { id: "TK016", name: "select-loop-not-cancel-safe", severity: "high",
           why: "select! drops the losing futures: read_exact/read_line/write_all lose partial data, a fresh sleep() never fires",
           fix: "pin the long-lived future outside the loop (let sleep = sleep(d); tokio::pin!(sleep); &mut sleep), use cancel-safe reads (read/recv) or a framed codec" },
    Rule { id: "TK019", name: "spawn-without-move", severity: "low",
           why: "a spawned future must be 'static: without `move` it borrows locals (E0373) or only compiles by accident",
           fix: "tokio::spawn(async move { .. }) with owned or Arc data" },
];

const USAGE: &str = "usage: task_hygiene <FILES|DIRS|-> [options]

Report detached tokio::spawn calls (TK009), unbounded channels (TK010), select! loops racing
futures that are not cancel safe (TK016) and spawned async blocks without `move` (TK019).";

const NOT_CANCEL_SAFE: &[&str] = &["read_exact(", "read_line(", "read_to_end(", "read_to_string(", "write_all(", "sleep("];

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, _, _) = items(&src);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, what: String| {
            let place = fn_at(&src, &fns, off).map_or(String::new(), |f| format!(" in fn {}", f.name));
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg: format!("{what}{place}"), fix: String::new() });
        };

        for (off, _) in code.match_indices("tokio::spawn(") {
            let before = code[..off].trim_end();
            let statement_start = before.is_empty() || before.ends_with([';', '{', '}']);
            let open = off + "tokio::spawn".len();
            let after = code[close_of(code, open)..].trim_start();
            if statement_start && after.starts_with(';') {
                push(off, "TK009", "`tokio::spawn(..);` drops its JoinHandle".into());
            }
        }
        for (off, _) in code.match_indices("unbounded_channel") {
            if code[off..].trim_start_matches("unbounded_channel").trim_start().starts_with(['(', ':']) {
                push(off, "TK010", "`unbounded_channel()` has no backpressure".into());
            }
        }
        // select! inside loop / while / for bodies
        let loops: Vec<(usize, usize)> = ["loop", "while", "for"]
            .iter()
            .flat_map(|kw| word_positions(code, kw))
            .filter_map(|i| code[i..].find('{').map(|b| (i + b, close_of(code, i + b))))
            .collect();
        for (a, b) in macro_spans(code, "select!") {
            if !loops.iter().any(|&(la, lb)| la < a && b <= lb) {
                continue;
            }
            let body = &code[a..b];
            let racing: Vec<&str> = NOT_CANCEL_SAFE
                .iter()
                .filter(|p| body.match_indices(*p).any(|(i, _)| !body[..i].ends_with("&mut ")))
                .map(|p| p.trim_end_matches('('))
                .collect();
            if !racing.is_empty() {
                push(a, "TK016", format!("select! in a loop races {} (recreated or partially done each iteration)", racing.join(", ")));
            }
        }
        for pat in ["tokio::spawn(", ".spawn("] {
            for (off, _) in code.match_indices(pat) {
                let arg = code[off + pat.len()..].trim_start();
                if arg.starts_with("async") && arg[5..].trim_start().starts_with('{') {
                    push(off, "TK019", format!("`{}async {{ .. }})` without move", pat));
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
    cli::finish(&opts, RULES, findings, inputs.len(), "task")
}
