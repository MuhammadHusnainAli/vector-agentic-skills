# Notation and Annotation Kit

## Markers

- Numbered circles (1, 2, 3...) placed beside the element with a thin leader line; the number refers to a note in the
  annotation panel next to the frame.
- One number per rule; reuse the same number wherever the rule applies.
- Keep annotations outside the frame, in a column to the right (or below on wide frames).

## Category colours (choose and keep)

| Category | Colour | Examples |
|----------|--------|----------|
| Layout and spacing | Magenta | Gaps, padding, sizing, max widths |
| Behaviour | Blue | Interactions, scroll, sticky, states |
| Content | Orange | Truncation, copy rules, limits |
| Responsive | Purple | Breakpoint changes |
| Accessibility | Green | Headings, focus order, names (see accessibility-annotation-writer) |

Use colours that aren't in the product's palette so annotations never look like UI. Add a legend on every annotated page.

## Annotation kit in Figma

Build a small component library (on a separate page or library file):
- **Marker**: number property, category variant (colour), size small/large.
- **Note card**: marker + title + body text + optional token chips; auto layout; category variant.
- **Measurement line**: horizontal/vertical with label slot (for the few measurements that matter).
- **Breakpoint label**: "Below 768", "768-1199", ">= 1200".
- **Legend**: category colours and marker meaning.

Figma's built-in Dev Mode annotations (with categories and pinned properties) cover many cases; use the kit for
cross-frame rules and presentations.

## Hygiene

- Put annotations on a separate layer group per frame ("Annotations - S03") so they can be hidden.
- Update annotations when the design changes; stale annotations are worse than none.
- Date or version the annotation panel.
