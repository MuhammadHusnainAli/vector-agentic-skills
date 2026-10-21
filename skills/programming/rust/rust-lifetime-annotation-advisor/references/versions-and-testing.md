# Versions and Testing

Which Rust version and edition introduced each lifetime feature (so a suggestion matches the project's MSRV),
the lints that catch lifetime noise, and how to keep lifetime-related API guarantees under test.

## Contents

- [Lifetime features by Rust version](#lifetime-features-by-rust-version)
- [Edition differences](#edition-differences)
- [Error codes that changed over time](#error-codes-that-changed-over-time)
- [Lints](#lints)
- [Testing lifetime guarantees](#testing-lifetime-guarantees)
- [CI with the scripts](#ci-with-the-scripts)

## Lifetime features by Rust version

| Rust | Feature | Use instead before it |
|------|---------|-----------------------|
| 1.0 | elision rules, `'static`, `T: 'a`, HRTB `for<'a>`, `PhantomData` | |
| 1.26 | `impl Trait` in argument and return position | `Box<dyn Trait>`, named generics |
| 1.31 (edition 2018) | NLL; anonymous lifetime `'_`; impl-header elision (`impl Display for T<'_>`); inferred `T: 'a` on struct fields | named lifetimes everywhere; explicit `where T: 'a` |
| 1.36 | NLL on edition 2015 | |
| 1.39 | `async fn` / `.await` | futures 0.1 combinators |
| 1.63 | `std::thread::scope`; old borrow checker removed | `crossbeam::scope`, `Arc` |
| 1.65 | generic associated types (`type Item<'a> where Self: 'a`) | lending-iterator crates, boxing |
| 1.70 | `OnceCell`, `OnceLock` | `once_cell`, `lazy_static` |
| 1.75 | `async fn` and `-> impl Trait` in traits (RPITIT) | `async-trait` (boxes), associated future types |
| 1.80 | `LazyCell`, `LazyLock` | `once_cell::sync::Lazy` |
| 1.82 | precise capturing `-> impl Trait + use<'a, T>` | the `Captures<'a>` trait trick, `+ 'a` |
| 1.85 (edition 2024) | RPIT captures all in-scope lifetimes; tail-expression temporaries drop earlier; async closures and `AsyncFn*` traits | explicit `+ '_`; `Fn(..) -> Fut` with owned args |

Check `rust-version` in `Cargo.toml` (or `rust-toolchain.toml`) before suggesting GATs, `use<..>`, async fns in
traits or async closures.

## Edition differences

| Topic | 2015 | 2018 / 2021 | 2024 |
|-------|------|-------------|------|
| Borrow checker | lexical, then NLL from 1.36 | NLL | NLL |
| `'_` and impl-header elision | no | yes | yes |
| Hidden lifetimes in paths (`Formatter` vs `Formatter<'_>`) | allowed | allowed; `elided_lifetimes_in_paths` (in the `rust_2018_idioms` group, allow-by-default) asks for `<'_>` | same |
| `-> impl Trait` captures | type params only; lifetimes only if named in bounds (else E0700) | same | **all** in-scope type params and lifetimes; opt out with `use<..>` |
| Closure captures | whole variables | 2021: disjoint fields | disjoint fields |
| Tail-expression temporaries | dropped after locals | dropped after locals | dropped before locals (fixes some E0597 on `x.borrow().len()` at the end of a block) |

Migrating to 2024: `cargo fix --edition` runs `impl_trait_overcaptures`, which inserts `use<..>` where the new
default would capture more than before. Review those additions: many can go once you confirm callers do
not hold arguments while using the result.

## Error codes that changed over time

Older answers on the web cite codes current rustc no longer emits; translate them:

| Old | Meaning | Today |
|-----|---------|-------|
| E0495 cannot infer an appropriate lifetime | conflicting requirements | "lifetime may not live long enough" with `'1`/`'2` labels |
| E0623 lifetime mismatch | data flows between two differently-named lifetimes | "lifetime may not live long enough" |
| E0759 / E0772 `'static` requirement introduced by ... | a `dyn Trait` / `impl Trait` defaults to `'static` | E0521 "borrowed data escapes", or "lifetime may not live long enough" with a note about `'static` |
| E0700 hidden type captures lifetime | still emitted on editions <= 2021 | fixed by `+ '_` / `use<'a>` or edition 2024 |

Run `rustc --explain E0106` for the full text of any current code.

## Lints

| Lint | Tool | Catches |
|------|------|---------|
| `clippy::needless_lifetimes` | clippy (warn by default) | named lifetimes elision would produce (also `elision_check` LT001) |
| `clippy::extra_unused_lifetimes` | clippy (warn by default) | declared and unused lifetimes (LT005) |
| `elided_lifetimes_in_paths` | rustc (allow; enable via `#![warn(rust_2018_idioms)]`) | `Formatter` instead of `Formatter<'_>` |
| `unused_lifetimes` | rustc (allow-by-default) | unused lifetime parameters |
| `single_use_lifetimes` | rustc (allow-by-default) | a lifetime used once, replaceable by `'_` (LT002) |
| `impl_trait_overcaptures` | rustc (edition-2024 migration) | RPIT that would capture more in 2024 |
| `clippy::needless_pass_by_ref_mut`, `clippy::ref_option` | clippy | API shapes that create needless borrows |

Enable in `Cargo.toml` for the whole workspace:

```toml
[lints.rust]
rust_2018_idioms = { level = "warn", priority = -1 }
unused_lifetimes = "warn"

[lints.clippy]
needless_lifetimes = "warn"
extra_unused_lifetimes = "warn"
```

## Testing lifetime guarantees

A lifetime in a public API is a promise: "the token does not borrow the parser", "the iterator owns its data".
Lock such promises in with tests that fail to compile if someone changes the signature.

**Positive tests** (must compile): exercise the pattern callers rely on.

```rust
pub struct Parser<'a> { src: &'a str, pos: usize }

impl<'a> Parser<'a> {
    pub fn new(src: &'a str) -> Self { Parser { src, pos: 0 } }
    pub fn next_token(&mut self) -> Option<&'a str> {
        let rest = self.src.get(self.pos..)?.trim_start();
        if rest.is_empty() { return None; }
        let start = self.src.len() - rest.len();
        let end = rest.find(' ').unwrap_or(rest.len());
        self.pos = start + end;
        Some(&rest[..end])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokens_outlive_the_parser_borrow() {
        let text = String::from("a b");
        let mut p = Parser::new(&text);
        let a = p.next_token();
        let b = p.next_token();     // compiles only if next_token takes a short &mut self
        drop(p);                    // tokens borrow `text`, not `p`
        assert_eq!((a, b), (Some("a"), Some("b")));
    }

    fn is_static<T: 'static>(_: &T) {}

    #[test]
    fn config_is_owned() {
        let cfg = String::from("x");     // stand-in for an owned config type
        is_static(&cfg);                 // fails to compile if the type gains a borrowed field
    }
}
```

**Negative tests** (must not compile): `compile_fail` doctests or `trybuild` snapshots.

````rust
/// A token cannot outlive the source text:
///
/// ```compile_fail
/// let tok;
/// {
///     let text = String::from("a b");
///     let mut p = mycrate::Parser::new(&text);
///     tok = p.next_token();
/// }
/// println!("{tok:?}");
/// ```
pub fn _doc_anchor() {}
````

`compile_fail,E0597` additionally checks the error code (enforced on nightly). `trybuild` compares the full
compiler output against `tests/ui/*.stderr`; run `TRYBUILD=overwrite cargo test` after a compiler upgrade
changes the wording.

## CI with the scripts

The scripts are single-file, std-only Rust programs: compile with `rustc` (about a second each), no Cargo
project needed, then run them as a gate next to `cargo clippy`.

```bash
SKILL=path/to/rust-lifetime-annotation-advisor
for t in elision_check missing_lifetime static_bounds lifetime_smells; do
  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"
done
/tmp/missing_lifetime src/ --strict          # high-severity: would not compile
/tmp/elision_check src/ --strict             # noise: elidable and unused lifetimes
/tmp/static_bounds src/ --json > static.json # advisory: review, do not gate
/tmp/lifetime_smells src/ --max-lifetimes 2
```

All scripts share options (`--json`, `--strict`, `--select`, `--ignore`, `--edition`, `--list-rules`) and
exit codes (0 clean or advisory, 1 findings with `--strict`, 2 usage error).
