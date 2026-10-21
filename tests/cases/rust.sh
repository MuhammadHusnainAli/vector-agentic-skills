# Rust skill script cases. Syntax: see tests/run_tests.sh. Rust scripts are compiled by the runner.

# --- rust-borrow-checker-error-explainer
BCK=$RS/rust-borrow-checker-error-explainer/scripts
t 'parse_diagnostics: conditional return is BCK002' 0 'pattern : BCK002 conditional-return-of-borrow' \
  "$BCK/parse_diagnostics.rs" "$FX/rust/borrow_cargo_check.txt"
t 'parse_diagnostics: labels keep source lines' 0 'L52   `batch` moved due to this implicit call to `.into_iter()`' \
  "$BCK/parse_diagnostics.rs" "$FX/rust/borrow_cargo_check.txt"
t 'parse_diagnostics: all nine explained' 0 '9 error(s): 9 borrow/ownership explained, 0 other; 1 warning(s) ignored.' \
  "$BCK/parse_diagnostics.rs" "$FX/rust/borrow_cargo_check.txt" --strict
t 'parse_diagnostics: cargo json, non-borrow error fails strict' 1 'error[E0425] src/routes.rs:55:37' \
  "$BCK/parse_diagnostics.rs" "$FX/rust/borrow_cargo_messages.jsonl" --strict
t 'parse_diagnostics: json report' 0 '"pattern":{"id":"BCK015","name":"spawn-needs-move"}' \
  "$BCK/parse_diagnostics.rs" "$FX/rust/borrow_cargo_messages.jsonl" --json
t 'parse_diagnostics: clean build' 0 'No compiler errors found (1 warning(s) ignored).' \
  "$BCK/parse_diagnostics.rs" "$FX/rust/borrow_clean_build.txt" --strict
STDIN=$'error[E0596]: cannot borrow data in an `Rc` as mutable\n --> src/lib.rs:5:5\n  |\n5 |     shared.push(1);\n  |     ^^^^^^ cannot borrow as mutable\n' \
t 'parse_diagnostics: stdin rc mutation' 0 'BCK022 mutate-through-rc' \
  "$BCK/parse_diagnostics.rs" -
STDIN='' t 'parse_diagnostics: empty input' 2 'input is empty' \
  "$BCK/parse_diagnostics.rs" -
t 'explain_code: E0502 ranked fixes' 0 '1. [restructure] copy the needed value out' \
  "$BCK/explain_code.rs" E0502
t 'explain_code: pattern by name' 0 'BCK001 iterate-and-mutate (E0499, E0502)' \
  "$BCK/explain_code.rs" iterate-and-mutate
t 'explain_code: unknown code' 2 "unknown code or pattern 'E9999'" \
  "$BCK/explain_code.rs" E9999
t 'runtime_panic: poison linked to root cause' 0 'root    : #2 thread '"'<unnamed>'"' at src/stats.rs:18:13: counter overflow' \
  "$BCK/runtime_panic.rs" "$FX/rust/borrow_refcell_panic.txt" --strict
STDIN=$'thread \'main\' panicked at \'index out of bounds: the len is 3 but the index is 7\', src/main.rs:4:5\n' \
t 'runtime_panic: unrelated panic fails strict (old format)' 1 'not a borrow/ownership panic' \
  "$BCK/runtime_panic.rs" - --strict

# --- rust-lifetime-annotation-advisor
LTS=$RS/rust-lifetime-annotation-advisor/scripts
t 'elision_check: needless lifetime with elided signature' 1 'fix: fn first_word(line: &str) -> &str' \
  "$LTS/elision_check.rs" "$FX/rust/lt_bad.rs" --strict
t 'elision_check: impl header elision' 1 "fix: impl fmt::Display for Tokenizer<'_>" \
  "$LTS/elision_check.rs" "$FX/rust/lt_bad.rs" --strict --select LT002
t 'elision_check: clean file' 0 'No elision issues found in 1 file(s).' \
  "$LTS/elision_check.rs" "$FX/rust/lt_clean.rs" --strict
STDIN=$'fn pick<\'a>(xs: &\'a [u8], n: usize) -> &\'a [u8] { &xs[..n] }\n' \
t 'elision_check: stdin rule 2' 1 'fix: fn pick(xs: &[u8], n: usize) -> &[u8]' \
  "$LTS/elision_check.rs" - --strict
t 'missing_lifetime: E0106 return gets a signature' 1 "fix: fn longer<'a>(a: &'a str, b: &'a str) -> &'a str" \
  "$LTS/missing_lifetime.rs" "$FX/rust/lt_bad.rs" --strict
