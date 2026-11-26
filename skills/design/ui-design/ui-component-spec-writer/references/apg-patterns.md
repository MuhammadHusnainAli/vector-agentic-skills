# Keyboard and ARIA by Pattern

From the WAI-ARIA Authoring Practices Guide (APG). Map the component to a pattern first. The visual design does not
decide the pattern; the job does. A "dropdown" can be a menu, a listbox or a combobox.

## Button
Anatomy: container, label, optional leading/trailing icon, focus ring, spinner (loading).
States: default, hover, focus-visible, pressed, disabled, loading.

| Key | Action |
|-----|--------|
| Enter | Activate |
| Space | Activate (on key up) |

- Native `<button>`; `type="button"` unless it submits a form. Never a `<div>` with a click handler.
- Toggle button: `aria-pressed`, and the label does not change with state ("Mute", not "Mute"/"Unmute").
- Icon-only: `aria-label`; the target is at least 24x24 CSS px (WCAG 2.5.8).
- Loading keeps its width (no layout shift) and blocks double submit.

## Tabs
Anatomy: tablist, tab, selected indicator, tab panel, overflow control.
States: default, hover, focus-visible, selected, disabled.

| Key | Action |
|-----|--------|
| Tab | Into the tablist, landing on the selected tab; next Tab goes to the panel |
| Left / Right Arrow | Previous / next tab (wraps) |
| Home / End | First / last tab |
| Enter / Space | Activate the focused tab (manual activation only) |

- `role=tablist` > `tab`; panel `role=tabpanel`; `aria-selected` on the active tab; `aria-controls` tab -> panel;
  `aria-labelledby` panel -> tab; roving `tabindex` (-1 on inactive tabs).
- Automatic activation (arrow selects) only when panels render instantly; otherwise manual.
- Tabs switch views within a page. Links to other pages are navigation, not tabs.
- Overflow: horizontal scroll with a visible affordance, never a second row of tabs.

## Dialog (modal)
Anatomy: scrim, container, title, body, actions, close button.
States: closed, opening, open, closing.

| Key | Action |
|-----|--------|
| Tab / Shift+Tab | Cycle focus within the dialog only |
| Escape | Close; focus returns to the trigger |

- Prefer native `<dialog>` with `showModal()`. Otherwise `role=dialog` + `aria-modal=true` + `aria-labelledby` the title;
  background `inert`.
- Confirmation of a destructive action: `role=alertdialog`, initial focus on the least destructive button.
- Content taller than the viewport scrolls inside the body; actions stay visible. Below a width threshold, a full-screen sheet.
- Escape or scrim click with unsaved input: define whether to confirm or discard.

## Combobox
Anatomy: label, input, toggle button, listbox popup, option, empty/loading row, helper/error text.
States: default, hover, focus-visible, expanded, disabled, error, loading.

| Key | Action |
|-----|--------|
| Down Arrow | Open popup / next option |
| Up Arrow | Previous option |
| Enter | Accept active option, close |
| Escape | Close; second press clears the input |
| Alt+Down Arrow | Open without moving the active option |

- `role=combobox` on the input, `aria-expanded`, `aria-controls` -> listbox, `aria-activedescendant` -> active option (DOM
  focus stays in the input), `aria-autocomplete` matching the behaviour.
- Decide whether free text is allowed: it decides what blur does.
- Async: debounce, loading row, discard stale responses, announce the result count in a polite live region.

## Menu button
Anatomy: button, menu, item, separator, group label, submenu indicator.
States: default, hover, focus-visible, expanded, disabled.

| Key | Action |
|-----|--------|
| Enter / Space / Down Arrow | Open, focus first item |
| Up Arrow (on button) | Open, focus last item |
| Up / Down Arrow | Move between items (wraps) |
| Home / End | First / last item |
| Escape | Close, focus returns to the button |
| Letter keys | Type-ahead to next matching item |

