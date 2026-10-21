# Version History: Unsafe Rust Features

Unsafe-related stabilisations by Rust version and the edition 2024 changes, so a safe alternative or a fix
matches the project's MSRV (`rust-version` in `Cargo.toml`).

## Contents

- [Stabilisations](#stabilisations)
- [Edition 2024 unsafe changes](#edition-2024-unsafe-changes)
- [Migrating a crate to edition 2024](#migrating-a-crate-to-edition-2024)
- [Before-and-after for older MSRVs](#before-and-after-for-older-msrvs)

## Stabilisations

| Rust | Feature | Replaces |
|------|---------|----------|
| 1.25 | `std::ptr::NonNull<T>` | `*mut T` with manual null checks |
| 1.36 | `MaybeUninit<T>` | `mem::uninitialized` (deprecated in 1.39) |
| 1.51 | `ptr::addr_of!` / `addr_of_mut!` | `&x as *const _` (creates a reference first) |
| 1.52 | `unsafe_op_in_unsafe_fn` lint | implicit unsafe bodies |
| 1.59 | inline assembly `asm!` / `global_asm!` | `llvm_asm!` (nightly) |
| 1.71 | `extern "C-unwind"` and the other `-unwind` ABIs | UB when a panic crossed `extern "C"` |
| 1.76 | `ptr::from_ref`, `ptr::from_mut` | `x as *const T` casts |
| 1.79 | unchecked integer arithmetic (`unchecked_add`, ...) | `checked_add(..).unwrap_unchecked()` |
| 1.81 | panics unwinding out of `extern "C"` functions abort the process | UB |
| 1.82 | `&raw const` / `&raw mut`; `unsafe extern` blocks with `safe` items; unsafe attributes `#[unsafe(no_mangle)]` | `addr_of!`; plain `extern` blocks; `#[no_mangle]` |
| 1.84 | strict provenance APIs: `addr`, `with_addr`, `map_addr`, `ptr::without_provenance`, `expose_provenance`, `with_exposed_provenance` | `as usize` / `as *const T` round trips |
| 1.85 | edition 2024 (see below) | |
| 1.88 | naked functions: `#[unsafe(naked)]` with `naked_asm!` | nightly only |

`&raw const`/`&raw mut` and `addr_of!` produce raw pointers without creating an intermediate reference, which
matters for packed fields, uninitialised memory and `static mut`.

## Edition 2024 unsafe changes

| Change | Lint (migration) | Script rule |
|--------|------------------|-------------|
| `unsafe_op_in_unsafe_fn` warns by default: unsafe operations inside an `unsafe fn` need their own `unsafe {}` block | `unsafe_op_in_unsafe_fn` | US027 |
| References to `static mut` are denied (`&X`, `&mut X`, method calls) | `static_mut_refs` | US009 |
| `extern` blocks must be written `unsafe extern`; items inside may be marked `safe` | `missing_unsafe_on_extern` | US019 |
| `#[no_mangle]`, `#[export_name]`, `#[link_section]` must be written `#[unsafe(..)]` | `unsafe_attr_outside_unsafe` | US020 |
| `std::env::set_var`, `remove_var` and `std::os::unix::process::CommandExt::before_exec` are `unsafe fn` | `deprecated_safe_2024` | US021 |

The new syntax (`unsafe extern`, `#[unsafe(..)]`, `&raw`) works on Rust 1.82+ in every edition, so you can
adopt it before switching editions.

## Migrating a crate to edition 2024

1. Update the toolchain to 1.85+ and run `cargo fix --edition` on edition 2021: it rewrites extern blocks and
   attributes and wraps unsafe operations inside unsafe fns.
2. Review every generated `unsafe {}` block inside unsafe fns: give each its own `// SAFETY:` comment (it now
   discharges part of the fn's `# Safety` contract).
3. Replace `static mut` with atomics, `Mutex`, `OnceLock`/`LazyLock` or `thread_local!` (see the
   undefined-behaviour catalog); where it must stay, use `&raw mut X`.
4. Audit `env::set_var` calls: move them before any thread starts, or pass configuration explicitly.
5. Set `edition = "2024"` and run the scanners: US019-US021 and US009 should now be empty.

## Before-and-after for older MSRVs

| Need | 1.82+ | Older |
|------|-------|-------|
| Raw pointer to a field without a reference | `&raw const s.field` | `ptr::addr_of!(s.field)` (1.51) |
| Raw pointer to a `static mut` | `&raw mut COUNTER` | `ptr::addr_of_mut!(COUNTER)` (1.51) |
| Change pointer address, keep provenance | `p.map_addr(|a| a | 1)` (1.84) | `p.cast::<u8>().wrapping_add(n).cast()` |
| Pointer from an MMIO address | `ptr::with_exposed_provenance::<u32>(0x4000_0000)` (1.84) | `0x4000_0000 as *const u32` |
| Unwind across FFI on purpose | `extern "C-unwind"` (1.71) | not possible soundly |
