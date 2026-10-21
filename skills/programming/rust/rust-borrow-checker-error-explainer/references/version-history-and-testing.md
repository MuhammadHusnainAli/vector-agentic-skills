# Version History and Testing

Which Rust release changed what the borrow checker accepts, which APIs remove the need for workarounds, and
how to lock fixes in with tests and CI.

## Contents

- [Stabilisations that matter for borrow errors](#stabilisations-that-matter-for-borrow-errors)
- [Edition 2021 changes](#edition-2021-changes)
- [Edition 2024 changes](#edition-2024-changes)
- [Checking your MSRV before suggesting an API](#checking-your-msrv-before-suggesting-an-api)
- [Testing that code does not compile](#testing-that-code-does-not-compile)
- [Testing runtime borrow failures](#testing-runtime-borrow-failures)
- [CI with the scripts](#ci-with-the-scripts)

## Stabilisations that matter for borrow errors

| Rust | Feature | Replaces |
|------|---------|----------|
| 1.31 | NLL on edition 2018 | lexical lifetimes (borrows lasting to the closing brace) |
| 1.36 | NLL on edition 2015 too | |
| 1.40 | `mem::take` | `mem::replace(&mut x, Default::default())` |
| 1.53 | `IntoIterator` for arrays by value (edition 2021 for method syntax) | `.iter().cloned()` on arrays |
| 1.61 | `Vec::retain_mut` | index loops with `remove` |
| 1.63 | `std::thread::scope`; old AST borrow checker removed | `crossbeam::scope`, `Arc` for borrowed data |
| 1.65 | `let ... else`; generic associated types | nested `match` for E0381; workarounds for lending iterators |
| 1.70 | `OnceCell`/`OnceLock`; `Arc::into_inner`, `Rc::into_inner` | `lazy_static`, racy `try_unwrap` loops |
| 1.73 | panic message on its own line (`panicked at src/x.rs:1:2:`) | `panicked at 'msg', src/x.rs:1:2` (both parsed by `runtime_panic`) |
| 1.76 | `Rc::unwrap_or_clone`, `Arc::unwrap_or_clone` | `try_unwrap(..).unwrap_or_else(|rc| (*rc).clone())` |
| 1.77 | `Mutex::clear_poison`, `RwLock::clear_poison` | rebuilding the mutex after a panic |
| 1.80 | `LazyCell`/`LazyLock`; `Option::take_if` | `once_cell::sync::Lazy`; manual `if pred { x.take() }` |
| 1.82 | precise capturing `impl Trait + use<'a, T>`; `&raw const`/`&raw mut` | `Captures<'a>` trick |
| 1.85 | edition 2024; async closures (`async \|\| {}`) | |
| 1.86 | `<[T]>::get_disjoint_mut`, `HashMap::get_disjoint_mut`; trait upcasting | `split_at_mut` gymnastics |
| 1.87 | `Vec::extract_if`, `LinkedList::extract_if` | `retain` + clone into a second `Vec` |

## Edition 2021 changes

- **Disjoint closure captures**: closures capture the exact paths they use (`self.a.b`), not whole variables.
  Fixes many E0502/E0499 errors with closures inside methods. Side effect: drop order of captured values can
  change; `cargo fix --edition` inserts `let _ = &x;` where it matters.
- **`array.into_iter()`** yields values, not references (method syntax), which can move arrays you expected
  to borrow.
- Panics: `panic!("{}")` requires a format string; not borrow related.

## Edition 2024 changes

Edition 2024 (Rust 1.85) changes several rules that affect borrows:

| Change | Effect on borrow errors |
|--------|------------------------|
| Tail-expression temporaries are dropped before the block's locals | Fixes classic E0597 "borrowed value does not live long enough" on `fn f() -> usize { let c = RefCell::new(..); c.borrow().len() }` |
| `if let` scrutinee temporaries are dropped before the `else` block | `if let Some(x) = m.lock().unwrap().get(..) {} else { m.lock() }` no longer deadlocks; may change drop order |
| RPIT (`-> impl Trait`) captures all in-scope generic parameters, including lifetimes | Can **introduce** E0502/E0505 at call sites: the returned value now borrows arguments it did not before. Fix with `+ use<..>` listing only what is captured |
| `static mut` references are denied (`static_mut_refs`) | use atomics, `Mutex`, `OnceLock`, or `&raw mut` |
| `unsafe_op_in_unsafe_fn` warns | unrelated to borrows, appears in the same migration |

Migrate with `cargo fix --edition` on 2021, check, then set `edition = "2024"` and re-run `cargo check`;
run `parse_diagnostics` on the output to triage new borrow errors.

```rust
// Edition 2024 RPIT capture and its precise-capturing fix (1.82+ syntax, works on 2021 too).
fn evens<'a>(v: &'a [u32], _scratch: &mut Vec<u32>) -> impl Iterator<Item = u32> + use<'a> {
    v.iter().copied().filter(|x| x % 2 == 0)   // captures 'a only, not the `_scratch` borrow
}
```

## Checking your MSRV before suggesting an API

- Read `rust-version` in `Cargo.toml` (or the toolchain in `rust-toolchain.toml`).
- Below 1.86: suggest `split_at_mut`, not `get_disjoint_mut`. Below 1.87: `retain` (+ clone) instead of
  `extract_if`. Below 1.80: `once_cell` crate instead of `LazyLock`. Below 1.65: no `let ... else`.
- The `explain_code` fix lists name the minimum version next to each newer API.
- `cargo +1.70 check` (with that toolchain installed) or `cargo msrv verify` confirm a fix builds on the MSRV.

## Testing that code does not compile

Keep a regression test for "this misuse must stay a compile error", for example a type that must not be
`Send`, or an API whose returned reference must not outlive its owner.

**`compile_fail` doctests** (stable, no extra crates):

````rust
/// The guard cannot outlive the pool:
///
/// ```compile_fail,E0597
/// let conn;
/// {
///     let pool = mycrate::Pool::new();
///     conn = pool.get();
/// }
/// conn.query("select 1");
/// ```
pub struct Pool;
````

The error code after `compile_fail,` makes rustdoc check that the failure is the expected one (the code check
is enforced on nightly; stable only checks that it fails). Prefer tests that fail for exactly one reason.

**`trybuild`** (dev-dependency) compares full compiler output with `.stderr` snapshots:

```rust,ignore
#[test]
fn ui() {
    let t = trybuild::TestCases::new();
    t.compile_fail("tests/ui/*.rs");   // each file must fail; output compared to tests/ui/*.stderr
    t.pass("tests/ui-pass/*.rs");
}
```

Run `TRYBUILD=overwrite cargo test` to accept new snapshots after a compiler upgrade changes wording.

## Testing runtime borrow failures

```rust
use std::cell::RefCell;

struct Bus { listeners: RefCell<Vec<String>> }

impl Bus {
    fn emit(&self) -> usize {
        let snapshot = self.listeners.borrow().clone(); // guard dropped before calling out
        for _l in &snapshot {
            self.listeners.borrow_mut().push("re-subscribed".into());
        }
        snapshot.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn emit_can_resubscribe() {
        let bus = Bus { listeners: RefCell::new(vec!["a".into()]) };
        assert_eq!(bus.emit(), 1);
        assert_eq!(bus.listeners.borrow().len(), 2);
    }

    #[test]
    #[should_panic(expected = "already borrowed")]
    fn holding_a_guard_while_mutating_panics() {
        let cell = RefCell::new(vec![1]);
        let _r = cell.borrow();
        cell.borrow_mut().push(2);
    }
}
```

For mutexes, test the recovery path: spawn a thread that panics while holding the lock, `join()` it (it
returns `Err`), then assert that `lock()` returns `Err` and that your recovery (`into_inner`/`clear_poison`)
works.

## CI with the scripts

The scripts are single-file, std-only Rust programs: build with `rustc`, no Cargo project needed.

```bash
SKILL=path/to/rust-borrow-checker-error-explainer
for t in parse_diagnostics runtime_panic; do
  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"
done

# Fail fast with an explanation when a PR introduces borrow errors:
cargo check --all-targets --message-format=json > check.jsonl || /tmp/parse_diagnostics check.jsonl

# Explain RefCell / Mutex panics in test failures:
cargo test 2>&1 | tee test.txt || /tmp/runtime_panic test.txt
```

`--strict` makes either tool exit 1 when the output contains errors or panics that are not borrow-related, so
a pipeline step can tell "borrow problem, see explanation" from "something else broke".
