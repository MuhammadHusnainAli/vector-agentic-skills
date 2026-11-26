# Layering and Z-Index

## Z-index token scale

```css
:root {
  --z-base: 0;
  --z-raised: 1;        /* cards lifted on hover, in-flow overlaps */
  --z-sticky: 100;      /* sticky headers, table headers */
  --z-dropdown: 200;    /* menus, popovers, select lists, tooltips anchored in page */
  --z-overlay: 300;     /* drawers and their scrims */
  --z-modal: 400;       /* dialogs and their scrims */
  --z-toast: 500;       /* toasts, snackbars */
  --z-tooltip: 600;     /* tooltips must sit above everything they can describe */
}
```
Gaps of 100 leave room for local ordering without new global values. Never use raw numbers in components.

## Stacking contexts

z-index only competes within the same stacking context. New contexts are created by, among others:
`position` with `z-index`, `opacity < 1`, `transform`, `filter`, `will-change`, `isolation: isolate`, `contain: paint`,
`position: fixed/sticky`.

Common bug: a menu with `z-index: 9999` inside a card that has `transform` still renders under the sticky header, because
the card's stacking context is lower. Fixes:
- Render overlays (menus, popovers, dialogs, toasts) in a portal at the end of `<body>`.
- Use the native top layer: `<dialog>` with `showModal()` and the Popover API (`popover` attribute) render above
  everything without z-index.
- Use `isolation: isolate` on components to contain their internal z-index.

## Layer order rules

| Rule | Why |
|------|-----|
| Toasts above dialogs | A save confirmation shouldn't hide behind the dialog that triggered it |
| Tooltips above everything | They describe whatever they're attached to, including dialog content |
| Dropdowns opened inside a dialog render above the dialog | Portal them, or use the top layer |
| Sticky headers below dropdowns | Menus opened near the header must cover it |
| Scrims sit directly under their dialog or drawer | Scrim blocks the page, not the dialog |

## Scrims

- Modal dialogs and drawers use a scrim (about 30-60% black, or tinted) to show the page is inactive.
- Clicking the scrim closes non-critical dialogs; never for dialogs with unsaved input without confirmation.
- In dark mode the scrim still needs to darken the page visibly (higher alpha).

## Elevation vs focus

Focus is not elevation. Keyboard focus uses a focus ring; raising an element on focus can be added for cards but never
replaces the ring.