t 'missing_lifetime: E0392 unused type lifetime' 1 "LT006 [high] unused-type-lifetime: struct Settings declares \`'a\` but no field uses it (E0392)" \
  "$LTS/missing_lifetime.rs" "$FX/rust/lt_bad.rs" --strict
t 'missing_lifetime: clean file' 0 'No missing-lifetime issues found in 1 file(s).' \
  "$LTS/missing_lifetime.rs" "$FX/rust/lt_clean.rs" --strict
t 'static_bounds: boxed dyn defaults to static' 1 "fix: Box<dyn Fn(&str) -> bool + 'src>" \
  "$LTS/static_bounds.rs" "$FX/rust/lt_bad.rs" --strict
t 'static_bounds: borrow-only static bound' 1 "fn log_value requires T: 'static but only borrows T" \
  "$LTS/static_bounds.rs" "$FX/rust/lt_bad.rs" --strict
t 'static_bounds: clean file (spawn keeps its bound)' 0 "No 'static issues found in 1 file(s)." \
  "$LTS/static_bounds.rs" "$FX/rust/lt_clean.rs" --strict
t 'lifetime_smells: &mut tied to own lifetime' 1 "fn next_token takes \`&'a mut self\` with the impl's own lifetime" \
  "$LTS/lifetime_smells.rs" "$FX/rust/lt_bad.rs" --strict
t 'lifetime_smells: rpit capture only on edition 2024' 1 'LT012 [low] rpit-captures-2024: fn lengths' \
  "$LTS/lifetime_smells.rs" "$FX/rust/lt_bad.rs" --strict --edition 2024
t 'lifetime_smells: clean file on 2024' 0 'No lifetime design issues found in 1 file(s).' \
  "$LTS/lifetime_smells.rs" "$FX/rust/lt_clean.rs" --strict --edition 2024
t 'lifetime_smells: bad threshold' 2 '--max-lifetimes needs a number' \
  "$LTS/lifetime_smells.rs" "$FX/rust/lt_bad.rs" --max-lifetimes many
t 'lifetime_smells: unknown rule' 2 'unknown rule LT999' \
  "$LTS/lifetime_smells.rs" "$FX/rust/lt_bad.rs" --select LT999

# --- rust-trait-design-reviewer
TRS=$RS/rust-trait-design-reviewer/scripts
t 'dyn_compat: every reason listed' 1 '`open` has no self receiver; `put` has type parameters; `try_clone` uses `Self` outside the receiver (E0038)' \
  "$TRS/dyn_compat.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'dyn_compat: async fn in pub trait' 1 'TR008 [medium] async-fn-public-trait: pub trait RemoteStore has async fn fetch, store' \
  "$TRS/dyn_compat.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'dyn_compat: clean (Self: Sized escape hatch, trait_variant)' 0 'No dyn-compatibility issues found in 1 file(s).' \
  "$TRS/dyn_compat.rs" "$FX/rust/tr_clean_storage.rs" --strict
STDIN=$'pub trait Shape { const SIDES: u32; fn area(&self) -> f64; }\npub fn total(s: &[Box<dyn Shape>]) -> f64 { 0.0 }\n' \
t 'dyn_compat: stdin associated const' 1 'it has associated consts' \
  "$TRS/dyn_compat.rs" - --strict
t 'trait_shape: Into becomes From' 1 'fix: impl From<RawId> for DocumentId' \
  "$TRS/trait_shape.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'trait_shape: deref inheritance' 1 'VersionedDocument derefs to Document: Deref used as inheritance on a 3-field struct' \
  "$TRS/trait_shape.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'trait_shape: fat trait threshold' 1 'pub trait Storage has 5 required methods (max 3)' \
  "$TRS/trait_shape.rs" "$FX/rust/tr_bad_storage.rs" --strict --max-methods 3 --select TR006
t 'trait_shape: clean (extension trait on str is fine)' 0 'No trait-shape issues found in 1 file(s).' \
  "$TRS/trait_shape.rs" "$FX/rust/tr_clean_storage.rs" --strict
t 'api_traits: error type without Error impl' 1 'pub enum StorageError is missing Display and std::error::Error' \
  "$TRS/api_traits.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'api_traits: derived Hash with manual PartialEq' 1 'CaseInsensitiveKey derives Hash but implements PartialEq by hand' \
  "$TRS/api_traits.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'api_traits: clean (cfg(test) types skipped)' 0 'No API trait issues found in 1 file(s).' \
  "$TRS/api_traits.rs" "$FX/rust/tr_clean_storage.rs" --strict
