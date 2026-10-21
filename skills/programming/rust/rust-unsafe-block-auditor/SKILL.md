---
name: rust-unsafe-block-auditor
description: "Audit unsafe Rust for soundness: inventory every unsafe block, unsafe fn, unsafe impl/trait, extern block and unsafe attribute, check // SAFETY: comments and # Safety docs, and classify each as sound, needs-justification or likely UB, proposing safe alternatives first. Covers the five unsafe superpowers, aliasing (Stacked/Tree Borrows), invalid values, MaybeUninit vs mem::zeroed/uninitialized, transmute, slice::from_raw_parts, Vec::set_len/from_raw_parts, get_unchecked, CString::as_ptr dangling, unsafe impl Send/Sync, Pin projection, FFI (extern \"C\", repr(C), C-unwind, Box::into_raw/from_raw), strict provenance, static mut and &raw, edition 2024 (unsafe extern, #[unsafe(no_mangle)], unsafe_op_in_unsafe_fn, env::set_var), Miri, sanitizers, cargo-fuzz, loom, cargo-geiger and clippy safety lints. Use when reviewing or writing unsafe code or FFI bindings, debugging a segfault, heap corruption or Miri error, migrating to edition 2024, or asked whether unsafe code is sound."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Unsafe Block Auditor

Audit `unsafe` Rust the way a soundness reviewer does: find every place the compiler stopped checking,
write down the invariant each one relies on, prove it holds for every input a safe caller can supply, and
replace the unsafe code with a safe API whenever one exists. The output is a per-item verdict (sound /
needs-justification / likely UB) with evidence, a safe alternative first, and a minimal documented unsafe
fallback second. Small std-only Rust programs in `scripts/` produce the inventory (a mini cargo-geiger) and
flag 28 known hazard patterns from source text; Miri, sanitizers and fuzzing confirm the verdicts.

## Trigger Conditions

Activate this skill when the user:
- Asks "is this unsafe sound?", wants an unsafe/FFI code review, or asks for `// SAFETY:` comments or
  `# Safety` docs to be written
- Uses raw pointers, `transmute`, `MaybeUninit`, `mem::zeroed`, `set_len`, `from_raw_parts`,
  `get_unchecked`, `static mut`, unions, inline `asm!`, `Pin::new_unchecked`, or `unsafe impl Send/Sync`
- Writes bindings with `extern "C"`, `#[repr(C)]`, `CString`/`CStr`, callbacks, `Box::into_raw`
- Sees a segfault, double free, `free(): invalid pointer`, heap corruption, a Miri "Undefined Behavior"
  error, an ASan/TSan report, or "panic in a function that cannot unwind"
- Migrates to edition 2024 and hits `unsafe_op_in_unsafe_fn`, `static_mut_refs`, `missing_unsafe_on_extern`,
  `unsafe_attr_outside_unsafe` or `deprecated_safe_2024` (`env::set_var`)
- Wants to measure or reduce unsafe surface (cargo-geiger, `#![forbid(unsafe_code)]`) or set up Miri/loom/fuzzing

## Workflow

```
0. BUILD     -> once: for t in unsafe_inventory safety_comments ub_patterns risky_calls ffi_and_globals; do
                  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
1. INVENTORY -> /tmp/unsafe_inventory src/
                every unsafe block/fn/impl/trait/extern block with location, size, SAFETY status, risky ops
                then: /tmp/ub_patterns src/  /tmp/risky_calls src/  /tmp/ffi_and_globals src/  /tmp/safety_comments src/
2. AVOID     -> For each item: does a safe API do the same job? (table below) If yes, replace it.
3. CONTRACT  -> For what remains, write the invariant: `# Safety` on unsafe fn/trait (caller's duty),
                `// SAFETY:` on every block/impl (why the duty is met HERE). No proof -> needs-justification.
4. PROVE     -> Check each unsafe op against its preconditions (references/undefined-behavior-catalog.md):
                validity, alignment, initialisation, aliasing, lifetime, provenance, thread safety, unwinding.
                Ask: can SAFE code calling this API break the invariant? If yes -> unsound API.
5. CLASSIFY  -> sound | needs-justification | likely UB, with file:line and rule id (USxxx)
6. VERIFY    -> cargo +nightly miri test (also MIRIFLAGS=-Zmiri-tree-borrows), sanitizers for FFI,
                loom for atomics, cargo-fuzz for parsers; every scanner with --strict in CI
