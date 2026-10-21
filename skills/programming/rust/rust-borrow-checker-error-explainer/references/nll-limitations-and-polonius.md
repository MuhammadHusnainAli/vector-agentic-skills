# NLL Limitations and Polonius

Non-lexical lifetimes (NLL) accept most sound code, but a few well-known shapes are still rejected even though
they are memory-safe. Recognise them quickly so you do not waste time "fixing" code that is correct in
principle: apply the standard workaround and move on.

## Contents

- [How NLL decides](#how-nll-decides)
- [Problem case #3: conditional return of a borrow](#problem-case-3-conditional-return-of-a-borrow)
- [Get-or-insert on maps](#get-or-insert-on-maps)
- [Cursor loops over linked structures](#cursor-loops-over-linked-structures)
- [Borrows that flow into a loop's next iteration](#borrows-that-flow-into-a-loops-next-iteration)
- [Two-phase borrows: what is already accepted](#two-phase-borrows-what-is-already-accepted)
- [Destructors and liveness](#destructors-and-liveness)
- [Polonius status](#polonius-status)
- [How to tell an NLL limitation from a real bug](#how-to-tell-an-nll-limitation-from-a-real-bug)

## How NLL decides

NLL computes, for every borrow, the set of program points where it may still be used ("live"). A conflicting
access at a point inside that set is an error. The weakness: when a borrow is **returned from the function on
some path**, its lifetime must cover the entire rest of the function (the caller's region), so NLL treats it
as live on every path after the borrow was created, including paths where it was not returned.

The newer analysis, Polonius, tracks *which loans* flow into *which origins* along each control-flow path, so it
sees that on the non-returning path the loan is dead.

## Problem case #3: conditional return of a borrow

```rust
use std::collections::HashMap;

// Rejected today (E0499 on the insert), accepted by Polonius:
//
// fn get_default<'m>(map: &'m mut HashMap<u32, String>, key: u32) -> &'m mut String {
//     match map.get_mut(&key) {
//         Some(v) => v,                       // borrow returned on this path...
//         None => {
//             map.insert(key, String::new()); // ...so it is "live" here too: E0499
//             map.get_mut(&key).unwrap()
//         }
//     }
// }

fn get_default<'m>(map: &'m mut HashMap<u32, String>, key: u32) -> &'m mut String {
    map.entry(key).or_default()
}
```

The compiler's tell-tale label: **"returning this value requires that `*map` is borrowed for `'m`"** (or
`'1`). `parse_diagnostics` reports it as BCK002.

Workarounds, in order:

1. A purpose-built API: `entry`, `get_or_insert_with` on `Option`, `Vec::last_mut().unwrap()` after a push.
2. Test first, borrow second: `if map.contains_key(&k) { return map.get_mut(&k).unwrap(); }`. Two lookups,
   no clone of the key on hits.
3. Return something that is not a borrow: an index, a key, a `bool` "found".
4. The `polonius-the-crab` crate, which wraps the pattern in a macro that is sound under today's checker.

## Get-or-insert on maps

With `String` keys and `&str` lookups, `entry(key.to_owned())` allocates on every call even when the key
exists. Options:

```rust
use std::collections::HashMap;

fn bucket<'m>(map: &'m mut HashMap<String, Vec<u32>>, key: &str) -> &'m mut Vec<u32> {
    if !map.contains_key(key) {
        map.insert(key.to_owned(), Vec::new()); // allocate only on a miss
    }
    map.get_mut(key).expect("just inserted")
}
```

`hashbrown::HashMap::entry_ref(&str)` does a single lookup and clones the key only when inserting.

## Cursor loops over linked structures

Walking a linked list or tree with a `&mut` cursor and stopping at a node is another case NLL rejects when
the loop may return the cursor:

```rust
struct Node { value: i32, next: Option<Box<Node>> }

// Rejected (E0499/E0506): `cur` is reassigned while the loan from `cur.next.as_mut()` may be returned.
//
// fn last_mut(mut cur: &mut Node) -> &mut Node {
//     while let Some(next) = cur.next.as_mut() {
//         cur = next;
//     }
//     cur
// }

fn last_mut(mut cur: &mut Node) -> &mut Node {
    while cur.next.is_some() {
        cur = cur.next.as_mut().unwrap(); // test first, then borrow unconditionally
    }
    cur
}

fn find_mut(mut cur: &mut Node, target: i32) -> Option<&mut Node> {
    loop {
        if cur.value == target {
            return Some(cur);
        }
        cur = cur.next.as_deref_mut()?;   // `?` returns None at the end of the list
    }
}
```

The trick is the same as problem case #3: decide with a check that does not keep a borrow alive, then take
the borrow on a path where it is always used.

## Borrows that flow into a loop's next iteration

```rust
fn longest<'a>(words: &[&'a str]) -> &'a str {
    let mut best = "";
    for &w in words {
        if w.len() > best.len() {
            best = w;          // fine: `best` holds a borrow of the input, not of a local
        }
    }
    best
}
```

Errors here usually mean a reference to a value created inside the loop is stored outside it (E0597 "does
not live long enough"). Move the owner out of the loop or store owned data:

```rust
fn collect_upper(words: &[&str]) -> Vec<String> {
    let mut out = Vec::new();
    for w in words {
        let up = w.to_uppercase();   // owned inside the loop
        out.push(up);                // move it out; a `&up` would die at the end of the iteration
    }
    out
}
```

## Two-phase borrows: what is already accepted

Some code that looks like it should conflict compiles because of two-phase borrows: the `&mut` for a method
receiver is "reserved" first and only "activated" when the call runs, so the arguments may read the same
value.

```rust
fn grow(v: &mut Vec<usize>) {
    v.push(v.len());          // OK: `&mut *v` reserved, `v.len()` reads, then push activates
    let n = v[0];
    // v[n % v.len()] += 1;   // E0502: `IndexMut` borrows `*v` before the index reads `v.len()`
    let i = n % v.len();      // compute the index first
    v[i] += 1;
}
```

Two-phase borrows apply to autoref method calls (`v.push(v.len())`), not to indexing with `IndexMut`
(`v[v.len() - 1] += 1` on a `Vec` is E0502; compute the index into a local first) and not to an explicit
`&mut` taken into a variable first (`let r = &mut v; r.push(v.len());` is E0502).

## Destructors and liveness

NLL ends a borrow at its last *use*, and dropping a value whose type has a destructor counts as a use. A
`MutexGuard`, `Ref`, `RefMut`, `Peekable<Iter>` or any struct holding a reference with a `Drop` impl keeps its
borrow alive to the end of the scope.

```rust
use std::sync::Mutex;

fn total(m: &Mutex<Vec<u32>>) -> u32 {
    let sum = {
        let g = m.lock().unwrap();
        g.iter().sum()          // guard dropped at the end of this block
    };
    m.lock().unwrap().push(sum);
    sum
}
```

The compiler label is "borrow might be used here, when `x` is dropped and runs the `Drop` code". Drop it
explicitly (`drop(g)`) or scope it with a block.

## Polonius status

- Polonius is the reformulated borrow checker (origins as sets of loans, flow-sensitive). A first version runs
  on nightly with `-Zpolonius` (the older datalog prototype) / `-Zpolonius=next` (the in-tree "location
  sensitive" implementation).
- The Rust project's goal is to stabilise the subset that accepts problem case #3 and the cursor loops above;
  as of this writing it is not on stable. Do not rely on it for production code; write the workaround.
- When it lands, the workarounds stay correct; they only become unnecessary.

## How to tell an NLL limitation from a real bug

| Sign | Likely |
|------|--------|
| Label "returning this value requires that `x` is borrowed for `'1`" and the conflicting access is on a path that does **not** return | NLL limitation (BCK002) |
| `while let Some(n) = cur.next.as_mut() { cur = n; }` style cursor update | NLL limitation (cursor loop) |
| The reference really is used after the mutation on the same path | real conflict: restructure |
| Reference into a value dropped earlier (E0597, E0716, E0515) | real bug: would be a dangling pointer |
| `'static` required by `spawn` | real requirement: own the data |

If you are unsure, write the code with indices or owned data first; if that version is obviously correct and
the borrowing version is the same logic, it was the limitation.