- `aria-haspopup=menu` + `aria-expanded` on the button; `role=menu` > `menuitem` / `menuitemcheckbox` / `menuitemradio`.
- Application-style actions only. Site navigation uses links in `<nav>`, not `role=menu`.
- Disabled items stay focusable so they can be discovered. Flip near the viewport edge.

## Switch
States: off, on, hover, focus-visible, disabled. Keys: Space toggles (Enter optional).
- `role=switch` + `aria-checked`, or a native checkbox with `role=switch`.
- Takes effect immediately. If a Save button applies the change, it is a checkbox.
- If the action fails after toggling, revert and show the error. State never by colour alone (WCAG 1.4.1).

## Checkbox
States: unchecked, checked, indeterminate, hover, focus-visible, disabled, error. Keys: Space toggles.
- Native `input type=checkbox`; group in `fieldset` + `legend`; the label is part of the click target.
- Indeterminate shows a partially selected parent (`aria-checked=mixed` for custom ones).

## Radio group
States: unselected, selected, hover, focus-visible, disabled, error.

| Key | Action |
|-----|--------|
| Tab | Into the group, landing on the selected radio |
| Arrow keys | Move and select next / previous |

- Native radios sharing a `name`, in `fieldset` + `legend`.
- No default selection when the choice matters. Beyond about 6 options consider a select.

## Accordion
States: collapsed, expanded, hover, focus-visible, disabled.
Keys: Enter / Space toggle; optional Up/Down between headers, Home/End.
- A `<button>` inside a heading of the right level; `aria-expanded`; `aria-controls` -> panel.
- Decide single vs multiple open. Deep links open the target panel. Use `hidden="until-found"` so find-in-page works.

## Tooltip
Keys: shows on focus as well as hover; Escape hides without moving focus.
- `role=tooltip`, `aria-describedby` from the trigger. Plain text only; interactive content needs a popover.
- WCAG 1.4.13: dismissible, hoverable, persistent. Touch has no hover, so essential info never lives only in a tooltip.

## Disclosure
Keys: Enter / Space toggle. `aria-expanded`, `aria-controls`. Collapsed content is out of the tab order.

## Listbox
| Key | Action |
|-----|--------|
| Up / Down Arrow | Move focus |
| Home / End | First / last |
| Letter keys | Type-ahead |
| Space | Toggle selection (multi-select) |
| Shift+Arrow | Extend selection (multi-select) |

- `role=listbox` > `option`, `aria-selected`, `aria-multiselectable`. Virtualised long lists keep `aria-setsize` /
  `aria-posinset`.

## Slider
| Key | Action |
|-----|--------|
| Left / Down Arrow | Decrease one step |
| Right / Up Arrow | Increase one step |
| Page Down / Page Up | Large step |
| Home / End | Minimum / maximum |

- `role=slider` (or `input type=range`), `aria-valuenow/min/max`, `aria-valuetext` for human values ("$40", "Medium").
- Precise values need a paired number input. Dragging alternative required (WCAG 2.5.7): tap the track or +/- buttons.

## Text field
States: default, hover, focus-visible, filled, disabled, read-only, error.
- Visible `<label for>`; the placeholder is not a label. `aria-describedby` -> helper and error text; `aria-invalid` while
  in error; correct `autocomplete` token for personal data (WCAG 1.3.5).
- Error on blur or submit, not on every keystroke. Accept pasted formatted values (spaces in card numbers).

## Toast / snackbar
States: entering, visible, paused (hover/focus), exiting.
- `role=status` (polite); `role=alert` only for urgent errors. Never steal focus.
- Toasts with an action do not auto-dismiss (WCAG 2.2.1); give a documented way to reach them (F6 or a shortcut).
- Define the stack limit when several arrive at once.

## Card
- `article` or `li` with the title as a heading. One primary link on the title, stretched over the card with a
  pseudo-element. Secondary actions are separate tab stops. Never nest interactive elements inside a link.
- Missing image, 1-word vs 3-line titles, unequal heights in a row.