```

## Classification

| Verdict | Criteria | Action |
|---------|----------|--------|
| **sound** | Every precondition of every unsafe op is proven from local facts or a documented, enforced invariant (private fields, checked constructor); no safe caller can violate it; Miri clean | Keep; SAFETY comment states the proof; consider a `debug_assert!` of the precondition |
| **needs-justification** | Plausibly correct but the proof is missing or relies on something not enforced (an undocumented caller duty, a "nobody calls this from two threads" assumption, a C library contract not cited) | Write the contract; enforce the invariant with types/privacy or make the fn `unsafe fn`; add a Miri test |
| **likely UB** | A precondition is violated on a reachable path, or a safe caller can trigger it (safe fn derefs a raw pointer argument, `&self -> &mut T`, zeroed reference, dangling `CString` pointer, `set_len` over uninit, unbounded `unsafe impl<T> Send`) | Fix before merge; add a regression test that fails under Miri |

Unsoundness is a property of the API, not of today's callers: a safe function that is UB for *some* input
is unsound even if no current caller passes that input.

## Safe Alternatives First

| Unsafe pattern | Safe replacement |
|----------------|------------------|
| `transmute::<[u8; 4], u32>(b)` / `transmute::<u32, f32>` | `u32::from_ne_bytes(b)` (`from_le_bytes`/`from_be_bytes`), `f32::from_bits` |
| `transmute` between pointer types / `&T -> &U` | `ptr.cast::<U>()`; `bytemuck::cast_ref` / `zerocopy` derive (checked layout) |
| `mem::zeroed()` / `mem::uninitialized()` | `Default::default()`, `[0u8; N]`, `MaybeUninit` written field by field |
| `Vec::with_capacity(n)` + `set_len(n)` | `vec![0; n]`, `resize`, `extend`, or write `spare_capacity_mut()` then `set_len` |
| `get_unchecked(i)` | `get(i)`, iterators, `chunks_exact`, an `assert!(i < len)` hoisted before the loop |
| `slice::from_raw_parts` on your own data | keep the slice (`&[T]`), `split_at_mut`, `chunks_mut`, `as_chunks` |
| `static mut` | `AtomicU64`, `Mutex`/`RwLock`, `OnceLock`/`LazyLock` (1.80+), `thread_local!` |
| `&self -> &mut T` via `UnsafeCell` | `RefCell`, `Cell`, `Mutex`, or `&mut self` |
| `unreachable_unchecked()` | `unreachable!()`; restructure the match so the arm does not exist |
| manual pin projection | `pin-project-lite::pin_project!`, `std::pin::pin!` (1.68+), `Box::pin` |
| `unsafe impl Send` for a raw-pointer wrapper | `NonNull<T>` + `PhantomData<T>` + bounded impl, or store an index/`Arc<Mutex<_>>` |
| hand-written FFI declarations | `bindgen` (C -> Rust), `cbindgen` (Rust -> C), `cxx` for C++, `CString`/`CStr` |
| int -> pointer casts | strict provenance: `ptr.map_addr`, `with_addr`, `ptr::without_provenance` (1.84+) |
| union for type punning | `from_ne_bytes`, `to_bits`, an enum, or `bytemuck::Pod` |

## Core Rules

1. **Unsafe blocks are proof obligations, not permission.** The block must uphold every precondition of
   every unsafe operation inside it, and the module must keep the invariant for all safe code paths.
2. **Every `unsafe {}` and `unsafe impl` gets `// SAFETY:`** directly above it, naming each precondition
   and why it holds here. Every `unsafe fn` and `unsafe trait` gets a `# Safety` doc section listing the
   caller's (or implementor's) duties.
3. **Keep blocks tiny.** One unsafe operation per block where practical
   (`clippy::multiple_unsafe_ops_per_block`); safe code stays outside.
4. **Encapsulate invariants behind privacy.** The invariant lives in private fields of one module; every
   way to construct or mutate them is checked. Unsafe code may trust only that module, never callers.
5. **A safe fn must be sound for all inputs.** Raw-pointer parameters mean `unsafe fn` (or take `&T`,
   `&[T]`, `NonNull<T>`). Never return `&mut` from `&self` without a guard.