t 'api_signatures: concrete slice suggestion' 1 'fix: `filter: &[String]` accepts Vec and more' \
  "$TRS/api_signatures.rs" "$FX/rust/tr_bad_storage.rs" --strict
t 'api_signatures: json report' 0 '"rule":"TR009","name":"box-dyn-error-not-send"' \
  "$TRS/api_signatures.rs" "$FX/rust/tr_bad_storage.rs" --json
t 'api_signatures: clean (Error::source and main are exempt)' 0 'No API signature issues found in 1 file(s).' \
  "$TRS/api_signatures.rs" "$FX/rust/tr_clean_storage.rs" --strict
t 'scaffold_trait: typestate builder' 0 'impl ClientBuilder<Present> {' \
  "$TRS/scaffold_trait.rs" typestate
t 'scaffold_trait: named sealed trait' 0 'pub trait Backend: private::Sealed {' \
  "$TRS/scaffold_trait.rs" sealed --name Backend
t 'scaffold_trait: unknown kind' 2 "unknown kind 'mixin'" \
  "$TRS/scaffold_trait.rs" mixin

# --- rust-error-handling-thiserror-anyhow-designer
ERS=$RS/rust-error-handling-thiserror-anyhow-designer/scripts
t 'unwrap_audit: unwrap and todo in library code' 1 'ERR003 [high] panic-in-lib: `todo!` in fn compact: unfinished code path' \
  "$ERS/unwrap_audit.rs" "$FX/rust/err_bad_store.rs" --strict
t 'unwrap_audit: binary code is exempt' 0 'No panic issues found in 1 file(s).' \
  "$ERS/unwrap_audit.rs" "$FX/rust/err_bad_store.rs" --app --strict
t 'unwrap_audit: clean (tests and doc examples skipped)' 0 'No panic issues found in 1 file(s).' \
  "$ERS/unwrap_audit.rs" "$FX/rust/err_clean_store.rs" --strict
t 'error_types: source printed twice' 1 'StoreError::Io: message "i/o error: {0}" prints `{0}`' \
  "$ERS/error_types.rs" "$FX/rust/err_bad_store.rs" --strict
t 'error_types: anyhow in a library API' 1 'ERR005 [high] anyhow-in-lib-api: pub fn open returns anyhow in library code' \
  "$ERS/error_types.rs" "$FX/rust/err_bad_store.rs" --strict
t 'error_types: clean' 0 'No error type issues found in 1 file(s).' \
  "$ERS/error_types.rs" "$FX/rust/err_clean_store.rs" --strict
STDIN=$'#[derive(Debug, thiserror::Error)]\npub enum AppError {\n    #[error("db failed: {source}")]\n    Db { source: std::io::Error },\n}\n' \
t 'error_types: stdin implicit source field' 1 'AppError::Db: message "db failed: {source}" prints `{source}`' \
  "$ERS/error_types.rs" - --strict --select ERR009
t 'error_flow: discarded source and stringly errors' 1 'ERR006 [medium] map-err-discards-source' \
  "$ERS/error_flow.rs" "$FX/rust/err_bad_store.rs" --strict
t 'error_flow: missing context in anyhow code' 1 'bare `?` on `let text = fs::read_to_string(path)` in fn read_config' \
  "$ERS/error_flow.rs" "$FX/rust/err_bad_store.rs" --strict
t 'error_flow: clean' 0 'No error flow issues found in 1 file(s).' \
  "$ERS/error_flow.rs" "$FX/rust/err_clean_store.rs" --strict
t 'scaffold_errors: spec with keyword field' 0 'r#type: &'"'"'static str,' \
  "$ERS/scaffold_errors.rs" --spec "$FX/rust/err_store_spec.json"
t 'scaffold_errors: web-app preset has IntoResponse' 0 'impl axum::response::IntoResponse for ApiError {' \
  "$ERS/scaffold_errors.rs" --preset web-app
STDIN='{"name":"E","variants":[{"name":"A","source":"std::io::Error","message":"x {source}"}]}' \
t 'scaffold_errors: message printing the source is rejected' 2 'the message must not print the source error' \
  "$ERS/scaffold_errors.rs" --spec -
STDIN='{"name": "E", "variants": [' \
t 'scaffold_errors: broken JSON' 2 'cannot parse spec JSON' \
  "$ERS/scaffold_errors.rs" --spec -

# --- rust-unsafe-block-auditor
USS=$RS/rust-unsafe-block-auditor/scripts
t 'unsafe_inventory: counts and risky items' 0 'L31    block  encode                         5 line(s)  undocumented+risky  set_len' \
  "$USS/unsafe_inventory.rs" "$FX/rust/us_ffi_tokenizer.rs"
