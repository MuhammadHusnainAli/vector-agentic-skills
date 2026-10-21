//! A fixed-capacity ring buffer and FFI shim with a minimal, documented unsafe
//! surface (edition 2024, MSRV 1.85). Every unsafe block carries a SAFETY
//! comment and every unsafe fn documents its contract.
#![deny(unsafe_op_in_unsafe_fn)]
#![warn(clippy::undocumented_unsafe_blocks, clippy::missing_safety_doc)]

use std::ffi::{CString, c_char, c_int};
use std::marker::PhantomData;
use std::mem::MaybeUninit;
use std::panic::{self, AssertUnwindSafe};
use std::ptr::NonNull;
use std::sync::atomic::{AtomicUsize, Ordering};

unsafe extern "C" {
    /// Logs a NUL-terminated message; safe for any valid C string.
    fn host_log(msg: *const c_char) -> c_int;
    pub safe fn host_abs(x: c_int) -> c_int;
}

static LOG_CALLS: AtomicUsize = AtomicUsize::new(0);

/// Ring buffer whose invariant is: slots `[head, head + len)` (mod N) are initialised.
pub struct Ring<T, const N: usize> {
    slots: [MaybeUninit<T>; N],
    head: usize,
    len: usize,
}

impl<T, const N: usize> Ring<T, N> {
    pub const fn new() -> Self {
        Self { slots: [const { MaybeUninit::uninit() }; N], head: 0, len: 0 }
    }

    pub fn push(&mut self, value: T) -> Result<(), T> {
        if self.len == N {
            return Err(value);
        }
        let idx = (self.head + self.len) % N;
        self.slots[idx].write(value);
        self.len += 1;
        Ok(())
    }

    pub fn pop(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        let idx = self.head;
        self.head = (self.head + 1) % N;
        self.len -= 1;
        // SAFETY: `idx` was the head of a non-empty ring, so by the struct invariant the
        // slot is initialised; head/len were advanced first, so it is read exactly once.
        Some(unsafe { self.slots[idx].assume_init_read() })
    }

    pub fn get(&self, i: usize) -> Option<&T> {
        if i >= self.len {
            return None;
        }
        let idx = (self.head + i) % N;
        // SAFETY: i < len, so `idx` lies in the initialised window [head, head + len).
        Some(unsafe { self.slots.get_unchecked(idx).assume_init_ref() })
    }

    /// Returns the element at logical index `i` without bounds checks.
    ///
    /// # Safety
    ///
    /// `i` must be less than `self.len()`.
    pub unsafe fn get_unchecked(&self, i: usize) -> &T {
        debug_assert!(i < self.len);
        let idx = (self.head + i) % N;
        // SAFETY: the caller guarantees i < len, so the slot is initialised.
        unsafe { self.slots.get_unchecked(idx).assume_init_ref() }
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

impl<T, const N: usize> Drop for Ring<T, N> {
    fn drop(&mut self) {
        while self.pop().is_some() {}
    }
}

/// Owning pointer to a heap value shared with C as an opaque handle.
pub struct Handle<T> {
    ptr: NonNull<T>,
    _owns: PhantomData<T>,
}

// SAFETY: Handle uniquely owns its allocation (created from Box, freed once in Drop),
// so sending it is exactly as safe as sending a Box<T>, which requires T: Send.
unsafe impl<T: Send> Send for Handle<T> {}

impl<T> Handle<T> {
    pub fn new(value: T) -> Self {
        Self { ptr: NonNull::from(Box::leak(Box::new(value))), _owns: PhantomData }
    }

    pub fn get(&self) -> &T {
        // SAFETY: ptr came from Box::leak and stays valid until Drop; &self forbids &mut.
        unsafe { self.ptr.as_ref() }
    }
}

impl<T> Drop for Handle<T> {
    fn drop(&mut self) {
        // SAFETY: ptr was produced by Box::leak in `new` and is freed only here, once.
        drop(unsafe { Box::from_raw(self.ptr.as_ptr()) });
    }
}

/// Sums `len` values starting at `data`.
///
/// # Safety
///
/// `data` must be non-null, aligned, and valid for reads of `len` initialised `u32`s that
/// are not mutated for the duration of the call; `len * 4` must not exceed `isize::MAX`.
pub unsafe fn sum_raw(data: *const u32, len: usize) -> u64 {
    // SAFETY: forwarded verbatim from this function's documented contract.
    let values = unsafe { std::slice::from_raw_parts(data, len) };
    values.iter().map(|&v| u64::from(v)).sum()
}

pub fn log(msg: &str) -> bool {
    let Ok(text) = CString::new(msg) else {
        return false;
    };
    LOG_CALLS.fetch_add(1, Ordering::Relaxed);
    // SAFETY: `text` is a valid NUL-terminated string that outlives the call.
    unsafe { host_log(text.as_ptr()) == 0 }
}

pub fn magnitude(x: i32) -> i32 {
    host_abs(x)
}

pub fn bits_of(x: f32) -> u32 {
    x.to_bits()
}

/// C entry point: returns the sum of `len` values, or -1 if `data` is null or Rust panics.
///
/// # Safety
///
/// If non-null, `data` must be valid for reads of `len` initialised `u32`s.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ring_sum(data: *const u32, len: usize) -> i64 {
    if data.is_null() {
        return -1;
    }
    let result = panic::catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: non-null checked above; validity is the caller's documented contract.
        let total = unsafe { sum_raw(data, len) };
        i64::try_from(total).unwrap_or(i64::MAX)
    }));
    result.unwrap_or(-1)
}
