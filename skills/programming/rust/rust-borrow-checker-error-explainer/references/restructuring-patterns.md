# Restructuring Patterns

Fixes from the top of the ladder: change the shape of the code so the borrows no longer overlap, without
adding clones, reference counting or runtime checks. Every example compiles on stable Rust 2021; the
rejected version is kept as a comment with its error code.

## Contents

- [Shorten the borrow](#shorten-the-borrow)
- [Collect then apply](#collect-then-apply)
- [Remove while iterating](#remove-while-iterating)
- [Two mutable elements](#two-mutable-elements)
- [Split borrows of struct fields](#split-borrows-of-struct-fields)
- [Entry API instead of get-then-insert](#entry-api-instead-of-get-then-insert)
- [Taking values out of `&mut`](#taking-values-out-of-mut)
- [State machines with `mem::replace`](#state-machines-with-memreplace)
- [Indices and keys instead of references](#indices-and-keys-instead-of-references)
- [Arenas for graphs and trees](#arenas-for-graphs-and-trees)
- [Self-referential structs](#self-referential-structs)
- [Worklists instead of recursion over `&mut`](#worklists-instead-of-recursion-over-mut)
- [Choosing a pattern](#choosing-a-pattern)

## Shorten the borrow

Most E0502/E0499 errors disappear once the first borrow ends before the conflicting access. NLL already
ends a borrow at its last use, so the job is to move that last use earlier or copy the value out.

```rust
fn bump_first(v: &mut Vec<u32>) {
    // let first = &v[0];        // shared borrow...
    // v.push(*first + 1);       // E0502: ...still used by the argument
    let first = v[0];            // u32 is Copy: no borrow survives the statement
    v.push(first + 1);
}

fn log_len_then_clear(names: &mut Vec<String>) {
    let n = names.len();         // read what you need first
    names.clear();
    println!("cleared {n} names");
}
```

When the value is not `Copy`, clone only the small piece you need (`let id = order.id.clone();`), not the
whole container.

## Collect then apply

The iterator borrows the collection for the whole loop. Compute the changes into a separate `Vec`, end the
loop, then apply them.

```rust
#[derive(Debug, Clone)]
struct Job { id: u32, retries: u32, failed: bool }

fn schedule_retries(jobs: &mut Vec<Job>) {
    // for j in jobs.iter() { if j.failed { jobs.push(..) } }   // E0502
    let retries: Vec<Job> = jobs
        .iter()
        .filter(|j| j.failed && j.retries < 3)
        .map(|j| Job { id: j.id, retries: j.retries + 1, failed: false })
        .collect();
    jobs.retain(|j| !j.failed);
    jobs.extend(retries);
}
```

For maps, collect keys first: `let stale: Vec<K> = map.iter().filter(..).map(|(k, _)| k.clone()).collect();
for k in stale { map.remove(&k); }` (or simply `map.retain(|_, v| !v.stale)`).

## Remove while iterating

| Goal | API | Since |
|------|-----|-------|
| Drop elements matching a predicate | `Vec::retain`, `HashMap::retain`, `VecDeque::retain` | 1.0 / 1.18 / 1.4 |
| Mutate and maybe drop in one pass | `Vec::retain_mut` | 1.61 |
| Remove and keep the removed elements | `Vec::extract_if(range, pred)` | 1.87 |
| Remove a range | `Vec::drain(range)` | 1.6 |
| Remove one element by index, order irrelevant | `Vec::swap_remove(i)` | 1.0 |

```rust
fn split_expired(sessions: &mut Vec<(u64, String)>, now: u64) -> Vec<(u64, String)> {
    let mut expired = Vec::new();
    sessions.retain(|s| {
        if s.0 < now { expired.push(s.clone()); false } else { true }
    });
    expired
}
```

On Rust 1.87+ the same is `sessions.extract_if(.., |s| s.0 < now).collect()` without the clone.

## Two mutable elements

The checker cannot prove that `v[i]` and `v[j]` are different places, so two `&mut v[..]` conflict (E0499).
Use an API that checks or guarantees disjointness.

```rust
#[derive(Debug)]
struct Account { balance: i64 }

fn transfer(accts: &mut [Account], from: usize, to: usize, amount: i64) {
    // let a = &mut accts[from]; let b = &mut accts[to];   // E0499
    assert_ne!(from, to, "transfer to self");
    let (a, b) = if from < to {
        let (lo, hi) = accts.split_at_mut(to);
        (&mut lo[from], &mut hi[0])
    } else {
        let (lo, hi) = accts.split_at_mut(from);
        (&mut hi[0], &mut lo[to])
    };
    a.balance -= amount;
    b.balance += amount;
}
```

Rust 1.86 adds `<[T]>::get_disjoint_mut([i, j])`, which returns `Result<[&mut T; N], GetDisjointMutError>`
(the error says whether an index was out of bounds or two overlapped), and `HashMap::get_disjoint_mut([&k1,
&k2])`, which returns `[Option<&mut V>; N]` and panics on duplicate keys. To just exchange two elements,
`slice.swap(i, j)` needs no references at all.

## Split borrows of struct fields

A method taking `&mut self` borrows the whole struct. Inside one function, borrowing two different fields is
fine because the checker tracks places (`self.a`, `self.b`) separately.

```rust
struct Renderer { frames: Vec<String>, stats: Stats }
#[derive(Default)]
struct Stats { drawn: u32 }

impl Stats {
    fn record(&mut self) { self.drawn += 1; }
}

impl Renderer {
    fn draw_all(&mut self) {
        // for f in &self.frames { self.record_frame(f) }   // E0502 if record_frame takes &mut self
        let stats = &mut self.stats;                         // borrow the field, not self
        for frame in &self.frames {
            let _ = frame.len();
            stats.record();
        }
    }
}
```

Three ways to keep the split when the logic lives in a helper:

1. Make the helper a method on the field's type (`Stats::record` above).
2. Make it an associated function that takes the fields: `fn record(stats: &mut Stats, frame: &str)`.
3. Split the struct: `struct Renderer { frames: Frames, stats: Stats }` with methods on each part.

Edition 2021 closures capture disjoint fields too: `|| self.stats.drawn += 1` captures only `self.stats.drawn`.

## Entry API instead of get-then-insert

```rust
use std::collections::HashMap;

fn count_words(text: &str) -> HashMap<&str, usize> {
    let mut counts = HashMap::new();
    for w in text.split_whitespace() {
        *counts.entry(w).or_insert(0) += 1;
    }
    counts
}

fn cache_get<'m>(cache: &'m mut HashMap<u64, Vec<u8>>, key: u64, load: impl FnOnce() -> Vec<u8>) -> &'m mut Vec<u8> {
    // if let Some(v) = cache.get_mut(&key) { return v; }   // E0499 (NLL problem case #3)
    // cache.insert(key, load()); cache.get_mut(&key).unwrap()
    cache.entry(key).or_insert_with(load)
}
```

`entry` needs an owned key. With `String` keys and a `&str` lookup, the clone on every call can matter; then
check first (`if cache.contains_key(k) { return cache.get_mut(k).unwrap(); }`), which does two lookups on a
hit but allocates only on a miss. `hashbrown`'s `entry_ref` avoids both costs.

## Taking values out of `&mut`

You cannot move a field out of `&mut self` (E0507) because the struct would be left with a hole. Put
something back in the same step:

| Field type | Take it with | Leaves behind |
|------------|--------------|---------------|
| `Option<T>` | `self.x.take()` | `None` |
| `Option<T>`, conditionally | `self.x.take_if(|v| pred(v))` (1.80) | `None` if taken |
| `T: Default` (`Vec`, `String`, maps) | `std::mem::take(&mut self.x)` | `T::default()` |
| any `T` | `std::mem::replace(&mut self.x, new)` | `new` |
| two places | `std::mem::swap(&mut a, &mut b)` | each other's values |

```rust
use std::mem;

struct Batcher { pending: Vec<String>, last_error: Option<String> }

impl Batcher {
    fn flush(&mut self) -> Vec<String> { mem::take(&mut self.pending) }
    fn error(&mut self) -> Option<String> { self.last_error.take() }
}
```

## State machines with `mem::replace`

Transitions that consume the old state need ownership of it. Swap in a cheap placeholder, match on the old
value, store the new one.

```rust
use std::mem;

enum Conn {
    Idle,
    Connecting { attempts: u32 },
    Open { session: String },
    Closed,
}

struct Client { state: Conn }

impl Client {
    fn on_connected(&mut self, session: String) {
        self.state = match mem::replace(&mut self.state, Conn::Closed) {
            Conn::Connecting { .. } => Conn::Open { session },
            other => other, // unexpected event: keep the old state
        };
    }
    fn retry(&mut self) {
        if let Conn::Connecting { attempts } = &mut self.state {
            *attempts += 1;                  // in-place change: a `&mut` binding is enough
        } else if matches!(self.state, Conn::Idle) {
            self.state = Conn::Connecting { attempts: 1 };
        }
    }
}
```

If the method can consume `self` (`fn connect(self) -> Client`), typestate types avoid the placeholder.

## Indices and keys instead of references

A stored reference freezes its target for as long as the holder lives. Storing an index or key instead lets
you mutate the collection freely and re-borrow briefly when needed.

```rust
struct Library { books: Vec<Book>, loans: Vec<Loan> }
struct Book { title: String, available: bool }
struct Loan { book: usize, member: String } // index into `books`, not &Book

impl Library {
    fn lend(&mut self, book: usize, member: &str) -> Result<(), String> {
        let b = self.books.get_mut(book).ok_or("no such book")?;
        if !b.available { return Err(format!("{} is out", b.title)); }
        b.available = false;
        self.loans.push(Loan { book, member: member.to_owned() });
        Ok(())
    }
}
```

Costs: an index can go stale if elements are removed. Use generational indices (`slotmap`, `thunderdome`) or
never-removing arenas when that matters.

## Arenas for graphs and trees

Doubly linked lists, graphs with cycles and parent pointers cannot be expressed with plain `&mut`. Keep all
nodes in a `Vec` and link them by index.

```rust
#[derive(Debug)]
struct Node { name: String, parent: Option<usize>, children: Vec<usize> }

#[derive(Default)]
struct Tree { nodes: Vec<Node> }

impl Tree {
    fn add(&mut self, name: &str, parent: Option<usize>) -> usize {
        let id = self.nodes.len();
        self.nodes.push(Node { name: name.into(), parent, children: Vec::new() });
        if let Some(p) = parent {
            self.nodes[p].children.push(id);
        }
        id
    }
    fn path(&self, mut id: usize) -> Vec<&str> {
        let mut out = vec![self.nodes[id].name.as_str()];
        while let Some(p) = self.nodes[id].parent {
            out.push(&self.nodes[p].name);
            id = p;
        }
        out.reverse();
        out
    }
}
```

`Rc<RefCell<Node>>` with `Weak` parents also works but adds runtime borrow checks, reference cycles to manage
and noisy code; prefer the arena unless nodes must be shared across independent owners.

## Self-referential structs

`struct Doc { text: String, words: Vec<&str> }` cannot be written: the references would point into a field
of the same struct, and moving the struct would move `text`'s `String` header (the heap buffer stays, but the
type system cannot express that). Options, best first:

1. Store ranges: `words: Vec<std::ops::Range<usize>>` and slice on demand (`&self.text[r.clone()]`).
2. Split owner and view: keep `text: String` in the caller and build `struct Words<'a> { words: Vec<&'a str> }`
   that borrows it.
3. Own the pieces: `Vec<String>` (allocations) or `Arc<str>` slices.
4. Crates designed for it: `self_cell` (small, no proc macro), `yoke` (zero-copy deserialization),
   `ouroboros` (macro-based). Avoid hand-written `unsafe` pinning.

```rust
struct Doc { text: String, words: Vec<std::ops::Range<usize>> }

impl Doc {
    fn new(text: String) -> Self {
        let mut words = Vec::new();
        let mut start = None;
        for (i, ch) in text.char_indices() {
            match (ch.is_whitespace(), start) {
                (false, None) => start = Some(i),
                (true, Some(s)) => { words.push(s..i); start = None; }
                _ => {}
            }
        }
        if let Some(s) = start { words.push(s..text.len()); }
        Doc { text, words }
    }
    fn word(&self, n: usize) -> Option<&str> { self.words.get(n).map(|r| &self.text[r.clone()]) }
}
```

## Worklists instead of recursion over `&mut`

Recursing while holding `&mut` to a parent and a child at the same time fails; a queue of indices does not.

```rust
use std::collections::VecDeque;

fn mark_reachable(edges: &[Vec<usize>], start: usize) -> Vec<bool> {
    let mut seen = vec![false; edges.len()];
    let mut queue = VecDeque::from([start]);
    while let Some(n) = queue.pop_front() {
        if std::mem::replace(&mut seen[n], true) { continue; }
        queue.extend(edges[n].iter().copied().filter(|&m| !seen[m]));
    }
    seen
}
```

## Choosing a pattern

| Situation | Pattern |
|-----------|---------|
| Reference used once more after a mutation | shorten the borrow / copy out |
| Loop adds or removes elements of the collection it walks | collect then apply; `retain`/`extract_if` |
| Two elements of one slice/map mutably | `split_at_mut`, `get_disjoint_mut`, `swap` |
| Helper method needs `&mut self` while a field is borrowed | split borrows, associated fn, sub-structs |
| Lookup-or-insert returning a reference | entry API |
| Moving a field out of `&mut self` | `take`/`mem::take`/`mem::replace` |
| Enum state transitions | `mem::replace` with a placeholder, or typestate |
| Long-lived references between objects | indices/keys, arenas, generational slots |
| A struct that wants to borrow from itself | ranges, owner + view split, `self_cell`/`yoke` |