6. **References are stronger than pointers.** A `&T`/`&mut T` must be non-null, aligned, point to a valid
   value, and obey aliasing for its whole lifetime. Stay in raw pointers (`&raw mut`, `addr_of_mut!`,
   `ptr.add`) until the access is proven.
7. **Validity is checked at every typed copy.** `bool` must be 0/1, `char` a scalar value, enums a
   declared discriminant, references non-null and aligned, and no uninitialised bytes in integers.
8. **FFI: own the boundary.** `#[repr(C)]` on shared types, null checks on every incoming pointer, clear
   ownership (who frees, with which allocator), no panic crossing `extern "C"` (catch it or use `"C-unwind"`).
9. **Send/Sync impls are global claims.** Bound every type parameter (`unsafe impl<T: Send> Send`) and
   prove no unsynchronised shared mutation.
10. **Verify mechanically.** Miri for every unsafe module's tests, sanitizers for FFI, loom for lock-free
    code, fuzzing for parsers that use unchecked indexing.

## Writing Safety Contracts

```rust
// Edition 2024 (MSRV 1.85). Crate root:
#![deny(unsafe_op_in_unsafe_fn)]
#![warn(clippy::undocumented_unsafe_blocks, clippy::multiple_unsafe_ops_per_block)]

/// Splits `values` into `[0, mid)` and `[mid, len)`. (std has `split_at_mut`; this is the textbook shape.)
pub fn split_halves(values: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    let len = values.len();
    assert!(mid <= len, "mid {mid} > len {len}");
    let ptr = values.as_mut_ptr();
    // SAFETY: mid <= len (asserted above), so both ranges lie inside the one allocation of
    // `values`, are initialised, and do not overlap; both inherit the unique borrow of `values`.
    unsafe {
        (
            std::slice::from_raw_parts_mut(ptr, mid),
            std::slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}

/// Reads the element at `i` without a bounds check.
///
/// # Safety
///
/// `i` must be less than `slice.len()`.
pub unsafe fn read_unchecked(slice: &[u64], i: usize) -> u64 {
    debug_assert!(i < slice.len());
    // SAFETY: the caller guarantees `i < slice.len()` (see `# Safety`).
    unsafe { *slice.get_unchecked(i) }
}
```

Encapsulation: the invariant "`len` elements are initialised" is guarded by privacy, so safe code in other
modules cannot break it.

```rust
mod stack {
    use std::mem::MaybeUninit;

    pub struct Stack<T, const N: usize> {
        items: [MaybeUninit<T>; N], // invariant: items[..len] are initialised
        len: usize,                 // private: only this module can change it
    }

    impl<T, const N: usize> Stack<T, N> {
        pub const fn new() -> Self {
            Self { items: [const { MaybeUninit::uninit() }; N], len: 0 } // inline const: 1.79+
        }

        pub fn push(&mut self, v: T) -> Result<(), T> {
            let Some(slot) = self.items.get_mut(self.len) else {
                return Err(v); // full
            };
            slot.write(v);
            self.len += 1;
            Ok(())
        }

        pub fn pop(&mut self) -> Option<T> {
            self.len = self.len.checked_sub(1)?;
            // SAFETY: the slot at the old `len - 1` was initialised by `push`; len was
            // decremented first, so the value is moved out exactly once.
            Some(unsafe { self.items[self.len].assume_init_read() })
        }
    }

    impl<T, const N: usize> Drop for Stack<T, N> {
        fn drop(&mut self) {
            while self.pop().is_some() {}
        }
    }
}
```

## Edition 2024 Changes (Rust 1.85)

| 2021 code | 2024 requirement | Lint / fix |
|-----------|------------------|------------|
| unsafe ops directly in an `unsafe fn` body | each op needs its own `unsafe {}` + SAFETY | `unsafe_op_in_unsafe_fn` now warn-by-default |
| `extern "C" { fn f(); }` | `unsafe extern "C" { fn f(); pub safe fn g(); }` | `missing_unsafe_on_extern`; `unsafe extern` accepted since 1.82 |
| `#[no_mangle]`, `#[export_name]`, `#[link_section]` | `#[unsafe(no_mangle)]` etc. | `unsafe_attr_outside_unsafe`; accepted since 1.82 |
| `&STATIC_MUT`, `STATIC_MUT.push(x)` | `&raw const`/`&raw mut STATIC_MUT` (1.82) or replace the static | `static_mut_refs` deny-by-default |
| `std::env::set_var(k, v)` / `remove_var` | `unsafe { ... }` with a single-threaded SAFETY argument | `deprecated_safe_2024` |
| `CommandExt::before_exec` | unsafe to call | `deprecated_safe_2024` |

