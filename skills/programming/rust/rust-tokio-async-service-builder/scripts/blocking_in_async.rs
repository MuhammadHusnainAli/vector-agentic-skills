//! Find blocking calls on Tokio worker threads.
//!   TK001 blocking-sleep          std::thread::sleep in async code
//!   TK002 blocking-fs             std::fs::* / File::open without .await in async code
//!   TK003 blocking-http           reqwest::blocking / ureq in async code
//!   TK004 blocking-net-or-stdin   std TcpStream::connect / TcpListener::bind / UdpSocket::bind, std::io::stdin()
//!   TK005 blocking-wait           .recv() / .recv_timeout() / .join() / .wait() without .await
//!   TK015 runtime-in-runtime      block_on, Runtime::new, blocking_recv/send/lock/read/write in async code
//!   TK018 block-in-place-current-thread  block_in_place where the runtime is current_thread
//!
//! Build: rustc -O --edition 2021 scripts/blocking_in_async.rs -o /tmp/blocking_in_async
//! Usage: blocking_in_async <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod async_ctx;
mod cli;
mod rsparse;

use async_ctx::{fn_at, macro_spans, AsyncCtx};
use cli::{Finding, Rule};
use rsparse::{close_of, items, Src};

const RULES: &[Rule] = &[
    Rule { id: "TK001", name: "blocking-sleep", severity: "high",
           why: "std::thread::sleep parks a runtime worker: every task scheduled on it stalls",
           fix: "tokio::time::sleep(d).await" },
    Rule { id: "TK002", name: "blocking-fs", severity: "medium",
           why: "std::fs blocks the worker for the duration of the syscall (slow disks, NFS)",
           fix: "tokio::fs::*(..).await, or tokio::task::spawn_blocking(move || std::fs::..).await" },
    Rule { id: "TK003", name: "blocking-http", severity: "high",
           why: "blocking HTTP clients block the worker and reqwest::blocking panics when dropped inside a runtime",
           fix: "the async reqwest::Client (one shared instance) with .await" },
    Rule { id: "TK004", name: "blocking-net-or-stdin", severity: "high",
           why: "std networking and stdin block until the peer or user responds",
           fix: "tokio::net::{TcpStream, TcpListener, UdpSocket} and tokio::io::stdin() with .await" },
    Rule { id: "TK005", name: "blocking-wait", severity: "high",
           why: "std channel recv, thread join and process wait block the worker until the other side finishes",
           fix: "tokio::sync::mpsc/oneshot with .recv().await, JoinHandle.await, tokio::process::Child::wait().await" },
    Rule { id: "TK015", name: "runtime-in-runtime", severity: "high",
           why: "block_on / blocking_* inside async code panics ('Cannot start a runtime from within a runtime') or deadlocks",
           fix: "just .await the future; from sync code called by async code, restructure or use spawn_blocking + Handle::block_on" },
    Rule { id: "TK018", name: "block-in-place-current-thread", severity: "high",
           why: "block_in_place panics on the current_thread runtime (and plain #[tokio::test] is current_thread)",
           fix: "tokio::task::spawn_blocking(..).await, or a multi_thread runtime (#[tokio::test(flavor = \"multi_thread\")])" },
];

const USAGE: &str = "usage: blocking_in_async <FILES|DIRS|-> [options]

