//! Knowledge base shared by explain_code.rs and parse_diagnostics.rs: borrow/ownership
//! error codes, the recurring patterns behind them (BCK ids) and fixes ranked by tier.
//! Not an entry point; pulled in with `mod catalog;`.
#![allow(dead_code)]

/// Fix tiers, best first. Tier numbers in `Fix` index into this list (1-based).
pub const TIERS: [&str; 5] = ["restructure", "std api", "own the data", "shared ownership", "last resort"];

pub struct Fix {
    pub tier: u8,
    pub text: &'static str,
}

pub struct Code {
    /// "E0502", or a pseudo code for coded-less errors ("lifetime", "not-send").
    pub code: &'static str,
    pub title: &'static str,
    pub meaning: &'static str,
    pub fixes: &'static [Fix],
    /// Only a borrow problem when a pattern matches (E0308 is usually a plain type error).
    pub needs_pattern: bool,
}

pub struct Pattern {
    pub id: &'static str,
    pub name: &'static str,
    pub codes: &'static [&'static str],
    /// Lower-case substrings; any one must appear in the diagnostic (empty = always).
    pub any: &'static [&'static str],
    pub why: &'static str,
    pub fixes: &'static [Fix],
}

const fn f(tier: u8, text: &'static str) -> Fix {
    Fix { tier, text }
}

const fn c(code: &'static str, title: &'static str, meaning: &'static str, fixes: &'static [Fix]) -> Code {
    Code { code, title, meaning, fixes, needs_pattern: false }
}