```rust
use std::sync::atomic::{AtomicU64, Ordering};

unsafe extern "C" {
    pub safe fn abs(x: i32) -> i32;           // declared safe: callable without unsafe
    fn strlen(s: *const std::ffi::c_char) -> usize; // unqualified items stay unsafe to call
}

static REQUESTS: AtomicU64 = AtomicU64::new(0); // instead of `static mut REQUESTS: u64`

static mut SCRATCH: [u8; 64] = [0; 64];
pub fn scratch_ptr() -> *mut u8 {
    (&raw mut SCRATCH).cast::<u8>() // creating a raw pointer to a static mut is safe since 1.82
}

pub fn bump() -> u64 {
    REQUESTS.fetch_add(1, Ordering::Relaxed) + 1
}

pub fn len_of(s: &std::ffi::CStr) -> usize {
    // SAFETY: `s` is a valid NUL-terminated string borrowed for the duration of the call.
    unsafe { strlen(s.as_ptr()) }
}
```

`cargo fix --edition` rewrites most of these mechanically; it cannot write the SAFETY arguments.

## Symptom -> Cause -> Fix

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Miri: `... tag does not exist in the borrow stack` / Tree Borrows `forbidden` access | aliasing: a `&mut` used after another pointer/ref to the same memory was created, or a write through a pointer derived from `&T` | derive all pointers from one raw pointer (`as_mut_ptr` once); stay raw until done; `UnsafeCell` for shared mutation |
| Miri: `constructing invalid value` | transmute/zeroed into `bool`, `char`, enum, reference, `NonNull`, `NonZero*` | checked conversion (`char::from_u32`, `bool` from `!= 0`, `TryFrom` for enums) |
| Miri: `using uninitialized data` | `set_len` before writes, `assume_init` too early, reading padding bytes | write every element first; `MaybeUninit` arrays; never transmute structs with padding to bytes |
| Miri/ASan: use-after-free, dangling pointer | `CString::new(..).unwrap().as_ptr()`, pointer into a `Vec` that reallocated, returning `as_ptr()` of a local | bind owners to a variable that outlives every use; re-derive pointers after `push` |
| `free(): invalid pointer`, double free, Miri `incorrect layout on deallocation` | `Vec::from_raw_parts` with wrong capacity, freeing C memory with Rust (or reverse), `Box::from_raw` twice | free with the allocator that allocated; return a free fn across FFI; `into_raw`/`from_raw` exactly once |
| Miri: misaligned pointer / `alignment N is required` | casting `*const u8` to `*const u32` and dereferencing | `ptr.read_unaligned()`, `u32::from_le_bytes(chunk.try_into()?)` |
| Miri/TSan: data race | `static mut`, unsynchronised `UnsafeCell`, wrong `unsafe impl Sync` | atomics with correct `Ordering`, `Mutex`; remove the Sync impl; loom test |
| Process aborts with `panic in a function that cannot unwind` | panic escaping `extern "C"` (aborts since 1.81) | `catch_unwind` at the boundary, return an error code; or `extern "C-unwind"` |
| Random crash only in release | UB the optimiser exploited: `unreachable_unchecked`, `get_unchecked` OOB, invalid enum | run the debug build under Miri; replace with checked versions; debug assertions on preconditions |
| Self-referential future corrupts after move | manual `Pin` projection or `Pin::new_unchecked` on a movable value | `pin-project-lite`, `pin!`, never expose `&mut` to a structurally pinned field |
| Works on x86-64, fails on ARM / 32-bit / big-endian | alignment, `usize` width, endianness assumptions in transmute | Miri with `--target i686-unknown-linux-gnu` and `--target s390x-unknown-linux-gnu`; explicit `from_le_bytes` |

## Verification

```bash
rustup +nightly component add miri
cargo +nightly miri test                                   # Stacked Borrows (default)
MIRIFLAGS="-Zmiri-tree-borrows" cargo +nightly miri test   # Tree Borrows model
MIRIFLAGS="-Zmiri-strict-provenance" cargo +nightly miri test
cargo +nightly miri test --target s390x-unknown-linux-gnu  # big-endian
RUSTFLAGS="-Zsanitizer=address" cargo +nightly test --target x86_64-unknown-linux-gnu
RUSTFLAGS="--cfg loom" cargo test --release --test loom_queue
cargo +nightly fuzz run parse_header -- -max_total_time=300
cargo geiger                                               # unsafe usage across the dependency tree
cargo clippy -- -W clippy::undocumented_unsafe_blocks -W clippy::missing_safety_doc
```

