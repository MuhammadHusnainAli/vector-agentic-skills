# Formulas and Debugging

## Formula basics

- Formulas are used wherever a value is expected (Assign, Move, Text, conditions).
- Reference layer properties with the layer name in backticks: `` `Thumb`.x ``, `` `Card`.width ``,
  `` `Email input`.text ``, `` `List`.scrollY ``.
- Reference variables by name: `cartCount`, `code`.
- Arithmetic: `+ - * /`, parentheses; comparisons `= != > < >= <=` in conditions.
- Text joins with `+` or a concat function, depending on the version; numbers inside text may need conversion.

Common functions (check the formula reference for your ProtoPie version; names occasionally change):

| Purpose | Functions |
|---------|-----------|
| Rounding and limits | `round`, `floor`, `ceil`, `abs`, `min`, `max` |
| Maths | `sqrt`, `pow`, `sin`, `cos`, `random` |
| Text | `length`, `left`, `right`, `indexOf`, `replace`, `lowerCase`, `upperCase` |
| Conversion | `number(text)`, `text(number)` |

Clamp a value and map a drag position to 0-100:
```
min(max(value, 0), 100)
round((`Thumb`.x - `Track`.x) / (`Track`.width - `Thumb`.width) * 100)
```

## Debugging approach

1. Open the Debug panel in preview: it shows variable values and which triggers fire.
2. Put a temporary text layer that shows the variable or formula result on screen.
3. Simplify: disable other interactions on the layer to find conflicts.
4. Check names: formulas break silently when a referenced layer is renamed.

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Variable never changes | Assign in an interaction whose trigger never fires; wrong scope | Check the trigger in Debug; set scope to all scenes if it must survive scene changes |
| Value resets after Jump | Scene-scoped variable | Make it global |
| Two things happen on one tap | Two interactions with the same trigger on overlapping layers | Use one interaction with conditions, or restrict hit areas |
| Drag fights with scroll | Drag inside a scroll container | Constrain drag axis; use conditions on direction; or move the dragged layer out of the scroll container |
| Keyboard doesn't appear | Text layer used instead of an Input layer; no Focus response | Use an Input layer; Focus on scene start or tap |
| Animation jumps | Responses with no duration, or conflicting Move responses | Add duration/easing; Stop previous animations before starting new ones |
| Pie is slow | Large images, videos, many layers in one scene | Compress media; split into scenes; use components |

## Keeping pies maintainable

- Name layers by role ("Email input", "Cart badge") and interactions by intent ("Validate email on continue").
- Group interactions by feature; add notes.
- Keep a "Reset" interaction (hidden tap area or Start trigger) that sets every variable to its initial value.
- Use components for repeated items; pass data with Send/Receive values instead of copying logic.