pub const CODES: &[Code] = &[
    c("E0382", "use of moved value", "The value was moved (passed by value, `for x in v`, `move` closure, a `self` method) and then used again. Only `Copy` types survive a move.", &[
        f(1, "borrow instead of moving: `&v`, `v.iter()`, `opt.as_ref()`, a `&self` method"),
        f(1, "move the last use after every other use (reorder)"),
        f(3, "clone before the move when both copies are really needed (`Arc`/`Sender` clones are cheap)"),
    ]),
    c("E0499", "cannot borrow as mutable more than once at a time", "Two `&mut` to the same place are alive at once.", &[
        f(1, "end the first `&mut` before creating the second (shorter block, reorder)"),
        f(1, "borrow disjoint fields directly (`&mut self.a`, `&mut self.b`) instead of calling `&mut self` methods"),
        f(2, "`split_at_mut`, `get_disjoint_mut` (1.86+), `swap`, `entry()` instead of get-then-insert"),
        f(3, "use indices/keys and look up again when needed"),
    ]),
    c("E0502", "cannot borrow as mutable because it is also borrowed as immutable", "A shared borrow is still used after the point that needs a mutable one (or the reverse).", &[
        f(1, "copy the needed value out (`let n = v.len();`, `.clone()` of a small field) before mutating"),
        f(1, "collect changes first, apply them after the loop"),
        f(2, "`retain`/`retain_mut`, `extract_if` (1.87+), `entry()`, `swap`"),
        f(3, "keep an index or key instead of a reference across the mutation"),
    ]),
    c("E0503", "cannot use because it was mutably borrowed", "The original binding is read while a `&mut` to it is still live.", &[
        f(1, "read through the `&mut` you already have, or finish using it first"),
    ]),
    c("E0505", "cannot move out because it is borrowed", "A value is moved (or dropped) while a reference to it is still used later.", &[
        f(1, "move it after the last use of the reference"),
        f(3, "take an owned copy of what the reference pointed at (`.clone()`, `.to_owned()`) before the move"),
    ]),
    c("E0506", "cannot assign because it is borrowed", "The place is overwritten while a reference into it is still used later.", &[
        f(1, "finish with the reference before assigning"),
        f(2, "`mem::replace(&mut x, new)` to take the old value and assign in one step"),
    ]),
    c("E0507", "cannot move out of a borrow", "Ownership is taken through a reference, an index, or an `Rc`/`Arc`, which only lend the value.", &[
        f(1, "borrow it (`&v[i]`, `&self.field`, `.as_ref()`, `.iter()`)"),
        f(2, "`Option::take`, `mem::take`, `mem::replace`, `Vec::swap_remove`/`remove`"),
        f(2, "`Rc::try_unwrap`/`Rc::unwrap_or_clone` (1.76+) when you hold the last handle"),
        f(3, "`.clone()` when an owned copy is genuinely needed"),
    ]),
    c("E0508", "cannot move out of type `[T; N]`, a non-copy array", "Indexing an array by value tries to move one element out of it.", &[
        f(1, "borrow the element: `&arr[i]`"),
        f(2, "destructure (`let [a, b, c] = arr;`), `into_iter()`, or `mem::take(&mut arr[i])`"),
    ]),
    c("E0509", "cannot move out of type which implements the `Drop` trait", "Destructuring or moving a field out of a type with a destructor is not allowed.", &[
        f(2, "`mem::take`/`mem::replace`/`Option::take` the field through `&mut`"),
        f(1, "borrow the field instead"),
    ]),
    c("E0515", "cannot return reference to local variable or temporary", "The function returns a reference into data it owns and drops at the end of the call.", &[
        f(3, "return the owned value (`String`, `Vec<T>`, `PathBuf`)"),
        f(1, "return a reference derived from an input parameter instead"),
        f(2, "`Cow<'_, str>` when you sometimes borrow and sometimes allocate"),
    ]),
    c("E0521", "borrowed data escapes outside of function", "A reference parameter flows into something that must be `'static` (spawned task, boxed `'static` trait object).", &[
        f(3, "take owned data or an `Arc<T>` parameter and move it in"),
        f(2, "`std::thread::scope` (1.63+) when the work finishes before the function returns"),
    ]),
    c("E0373", "closure may outlive the current function, but it borrows a local", "A non-`move` closure or async block that borrows locals is handed to something that can outlive the function (`thread::spawn`, `tokio::spawn`).", &[
        f(1, "`move ||` / `async move` and move owned data in"),
        f(4, "clone an `Arc` handle per task and move the clone"),
        f(2, "`std::thread::scope` (1.63+) to borrow locals from threads"),
    ]),
    c("E0381", "used binding isn't initialized", "The variable is assigned on some paths only.", &[
        f(1, "initialise from an expression: `let x = if c { a } else { b };` or `match`"),
        f(1, "`let Some(x) = opt else { return ... };` (1.65+)"),
    ]),
    c("E0384", "cannot assign twice to immutable variable", "The binding is not `mut`.", &[
        f(1, "`let mut x`, or shadow with a new `let x = ...`"),
    ]),
    c("E0594", "cannot assign to data behind a reference or not declared mutable", "Assignment through `&T`, an `Rc`/`Arc`, or a non-`mut` binding.", &[
        f(1, "`let mut`, `&mut self`, `iter_mut()`"),
        f(4, "`Cell`/`RefCell`/`Mutex`/atomics when shared mutation is the design"),
    ]),
    c("E0596", "cannot borrow as mutable", "A `&mut` is taken from a non-`mut` binding, from behind `&`, or from inside an `Rc`/`Arc`.", &[
        f(1, "`let mut`, take `&mut self`, use `iter_mut()`/`get_mut()`"),
        f(2, "`Rc::make_mut`/`Arc::make_mut` (clone-on-write) or `Rc::get_mut`"),
        f(4, "`RefCell`/`Mutex`/`RwLock` inside the shared pointer"),
    ]),
    c("E0597", "borrowed value does not live long enough", "A reference outlives its owner: the owner is dropped at the end of a scope, or a `'static` bound demands it live forever.", &[
        f(1, "declare the owner in an outer scope so it outlives the reference"),
        f(3, "store/return owned data instead of a reference"),
        f(2, "`std::thread::scope` (1.63+) instead of `thread::spawn` for borrowed data"),
        f(4, "`Arc<T>` for data shared with spawned tasks"),
    ]),
    c("E0713", "borrow may still be in use when destructor runs", "Returning a reborrow through a value with a `Drop` impl, whose destructor could still use it.", &[
        f(1, "return data you take out first, or return the inner `&'a mut` instead of reborrowing through `self`"),
        f(3, "return owned data"),
    ]),
    c("E0716", "temporary value dropped while borrowed", "A reference points into a temporary (a `lock()` guard, `format!`, a call result) that is dropped at the end of the statement.", &[
        f(1, "bind the temporary with `let` so it lives for the block: `let guard = m.lock().unwrap();`"),
        f(3, "keep the owned value instead of a reference into it"),
    ]),
    c("E0500", "closure requires unique access while borrowed", "A closure needs exclusive access to a value that is already borrowed.", &[
        f(1, "end the other borrow before creating the closure, or pass the value as a closure argument"),
    ]),
    c("E0501", "cannot borrow because previous closure requires unique access", "A closure holds exclusive access and something else borrows the same value while the closure is alive.", &[
        f(1, "call/drop the closure before the other borrow; pass the value as an argument"),
    ]),
    c("E0524", "two closures require unique access at the same time", "Two closures each capture the same value mutably.", &[
        f(1, "use one closure, or pass the value as an argument to each call"),
        f(4, "`RefCell`/`Cell` if both closures must keep it"),
    ]),
    Code { code: "E0308", title: "mismatched types (`&` vs `&mut`)", meaning: "A `&T` was given where `&mut T` is expected (\"types differ in mutability\").", fixes: &[
        f(1, "pass `&mut x` and declare the binding `mut`"),
    ], needs_pattern: true },
    c("lifetime", "lifetime may not live long enough", "The signature's lifetimes do not match how data actually flows (a return value tied to the wrong input, or a `'static` requirement).", &[
        f(1, "tie the output lifetime to the input it really borrows from (`fn f<'a>(x: &'a T, y: &U) -> &'a V`)"),
        f(3, "return owned data"),
        f(1, "add `+ use<'a, T>` (1.82+) or `+ '_` to `impl Trait` returns that capture too much / too little"),
    ]),
    c("not-send", "future cannot be sent between threads safely", "A `!Send` value (`std::sync::MutexGuard`, `Rc`, `RefCell` guard) is alive across an `.await` in a future given to a multi-threaded runtime.", &[
        f(1, "end the guard before `.await`: put it in its own `{ ... }` block or `drop(guard)`"),
        f(4, "`Arc` instead of `Rc`; `tokio::sync::Mutex` only when the lock must be held across `.await`"),
    ]),
];

