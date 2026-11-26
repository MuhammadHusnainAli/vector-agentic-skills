# Variant Hierarchy and Behaviour

## Variants and their jobs

| Variant | Job | Typical style | Do not use for |
|---------|-----|---------------|----------------|
| Primary | The one action that moves the user forward in this region | Filled, brand/action colour | More than one per region; navigation |
| Secondary | Alternatives of equal validity (Save draft next to Publish) | Outline or tonal fill | The main path |
| Tertiary / ghost | Low-emphasis actions, toolbars, dense UIs | Text only, state layer on hover | Isolated actions with no surrounding context (they don't look clickable) |
| Danger | Irreversible or destructive commit (Delete account) | Filled red for the final confirm; outline/text red for the entry point | Every "Remove" in a list (use tertiary + undo) |
| Link-style | Inline actions inside text | Underlined text | Anything that is not inline |
| Icon button | Repeated compact actions with universally known icons | Icon + state layer, tooltip and aria-label | Unfamiliar actions (add the label) |

Five is enough. Variants named by colour (blue, grey) instead of job are a sign the system follows screens, not roles.

## Sizes (8px grid example)

| Size | Height | Horizontal padding | Type | Icon | Use |
|------|--------|-------------------|------|------|-----|
| sm | 32 | 12 | label-sm (14/20) | 16 | Dense tables, toolbars (desktop only, or with 44px hit area) |
| md | 40 | 16 | label-md (14-16/20) | 20 | Default web |
| lg | 48 | 20-24 | label-lg (16/24) | 20-24 | Touch, marketing, key CTAs |

On touch products the hit area is at least 44x44pt (iOS) / 48x48dp (Android) even when the visible button is smaller: extend
it with padding or a pseudo-element. WCAG 2.5.8 (AA) floor is 24x24 CSS px, or enough spacing that a 24px circle on each
target doesn't overlap another target.

## Groups and order

| Context | Order |
|---------|-------|
| Web dialogs and forms | Pick one convention and apply it everywhere. Common: primary on the right (forward motion), or primary first on the left in left-aligned forms (closest to the last field) |
| macOS | Default (primary) button on the right, Cancel to its left |
| Windows (Fluent) | Primary on the left, Cancel on the right |
| Android (Material) | Confirming action on the right (end) of dialogs |
| iOS alerts | Two buttons side by side, preferred on the right; Cancel uses the bold cancel style where appropriate |
| Mobile full-width | Stack with the primary on top (closest to the thumb is arguable; be consistent) |

Destructive buttons are never the default (Enter) action in a confirmation.

## Labels

- Verb + object, sentence case: "Create project", "Send invoice". Two to three words.
- The label matches what happens: the confirmation of "Delete project" says "Delete", not "OK".
- Avoid: OK, Submit, Yes/No, Click here, Learn more (repeated without context).
- Toggle buttons keep one label and change `aria-pressed`; don't switch "Mute" to "Unmute".

## Loading

- Keep the width: show the spinner in place of the icon or beside the label, or overlay it while keeping the label in layout
  (visibility hidden).
- Block repeat activation; keep focus on the button.
- Announce completion or errors with a live region; the spinner alone says nothing to a screen reader.
- After about 1 second show progress text ("Saving..."); after about 10 seconds give a way to cancel or background it.

## Disabled

Disabled buttons don't say why, can't be focused (native `disabled`), and are skipped by screen readers.
Prefer, in order:
1. Keep enabled; on click, validate and point to what is missing.
2. `aria-disabled="true"` (focusable, announced) + visible reason near the button.
3. Native `disabled` only for genuinely unavailable actions with an obvious reason.
WCAG exempts inactive components from contrast, but users still need to read them. Aim for at least 3:1 on the label anyway.

## Destructive actions

| Severity | Pattern |
|----------|---------|
| Reversible (archive, remove from list) | Do it immediately + Undo toast (5-10 s, longer with an action; don't auto-dismiss if it holds the only undo) |
| Irreversible, single object | Confirmation dialog naming the object ("Delete 'Q3 report'?"), danger button labelled with the verb |
| Irreversible, high impact (delete account, workspace) | Type the name to confirm; explain consequences; danger button stays disabled until it matches, with the reason shown |

## Button vs link

| Does it... | Element |
|------------|---------|
| Navigate to a URL (could open in new tab) | `<a href>` (may be styled as a button) |
| Change data, open a dialog, toggle UI | `<button>` |
| Submit a form | `<button type="submit">` |
