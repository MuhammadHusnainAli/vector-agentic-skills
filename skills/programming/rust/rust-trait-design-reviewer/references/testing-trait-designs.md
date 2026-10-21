# Testing Trait Designs

Traits are seams for tests and promises to implementors. Test both sides: code that *uses* a trait (with fakes
or mocks), and the trait's *contract* (dyn compatibility, `Send`/`Sync`, laws such as Eq/Hash consistency, and
what must not compile). Blocks marked `rust,ignore` need a crate (`mockall`, `proptest`, `trybuild`,
`static_assertions`); the rest compile with std.

## Contents

- [Hand-written fakes](#hand-written-fakes)
- [mockall](#mockall)
- [Compile-time contract checks](#compile-time-contract-checks)
- [Things that must not compile](#things-that-must-not-compile)
- [Property tests for trait laws](#property-tests-for-trait-laws)
- [Testing default methods and blanket impls](#testing-default-methods-and-blanket-impls)
- [Async traits](#async-traits)
- [Checklist](#checklist)

## Hand-written fakes

The simplest and most readable test double: a struct implementing the trait with in-memory state. Prefer it
when the trait is small and you want to assert on effects rather than on call sequences.

```rust
use std::cell::RefCell;
use std::collections::HashMap;

pub trait Store {
    fn get(&self, key: &str) -> Option<String>;
    fn put(&self, key: &str, value: String);
}

pub fn remember_name(store: &dyn Store, user: &str, name: &str) -> bool {
    let key = format!("name:{user}");
    if store.get(&key).is_some() {
        return false;
    }
    store.put(&key, name.to_string());
    true
}

#[derive(Default)]
struct FakeStore {
    data: RefCell<HashMap<String, String>>,
    puts: RefCell<Vec<String>>,          // record calls for assertions
}

impl Store for FakeStore {
    fn get(&self, key: &str) -> Option<String> {
        self.data.borrow().get(key).cloned()
    }
    fn put(&self, key: &str, value: String) {
        self.puts.borrow_mut().push(key.to_string());
        self.data.borrow_mut().insert(key.to_string(), value);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stores_once() {
        let store = FakeStore::default();
        assert!(remember_name(&store, "u1", "Ada"));
        assert!(!remember_name(&store, "u1", "Bob"));
        assert_eq!(store.puts.borrow().as_slice(), ["name:u1"]);
    }
}
```

Fakes for generic code work the same way; pass the fake as the type parameter.

## mockall

`mockall` generates a `MockTrait` with expectations. Useful for checking call counts, argument values and
ordering, or for traits with many methods where a fake would be long.

```rust,ignore
use mockall::{automock, predicate::eq};

#[cfg_attr(test, automock)]
pub trait Clock {
    fn now_ms(&self) -> u64;
}

#[cfg_attr(test, automock)]
pub trait Store {
    fn get(&self, key: &str) -> Option<String>;
}

pub fn is_fresh(clock: &dyn Clock, store: &dyn Store, key: &str) -> bool {
    store.get(key).and_then(|v| v.parse::<u64>().ok()).is_some_and(|t| clock.now_ms() - t < 60_000)
}

#[test]
fn fresh_within_a_minute() {
    let mut clock = MockClock::new();
    clock.expect_now_ms().return_const(100_000u64);
    let mut store = MockStore::new();
    store.expect_get().with(eq("k")).times(1).returning(|_| Some("90000".into()));
    assert!(is_fresh(&clock, &store, "k"));
}
```

Notes: `#[automock]` handles generic methods and associated types with some limits; traits with lifetimes in
return types may need `#[mockall::concretize]` or a hand-written fake. Over-specified mocks (exact call order
everywhere) make refactoring painful: assert on outcomes where you can.

## Compile-time contract checks

Make the contract fail at compile time instead of in a downstream crate:

```rust
use std::fmt::Debug;

pub trait Backend: Debug + Send + Sync {
    fn name(&self) -> &str;
}

#[derive(Debug)]
pub struct Memory;
impl Backend for Memory {
    fn name(&self) -> &str { "memory" }
}

// 1. The trait stays dyn compatible (fails with E0038 if someone adds a generic method).
#[allow(dead_code)]
fn assert_dyn_compatible(_: &dyn Backend) {}

// 2. Public types keep their auto traits (removing Send is a breaking change).
const _: () = {
    const fn send_sync<T: Send + Sync>() {}
    send_sync::<Memory>();
    send_sync::<Box<dyn Backend>>();
};
```

The `static_assertions` crate offers the same as macros: `assert_impl_all!(Memory: Send, Sync, Debug);`,
`assert_not_impl_any!(Guard: Send);`, `assert_obj_safe!(Backend);`.

## Things that must not compile

Some promises are negative: a sealed trait cannot be implemented downstream, a guard is not `Send`, a typestate
builder has no `build()` before `url()`. Test them with `compile_fail` doctests (stable, no crates):

````rust
/// A typestate builder: `build()` is unavailable until a URL is set.
///
/// ```compile_fail
/// let client = mycrate::Client::builder().build(); // no `build` on ClientBuilder<Missing>
/// ```
///
/// Downstream crates cannot implement the sealed `Codec` trait:
///
/// ```compile_fail
/// struct Mine;
/// impl mycrate::Codec for Mine { fn name(&self) -> &'static str { "mine" } }
/// ```
pub struct Client;
````

Each `compile_fail` block should fail for exactly one reason; add the error code (`compile_fail,E0599`) so a
different failure does not pass the test (the code is checked on nightly rustdoc). For many cases, or to pin
the exact diagnostic, use `trybuild`:

```rust,ignore
#[test]
fn ui() {
    let t = trybuild::TestCases::new();
    t.compile_fail("tests/ui/*.rs"); // each file must fail; stderr compared to tests/ui/*.stderr
}
```

Regenerate snapshots with `TRYBUILD=overwrite cargo test` after a compiler update changes wording.

## Property tests for trait laws

Some std traits have laws the compiler cannot check. A broken law causes wrong `HashMap` lookups, unstable
sorts or `BTreeMap` corruption.

| Trait(s) | Law |
|----------|-----|
| `PartialEq` + `Hash` | `a == b` implies `hash(a) == hash(b)` |
| `Eq` | reflexive, symmetric, transitive |
| `Ord` / `PartialOrd` | total order consistent with `Eq`; `partial_cmp == Some(cmp)` |
| `Borrow<Q>` | `x.borrow() == y.borrow()` iff `x == y`, and hashes agree |
| `Clone` | `x.clone() == x` (for `PartialEq` types) |
| `FromStr` + `Display` | `s.parse::<T>()?.to_string() == s` for canonical strings (round trip) |
| `From<A> for B` | lossless and infallible; otherwise use `TryFrom` |

```rust,ignore
use proptest::prelude::*;
use std::hash::{BuildHasher, RandomState};

proptest! {
    #[test]
    fn eq_implies_same_hash(a in "[a-zA-Z]{0,8}", b in "[a-zA-Z]{0,8}") {
        let (ka, kb) = (CaseInsensitiveKey::new(&a), CaseInsensitiveKey::new(&b));
        if ka == kb {
            let s = RandomState::new();
            prop_assert_eq!(s.hash_one(&ka), s.hash_one(&kb));
        }
    }
}
```

The same check without a crate, for a fixed set of inputs:

```rust
use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hash, Hasher};

#[derive(Debug, Clone, Eq)]
pub struct Key(String);

impl PartialEq for Key {
    fn eq(&self, other: &Self) -> bool { self.0.eq_ignore_ascii_case(&other.0) }
}

impl Hash for Key {
    fn hash<H: Hasher>(&self, h: &mut H) {
        self.0.to_ascii_lowercase().hash(h); // hash what eq compares
    }
}

#[test]
fn eq_and_hash_agree() {
    let s = RandomState::new();
    for (a, b) in [("Ab", "aB"), ("x", "X"), ("", "")] {
        let (a, b) = (Key(a.into()), Key(b.into()));
        assert_eq!(a, b);
        assert_eq!(s.hash_one(&a), s.hash_one(&b));
    }
}
```

## Testing default methods and blanket impls

- Write a *minimal* test implementor that only provides required methods, then test every default method
  through it. This catches defaults that accidentally depend on a method an implementor might override.
- For blanket impls (`impl<T: Display> Describe for T`), test with a std type, a local type and a reference
  (`&T`) to confirm the impl covers what you think.
- For extension traits, test that the method is available after `use crate::prelude::*` only (an import test).

## Async traits

- Test async trait users with `#[tokio::test]` and a fake whose futures complete immediately.
- Assert the `Send` promise of an RPITIT method at compile time:

```rust
use std::future::Future;

pub trait Fetch: Sync {
    fn fetch(&self, key: &str) -> impl Future<Output = Option<Vec<u8>>> + Send;
}

pub struct Fake;
impl Fetch for Fake {
    async fn fetch(&self, _key: &str) -> Option<Vec<u8>> { Some(vec![1]) }
}

#[allow(dead_code)]
fn assert_send_future<F: Fetch>(f: &F) {
    fn is_send<T: Send>(_: T) {}
    is_send(f.fetch("k")); // fails to compile if an impl's future is not Send
}
```

## Checklist

| Promise | Test |
|---------|------|
| Usable as `dyn Trait` | `fn _a(_: &dyn Trait) {}` in the crate |
| Public types are `Send + Sync` | const-fn assertion or `static_assertions` |
| Sealed / typestate restrictions | `compile_fail` doctests or `trybuild` |
| Eq/Hash/Ord laws | table test or `proptest` over generated inputs |
| Default methods correct | minimal implementor + tests per default |
| Callers behave correctly | hand-written fake (effects) or `mockall` (interactions) |
| No accidental API break | `cargo semver-checks` in CI before publishing |
