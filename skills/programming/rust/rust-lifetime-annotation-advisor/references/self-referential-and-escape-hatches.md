# Self-Referential Structs and Escape Hatches

What to do when the design wants a struct that owns data *and* holds references into it, or a graph whose
nodes point at each other: the cases plain lifetimes cannot express. Choose the simplest option that works;
reach for crates only when ownership-based designs are clearly worse.

## Contents

- [Why self-reference cannot be written](#why-self-reference-cannot-be-written)
- [Option 1: store offsets or ranges](#option-1-store-offsets-or-ranges)
- [Option 2: split owner and view](#option-2-split-owner-and-view)
- [Option 3: own the pieces](#option-3-own-the-pieces)
- [Option 4: arenas and indices](#option-4-arenas-and-indices)
- [Option 5: `Rc`/`Arc` graphs with `Weak`](#option-5-rcarc-graphs-with-weak)
- [Option 6: crates built for self-reference](#option-6-crates-built-for-self-reference)
- [`Pin` is not a lifetime tool](#pin-is-not-a-lifetime-tool)
- [Decision table](#decision-table)

## Why self-reference cannot be written

```rust,compile_fail
struct Doc {
    text: String,
    words: Vec<&'??? str>, // no lifetime names "borrowed from my own `text` field"
}
```

Even with a lifetime parameter (`struct Doc<'a> { text: String, words: Vec<&'a str> }`), you cannot construct
it: `words` would borrow `text` while `text` is being moved into the struct, and moving a `Doc` later would
move the `String` (its heap buffer stays put, but the type system cannot know that). The compiler rejects
every attempt with E0505/E0597; the fix is a different shape, not a different lifetime.

## Option 1: store offsets or ranges

The cheapest and most robust: keep the owner, store positions instead of references, borrow on demand.

```rust
use std::ops::Range;

struct Doc {
    text: String,
    words: Vec<Range<usize>>,
}

impl Doc {
    fn parse(text: String) -> Doc {
        let mut words = Vec::new();
        let mut start = None;
        for (i, c) in text.char_indices() {
            match (c.is_whitespace(), start) {
                (false, None) => start = Some(i),
                (true, Some(s)) => { words.push(s..i); start = None; }
                _ => {}
            }
        }
        if let Some(s) = start { words.push(s..text.len()); }
        Doc { text, words }
    }

    fn words(&self) -> impl Iterator<Item = &str> + '_ {
        self.words.iter().map(|r| &self.text[r.clone()])
    }
}

fn main() {
    let d = Doc::parse("owned text survives moves".to_string());
    let moved = d;                                    // moving is fine: ranges stay valid
    assert_eq!(moved.words().nth(1), Some("text"));
}
```

Ranges cost 16 bytes each on 64-bit targets (a `Range<u32>` halves that for inputs under 4 GiB).

## Option 2: split owner and view

Let the caller own the data and build a borrowing view next to it. This is how most zero-copy parsers work.

```rust
struct Tokens<'a> {
    words: Vec<&'a str>,
}

impl<'a> Tokens<'a> {
    fn new(text: &'a str) -> Self {
        Tokens { words: text.split_whitespace().collect() }
    }
}

fn main() {
    let text = std::fs::read_to_string("Cargo.toml").unwrap_or_else(|_| "a b c".into()); // owner
    let tokens = Tokens::new(&text);                                                         // view
    println!("{} words", tokens.words.len());
}
```

The cost: two values instead of one, and the view cannot outlive the owner (cannot be returned from the
function that created the owner, or stored in a long-lived struct).

## Option 3: own the pieces

Allocate per piece: `Vec<String>`, or `Arc<str>` when pieces are shared. Simplest code, more allocations.
Fine for configs, CLI arguments, error messages and anything not on a hot path.

```rust
use std::sync::Arc;

struct Record { fields: Vec<Arc<str>> }

fn parse(line: &str) -> Record {
    Record { fields: line.split(',').map(Arc::from).collect() }
}
```

## Option 4: arenas and indices

For graphs and trees (parent pointers, cycles), store nodes in a `Vec` and link by index. A typed index keeps
ids from different arenas apart.

```rust
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
struct NodeId(usize);

struct Node { label: String, parent: Option<NodeId>, children: Vec<NodeId> }

#[derive(Default)]
struct Tree { nodes: Vec<Node> }

impl Tree {
    fn add(&mut self, label: &str, parent: Option<NodeId>) -> NodeId {
        let id = NodeId(self.nodes.len());
        self.nodes.push(Node { label: label.into(), parent, children: vec![] });
        if let Some(p) = parent { self.nodes[p.0].children.push(id); }
        id
    }
    fn depth(&self, mut id: NodeId) -> usize {
        let mut d = 0;
        while let Some(p) = self.nodes[id.0].parent { d += 1; id = p; }
        d
    }
}
```

When nodes are removed, use generational indices (`slotmap`, `thunderdome`) so stale ids are detected. A
bump arena such as `bumpalo` or `typed-arena` gives real references `&'arena Node` that may point at each
other, all freed together; the arena's lifetime is then the only one in the API.

## Option 5: `Rc`/`Arc` graphs with `Weak`

Shared ownership with runtime-checked mutation. Use `Weak` for back edges to avoid leaks from cycles.

```rust
use std::cell::RefCell;
use std::rc::{Rc, Weak};

struct Node {
    name: String,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}

fn link(parent: &Rc<Node>, child: Rc<Node>) {
    *child.parent.borrow_mut() = Rc::downgrade(parent);
    parent.children.borrow_mut().push(child);
}

fn main() {
    let root = Rc::new(Node { name: "root".into(), parent: RefCell::new(Weak::new()), children: RefCell::new(vec![]) });
    let leaf = Rc::new(Node { name: "leaf".into(), parent: RefCell::new(Weak::new()), children: RefCell::new(vec![]) });
    link(&root, leaf.clone());
    assert_eq!(leaf.parent.borrow().upgrade().map(|p| p.name.clone()), Some("root".to_string()));
}
```

Costs: a heap allocation per node, refcount traffic, possible `BorrowMutError` panics, more verbose code.
Prefer the arena unless nodes really have independent owners.

## Option 6: crates built for self-reference

| Crate | Approach | Good for |
|-------|----------|----------|
| `self_cell` | declarative macro, owner + dependent in one value, no proc macro | "owned text + parsed view" in one struct |
| `ouroboros` | proc macro generating builders and accessors | several borrowed fields; heavier compile |
| `yoke` | `Yoke<Y, C>`: a zero-copy deserialized value plus its backing cart (`Rc<[u8]>`, `Arc`) | caching parsed data from owned buffers (ICU4X) |
| `owning_ref` | historical; has known soundness issues | do not use in new code |

```rust,ignore
// self_cell: one value that owns the text and a view into it.
use self_cell::self_cell;

struct Ast<'a>(Vec<&'a str>);

self_cell!(
    struct OwnedAst {
        owner: String,
        #[covariant]
        dependent: Ast,
    }
);

let ast = OwnedAst::new("a b c".to_string(), |s| Ast(s.split(' ').collect()));
assert_eq!(ast.borrow_dependent().0.len(), 3);
```

Hand-rolled `unsafe` with raw pointers into your own fields is easy to get wrong (moves, drops, variance);
use a crate whose soundness has been reviewed.

## `Pin` is not a lifetime tool

`Pin<P>` promises that a value will not move again, which async state machines need (a future may hold
references into its own fields across `.await`). It does not let *your* structs borrow from themselves in
safe code, and it does not change lifetimes. You meet it when implementing `Future`/`Stream` by hand (use
`pin-project-lite` for field projection) or when boxing futures (`Pin<Box<dyn Future + 'a>>`).

## Decision table

| Need | Choose |
|------|--------|
| Owned buffer + positions into it, value is moved around | ranges/offsets (Option 1) |
| Short-lived processing of caller-owned input | owner + view (Option 2) |
| Small or infrequent data, simplicity first | own the pieces, `Arc<str>` for sharing (Option 3) |
| Trees/graphs with parent links or cycles | arena + typed indices; `slotmap` if nodes are removed (Option 4) |
| Nodes with independent owners across the program | `Rc`/`Arc` + `Weak` back edges (Option 5) |
| One value that must own data and expose a borrowed view, and options 1-3 are clearly worse | `self_cell` / `yoke` (Option 6) |