const fn p(id: &'static str, name: &'static str, codes: &'static [&'static str], any: &'static [&'static str], why: &'static str, fixes: &'static [Fix]) -> Pattern {
    Pattern { id, name, codes, any, why, fixes }
}

/// Ordered most specific first: `classify` returns the first match.
pub const PATTERNS: &[Pattern] = &[
    p("BCK002", "conditional-return-of-borrow", &["E0499", "E0502", "E0505", "E0506"], &["returning this value requires that"],
      "A borrow returned on one branch is treated as live on the other branch too (NLL problem case #3); sound code, current checker rejects it.",
      &[f(2, "use the entry API: `map.entry(k).or_insert_with(..)`"),
        f(1, "check first, then borrow: `if map.contains_key(k) { return map.get_mut(k).unwrap(); }`"),
        f(3, "return an index/key instead of the reference"),
        f(5, "`polonius-the-crab` crate for loops that cannot be restructured")]),
    p("BCK003", "two-elements-mut", &["E0499"], &["split_at_mut", "get_disjoint_mut", "get_many_mut"],
      "Two `&mut` into one slice/map by index: the checker cannot prove `i != j`.",
      &[f(2, "`slice.get_disjoint_mut([i, j])` (1.86+) or `HashMap::get_disjoint_mut`"),
        f(2, "`split_at_mut(hi)` then take one element from each half"),
        f(2, "`slice.swap(i, j)` when you only need to exchange them")]),
    p("BCK004", "whole-self-borrow", &["E0499", "E0502"], &["`*self`"],
      "A `&mut self`/`&self` method borrows the whole struct, even if it only touches one field.",
      &[f(1, "borrow the fields directly in the caller (`let items = &mut self.items; let log = &mut self.log;`)"),
        f(1, "make the helper an associated fn taking only the fields it needs"),
        f(1, "split the struct into sub-structs with their own methods")]),
    p("BCK001", "iterate-and-mutate", &["E0499", "E0502"], &["for ", ".iter()", ".iter_mut()", ".keys()", ".values()"],
      "The collection is borrowed by the loop's iterator and mutated inside the loop (iterator invalidation).",
      &[f(1, "collect what to add/remove first, apply after the loop (`extend`, second pass)"),
        f(2, "`retain`/`retain_mut` to remove, `extract_if` (1.87+) to remove and keep"),
        f(3, "iterate by index (`for i in 0..v.len()`) or use a `VecDeque` worklist")]),
    p("BCK006", "loop-move", &["E0382"], &["previous iteration of loop"],
      "A value is moved inside a loop body, so the second iteration uses a moved value.",
      &[f(1, "borrow inside the loop (`&x`) if the callee does not need ownership"),
        f(3, "clone per iteration (cheap for `Arc`, `Sender`, small strings)"),
        f(1, "move the value out of the loop: create it inside, or move after the loop")]),
    p("BCK007", "implicit-into-iter", &["E0382"], &["into_iter()"],
      "`for x in v` calls `v.into_iter()`, which consumes `v`.",
      &[f(1, "iterate by reference: `for x in &v` / `for x in &mut v` / `v.iter()`"),
        f(1, "read what you need from `v` (`len()`) before the loop")]),
    p("BCK008", "moved-into-closure", &["E0382"], &["moved into closure", "value moved into closure"],
      "A `move` closure took ownership; the variable is used again afterwards.",
      &[f(4, "clone the handle before the closure (`let tx2 = tx.clone();`) and move the clone"),
        f(1, "drop `move` if the closure does not outlive the function")]),
    p("BCK009", "consumed-by-method", &["E0382"], &["due to this method call", "takes ownership of the receiver"],
      "A method taking `self` consumed the value (`into_*`, builder `build()`, `unwrap()` on a non-Copy Option).",
      &[f(1, "use the borrowing variant (`as_ref()`, `iter()`, `as_str()`, `&self` methods)"),
        f(1, "call the consuming method last")]),
    p("BCK010", "partial-move", &["E0382"], &["partial move", "partially moved"],
      "A field was moved out of a struct, so the whole struct can no longer be used.",
      &[f(1, "borrow the field (`&s.name`) or bind it with `ref` in the pattern"),
        f(2, "`mem::take(&mut s.name)` / `Option::take` to leave a default behind")]),
    p("BCK012", "move-out-of-rc", &["E0507"], &["an `rc`", "an `arc`"],
      "`Rc`/`Arc` give shared access only; the value cannot be moved out while other handles may exist.",
      &[f(1, "borrow through the `Rc` (`&*rc`, `rc.field.clone()` of the small part)"),
        f(2, "`Rc::try_unwrap(rc)` / `Rc::unwrap_or_clone` (1.76+) / `Arc::into_inner` (1.70+)")]),
    p("BCK011", "move-out-of-index", &["E0507", "E0508"], &["out of index", "non-copy array", "out of a slice"],
      "Indexing (`v[i]`) yields a place; using it by value would move the element out of the container.",
      &[f(1, "borrow: `&v[i]`"),
        f(2, "`v.swap_remove(i)` / `v.remove(i)` / `mem::take(&mut v[i])` to really take it"),
        f(1, "consume the whole container with `into_iter()` if you no longer need it")]),
    p("BCK013", "move-out-of-mut-ref", &["E0507"], &["behind a mutable reference", "`self.", "`*self"],
      "Moving a field out of `&mut self` would leave the struct with a hole.",
      &[f(2, "`self.field.take()` for `Option`, `mem::take(&mut self.field)` for `Default` types"),
        f(2, "`mem::replace(&mut self.state, State::Empty)` for state machines"),
        f(1, "take `self` by value if the method really consumes the struct")]),
    p("BCK014", "move-out-of-shared-ref", &["E0507"], &["behind a shared reference"],
      "Moving out of `&T` (a `&self` field, a matched reference) is never allowed.",
      &[f(1, "borrow: match on `&x`/`x.as_ref()`, bind with `ref`, use `.iter()`"),
        f(3, "`.clone()` the small part you need to own")]),
    p("BCK015", "spawn-needs-move", &["E0373", "E0597", "E0521"], &["spawn("],
      "`thread::spawn`/`tokio::spawn` require `'static` data: the task may outlive the function, so it cannot borrow locals.",
      &[f(1, "`move ||` / `async move` and move owned values in"),
        f(4, "`let cfg = Arc::clone(&cfg);` per task, then move the clone"),
        f(2, "`std::thread::scope(|s| s.spawn(..))` (1.63+) to borrow locals from threads"),
        f(1, "Tokio: same rule, `tokio::spawn(async move { .. })` with owned or `Arc` captures")]),
    p("BCK016", "static-requirement", &["E0597", "E0521", "E0716", "lifetime"], &["'static"],
      "Something demands `'static` (a `'static` bound, `Box<dyn Trait>` default, global), but the data is borrowed from a local.",
      &[f(3, "own the data (`String`, `Arc<T>`) instead of borrowing"),
        f(1, "relax the bound: `Box<dyn Trait + 'a>`, `impl Trait + '_`, generic `T: 'a`"),
        f(5, "`Box::leak` only for data that truly lives for the whole program")]),
    p("BCK017", "closure-borrow-escapes", &["E0373", "E0521"], &[],
      "A closure that borrows locals is returned or stored somewhere that outlives them.",
      &[f(1, "`move` the captured values into the closure"),
        f(1, "return `impl Fn(..) + '_` tied to the borrowed input instead of `'static`")]),
    p("BCK018", "return-ref-to-local", &["E0515"], &[],
      "The returned reference points at a local or temporary that is dropped when the function returns.",
      &[f(3, "return the owned value"),
        f(1, "borrow from a parameter and tie lifetimes: `fn f<'a>(s: &'a str) -> &'a str`"),
        f(2, "`Cow<'a, str>` for borrow-or-own")]),
    p("BCK019", "lock-or-borrow-temporary", &["E0716"], &[".lock()", ".borrow()", ".borrow_mut()", ".read()", ".write()"],
      "A reference into a guard (`MutexGuard`, `Ref`) outlives the guard temporary, which is dropped at the end of the statement.",
      &[f(1, "`let guard = m.lock().unwrap();` then borrow from `guard` in the same block"),
        f(3, "copy/clone the data out while the guard is alive: `m.lock().unwrap().names().to_vec()`")]),
    p("BCK020", "temporary-dropped", &["E0716"], &[],
      "A reference points into a temporary value created in the same statement.",
      &[f(1, "bind the temporary: `let s = format!(..); let r = s.as_str();`"),
        f(3, "keep the owned value instead")]),
    p("BCK022", "mutate-through-rc", &["E0596", "E0594"], &["in an `rc`", "in an `arc`"],
      "`Rc`/`Arc` only hand out `&T`; mutation needs interior mutability or unique ownership.",
      &[f(2, "`Rc::make_mut`/`Arc::make_mut` (clone-on-write) or `Rc::get_mut` when unique"),
        f(4, "`Rc<RefCell<T>>` (single thread) / `Arc<Mutex<T>>` or atomics (threads)")]),
    p("BCK023", "mutate-behind-shared-ref", &["E0596", "E0594"], &["behind a `&` reference"],
      "Mutation through `&T` (usually a `&self` method or `.iter()`).",
      &[f(1, "take `&mut self` / use `iter_mut()` / `get_mut()`"),
        f(4, "`Cell`/`RefCell`/`Mutex` if mutation through shared references is the design (caches, counters)")]),
    p("BCK021", "binding-not-mut", &["E0384", "E0596", "E0594"], &[],
      "The binding is not declared `mut`.",
      &[f(1, "`let mut x` (or `mut x` in the parameter/pattern)")]),
    p("BCK026", "guard-across-await", &["not-send"], &[],
      "A `std::sync::MutexGuard`, `Rc` or `RefCell` guard is alive at an `.await`, so the future is not `Send`.",
      &[f(1, "scope the guard: `{ let g = m.lock().unwrap(); g.update(); }` before the `.await`"),
        f(4, "`tokio::sync::Mutex` only if the lock must be held across `.await`; `Arc` instead of `Rc`")]),
    p("BCK027", "uninitialized-on-some-path", &["E0381"], &[],
      "Assigned in some branches only, or declared without a value and read before assignment.",
      &[f(1, "initialise from `if`/`match` as an expression"), f(1, "`let ... else` (1.65+) for early return")]),
    p("BCK028", "drop-needs-exclusive", &["E0713"], &[],
      "The type implements `Drop`, so returning a reborrow through it conflicts with the destructor.",
      &[f(1, "return the inner `&'a mut T` field directly, or move data out before returning")]),
    p("BCK029", "mutability-mismatch", &["E0308"], &["differ in mutability", "expected `&mut"],
      "A shared reference is passed where a mutable one is required.",
      &[f(1, "pass `&mut x` and make the binding `mut`")]),
    p("BCK030", "closure-unique-access", &["E0500", "E0501", "E0524"], &[],
      "A closure captures a value mutably while something else also borrows it.",
      &[f(1, "pass the value to the closure as an argument instead of capturing it"),
        f(1, "finish using the closure before the other borrow")]),
    p("BCK005", "shared-borrow-held-across-mutation", &["E0502"], &[],
      "A shared reference taken earlier is still used after a mutation of the same value.",
      &[f(1, "copy the value out before mutating (`let first = v[0];` for `Copy`, `.clone()` otherwise)"),
        f(1, "reorder: finish using the reference before the mutation"),
        f(3, "store an index instead of the reference")]),
];

