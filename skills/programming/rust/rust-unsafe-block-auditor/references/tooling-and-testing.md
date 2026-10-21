# Tooling and Testing for Unsafe Code

A `// SAFETY:` comment is an argument; tools check whether the argument survives real executions. Use Miri
for undefined behaviour in Rust code, sanitizers for FFI and native code, fuzzing to find the inputs nobody
thought of, loom for lock-free concurrency, and lints to keep the documentation honest.

## Contents

- [Which tool finds what](#which-tool-finds-what)
- [Miri](#miri)
- [Sanitizers](#sanitizers)
- [Fuzzing with cargo-fuzz](#fuzzing-with-cargo-fuzz)
- [loom for concurrent code](#loom-for-concurrent-code)
- [Kani and cargo-careful](#kani-and-cargo-careful)
- [Lints](#lints)
- [Measuring unsafe surface](#measuring-unsafe-surface)
- [Testing a safe abstraction](#testing-a-safe-abstraction)
- [A CI pipeline](#a-ci-pipeline)

## Which tool finds what

| Problem | Tool | Notes |
|---------|------|-------|
| Aliasing violations (`&mut` while shared), use-after-free, out-of-bounds, invalid values, uninitialised reads, misalignment, data races | **Miri** | interprets MIR; slow; no FFI |
| Memory errors in code that calls C (and in C itself) | **AddressSanitizer** | nightly `-Zsanitizer=address` |
| Data races across threads (including C) | **ThreadSanitizer** | nightly; build std with it |
| Uninitialised reads reaching branches | **MemorySanitizer** | nightly; build std with it |
| Inputs that break parsers / decoders | **cargo-fuzz** (libFuzzer) | combine with ASan (default) |
| Wrong orderings in atomics / lock-free code | **loom** | explores thread interleavings |
| Proof for all inputs of a bounded harness | **Kani** | model checker |
| Missing SAFETY docs, risky patterns | **clippy**, rustc lints, the scanners in `scripts/` | static |

## Miri

```bash
rustup +nightly component add miri
cargo +nightly miri test                                  # run the test suite under Miri
cargo +nightly miri run                                   # run the binary
MIRIFLAGS="-Zmiri-tree-borrows" cargo +nightly miri test  # Tree Borrows instead of Stacked Borrows
MIRIFLAGS="-Zmiri-strict-provenance" cargo +nightly miri test
MIRIFLAGS="-Zmiri-many-seeds=0..16" cargo +nightly miri test   # several schedules / allocation seeds
```

Practical notes:

- Miri reports the first UB it hits with a backtrace and the violated rule ("attempting a read access using
  <tag> ... but that tag does not exist in the borrow stack").
- Stacked Borrows is the default model; Tree Borrows is newer and accepts some patterns Stacked Borrows rejects.
  Code that passes both is on solid ground.
- Miri cannot call foreign (C) functions. Put FFI behind a trait or `#[cfg(not(miri))]` and test the Rust side
  with a fake.
- It is slow: shrink inputs under `cfg!(miri)` (`let n = if cfg!(miri) { 10 } else { 10_000 };`) and skip heavy
  tests with `#[cfg_attr(miri, ignore)]`.
- `-Zmiri-disable-isolation` lets the program read the clock, env and filesystem.
- Leaks are reported at exit; `-Zmiri-ignore-leaks` silences them when intentional (`Box::leak`).

## Sanitizers

```bash
# AddressSanitizer: out-of-bounds, use-after-free, double free (Linux/macOS, nightly)
RUSTFLAGS="-Zsanitizer=address" RUSTDOCFLAGS="-Zsanitizer=address" \
  cargo +nightly test --target x86_64-unknown-linux-gnu

# ThreadSanitizer: data races; instrument std too for accurate results
RUSTFLAGS="-Zsanitizer=thread" cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu
```

- Always pass an explicit `--target`, so build scripts and proc macros are not instrumented.
- C/C++ code linked in must be built with the same sanitizer (`-fsanitize=address`) to be checked.
- MemorySanitizer needs every dependency (including std and C code) instrumented; it is the hardest to set up.

## Fuzzing with cargo-fuzz

```bash
cargo install cargo-fuzz
cargo fuzz init                     # creates fuzz/ with a libfuzzer-sys crate
cargo fuzz add parse_record
cargo +nightly fuzz run parse_record -- -max_total_time=300
```

```rust,ignore
// fuzz/fuzz_targets/parse_record.rs
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // Must never panic or trigger UB for any input; ASan is on by default.
    let _ = mycrate::parse_record(data);
});
```

Fuzz every function whose unsafe code depends on input (lengths, offsets, tags read from bytes). Keep the
crash inputs in `fuzz/artifacts/` as regression tests; derive `arbitrary::Arbitrary` for structured input.

## loom for concurrent code

```rust,ignore
// Cargo.toml: [target.'cfg(loom)'.dev-dependencies] loom = "0.7"
#[cfg(loom)]
use loom::sync::{atomic::{AtomicUsize, Ordering}, Arc};
#[cfg(loom)]
use loom::thread;

#[cfg(loom)]
#[test]
fn two_increments_are_seen() {
    loom::model(|| {
        let n = Arc::new(AtomicUsize::new(0));
        let n2 = n.clone();
        let t = thread::spawn(move || n2.fetch_add(1, Ordering::Release));
        n.fetch_add(1, Ordering::Release);
        t.join().unwrap();
        assert_eq!(n.load(Ordering::Acquire), 2);
    });
}
```

Run with `RUSTFLAGS="--cfg loom" cargo test --release`. loom explores every interleaving (bounded), so keep
models tiny: two or three threads, a few operations.

## Kani and cargo-careful

- **Kani** (`cargo kani`): bounded model checking; write `#[kani::proof]` harnesses with `kani::any()` inputs
  to prove a function never panics, overflows or performs UB for all inputs within the bounds.
- **cargo-careful** (`cargo +nightly careful test`): runs tests against a std built with debug assertions,
  catching precondition violations in `get_unchecked`, `from_raw_parts`, `copy_nonoverlapping` and others
  without Miri's slowdown.

## Lints

| Lint | Where | Catches (script rule) |
|------|-------|----------------------|
| `unsafe_code` | rustc (allow) | any unsafe; `#![forbid(unsafe_code)]` for crates that need none (US026) |
| `unsafe_op_in_unsafe_fn` | rustc (warn in 2024) | unsafe ops in an unsafe fn without an explicit block (US027) |
| `static_mut_refs` | rustc (deny in 2024) | references to `static mut` (US009) |
| `missing_unsafe_on_extern`, `unsafe_attr_outside_unsafe` | rustc (2024 migration) | US019, US020 |
| `deprecated_safe_2024` | rustc (2024 migration) | `env::set_var` and friends (US021) |
| `invalid_value` | rustc (warn) | `mem::zeroed`/`uninitialized` for types with invalid all-zero values (US004, US005) |
| `clippy::undocumented_unsafe_blocks` | clippy (restriction) | US001 (US028 checks it is on) |
| `clippy::missing_safety_doc` | clippy (style, warn) | US002 |
| `clippy::multiple_unsafe_ops_per_block` | clippy (restriction) | blocks doing several unsafe things (US018) |
| `clippy::not_unsafe_ptr_arg_deref` | clippy (correctness) | US023 |
| `clippy::mut_from_ref` | clippy (correctness) | US024 |
| `clippy::uninit_assumed_init`, `clippy::uninit_vec` | clippy (correctness) | US006, US007 |
| `clippy::transmute_ptr_to_ref`, `clippy::transmute_*` family | clippy | US003 |

Turn on the restriction lints for crates with unsafe code:

```toml
[lints.rust]
unsafe_op_in_unsafe_fn = "deny"

[lints.clippy]
undocumented_unsafe_blocks = "warn"
missing_safety_doc = "warn"
multiple_unsafe_ops_per_block = "warn"
```

## Measuring unsafe surface

- `cargo geiger` counts unsafe functions, expressions, impls, traits and methods in your crate and every
  dependency, marking crates that `forbid(unsafe_code)`.
- `/tmp/unsafe_inventory src/` gives the same picture for your own code with the documentation status of
  each item, which is what a review needs.
- Track the counts over time; new unsafe should arrive with its SAFETY argument and a test.

## Testing a safe abstraction

The goal is that **no safe code** can cause UB through your API. Test the edges a safe caller can reach:

- Empty, full and wrap-around states of buffers; zero-sized types (`Vec<()>`); maximum lengths.
- Panics in the middle of an operation (a panicking `Clone` or `Drop` inside `extend`): state must stay
  valid (no double drop, no exposed uninitialised memory). Use a `Drop` counter type to check.
- `Send`/`Sync` claims with compile-time assertions, and `compile_fail` doctests for what must not compile.
- Run all of it under Miri.

```rust
use std::cell::Cell;

/// Counts drops, to prove a container drops every element exactly once.
struct DropCounter<'a>(&'a Cell<usize>);

impl Drop for DropCounter<'_> {
    fn drop(&mut self) {
        self.0.set(self.0.get() + 1);
    }
}

#[test]
fn drops_each_element_once() {
    let drops = Cell::new(0);
    {
        let v = vec![DropCounter(&drops), DropCounter(&drops), DropCounter(&drops)];
        let mut it = v.into_iter();
        let _first = it.next();          // dropped at end of scope
    }                                    // iterator drops the remaining two
    assert_eq!(drops.get(), 3);
}
```

## A CI pipeline

```yaml
jobs:
  scan:
    steps:
      - run: |
          for t in unsafe_inventory safety_comments ub_patterns risky_calls ffi_and_globals; do
            rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
          /tmp/unsafe_inventory src/
          /tmp/ub_patterns src/ --strict
          /tmp/safety_comments src/ --strict
  miri:
    steps:
      - run: rustup toolchain install nightly --component miri
      - run: cargo +nightly miri test
      - run: MIRIFLAGS="-Zmiri-tree-borrows" cargo +nightly miri test
  asan:
    steps:
      - run: RUSTFLAGS="-Zsanitizer=address" cargo +nightly test --target x86_64-unknown-linux-gnu
  clippy:
    steps:
      - run: cargo clippy --all-targets -- -D clippy::undocumented_unsafe_blocks -D clippy::missing_safety_doc
```