Report blocking calls inside async code: std sleep (TK001), std::fs (TK002), blocking HTTP
(TK003), std networking/stdin (TK004), sync waits (TK005), nested runtimes and blocking_*
(TK015), and block_in_place on a current_thread runtime (TK018). Async code = async fn
bodies, async blocks and async closures, excluding spawn_blocking/block_in_place/thread::spawn
closures.";

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, _, _) = items(&src);
        let ctx = AsyncCtx::new(&src, &fns);
        let selects = macro_spans(code, "select!");
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, what: &str| {
            let place = fn_at(&src, &fns, off).map_or(String::new(), |f| format!(" in fn {}", f.name));
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg: format!("{what}{place}"), fix: String::new() });
        };
        let path_before = |off: usize| {
            let start = code[..off].rfind(|c: char| !(c.is_alphanumeric() || c == '_' || c == ':')).map_or(0, |i| i + 1);
            &code[start..off]
        };
        // `.await` right after the call that starts at `open` (`(`)?
        let awaited = |open: usize| code[close_of(code, open)..].trim_start().starts_with(".await");

        for (off, _) in code.match_indices("thread::sleep(") {
            if ctx.contains(off) {
                push(off, "TK001", "`std::thread::sleep` blocks the runtime worker");
            }
        }
        for (off, _) in code.match_indices("fs::") {
            let path = path_before(off);
            let call = code[off..].find('(').map(|n| off + n);
            if ctx.contains(off) && !path.ends_with("tokio::") && call.is_some_and(|c| !awaited(c)) && !path.ends_with("::fs::") {
                let name: String = code[off..].chars().take_while(|c| *c != '(').collect();
                push(off, "TK002", &format!("blocking `{}{name}`", path));
            }
        }
        for pat in ["File::open(", "File::create("] {
            for (off, _) in code.match_indices(pat) {
                if ctx.contains(off) && !path_before(off).ends_with("tokio::fs::") && !awaited(off + pat.len() - 1) {
                    push(off, "TK002", &format!("blocking `{}`", &pat[..pat.len() - 1]));
                }
            }
        }
        for pat in ["reqwest::blocking", "ureq::"] {
            for (off, _) in code.match_indices(pat) {
                if ctx.contains(off) && !code[..off].trim_end().ends_with("use") {
                    push(off, "TK003", &format!("blocking HTTP client `{}`", pat.trim_end_matches("::")));
                }
            }
        }
        for pat in ["TcpStream::connect(", "TcpListener::bind(", "UdpSocket::bind(", "stdin()"] {
            for (off, _) in code.match_indices(pat) {
                let path = path_before(off);
                let std_path = path.ends_with("std::net::") || path.ends_with("std::io::") || path.ends_with("io::") && !path.contains("tokio");
                let tokio_path = path.contains("tokio");
                let open = off + pat.len() - 1;
                if ctx.contains(off) && !tokio_path && (std_path || !awaited(open)) && !(pat == "stdin()" && !std_path) {
                    push(off, "TK004", &format!("blocking `{}{}`", path, &pat[..pat.len() - 1]));
                }
            }
        }
        for pat in [".recv()", ".recv_timeout(", ".join()", ".wait()"] {
            for (off, _) in code.match_indices(pat) {
                let open = off + pat.find('(').unwrap_or(0);
                let in_select = selects.iter().any(|&(a, b)| a < off && off < b);
                // A future handed to another call (`timeout(d, tracker.wait())`) is awaited there.
                let as_argument = code[close_of(code, open)..].trim_start().starts_with([',', ')']);
                if ctx.contains(off) && !in_select && !as_argument && !awaited(open) {
                    push(off, "TK005", &format!("`{}` without .await blocks until the other side answers", pat.trim_end_matches('(')));
                }
            }
        }
        for pat in ["block_on(", "Runtime::new(", ".blocking_recv(", ".blocking_send(", ".blocking_lock(", ".blocking_read(", ".blocking_write("] {
            for (off, _) in code.match_indices(pat) {
                if ctx.contains(off) {
                    push(off, "TK015", &format!("`{}` inside async code", pat.trim_start_matches('.').trim_end_matches('(')));
                }
            }
        }
        // Attribute arguments are string literals, which the scanner blanks: read the original text.
        let orig = &src.orig;
        let current_thread = orig.contains("\"current_thread\"")
            || orig.match_indices("#[tokio::test").any(|(i, _)| !orig[i..].split(']').next().unwrap_or("").contains("multi_thread"));
        if current_thread {
            for (off, _) in code.match_indices("block_in_place(") {
                push(off, "TK018", "`block_in_place` with a current_thread runtime in this file (it panics there)");
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
    cli::finish(&opts, RULES, findings, inputs.len(), "blocking-call")
}
