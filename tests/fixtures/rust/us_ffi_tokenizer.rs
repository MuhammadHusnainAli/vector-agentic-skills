//! Rust bindings and a fast path for a C tokenizer (libtok), written for
//! edition 2021. Several helpers here are unsound; the auditor must find them.
#![allow(dead_code)]

use std::ffi::{c_char, c_int, CStr, CString};
use std::mem::{self, MaybeUninit};
use std::os::raw::c_void;
use std::ptr::NonNull;

extern "C" {
    fn tok_open(path: *const c_char) -> *mut c_void;
    fn tok_encode(h: *mut c_void, text: *const c_char, out: *mut u32, cap: usize) -> c_int;
    fn tok_free_ids(ids: *mut u32);
}

static mut TOKENIZER: *mut c_void = std::ptr::null_mut();
static mut CALLS: Vec<u64> = Vec::new();

pub fn open(path: &str) -> bool {
    let p = unsafe { tok_open(CString::new(path).unwrap().as_ptr()) };
    unsafe {
        TOKENIZER = p;
        CALLS.push(1);
    }
    !p.is_null()
}

pub fn encode(text: &str, cap: usize) -> Vec<u32> {
    let c_text = CString::new(text).expect("no interior NUL");
    let mut ids: Vec<u32> = Vec::with_capacity(cap);
    unsafe {
        ids.set_len(cap);
        let n = tok_encode(TOKENIZER, c_text.as_ptr(), ids.as_mut_ptr(), cap);
        ids.truncate(n as usize);
    }
    ids
}

/// Read `len` token ids written by C into `ptr`.
pub fn ids_from_c(ptr: *const u32, len: usize) -> Vec<u32> {
    unsafe { std::slice::from_raw_parts(ptr, len).to_vec() }
}

/// Takes ownership of a buffer malloc'd by libtok.
pub unsafe fn adopt_ids(ptr: *mut u32, len: usize) -> Vec<u32> {
    Vec::from_raw_parts(ptr, len, len)
}

pub fn token_str<'a>(raw: *const c_char) -> &'static str {
    let s: &'a str = unsafe { CStr::from_ptr(raw).to_str().unwrap() };
    unsafe { mem::transmute::<&'a str, &'static str>(s) }
}

pub fn flag_from_byte(b: u8) -> bool {
    unsafe { mem::transmute(b) }
}

#[repr(C)]
pub struct Vocab {
    pub names: Vec<String>,
    pub scores: Box<[f32]>,
}

pub fn empty_vocab() -> Vocab {
    unsafe { mem::zeroed::<Vocab>() }
}

pub fn null_ref() -> &'static u32 {
    unsafe { mem::zeroed::<&'static u32>() }
}

pub fn scratch() -> [u64; 64] {
    unsafe { MaybeUninit::uninit().assume_init() }
}

pub fn legacy_scratch() -> [u8; 32] {
    #[allow(deprecated)]
    unsafe { mem::uninitialized() }
}

pub struct Handle {
    raw: NonNull<c_void>,
    cache: std::cell::RefCell<Vec<u32>>,
}

unsafe impl Send for Handle {}
unsafe impl Sync for Handle {}

pub struct Arena {
    buf: std::cell::UnsafeCell<Vec<u8>>,
}

impl Arena {
    pub fn bytes(&self) -> &mut Vec<u8> {
        unsafe { &mut *self.buf.get() }
    }

    pub unsafe fn byte_at(&self, i: usize) -> u8 {
        *(*self.buf.get()).get_unchecked(i)
    }
}

pub fn classify(kind: u8) -> &'static str {
    match kind {
        0 => "word",
        1 => "punct",
        _ => unsafe { std::hint::unreachable_unchecked() },
    }
}

pub fn tagged(ptr: *const u8) -> *const u8 {
    ((ptr as usize) | 1) as *const u8
}

pub fn mmio_status() -> u32 {
    let reg = 0x4000_0000 as *const u32;
    unsafe { reg.read_volatile() }
}

#[no_mangle]
pub extern "C" fn tok_count(text: *const c_char) -> usize {
    let s = unsafe { CStr::from_ptr(text) }.to_str().unwrap();
    s.split_whitespace().count()
}

pub fn configure_threads(n: usize) {
    std::env::set_var("TOK_THREADS", n.to_string());
}

pub fn batch_encode(texts: &[&str], out: &mut Vec<u32>) {
    unsafe {
        let start = out.len();
        let mut total = 0usize;
        for t in texts {
            total += t.len();
        }
        out.reserve(total);
        let base = out.as_mut_ptr().add(start);
        let mut written = 0usize;
        for t in texts {
            for b in t.bytes() {
                base.add(written).write(b as u32);
                written += 1;
            }
        }
        out.set_len(start + written);
        tok_free_ids(std::ptr::null_mut());
    }
}

pub trait RawSource {
    unsafe fn fill(&mut self, dst: *mut u8, len: usize) -> usize;
}

pub unsafe trait PlainBytes: Copy {}