/// Runtime patterns, reported by runtime_panic.rs (listed here so explain_code.rs can show them).
pub const RUNTIME_PATTERNS: &[Pattern] = &[
    p("BCK024", "refcell-double-borrow", &["runtime"], &["already borrowed", "already mutably borrowed"],
      "Two `RefCell` guards overlap at run time: a `borrow_mut()` while a `borrow()`/`borrow_mut()` guard is alive, often through a re-entrant callback.",
      &[f(1, "shorten guards: `let n = cell.borrow().len();` (guard dropped at `;`) instead of holding `Ref` in a variable"),
        f(1, "snapshot before calling out: `let ls = self.listeners.borrow().clone(); for l in ls { l(..) }`"),
        f(2, "`try_borrow_mut()` and defer the change (queue it) instead of panicking"),
        f(1, "restructure so the callback receives data, not the owner")]),
    p("BCK025", "mutex-poisoned", &["runtime"], &["poisonerror", "poisoned lock"],
      "A thread panicked while holding the lock; every later `lock().unwrap()` fails. The real bug is the earlier panic.",
      &[f(1, "fix the panic that happened while the guard was held (shown as the root cause)"),
        f(2, "recover deliberately: `m.lock().unwrap_or_else(PoisonError::into_inner)`; `Mutex::clear_poison` (1.77+)"),
        f(1, "keep critical sections small and panic-free")]),
];

pub fn find_code(code: &str) -> Option<&'static Code> {
    CODES.iter().find(|c| c.code.eq_ignore_ascii_case(code))
}

pub fn find_pattern(key: &str) -> Option<&'static Pattern> {
    PATTERNS.iter().chain(RUNTIME_PATTERNS).find(|p| p.id.eq_ignore_ascii_case(key) || p.name == key)
}

/// First pattern registered for `code` whose substrings occur in `text` (lower-cased by the caller).
pub fn classify(code: &str, text: &str) -> Option<&'static Pattern> {
    PATTERNS.iter().find(|p| p.codes.contains(&code) && (p.any.is_empty() || p.any.iter().any(|n| text.contains(n))))
}

pub fn tier_name(tier: u8) -> &'static str {
    TIERS[(tier as usize).saturating_sub(1).min(TIERS.len() - 1)]
}
