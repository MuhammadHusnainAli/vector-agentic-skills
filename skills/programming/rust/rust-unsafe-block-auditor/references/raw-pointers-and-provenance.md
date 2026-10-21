# Raw Pointers and Provenance

How to work with raw pointers without creating invalid references, keep pointer provenance intact, and
review the low-level escape hatches (`NonNull`, unchecked hints, volatile, inline assembly, target
features).

## Contents

- [Raw pointer basics](#raw-pointer-basics)
- [Creating pointers without references: `&raw` and `addr_of!`](#creating-pointers-without-references-raw-and-addr_of)
- [Alignment and packed structs](#alignment-and-packed-structs)
- [Pointer arithmetic](#pointer-arithmetic)
- [NonNull, variance and PhantomData](#nonnull-variance-and-phantomdata)
- [Provenance](#provenance)
- [Strict provenance APIs (1.84)](#strict-provenance-apis-184)
- [Exposed provenance and MMIO](#exposed-provenance-and-mmio)
- [Volatile access](#volatile-access)
- [Unchecked hints](#unchecked-hints)
- [Inline assembly](#inline-assembly)
- [Target features](#target-features)
- [Review checklist](#review-checklist)

## Raw pointer basics

- Creating, copying, comparing and casting raw pointers is safe; **dereferencing** is unsafe.
- `*const T` and `*mut T` differ only in intent and variance; a `*mut T` obtained from `&T` is still not
  writable (the memory is behind a shared reference).
- Prefer the typed methods over `as` casts so the compiler can catch mistakes:

| Instead of | Use | Since |
|------------|-----|-------|
| `p as *const U` | `p.cast::<U>()` (keeps mutability) | 1.38 |
| `p as *mut T` (from `*const T`) | `p.cast_mut()` | 1.65 |
| `p as *const T` (from `*mut T`) | `p.cast_const()` | 1.65 |
| `&x as *const T` | `ptr::from_ref(&x)` | 1.76 |
| `&mut x as *mut T` | `ptr::from_mut(&mut x)` | 1.76 |
| `p as usize` | `p.addr()` (strict provenance) | 1.84 |

clippy's `ptr_as_ptr`, `ptr_cast_constness`, `borrow_as_ptr` and `as_ptr_cast_mut` (pedantic/nursery)
push code towards these forms.

## Creating pointers without references: `&raw` and `addr_of!`

`&x as *const T` first creates a reference, which must satisfy all reference rules (aligned, initialised,
aliasing). When those do not hold, create the pointer directly:

```rust
use std::mem::MaybeUninit;

#[repr(C, packed)]
struct Header {
    tag: u8,
    len: u32, // unaligned inside a packed struct
}

fn read_len(h: &Header) -> u32 {
    let p = &raw const h.len; // 1.82+; older: std::ptr::addr_of!(h.len)
    // SAFETY: p points into a live Header; read_unaligned has no alignment requirement.
    unsafe { p.read_unaligned() }
}

struct Pair { a: u64, b: String }

fn init_pair() -> Pair {
    let mut slot = MaybeUninit::<Pair>::uninit();
    let p = slot.as_mut_ptr();
    // SAFETY: &raw mut projects to the fields without creating references to uninitialised data;
    // each field is written exactly once before assume_init.
    unsafe {
        (&raw mut (*p).a).write(7);
        (&raw mut (*p).b).write(String::from("x"));
        slot.assume_init()
    }
}
```

- Taking a reference to a field of a `#[repr(packed)]` struct is a hard error (E0793); copy the field
  (`let len = { h.len };`) or use `&raw const` + `read_unaligned`.
- `&raw mut STATIC_MUT` / `addr_of_mut!(STATIC_MUT)` is the 2024-compatible way to touch a `static mut`;
  since 1.82 creating the raw pointer is allowed in safe code (dereferencing it is not).

## Alignment and packed structs

| Situation | Correct approach |
|-----------|------------------|
| Parsing integers from a byte buffer | `u32::from_le_bytes(buf[i..i + 4].try_into().unwrap())` or `read_unaligned` |
| `*const u8` from the network cast to `*const Header` | `read_unaligned`, or `zerocopy::Ref` / `bytemuck::try_from_bytes` which check alignment |
| Checking at runtime | `p.is_aligned()`, `p.align_offset(align_of::<T>())` (may return `usize::MAX` in const contexts / Miri symbolic mode) |
| Allocating aligned memory | `std::alloc::Layout::from_size_align(size, align)?` + `alloc`/`dealloc` with the same layout |
| Over-aligned type | `#[repr(align(64))] struct CacheLine([u8; 64]);` |

Dereferencing a misaligned pointer is UB even on x86 where the CPU would tolerate it: the compiler emits
aligned instructions (SIMD loads) and assumes alignment. Miri reports it; add
`-Zmiri-symbolic-alignment-check` to catch code that is aligned only by luck of the allocator.

## Pointer arithmetic

- `p.add(n)`, `p.sub(n)`, `p.offset(n)`: the result must stay within the same allocated object or one byte
  past its end, and the byte offset must not overflow `isize`. Violating that is UB **even if the result
  is never dereferenced**.
- `p.wrapping_add(n)` / `wrapping_offset`: allowed to leave the object (for computing sentinels or
  tagged addresses); dereferencing is still only valid inside the original object.
- `p.byte_add(n)` (1.75) offsets in bytes without casting to `*const u8` and back.
- `q.offset_from(p)`: both must be in the same allocation, distance a multiple of `size_of::<T>()`.
- One-past-the-end pointers are valid to compute and compare, never to dereference.
- `ptr::null().add(0)` is fine; `ptr::null().add(1)` is UB (no allocation). Zero-sized types: every
  non-null, aligned pointer is valid for zero-sized accesses (`NonNull::dangling()`).

## NonNull, variance and PhantomData

`NonNull<T>` (1.25) is a `*mut T` that is never null and is **covariant** in `T` (like `*const T`), with the
null-pointer niche so `Option<NonNull<T>>` is pointer-sized.

```rust
use std::marker::PhantomData;
use std::ptr::NonNull;

pub struct RawVec<T> {
    ptr: NonNull<T>,    // dangling() when cap == 0: aligned, non-null, never dereferenced
    cap: usize,
    _owns: PhantomData<T>, // we logically own Ts: affects drop check and auto traits
}

impl<T> RawVec<T> {
    pub const fn new() -> Self {
        Self { ptr: NonNull::dangling(), cap: 0, _owns: PhantomData }
    }
}
```

Rules of thumb:
- `NonNull::new(p)` returns `Option`; `new_unchecked` requires a non-null proof (US012).
- `as_ref`/`as_mut` are unsafe: they create references with all the reference obligations.
- Covariance is wrong for types that hand out `&mut T` through shared paths (use
  `PhantomData<*mut T>` or `PhantomData<Cell<T>>` for invariance when needed; e.g. a `Cell`-like type).
- `PhantomData<T>` = "owns a T" (needed for dropck when `Drop` drops Ts); `PhantomData<&'a T>` = "borrows
  a T for 'a"; `PhantomData<fn() -> T>` = covariant without ownership and keeps the type `Send + Sync`.

## Provenance

A pointer is more than an address: it carries **provenance**, the permission to access a specific
allocation (and, under the aliasing models, a specific borrow). Two pointers with the same address can
have different permissions; one-past-the-end of array A may equal the start of B but cannot be used to
access B.

Consequences:
- Casting a pointer to an integer and back (`p as usize as *const T`) loses provenance unless the
  provenance was *exposed*; the result may not be usable to access memory under the strict model.
- Pointer tagging, XOR linked lists, and compressed pointers should manipulate the address while keeping
  the pointer value: that is what the strict provenance APIs are for.
- `transmute::<usize, *const T>` creates a pointer with **no** provenance (cannot be dereferenced);
  `transmute::<*const T, usize>` is also discouraged (use `addr()` / `expose_provenance()`).

## Strict provenance APIs (1.84)

| API | Purpose |
|-----|---------|
| `p.addr() -> usize` | read the address without exposing provenance |
| `p.with_addr(a)` | pointer with address `a` and the provenance of `p` |
| `p.map_addr(\|a\| ..)` | transform the address, keep provenance (tagging/untagging) |
| `ptr::without_provenance::<T>(a)` / `without_provenance_mut` | sentinel pointer that is never dereferenced |
| `ptr::dangling::<T>()` / `dangling_mut` | aligned, non-null, no provenance (like `NonNull::dangling`) |
| `p.expose_provenance() -> usize` | address + mark provenance as exposed (for int round trips, FFI handles) |
| `ptr::with_exposed_provenance::<T>(a)` / `_mut` | rebuild a pointer from an exposed address |

Tagged pointer, done right:

```rust
// Store a 1-bit tag in the low bit of an 8-aligned pointer (Rust 1.84+).
const TAG: usize = 0b1;

fn tag(p: *const u64) -> *const u64 {
    debug_assert!(p.addr() % align_of::<u64>() == 0);
    p.map_addr(|a| a | TAG)
}

fn untag(p: *const u64) -> (*const u64, bool) {
    (p.map_addr(|a| a & !TAG), p.addr() & TAG != 0)
}

fn demo() -> u64 {
    let x = 42u64;
    let (raw, tagged) = untag(tag(&raw const x));
    assert!(tagged);
    // SAFETY: `raw` has x's provenance and its original, aligned address; x is alive.
    unsafe { *raw }
}
```

Run with `MIRIFLAGS="-Zmiri-strict-provenance" cargo +nightly miri test` to reject integer-to-pointer
casts. On nightly, the `strict_provenance_lints` feature adds `fuzzy_provenance_casts` and
`lossy_provenance_casts` lints that flag `as` casts between pointers and integers. The auditor's US022 is a
lightweight version (integer literal or `as usize ... as *const`).

## Exposed provenance and MMIO

Some code genuinely needs integer -> pointer: memory-mapped I/O registers at fixed addresses, handles that
a C API passes back as `uintptr_t`, or JIT code. Use the exposed-provenance APIs to make the intent
explicit (an `as` cast from integer to pointer has the same semantics as `with_exposed_provenance`):

```rust
const UART_DR: usize = 0x4000_1000; // from the chip reference manual

fn uart_write(byte: u8) {
    let reg = std::ptr::with_exposed_provenance_mut::<u32>(UART_DR);
    // SAFETY: UART_DR is the documented, 4-aligned data register of a peripheral that is always
    // mapped on this target; volatile write because the access has side effects.
    unsafe { reg.write_volatile(u32::from(byte)) };
}
```

In embedded Rust prefer the generated peripheral access crate (svd2rust PAC) or HAL, which wrap these
addresses in typed, ownership-checked APIs. Miri cannot run MMIO code; keep it behind a small trait so the
rest is testable.

## Volatile access

`read_volatile`/`write_volatile` guarantee the access is emitted (not merged, elided or reordered relative
to other volatile accesses). They are for MMIO and memory shared with hardware, **not** for
inter-thread synchronisation: use atomics for that. Volatile accesses have the same validity, alignment
and provenance preconditions as normal reads and writes.

## Unchecked hints

| Hint | Contract | Safe alternative |
|------|----------|------------------|
| `std::hint::unreachable_unchecked()` (1.27) | never executed | `unreachable!()` |
| `std::hint::assert_unchecked(cond)` (1.81) | `cond` is true | `assert!`/`debug_assert!` + let LLVM prove it |
| `Option::unwrap_unchecked` / `Result::unwrap_unchecked` (1.58) | is `Some`/`Ok` | `unwrap`, `expect`, `?` |
| `slice::get_unchecked(_mut)` | index in bounds | `get`, hoisted slice `&v[..n]`, iterators |
| `u32::unchecked_add` etc. (1.79) | no overflow | `checked_add`, `wrapping_add`, `saturating_add` |
| `NonZero::new_unchecked` | non-zero | `NonZero::new(..)?` |

A false hint is UB that the optimiser actively exploits (it deletes the code it believes impossible), so
these produce the "works in debug, wrong in release" bugs. Always pair with a `debug_assert!` of the same
condition so debug test runs catch violations.

## Inline assembly

`asm!` (stable since 1.59; `global_asm!` too) is inherently unsafe (US025). The compiler trusts every
declaration: wrong operands or options are UB.

```rust
#[cfg(target_arch = "x86_64")]
fn timestamp() -> u64 {
    let lo: u32;
    let hi: u32;
    // SAFETY: `rdtsc` writes only EDX:EAX (declared as outputs), touches no memory or stack and
    // leaves the flags unchanged, matching the options below.
    unsafe {
        std::arch::asm!(
            "rdtsc",
            out("eax") lo,
            out("edx") hi,
            options(nomem, nostack, preserves_flags),
        );
    }
    (u64::from(hi) << 32) | u64::from(lo)
}
```

Review points:
- Every register written is declared (`out`, `lateout`, `inout`) or covered by `clobber_abi("C")` when
  calling functions.
- `options(nomem)` only if no memory is read or written; `readonly` if only read; `pure` requires
  `nomem` or `readonly` and no side effects; `nostack` only if nothing is pushed and the red zone is not
  used; `preserves_flags` only if flags are untouched; `noreturn` if it never returns.
- Stack alignment and the red zone on x86-64 when the asm pushes.
- Prefer intrinsics (`core::arch::x86_64::_rdtsc`, `core::arch::aarch64::*`): they are typed and visible
  to the optimiser.
- Naked functions (`#[unsafe(naked)]` with `naked_asm!`) are stable since 1.88; the whole body is asm and
  must follow the ABI by hand.

## Target features

`#[target_feature(enable = "avx2")]` compiles a function with instructions the baseline target may not
support. Calling it on a CPU without the feature is UB. Since 1.86 such functions may be safe `fn`s, but
calling them from code that does not itself enable the feature still requires `unsafe`:

```rust
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
fn sum_avx2(xs: &[f32]) -> f32 {
    xs.iter().sum() // auto-vectorised with AVX2
}

pub fn sum(xs: &[f32]) -> f32 {
    #[cfg(target_arch = "x86_64")]
    {
        if std::arch::is_x86_feature_detected!("avx2") {
            // SAFETY: the running CPU supports AVX2 (detected just above).
            return unsafe { sum_avx2(xs) };
        }
    }
    xs.iter().sum()
}
```

On older compilers declare it `unsafe fn` with a `# Safety` section ("the CPU must support AVX2").

## Review checklist

- [ ] Every raw pointer has a known origin (which allocation, which borrow) and the code never uses it after
      the owner moved, reallocated, was mutably borrowed or dropped.
- [ ] No reference is created to unaligned, uninitialised or aliased memory; `&raw`/`addr_of!` used instead.
- [ ] Arithmetic stays in bounds (`add`/`offset`) or uses `wrapping_*` and is never dereferenced outside.
- [ ] Integer <-> pointer conversions use `addr`/`with_addr`/`map_addr` or the exposed APIs, never `transmute`.
- [ ] Every `*_unchecked` / hint has a proof and a `debug_assert!`.
- [ ] asm operands, clobbers and options match what the instructions actually do.
- [ ] Target-feature functions are only called after runtime detection or under a matching `cfg`.
- [ ] Tests run under Miri with `-Zmiri-strict-provenance` and `-Zmiri-symbolic-alignment-check`.