t 'unsafe_inventory: strict fails on undocumented items' 1 '22 unsafe item(s) in 1 file(s): 22 undocumented.' \
  "$USS/unsafe_inventory.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'unsafe_inventory: clean file fully documented' 0 '13 unsafe item(s) in 1 file(s): 0 undocumented.' \
  "$USS/unsafe_inventory.rs" "$FX/rust/us_clean_ring_buffer.rs" --strict
t 'safety_comments: missing SAFETY and # Safety' 1 'US002 [medium] missing-safety-doc: unsafe fn adopt_ids has no # Safety section' \
  "$USS/safety_comments.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'safety_comments: large block threshold' 1 'unsafe block in fn batch_encode spans 18 lines (max 10)' \
  "$USS/safety_comments.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict --max-block-lines 10 --select US018
t 'safety_comments: clean' 0 'No safety-documentation issues found in 1 file(s).' \
  "$USS/safety_comments.rs" "$FX/rust/us_clean_ring_buffer.rs" --strict
t 'ub_patterns: lifetime-extending transmute' 1 "transmute::<&'a str, &'static str>(s)\`: extends a lifetime to 'static" \
  "$USS/ub_patterns.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'ub_patterns: zeroed struct with Vec field' 1 'mem::zeroed for `Vocab` (field `pub names: Vec<String>` cannot be zero)' \
  "$USS/ub_patterns.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'ub_patterns: clean' 0 'No undefined-behaviour issues found in 1 file(s).' \
  "$USS/ub_patterns.rs" "$FX/rust/us_clean_ring_buffer.rs" --strict
STDIN=$'use std::ffi::CString;\nfn f(s: &str) { unsafe { puts(CString::new(s).expect("nul").as_ptr()); } }\n' \
t 'ub_patterns: stdin CString temporary' 1 'US010 [high] cstring-temp-ptr' \
  "$USS/ub_patterns.rs" - --strict
t 'risky_calls: int-to-ptr cast' 1 '`0x4000_0000 as *const` casts an integer to a pointer' \
  "$USS/risky_calls.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'risky_calls: clean (documented blocks are quiet)' 0 'No risky-call issues found in 1 file(s).' \
  "$USS/risky_calls.rs" "$FX/rust/us_clean_ring_buffer.rs" --strict
t 'ffi_and_globals: static mut reference' 1 'reference to `static mut CALLS` (`CALLS.push(1)`)' \
  "$USS/ffi_and_globals.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'ffi_and_globals: panicking extern C fn' 1 'extern "C" fn tok_count can panic and has no catch_unwind' \
  "$USS/ffi_and_globals.rs" "$FX/rust/us_ffi_tokenizer.rs" --strict
t 'ffi_and_globals: clean (edition 2024 syntax)' 0 'No FFI/global issues found in 1 file(s).' \
  "$USS/ffi_and_globals.rs" "$FX/rust/us_clean_ring_buffer.rs" --strict
t 'ffi_and_globals: json report' 0 '"rule":"US021","name":"env-set-var"' \
  "$USS/ffi_and_globals.rs" "$FX/rust/us_ffi_tokenizer.rs" --json

# --- rust-tokio-async-service-builder
TKS=$RS/rust-tokio-async-service-builder/scripts
t 'blocking_in_async: std sleep and fs in a handler' 1 'TK001 [high] blocking-sleep: `std::thread::sleep` blocks the runtime worker in fn create_order' \
  "$TKS/blocking_in_async.rs" "$FX/rust/tk_bad_service.rs" --strict
t 'blocking_in_async: block_in_place on current_thread' 1 'TK018 [high] block-in-place-current-thread' \
  "$TKS/blocking_in_async.rs" "$FX/rust/tk_bad_service.rs" --strict
t 'blocking_in_async: clean (spawn_blocking, futures passed to timeout)' 0 'No blocking-call issues found in 1 file(s).' \
  "$TKS/blocking_in_async.rs" "$FX/rust/tk_clean_service.rs" --strict
t 'await_holding: std guard across await' 1 'std guard `orders` in fn get_order is still alive at the .await on line 41' \
  "$TKS/await_holding.rs" "$FX/rust/tk_bad_service.rs" --strict
t 'await_holding: clean (guard scoped in a block)' 0 'No await-holding issues found in 1 file(s).' \
  "$TKS/await_holding.rs" "$FX/rust/tk_clean_service.rs" --strict
STDIN=$'async fn f(r: &std::cell::RefCell<u8>) {\n    let b = r.borrow_mut();\n    tick().await;\n}\n' \
t 'await_holding: stdin RefCell borrow' 1 'std guard `b` in fn f is still alive at the .await on line 3' \
  "$TKS/await_holding.rs" - --strict