Miri cannot execute most foreign (C) functions: test FFI with sanitizers and keep the Rust-side logic
testable without the C library. Details: [tooling-and-testing.md](references/tooling-and-testing.md).

## Output Format

For each audited unsafe item:
1. **Location and kind** - `file:line`, block / unsafe fn / unsafe impl / extern / attribute, rule ids.
2. **Verdict** - sound, needs-justification or likely UB.
3. **Preconditions** - each unsafe operation with its preconditions and whether each is proven (cite the
   line that proves it) or violated (show the input or call sequence that breaks it).
4. **Safe alternative** - complete replacement code if one exists; otherwise the minimal unsafe version
   with its `// SAFETY:` comment and `# Safety` doc.
5. **Verification** - the Miri/sanitizer/loom/fuzz command and a test that would catch a regression.

Finish with a summary table (item, verdict, fix) and crate-level recommendations (`#![forbid(unsafe_code)]`
in safe crates, lint attributes, CI jobs).

## Scripts

Small, standard-library-only Rust programs that read source text (comments, strings, raw strings, char
literals and lifetimes handled; braces matched); they never compile or run your code. Build each once with
`rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>`.

| Script | Rules | Job |
|--------|-------|-----|
| `scripts/unsafe_inventory.rs` | - | every unsafe item: kind, line, size, `documented` / `undocumented` / `undocumented+risky`, risky ops inside; totals per file |
| `scripts/safety_comments.rs` | US001, US002, US018, US026-US028 | missing `// SAFETY:` and `# Safety`, oversized blocks, crate-level safety lints |
| `scripts/ub_patterns.rs` | US003-US007, US010, US024 | likely UB: transmute, uninitialized, invalid zeroed, uninit().assume_init(), set_len before init, CString temp pointer, &self -> &mut |
| `scripts/risky_calls.rs` | US012-US016, US022, US025 | needs a written argument: unchecked calls, from_raw_parts, from_raw, unreachable_unchecked, Pin unchecked, int-to-ptr casts, asm |
| `scripts/ffi_and_globals.rs` | US008, US009, US011, US017, US019-US021, US023 | static mut and references to it, Send/Sync impls, panicking extern "C", edition-2024 unsafe syntax, safe fns dereferencing raw pointers |
| `scripts/unsafe_items.rs`, `scripts/rsparse.rs`, `scripts/cli.rs` | - | shared modules: unsafe item finder with SAFETY/# Safety detection, source scanner, options and report |

```bash
/tmp/unsafe_inventory src/                              # walk *.rs (skips target/, .git/)
/tmp/unsafe_inventory src/ffi.rs --json > unsafe.json   # machine-readable inventory
cat lib.rs | /tmp/ub_patterns -                         # stdin
/tmp/safety_comments src/ --strict --max-block-lines 20 # CI gate (exit 1 on findings)
/tmp/risky_calls src/ --select US012,US013 --ignore US022
/tmp/ffi_and_globals --list-rules                       # each scanner lists its rules with why and fix
```

Triage: `ub_patterns` findings are presumed **likely UB** until disproved; `risky_calls` findings are
**needs-justification** (they stay quiet inside an unsafe block or fn that already has its SAFETY comment or
`# Safety` doc, except int-to-ptr casts); `safety_comments` findings mean the reasoning is missing. The final
verdict "sound" is yours to make after step 4. Silence one line with `// noqa: US012`. Exit codes: 0 no
findings (or without `--strict`), 1 findings with `--strict`, 2 usage error or unreadable file.

