# Unsafe Superpowers and Safety Contracts

What `unsafe` actually unlocks, what "sound" means, and how to write the contracts (`# Safety` docs and
`// SAFETY:` comments) that make an unsafe audit possible.

## Contents

- [The five superpowers](#the-five-superpowers)
- [What unsafe does not change](#what-unsafe-does-not-change)
- [Safety vs soundness](#safety-vs-soundness)
- [Two kinds of unsafe keyword](#two-kinds-of-unsafe-keyword)
- [Writing `# Safety` sections](#writing--safety-sections)
- [Writing `// SAFETY:` comments](#writing--safety-comments)
- [unsafe_op_in_unsafe_fn](#unsafe_op_in_unsafe_fn)
- [Encapsulation: the module is the safety boundary](#encapsulation-the-module-is-the-safety-boundary)
- [Unsafe traits](#unsafe-traits)
- [Designing a minimal unsafe surface](#designing-a-minimal-unsafe-surface)
- [Crate-level policy](#crate-level-policy)
- [Audit checklist per item](#audit-checklist-per-item)

## The five superpowers

Inside an `unsafe` block (or, before edition 2024 by default, anywhere in an `unsafe fn` body) you may:

| # | Superpower | Example | What you now have to prove |
|---|-----------|---------|----------------------------|
| 1 | Dereference a raw pointer | `*ptr`, `&*ptr`, `&mut *ptr`, `(*p).field` | non-null, aligned, dereferenceable, points to a valid initialised value, aliasing rules for the reference you create |
| 2 | Call an `unsafe fn` (including foreign fns and intrinsics) | `v.get_unchecked(i)`, `libc::write(..)`, `String::from_utf8_unchecked` | every item in the callee's `# Safety` section |
| 3 | Access or modify a mutable static | `COUNTER += 1` on `static mut COUNTER` | no data race, no overlapping references (use `&raw` instead) |
| 4 | Implement an `unsafe trait` | `unsafe impl Send for Handle {}` | every invariant the trait's `# Safety` section requires of implementors |
| 5 | Read a field of a `union` | `u.as_f32` | the bytes are a valid value of the field's type |

Edition 2024 adds unsafe *attributes* (`#[unsafe(no_mangle)]`, `#[unsafe(export_name = "..")]`,
`#[unsafe(link_section = "..")]`) and `unsafe extern` blocks: these are not new powers but places where the
author asserts something the compiler cannot check (no symbol collision; foreign signatures are correct).
Inline assembly (`asm!`) is also only allowed inside `unsafe`.

## What unsafe does not change

- The borrow checker still runs on references. `unsafe` does not turn it off; it only allows the five
  operations above. Code that compiles only "because it is in unsafe" is usually using raw pointers to hide
  a borrow conflict, which is exactly where aliasing UB lives.
- Types still mean what they mean. A `&mut T` created in unsafe code must be unique for its whole lifetime,
  a `bool` must be 0 or 1, a `&T` must point to a valid `T`. The compiler optimises safe code around your
  unsafe block using those facts.
- UB is not "implementation-defined". The optimiser assumes it never happens; the effects can appear far
  from the bug, only in release, only on one target, or only after an unrelated compiler upgrade.

## Safety vs soundness

- **Safe code** cannot cause UB, whatever it does, provided all unsafe code it calls is sound.
- **Sound unsafe code / API**: no sequence of safe calls can make it cause UB. Soundness is a property of
  the *interface*, quantified over all safe callers, not just the ones that exist today.
- **Unsound**: there is some safe program that triggers UB through it. That is a bug even if no current
  caller does it, and it is treated as a security issue (RustSec advisories are filed for unsound crates).

```rust
// UNSOUND: a safe function that trusts its caller.
pub fn first_byte(p: *const u8) -> u8 {
    unsafe { *p } // safe callers can pass null or a dangling pointer
}

// SOUND alternative 1: make the caller prove it.
/// # Safety
///
/// `p` must be non-null and valid for a 1-byte read.
pub unsafe fn first_byte_raw(p: *const u8) -> u8 {
    // SAFETY: guaranteed by the caller per `# Safety`.
    unsafe { *p }
}

// SOUND alternative 2: take a type that already carries the proof.
pub fn first_byte_of(bytes: &[u8]) -> Option<u8> {
    bytes.first().copied()
}
```

The audit question for every safe `pub fn` containing unsafe: **"Which argument values or call sequences
would break the SAFETY comment?"** If any exist and are reachable from safe code, the fn is unsound.

## Two kinds of unsafe keyword

| Position | Meaning | Who proves |
|----------|---------|------------|
| `unsafe fn f()` | "calling me has preconditions" | the caller (documented in `# Safety`) |
| `unsafe trait T` | "implementing me has invariants other unsafe code relies on" | the implementor |
| `unsafe { .. }` | "I have checked the preconditions of the ops in here" | the author of the block |
| `unsafe impl T for X` | "I have checked the trait's invariants for X" | the author of the impl |
| `unsafe extern "C" { .. }` | "these foreign signatures are correct" | the author of the block |
| `#[unsafe(attr)]` | "this attribute's requirement (e.g. unique symbol) holds" | the author |

`unsafe fn` and `unsafe trait` *declare* obligations; blocks and impls *discharge* them. An audit therefore
checks two things: every declaration documents its obligations precisely, and every discharge cites them.

## Writing `# Safety` sections

Rules (clippy `missing_safety_doc` checks the section exists on public items):

1. One bullet per precondition, each independently checkable by a caller.
2. State requirements on values (`ptr` non-null, aligned for `T`, valid for reads of `len * size_of::<T>()`
   bytes), on lifetimes ("the memory must not be mutated while the returned slice is alive"), on threads
   ("must be called from the thread that created `handle`"), and on ownership ("`ptr` must have been
   returned by `Buffer::into_raw` and not freed").
3. Say what happens to ownership: does the function take ownership, borrow, or copy?
4. Do not write "the pointer must be valid": define valid (null? aligned? initialised? how many bytes?).

```rust
/// Builds a `&[T]` from a C array.
///
/// # Safety
///
/// - `data` must be non-null and aligned for `T`, even when `len == 0`.
/// - `data` must point to `len` consecutive, initialised values of `T` inside one allocation.
/// - The memory must not be written through any other pointer for the lifetime `'a`.
/// - `len * size_of::<T>()` must not exceed `isize::MAX`.
pub unsafe fn slice_from_c<'a, T>(data: *const T, len: usize) -> &'a [T] {
    // SAFETY: each requirement of `slice::from_raw_parts` is a bullet of our own contract.
    unsafe { std::slice::from_raw_parts(data, len) }
}
```

Note the unbounded `'a`: returning a reference with a caller-chosen lifetime is part of the contract and
must be stated ("for the lifetime `'a`").

## Writing `// SAFETY:` comments

A SAFETY comment is a proof sketch, not a restatement of the code.

| Bad | Good |
|-----|------|
| `// SAFETY: this is safe` | `// SAFETY: idx < self.len (checked on line 42) and items[..len] are initialised (struct invariant)` |
| `// SAFETY: ptr is valid` | `// SAFETY: ptr came from Box::into_raw in new() and is only freed in Drop, which cannot run while &self exists` |
| `// SAFETY: needed for performance` | `// SAFETY: chunks_exact(4) yields exactly 4 bytes, so the read is in bounds; read_unaligned has no alignment requirement` |

Conventions:
- Directly above the block or the statement containing it (`let x = unsafe { .. };`); clippy's
  `undocumented_unsafe_blocks` looks there. Also above every `unsafe impl`.
- One comment per block; if a block needs several paragraphs, it probably does too much: split it.
- Reference the invariant by name (`// Invariant: ...` on the struct field) and the check that
  establishes it.
- For FFI, cite the C library's documentation ("libfoo docs: `foo_get` returns a pointer owned by the
  handle, valid until `foo_free`").
- `clippy::unnecessary_safety_comment` flags SAFETY comments on safe code; keep them honest.

## unsafe_op_in_unsafe_fn

Before edition 2024 the whole body of an `unsafe fn` was an implicit unsafe block, so unsafe operations
inside it needed no SAFETY comment and were easy to miss. The `unsafe_op_in_unsafe_fn` lint (stable since
1.52, warn-by-default in edition 2024) requires an explicit block:

```rust
#![deny(unsafe_op_in_unsafe_fn)]

/// # Safety
///
/// `p` must be valid for reads and writes of one `u32` and not aliased.
pub unsafe fn double_in_place(p: *mut u32) {
    // SAFETY: valid and unaliased per this function's contract.
    let v = unsafe { p.read() };
    let doubled = v.wrapping_mul(2); // safe code stays outside the block
    // SAFETY: same pointer, same contract; no reference was created in between.
    unsafe { p.write(doubled) };
}
```

Set it in every crate that has `unsafe fn`, regardless of edition: `#![deny(unsafe_op_in_unsafe_fn)]` or
`[lints.rust] unsafe_op_in_unsafe_fn = "deny"` in Cargo.toml.

## Encapsulation: the module is the safety boundary

Unsafe code may rely on invariants that *safe code in the same module* could break, because privacy stops
code in other modules from doing so. This means:

- The unit of audit is the **module** (privacy boundary), not the unsafe block. A change to a safe line in
  the module (e.g. `self.len += 1` without a write) can make an unrelated unsafe block unsound.
- Fields that carry an invariant must be private; constructors and every `&mut self` method must preserve it.
- Never expose `&mut` to an invariant-carrying field (`pub fn len_mut(&mut self) -> &mut usize` breaks the
  `Vec`-like invariant from safe code).
- Document the invariant on the field so every editor sees it.

```rust
mod ascii {
    /// A string that is guaranteed to contain only ASCII bytes.
    pub struct AsciiStr {
        bytes: Vec<u8>, // Invariant: every byte is < 0x80 (so it is also valid UTF-8).
    }

    impl AsciiStr {
        pub fn new(s: &str) -> Option<Self> {
            s.is_ascii().then(|| Self { bytes: s.as_bytes().to_vec() })
        }

        pub fn push(&mut self, c: u8) -> bool {
            if c.is_ascii() {
                self.bytes.push(c);
                true
            } else {
                false
            }
        }

        pub fn as_str(&self) -> &str {
            // SAFETY: by the field invariant every byte is ASCII, and ASCII is valid UTF-8.
            unsafe { std::str::from_utf8_unchecked(&self.bytes) }
        }
    }
}
```

Adding `pub fn bytes_mut(&mut self) -> &mut Vec<u8>` to this module would make `as_str` unsound without
touching any unsafe line. Audits must read the whole module.

## Unsafe traits

Declare a trait `unsafe` when *other unsafe code* relies on implementors being correct, and a wrong safe
impl would cause UB (examples: `Send`, `Sync`, `GlobalAlloc`, `bytemuck::Pod`). If a buggy impl can only
cause wrong results or panics, keep the trait safe.

```rust
/// Types whose every bit pattern is a valid value and that contain no padding.
///
/// # Safety
///
/// Implementors must be `#[repr(C)]` or `#[repr(transparent)]`, have no padding bytes, contain only
/// fields that are themselves `PlainBytes`, and accept every bit pattern as a valid value.
pub unsafe trait PlainBytes: Copy + 'static {}

// SAFETY: u32 has no padding and every 32-bit pattern is a valid u32.
unsafe impl PlainBytes for u32 {}

pub fn read_plain<T: PlainBytes>(bytes: &[u8]) -> Option<T> {
    if bytes.len() < size_of::<T>() {
        return None;
    }
    // SAFETY: length checked; read_unaligned needs no alignment; T: PlainBytes accepts any bits.
    Some(unsafe { bytes.as_ptr().cast::<T>().read_unaligned() })
}
```

In real code prefer `bytemuck::Pod` / `zerocopy::FromBytes` derives, which verify the layout rules at
compile time instead of trusting the impl. (`size_of` in the prelude needs Rust 1.80+; otherwise
`std::mem::size_of`.)

`unsafe impl Send/Sync` is the most common unsafe trait impl and the most common source of unsoundness:
see [undefined-behavior-catalog.md](undefined-behavior-catalog.md#send-and-sync).

## Designing a minimal unsafe surface

1. Put every unsafe operation for one invariant in one small module with private fields.
2. Expose only safe functions whose preconditions are checked (return `Option`/`Result`) or encoded in
   types (`NonNull`, `&[T]`, newtypes with checked constructors).
3. Offer an `unsafe fn *_unchecked` variant only when profiling shows the check matters, and implement the
   safe version as `check + call unchecked`.
4. Keep raw pointers internal; convert to references at the narrowest point.
5. Prefer well-audited crates for common needs: `bytemuck`/`zerocopy` (casting), `memchr`, `smallvec`,
   `arrayvec`, `crossbeam`, `parking_lot`, `once_cell` (or std `OnceLock`/`LazyLock`), `pin-project-lite`,
   `libc`/`windows-sys`, `bindgen`/`cxx`.

## Crate-level policy

```rust
// Crates with no unsafe at all (most application and library crates):
#![forbid(unsafe_code)]

// Crates that need unsafe:
#![deny(unsafe_op_in_unsafe_fn)]
#![warn(
    clippy::undocumented_unsafe_blocks,
    clippy::missing_safety_doc,
    clippy::multiple_unsafe_ops_per_block,
)]
```

Or in Cargo.toml (Rust 1.74+ `[lints]` table; workspaces can share `[workspace.lints]`):

```toml
[lints.rust]
unsafe_op_in_unsafe_fn = "deny"

[lints.clippy]
undocumented_unsafe_blocks = "warn"
missing_safety_doc = "warn"
multiple_unsafe_ops_per_block = "warn"
```

`forbid` cannot be overridden by an inner `#[allow]`; `deny` can, which lets a single audited module opt
in with `#[allow(unsafe_code)]` while the rest of the crate stays unsafe-free.

## Audit checklist per item

For each unsafe block / fn / impl:

- [ ] Is there a safe API that does this? (If yes, stop and replace.)
- [ ] List each unsafe operation and its preconditions (std docs `# Safety` sections are authoritative).
- [ ] For each precondition: where is it established? Is that check reachable on every path?
- [ ] Can safe code in this module or a caller break the invariant (pub fields, `&mut` getters, `mem::swap`,
      `mem::forget`, panics in the middle of an update, re-entrancy through callbacks/`Drop`)?
- [ ] Panic safety: if a closure/user code panics halfway, is the data structure still valid when unwinding
      runs `Drop`? (Set `len` before calling user code, or use a guard that fixes up on drop.)
- [ ] Thread safety: are Send/Sync derived correctly for any type holding raw pointers or `UnsafeCell`?
- [ ] Lifetimes: does any returned reference have an unbounded or caller-chosen lifetime?
- [ ] Is there a Miri test that exercises this path (including edge cases len 0, len max, empty, full)?
