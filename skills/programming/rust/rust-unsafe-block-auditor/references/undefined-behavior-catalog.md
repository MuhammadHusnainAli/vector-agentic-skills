# Undefined Behavior Catalog

The UB classes an unsafe audit looks for, each with the rule, a bad example, a fixed version and how to
detect it. Authoritative sources: the Rust Reference "Behavior considered undefined", the std docs
`# Safety` sections, and the Rustonomicon. Rule ids (USxxx) refer to the scanners in `scripts/` (see SKILL.md).

## Contents

- [What counts as UB](#what-counts-as-ub)
- [Aliasing: Stacked Borrows and Tree Borrows](#aliasing-stacked-borrows-and-tree-borrows)
- [Mutation behind a shared reference](#mutation-behind-a-shared-reference)
- [Invalid values](#invalid-values)
- [Uninitialised memory and MaybeUninit](#uninitialised-memory-and-maybeuninit)
- [mem::zeroed](#memzeroed)
- [transmute pitfalls](#transmute-pitfalls)
- [slice::from_raw_parts](#slicefrom_raw_parts)
- [Vec::set_len and spare capacity](#vecset_len-and-spare-capacity)
- [Vec::from_raw_parts and Box::from_raw](#vecfrom_raw_parts-and-boxfrom_raw)
- [get_unchecked and unreachable_unchecked](#get_unchecked-and-unreachable_unchecked)
- [Dangling pointers from temporaries](#dangling-pointers-from-temporaries)
- [static mut](#static-mut)
- [Unions](#unions)
- [Send and Sync](#send-and-sync)
- [Pin projection](#pin-projection)
- [Panic safety and double drop](#panic-safety-and-double-drop)
- [Quick precondition table](#quick-precondition-table)

## What counts as UB

From the Reference (abridged): data races; accessing a dangling or misaligned pointer through a place
expression; violating the aliasing rules of references and `Box`; mutating immutable bytes (behind `&T`
without `UnsafeCell`, or in a non-`mut` static/const); calling a function with the wrong ABI or unwinding
out of a function whose ABI does not allow it; producing an invalid value (even if it is never read
again); invoking compiler intrinsics or `unsafe fn`s outside their contracts; executing code compiled with
target features the CPU lacks; incorrect inline assembly.

Library UB is separate but equally binding: violating a `# Safety` precondition of a std function (for
example a `str` that is not UTF-8, or `Vec::set_len` past initialised elements) lets std code make
assumptions that lead to language UB later.

## Aliasing: Stacked Borrows and Tree Borrows

Rust's aliasing model is not finalised; Miri implements two candidate models:

- **Stacked Borrows** (Miri default): each location keeps a stack of permissions; creating a new `&mut`
  (or using the parent) pops permissions derived from other paths, so older raw pointers become invalid.
- **Tree Borrows** (`MIRIFLAGS=-Zmiri-tree-borrows`): permissions form a tree; it accepts some patterns
  Stacked Borrows rejects (notably around raw pointers obtained from `&mut` and two-phase borrows) and is
  the likely basis of the eventual model.

Write code that passes **both**. The practical rules:

1. A `&mut T` is unique while it is live: no other pointer or reference may read or write that memory
   while it is in use (except pointers derived from it).
2. Creating or using a `&mut` (or the original owner) invalidates raw pointers derived *before* it.
3. Derive every raw pointer you need from **one** base pointer, and do not touch the owner until done.

```rust
// BAD: `r` is created after `p`, and using `p` afterwards is UB under Stacked Borrows.
fn bad() -> u32 {
    let mut x = 0u32;
    let p = &mut x as *mut u32;
    let r = &mut x; // new unique borrow of x
    unsafe { *p = 1 }; // p was derived from an older borrow: invalidated
    *r += 1;
    x
}

// GOOD: one base pointer; the owner is not used until the raw accesses finish.
fn good() -> u32 {
    let mut x = 0u32;
    let p = &raw mut x; // Rust 1.82+; use std::ptr::addr_of_mut!(x) on older compilers
    // SAFETY: p points to a live local; no reference to x exists while p is used.
    unsafe {
        *p = 1;
        *p += 1;
    }
    x
}
```

Common real-world variants:

| Pattern | Problem | Fix |
|---------|---------|-----|
| `let a = slice.as_mut_ptr(); let b = slice.as_mut_ptr();` then use `a` | second `as_mut_ptr()` reborrows the slice mutably, invalidating `a` | call `as_mut_ptr()` once, derive `b = a.add(k)` |
| `let p = v.as_ptr(); v.push(x); *p` | reallocation frees the old buffer | re-derive after any method that may reallocate |
| `&mut *ptr` while a `&*ptr` from the same pointer is still used | `&mut` asserts uniqueness | keep raw pointers; create references only for disjoint, non-overlapping uses |
| two `&mut` to fields obtained via raw pointers to the whole struct | each `&mut *struct_ptr` claims the whole struct | project with `&raw mut (*p).field` and create the field reference from that |
| `Box<T>` aliased by a raw pointer that outlives a move of the Box | moving a `Box` asserts uniqueness like `&mut` (under Stacked Borrows) | `Box::into_raw` and work only with the raw pointer, rebuild with `from_raw` |

## Mutation behind a shared reference

Writing through a pointer derived from `&T` is UB unless the memory is inside an `UnsafeCell`
(directly or via `Cell`, `RefCell`, `Mutex`, atomics, ...). `invalid_reference_casting` (deny-by-default
since 1.73) catches the direct `&T as *const T as *mut T` write.

```rust,compile_fail
use std::cell::UnsafeCell;

// BAD: &self gives shared access; writing through a cast pointer is UB.
pub struct Counter { n: u64 }
impl Counter {
    pub fn bump(&self) {
        let p = &self.n as *const u64 as *mut u64;
        unsafe { *p += 1 }; // UB
    }
}

// GOOD: interior mutability; still !Sync automatically because UnsafeCell is !Sync.
pub struct Counter2 { n: UnsafeCell<u64> }
impl Counter2 {
    pub fn bump(&self) {
        // SAFETY: Counter2 is !Sync, so no other thread can access `n`; no reference into `n`
        // escapes this method, so there is no aliasing &mut.
        unsafe { *self.n.get() += 1 };
    }
}
```

Safe alternative: `Cell<u64>` (single thread) or `AtomicU64` (shared).

## Invalid values

Producing (not just reading) any of these is UB, including in a local that is never used:

| Type | Invalid |
|------|---------|
| `bool` | any byte other than 0 or 1 |
| `char` | surrogates `0xD800..=0xDFFF` and values above `0x10FFFF` |
| fieldless `enum` | a discriminant that matches no variant |
| `&T`, `&mut T`, `Box<T>` | null, dangling, unaligned, or pointing to an invalid `T` |
| `fn` pointers | null |
| `NonNull<T>`, `NonZero<u32>` etc. | zero / null |
| integers, floats, raw pointers | uninitialised bytes (any bit pattern is fine once initialised) |
| `!` (never) | any value at all |
| `dyn Trait` pointer metadata | a vtable that is not a valid vtable for the trait |
| `str` | non-UTF-8 bytes (library invariant: std may assume it) |

```rust
// BAD
fn to_bool_bad(b: u8) -> bool {
    unsafe { std::mem::transmute(b) } // UB for b > 1
}

// GOOD
fn to_bool(b: u8) -> bool {
    b != 0
}

#[derive(Debug, Clone, Copy)]
#[repr(u8)]
enum Op { Add = 0, Sub = 1 }

impl TryFrom<u8> for Op {
    type Error = u8;
    fn try_from(v: u8) -> Result<Self, u8> {
        match v {
            0 => Ok(Op::Add),
            1 => Ok(Op::Sub),
            other => Err(other),
        }
    }
}
```

## Uninitialised memory and MaybeUninit

`mem::uninitialized()` (deprecated since 1.39, US004) is UB for almost every type because the value is
invalid the moment it exists. `MaybeUninit<T>` (1.36) is the replacement: it may hold uninitialised bytes,
and `assume_init` is the point where you promise it is fully initialised.

```rust
use std::mem::MaybeUninit;

#[derive(Debug)]
struct Point { x: f64, y: f64 }

fn make_point() -> Point {
    let mut p = MaybeUninit::<Point>::uninit();
    let ptr = p.as_mut_ptr();
    // SAFETY: field projection through a raw pointer creates no reference to uninitialised memory;
    // both fields are written before assume_init.
    unsafe {
        (&raw mut (*ptr).x).write(1.0);
        (&raw mut (*ptr).y).write(2.0);
        p.assume_init()
    }
}

// Arrays: an array of MaybeUninit needs no initialisation (inline const, 1.79+).
fn squares() -> [u64; 8] {
    let mut buf = [const { MaybeUninit::<u64>::uninit() }; 8];
    for (i, slot) in buf.iter_mut().enumerate() {
        slot.write((i as u64) * (i as u64));
    }
    // SAFETY: every element was written by the loop above.
    buf.map(|s| unsafe { s.assume_init() })
}
```

Rules:
- `MaybeUninit::uninit().assume_init()` in one expression is UB (US006, clippy `uninit_assumed_init`),
  except when `T` is itself `MaybeUninit` or an array of it.
- Never create `&T`/`&mut T` to uninitialised memory; write through `as_mut_ptr()` / `&raw mut`.
- `assume_init_read` copies the value out: the `MaybeUninit` still holds the bits; do not read twice for a
  non-`Copy` type (double drop).
- Padding bytes are uninitialised: transmuting a struct with padding to `[u8; N]` reads uninit memory.
  Use `bytemuck`/`zerocopy` derives, which reject padded types.
- `std::array::from_fn(|i| ...)` (1.63) builds arrays without any unsafe.

## mem::zeroed

`mem::zeroed::<T>()` is sound only if the all-zero bit pattern is a valid `T`: integers, floats, raw
pointers, `bool` (false), `char` ('\0'), `Option<&T>`, `Option<Box<T>>`, `Option<NonNull<T>>`
(all `None`), and `#[repr(C)]` structs made only of such fields (typical for C structs). It is UB
for references, `Box`, `Vec`, `String`, `NonNull`, `NonZero*`, function pointers, and enums without a
zero discriminant (US005; rustc's `invalid_value` lint warns on the obvious cases).

```rust
#[repr(C)]
struct CConfig { flags: u32, timeout_ms: u32, name: *const std::ffi::c_char }

fn config_zeroed() -> CConfig {
    // SAFETY: CConfig is repr(C) with integer and raw-pointer fields only, so all-zero is a
    // valid value (a null `name` is what the C API documents as "default").
    unsafe { std::mem::zeroed() }
}

// Usually better: no unsafe at all. (Raw pointers do not implement Default, so write it by hand.)
impl Default for CConfig {
    fn default() -> Self {
        Self { flags: 0, timeout_ms: 0, name: std::ptr::null() }
    }
}
```

For Rust-only structs always use `Default` (or a constructor) instead of `zeroed`.

## transmute pitfalls

`mem::transmute::<T, U>` checks only that the sizes are equal (at compile time). Everything else is on you
(US003):

| Pitfall | Example | Use instead |
|---------|---------|-------------|
| lifetime extension | `transmute::<&'a str, &'static str>(s)` | redesign ownership (`String`, `Arc<str>`, `Box::leak` if a leak is intended) |
| `&T` to `&mut T` | `transmute::<&T, &mut T>(r)` | always UB; use `UnsafeCell`-based types |
| int to bool/char/enum | `transmute::<u8, bool>(b)` | `b != 0`, `char::from_u32`, `TryFrom` |
| bytes to int | `transmute::<[u8; 4], u32>(b)` | `u32::from_ne_bytes(b)` / `from_le_bytes` |
| float bits | `transmute::<f32, u32>(f)` | `f.to_bits()`, `f32::from_bits(u)` |
| pointer casts | `transmute::<*const u8, *const u32>(p)` | `p.cast::<u32>()` |
| int to pointer | `transmute::<usize, *const T>(a)` | `ptr::with_exposed_provenance(a)` or keep the pointer (see provenance reference) |
| collections | `transmute::<Vec<u32>, Vec<f32>>(v)` | `into_iter().map(f32::from_bits).collect()`; or `from_raw_parts` with identical layout (clippy `unsound_collection_transmute`) |
| `repr(Rust)` structs | `transmute::<A, B>(a)` with same fields | layout of `repr(Rust)` is unspecified: add `#[repr(C)]` or convert field by field |
| inferred types | `let x: Foo = transmute(y)` | always write the turbofish `transmute::<Src, Dst>` (clippy `missing_transmute_annotations`) |

`transmute_copy` is worse: it does not even check sizes and reads `size_of::<Dst>()` bytes from the
source.

## slice::from_raw_parts

`std::slice::from_raw_parts(data, len)` requires (US013):

1. `data` non-null and aligned for `T`, **even when `len == 0`** (use `NonNull::dangling()` /
   `ptr::dangling()` for empty slices; a null pointer from C must be special-cased).
2. `data` valid for reads of `len * size_of::<T>()` bytes, all within one allocation.
3. All `len` elements initialised and valid values of `T`.
4. The memory not mutated (except inside `UnsafeCell`) for the returned lifetime; for
   `from_raw_parts_mut`, not accessed through any other pointer at all.
5. `len * size_of::<T>() <= isize::MAX`.

```rust
/// # Safety
///
/// If `len > 0`, `ptr` must be non-null, aligned, and valid for reads of `len` initialised `u16`s that
/// are not written while the returned slice is alive.
pub unsafe fn c_array<'a>(ptr: *const u16, len: usize) -> &'a [u16] {
    if len == 0 {
        return &[]; // C may pass NULL for empty arrays; from_raw_parts(NULL, 0) is UB
    }
    debug_assert!(!ptr.is_null() && ptr.is_aligned());
    // SAFETY: len > 0 and the caller guarantees the rest of the from_raw_parts contract.
    unsafe { std::slice::from_raw_parts(ptr, len) }
}
```

Since Rust 1.78 debug builds check some of these preconditions (null, alignment, size) at runtime and
abort; a release build silently has UB.

## Vec::set_len and spare capacity

`set_len(new_len)` requires `new_len <= capacity()` and the elements `old_len..new_len` to be initialised
(US007; clippy `uninit_vec` flags `with_capacity` followed by `set_len`).

```rust
// BAD: exposes uninitialised u8s as initialised.
fn read_bad(n: usize) -> Vec<u8> {
    let mut buf = Vec::with_capacity(n);
    unsafe { buf.set_len(n) };
    buf
}

// GOOD (safe): zeroing is cheap compared with I/O.
fn read_zeroed(n: usize) -> Vec<u8> {
    vec![0u8; n]
}

// GOOD (unsafe, when filling from a source that writes the bytes):
fn fill_from(src: &[u8]) -> Vec<u8> {
    let mut buf: Vec<u8> = Vec::with_capacity(src.len());
    let spare = buf.spare_capacity_mut(); // &mut [MaybeUninit<u8>], 1.60+
    for (dst, &b) in spare.iter_mut().zip(src) {
        dst.write(b);
    }
    // SAFETY: the loop wrote exactly src.len() elements (spare.len() >= src.len() by
    // with_capacity), so 0..src.len() is initialised and within capacity.
    unsafe { buf.set_len(src.len()) };
    buf
}
```

For FFI reads, pass `buf.as_mut_ptr()` and the capacity, then `set_len(bytes_written)` using the count the
C function reports, after checking it is `<= capacity`.

## Vec::from_raw_parts and Box::from_raw

`Vec::from_raw_parts(ptr, length, capacity)` (US014) requires that `ptr` was allocated by the same
allocator (the global allocator for `Vec<T>`) with exactly the layout of `capacity` elements of `T`,
`length <= capacity`, and the first `length` elements initialised. `String::from_raw_parts` adds UTF-8.
`Box::from_raw` requires a pointer from `Box::into_raw` (or an allocation with the same layout from the
global allocator), and that it is reconstructed only once.

```rust
use std::mem::ManuallyDrop;

/// Splits a Vec into raw parts without freeing it.
fn into_parts(v: Vec<u32>) -> (*mut u32, usize, usize) {
    let mut v = ManuallyDrop::new(v); // stable alternative to the unstable Vec::into_raw_parts
    (v.as_mut_ptr(), v.len(), v.capacity())
}

/// # Safety
///
/// The arguments must come from one call to `into_parts`, and be passed here exactly once.
unsafe fn from_parts(ptr: *mut u32, len: usize, cap: usize) -> Vec<u32> {
    // SAFETY: same allocator, element type, length and capacity as the original Vec (contract).
    unsafe { Vec::from_raw_parts(ptr, len, cap) }
}
```

Never: `Vec::from_raw_parts(malloc_ptr, n, n)` (C allocator), `from_raw_parts(ptr, len, len)` when the
original capacity was larger (wrong dealloc layout), `Box::from_raw` on a pointer to a stack value or to an
element inside a `Vec`.

## get_unchecked and unreachable_unchecked

Out-of-bounds `get_unchecked` is UB even if the value is never used (US012). Measure before using it:
LLVM removes bounds checks when it can see the proof, so hoist the check.

```rust
// Usually as fast as get_unchecked: one check, then the loop has none.
fn sum_first(v: &[u64], n: usize) -> u64 {
    let v = &v[..n]; // panics once if n > len
    v.iter().sum()
}

/// # Safety
///
/// `idx` must be < `table.len()`.
unsafe fn lookup(table: &[u32; 256], idx: usize) -> u32 {
    // SAFETY: caller guarantees idx < 256.
    unsafe { *table.get_unchecked(idx) }
}
```

`std::hint::unreachable_unchecked()` (US015) tells the optimiser the path is impossible; reaching it is UB.
`unreachable!()` costs one cold branch. `std::hint::assert_unchecked(cond)` (1.81) is the same contract for
a boolean condition. Use them only with a proof and a measured win.

## Dangling pointers from temporaries

```rust
use std::ffi::{CString, c_char};

unsafe extern "C" {
    fn puts(s: *const c_char) -> i32;
}

fn print_bad(msg: &str) {
    let p = CString::new(msg).unwrap().as_ptr(); // CString dropped at end of this statement
    unsafe { puts(p) }; // use-after-free
}

fn print_good(msg: &str) -> Result<(), std::ffi::NulError> {
    let c = CString::new(msg)?;
    // SAFETY: `c` is NUL-terminated and alive until the end of this function.
    unsafe { puts(c.as_ptr()) };
    Ok(())
}
```

rustc warns (`dangling_pointers_from_temporaries`, formerly `temporary_cstring_as_ptr`) for the direct
form; the auditor flags it as US010. The same bug happens with `String`, `Vec`, `format!(..).as_ptr()` and
any pointer derived from a temporary.

## static mut

Any access is `unsafe`, and any reference to a `static mut` is suspect: two references (one `&mut`) alive
at once, from two call frames or two threads, is UB. Edition 2024 makes `static_mut_refs` deny-by-default
(US008/US009); that includes implicit references from method calls (`LOG.push(x)` autoref-borrows `LOG`).

```rust
use std::sync::{Mutex, OnceLock};
use std::sync::atomic::{AtomicUsize, Ordering};

static HITS: AtomicUsize = AtomicUsize::new(0);
static NAMES: Mutex<Vec<String>> = Mutex::new(Vec::new()); // const Mutex::new: 1.63+
static CONFIG: OnceLock<String> = OnceLock::new();          // 1.70+

fn record(name: &str) {
    HITS.fetch_add(1, Ordering::Relaxed);
    NAMES.lock().unwrap().push(name.to_owned());
    let _cfg = CONFIG.get_or_init(|| "default".to_owned());
}
```

If a `static mut` must remain (embedded, FFI-owned buffer), only take raw pointers: `&raw mut BUF`
(1.82+, allowed in safe code) or `addr_of_mut!(BUF)`, and document the single-threaded or
interrupt-disabled argument at every access.

## Unions

Reading a union field is unsafe (superpower 5) and sound only if the stored bytes are a valid value of the
field read. Unions never drop their fields automatically; fields must be `Copy` or wrapped in
`ManuallyDrop`.

```rust
#[repr(C)]
union Bits {
    f: f32,
    u: u32,
    flag: bool,
}

fn demo() -> (u32, f32) {
    let b = Bits { f: 1.5 };
    // SAFETY: every 32-bit pattern is a valid u32.
    let u = unsafe { b.u };
    let c = Bits { u: 0x3fc0_0000 };
    // SAFETY: every 32-bit pattern is a valid f32 (NaNs included).
    let f = unsafe { c.f };
    // Reading `flag` from Bits { u: 2 } would be UB: 2 is not a valid bool.
    (u, f)
}
```

Safe alternatives: `f32::to_bits`/`from_bits`, `from_ne_bytes`, an enum when you need a tag.

## Send and Sync

`Send`: safe to move to another thread. `Sync`: `&T` is safe to share between threads (`T: Sync` iff
`&T: Send`). Raw pointers, `NonNull`, `UnsafeCell`, `Cell`, `Rc` opt out automatically; an `unsafe impl`
opts back in and must prove it (US011).

```rust
use std::marker::PhantomData;
use std::ptr::NonNull;

// BAD: unbounded T means MyBox<Rc<u8>> becomes Send and the Rc's non-atomic count races.
pub struct MyBox<T> { ptr: NonNull<T> }
unsafe impl<T> Send for MyBox<T> {}

// GOOD: same bounds as Box<T>; PhantomData<T> tells dropck and auto traits we own a T.
pub struct MyBox2<T> { ptr: NonNull<T>, _own: PhantomData<T> }
// SAFETY: MyBox2 uniquely owns its T (like Box<T>), so it is Send/Sync exactly when T is.
unsafe impl<T: Send> Send for MyBox2<T> {}
// SAFETY: &MyBox2<T> only gives out &T, so sharing it is sound when T: Sync.
unsafe impl<T: Sync> Sync for MyBox2<T> {}
```

Checklist for a `Sync` impl: every method reachable through `&self` that mutates must synchronise (atomics
or locks), and every `&T` it hands out must itself be `Sync`. For FFI handles, cite the C library's thread
safety statement: "handle may be used from another thread but not concurrently" means `Send` but not
`Sync`. Concurrency proofs need tests: see loom in [tooling-and-testing.md](tooling-and-testing.md).

## Pin projection

`Pin<&mut T>` promises the pointee will not move until dropped (unless `T: Unpin`). Projecting to a field
(`Pin<&mut Self>` -> `Pin<&mut Field>`) is sound only if all of these hold (US016):

1. The struct does not implement `Unpin` unconditionally (auto-derived `Unpin` is fine).
2. Its `Drop` impl never moves out of the pinned field (`Drop::drop` takes `&mut self`, so it could).
3. No method offers `&mut Field` (or a way to move it out, `mem::swap`) from `Pin<&mut Self>`.
4. The struct is not `#[repr(packed)]`.

```rust,ignore
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};

// GOOD: pin-project-lite generates the projection and enforces the rules.
pin_project_lite::pin_project! {
    pub struct Counted<F> {
        #[pin]
        inner: F,
        polls: u32,
    }
}

impl<F: Future> Future for Counted<F> {
    type Output = (F::Output, u32);

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        let this = self.project(); // inner: Pin<&mut F>, polls: &mut u32
        *this.polls += 1;
        match this.inner.poll(cx) {
            Poll::Ready(v) => Poll::Ready((v, *this.polls)),
            Poll::Pending => Poll::Pending,
        }
    }
}
```

The hand-written equivalent `unsafe { self.map_unchecked_mut(|s| &mut s.inner) }` becomes unsound the day
someone adds `impl<F> Unpin for Counted<F> {}` or a `Drop` that swaps `inner`. For stack pinning use
`std::pin::pin!(fut)` (1.68+) instead of `Pin::new_unchecked(&mut fut)`.

## Panic safety and double drop

Unsafe code must leave data structures valid if user code (clone, closures, `Drop`, comparison) panics.

```rust
// BAD: length covers slots that are not written yet; a panicking clone() makes Vec's Drop
// drop uninitialised memory.
fn extend_bad<T: Clone>(v: &mut Vec<T>, src: &[T]) {
    v.reserve(src.len());
    let old = v.len();
    unsafe {
        v.set_len(old + src.len());
        for (i, x) in src.iter().enumerate() {
            v.as_mut_ptr().add(old + i).write(x.clone());
        }
    }
}

// GOOD: safe and just as fast.
fn extend_good<T: Clone>(v: &mut Vec<T>, src: &[T]) {
    v.extend_from_slice(src);
}
```

Double drop: `ptr::read` duplicates ownership; the source must then be forgotten (`mem::forget`,
`ManuallyDrop`) or overwritten with `ptr::write` (which does not drop the old value). Leaking
(`mem::forget`) is safe, so unsafe code must never rely on a destructor running for soundness
(the "leakpocalypse" rule; see `std::thread::scope` for the safe design).

## Quick precondition table

| Operation | Preconditions to prove |
|-----------|------------------------|
| `*p` / `&*p` / `&mut *p` | non-null, aligned, dereferenceable, valid `T`, aliasing for the reference's lifetime |
| `p.add(n)` / `p.offset(n)` | result within the same allocation (or one past the end), no overflow of `isize` bytes |
| `p.read()` / `p.write(v)` | as `*p` but no reference created; `write` does not drop the old value |
| `read_unaligned` / `write_unaligned` | as above minus alignment |
| `ptr::copy_nonoverlapping(src, dst, n)` | both valid for `n` elements, aligned, regions do not overlap |
| `slice::from_raw_parts(p, n)` | see above: non-null/aligned even for 0, one allocation, initialised, no mutation, size limit |
| `str::from_utf8_unchecked(b)` | `b` is valid UTF-8 |
| `String::from_utf8_unchecked(v)` | `v` is valid UTF-8 |
| `Vec::set_len(n)` | `n <= capacity`, elements `..n` initialised |
| `Vec::from_raw_parts(p, len, cap)` | global allocator, same `T` layout, original capacity, `len <= cap`, initialised |
| `Box::from_raw(p)` | from `Box::into_raw` of same `T`, once |
| `MaybeUninit::assume_init` | fully initialised valid value |
| `NonNull::new_unchecked(p)` | `p` non-null |
| `char::from_u32_unchecked(u)` | valid Unicode scalar value |
| `unwrap_unchecked()` | is `Some`/`Ok` |
| `get_unchecked(i)` | `i` in bounds |
| `unreachable_unchecked()` | never reached |
| `Pin::new_unchecked(p)` | pointee never moved again until dropped; `Deref`/`DerefMut`/`Drop` of the pointer type do not move it |
| `transmute::<A, B>` | the bits of `A` are a valid `B`; lifetimes and provenance are preserved correctly |
| union field read | stored bytes valid for that field's type |
| `env::set_var` (2024) | no other thread reads or writes the environment concurrently |