| Rule | Name | Sev | Flags |
|------|------|-----|-------|
| US001 | missing-safety-comment | medium | unsafe block / impl without `// SAFETY:` |
| US002 | missing-safety-doc | medium | unsafe fn / trait without `# Safety` (marked private when it is) |
| US003 | transmute | high | any transmute; message says when it mints `'static` |
| US004 | mem-uninitialized | high | `mem::uninitialized()` |
| US005 | zeroed-invalid-type | high | `mem::zeroed` for `&T`, `Box`, `Vec`, `String`, `NonNull`, fn ptr, `bool`, `char`, or local structs holding them |
| US006 | uninit-assume-init | high | `MaybeUninit::uninit().assume_init()` (not the `[MaybeUninit<T>; N]` idiom) |
| US007 | set-len-before-init | high | `set_len(n)` with no visible write before it |
| US008 | static-mut | medium | `static mut` items |
| US009 | static-mut-ref | high | `&X`, `&mut X`, `X.method()` on a `static mut` (`&raw` is fine) |
| US010 | cstring-temp-ptr | high | `CString::new(..).unwrap().as_ptr()` temporary |
| US011 | unsafe-impl-send-sync | medium | no SAFETY argument, or unbounded `impl<T> Send` |
| US012 | unchecked-call | low | `get_unchecked`, `unwrap_unchecked`, `from_utf8_unchecked`, `new_unchecked` ... |
| US013 | slice-from-raw-parts | low | `slice::from_raw_parts(_mut)` |
| US014 | owned-from-raw | medium | `Vec/String::from_raw_parts`, `Box/Arc/Rc/CString::from_raw` |
| US015 | unreachable-unchecked | medium | `hint::unreachable_unchecked()` |
| US016 | pin-unchecked | medium | `Pin::new_unchecked`, `map_unchecked(_mut)`, `get_unchecked_mut()` |
| US017 | extern-c-may-panic | low | `extern "C" fn` with unwrap/expect/panic and no `catch_unwind` |
| US018 | large-unsafe-block | low | block longer than `--max-block-lines` (default 15) |
| US019 | extern-block-not-unsafe | low | `extern "C" {}` without `unsafe` (2024) |
| US020 | unsafe-attr-2024 | low | `#[no_mangle]`/`#[export_name]`/`#[link_section]` not `#[unsafe(..)]` |
| US021 | env-set-var | low | `env::set_var` / `remove_var` |
| US022 | int-to-ptr-cast | low | `0x1000 as *const T`, `(p as usize ...) as *const T` |
| US023 | safe-fn-derefs-raw-ptr | high | safe `pub fn` dereferencing a raw-pointer parameter (also `extern "C"` ones) |
| US024 | mut-from-ref | high | `fn f(&self) -> &mut T` built with unsafe |
| US025 | inline-asm | low | `asm!`, `global_asm!`, `naked_asm!` |
| US026 | forbid-unsafe-code | info | crate root with no unsafe and no `forbid(unsafe_code)` |
| US027 | unsafe-op-lint | info | unsafe fns but no `unsafe_op_in_unsafe_fn` lint (editions before 2024) |
| US028 | safety-comment-lint | info | unsafe blocks but no `clippy::undocumented_unsafe_blocks` |

Crate-level rules (US026-US028) run on crate roots (`lib.rs`, `main.rs`, files with `#![..]`) and also read
`[lints]` in ancestor `Cargo.toml` files.

## Additional Resources

| File | Content |
|------|---------|
| [unsafe-superpowers-and-contracts.md](references/unsafe-superpowers-and-contracts.md) | The five superpowers, soundness vs safety, writing `# Safety`/`// SAFETY:`, encapsulation with privacy, unsafe traits, review checklist |
| [undefined-behavior-catalog.md](references/undefined-behavior-catalog.md) | Aliasing (Stacked/Tree Borrows), invalid values, uninit memory, transmute, from_raw_parts, set_len, static mut, unions, Send/Sync, Pin: bad vs fixed code |
| [raw-pointers-and-provenance.md](references/raw-pointers-and-provenance.md) | Raw pointer rules, `NonNull`, `&raw`/`addr_of!`, alignment, offset/add, strict provenance APIs, unchecked hints, inline asm |
| [ffi-boundaries.md](references/ffi-boundaries.md) | `extern "C"`, `repr(C)`, `unsafe extern` blocks, CString/CStr, null checks, ownership across FFI, callbacks, panics and `C-unwind`, bindgen/cbindgen |
| [tooling-and-testing.md](references/tooling-and-testing.md) | Miri flags, sanitizers, cargo-fuzz, loom, Kani, cargo-geiger, clippy/rustc safety lints, CI pipeline |
| [version-history.md](references/version-history.md) | Unsafe-related stabilisations by Rust version and the edition 2024 unsafe changes |