t 'task_hygiene: select loop not cancel safe' 1 'select! in a loop races read_exact, read_line, sleep' \
  "$TKS/task_hygiene.rs" "$FX/rust/tk_bad_service.rs" --strict
t 'task_hygiene: clean (TaskTracker, biased select)' 0 'No task issues found in 1 file(s).' \
  "$TKS/task_hygiene.rs" "$FX/rust/tk_clean_service.rs" --strict
t 'service_hygiene: axum 0.7 path syntax' 1 'route path "/orders/:id" uses axum 0.7 syntax' \
  "$TKS/service_hygiene.rs" "$FX/rust/tk_bad_service.rs" --strict
t 'service_hygiene: json report' 0 '"rule":"TK014","name":"no-graceful-shutdown"' \
  "$TKS/service_hygiene.rs" "$FX/rust/tk_bad_service.rs" --json
t 'service_hygiene: clean' 0 'No service issues found in 1 file(s).' \
  "$TKS/service_hygiene.rs" "$FX/rust/tk_clean_service.rs" --strict
t 'scaffold_service: main.rs with graceful shutdown' 0 '.with_graceful_shutdown(shutdown_signal(token.clone()))' \
  "$TKS/scaffold_service.rs" --name orders-api --file main
t 'scaffold_service: Cargo.toml' 0 'name = "orders-api"' \
  "$TKS/scaffold_service.rs" --name orders-api --file cargo
t 'scaffold_service: invalid name' 2 "--name must be lowercase letters, digits, '-' or '_'" \
  "$TKS/scaffold_service.rs" --name OrdersApi

# --- rust-cargo-workspace-designer
CWS=$RS/rust-cargo-workspace-designer/scripts
t 'crate_graph: cycle exits 1' 1 'cyclic dependency between workspace crates: shop-core -> shop-storage -> shop-core' \
  "$CWS/crate_graph.rs" "$FX/rust/cw_bad_workspace"
t 'crate_graph: stray crate and bad default member' 1 'default-members entry "apps/server" is not a workspace member' \
  "$CWS/crate_graph.rs" "$FX/rust/cw_bad_workspace"
t 'crate_graph: clean layers' 0 'shop-infra  -> shop-app, shop-domain' \
  "$CWS/crate_graph.rs" "$FX/rust/cw_clean_workspace" --strict
t 'crate_graph: dot output marks the cycle' 1 '"shop-storage" -> "shop-core" [color=red];' \
  "$CWS/crate_graph.rs" "$FX/rust/cw_bad_workspace" --dot
t 'manifest_lint: profile in a member' 1 'crates/core/Cargo.toml:14: CW002 [high] root-only-section-in-member' \
  "$CWS/manifest_lint.rs" "$FX/rust/cw_bad_workspace" --strict
t 'manifest_lint: virtual manifest without resolver' 1 'CW001 [high] resolver-missing: virtual manifest without `resolver`' \
  "$CWS/manifest_lint.rs" "$FX/rust/cw_bad_workspace" --strict
t 'manifest_lint: member path checks the whole workspace' 1 'shop-core uses edition 2018, the workspace uses 2021' \
  "$CWS/manifest_lint.rs" "$FX/rust/cw_bad_workspace/crates/api/Cargo.toml" --strict
t 'manifest_lint: clean' 0 'No manifest issues found in 7 file(s).' \
  "$CWS/manifest_lint.rs" "$FX/rust/cw_clean_workspace" --strict
STDIN=$'[package]\nname = "x"\nversion = "0.1.0"\nedition = "2024"\nrust-version = "1.80"\npublish = false\n' \
t 'manifest_lint: stdin MSRV below edition 2024' 1 'x declares rust-version 1.80 but uses edition 2024 (needs 1.85)' \
  "$CWS/manifest_lint.rs" - --strict
t 'dep_audit: duplicated tokio versions' 1 '`tokio` 1.28 is also declared by shop-storage 1.38' \
  "$CWS/dep_audit.rs" "$FX/rust/cw_bad_workspace" --strict
t 'dep_audit: ignored default-features' 1 '`default-features = false` on serde is ignored' \
  "$CWS/dep_audit.rs" "$FX/rust/cw_bad_workspace" --strict
t 'dep_audit: clean' 0 'No dependency issues found in 7 file(s).' \
  "$CWS/dep_audit.rs" "$FX/rust/cw_clean_workspace" --strict
STDIN='[package' t 'dep_audit: invalid TOML on stdin' 2 '<stdin>: line 1' \
  "$CWS/dep_audit.rs" -
