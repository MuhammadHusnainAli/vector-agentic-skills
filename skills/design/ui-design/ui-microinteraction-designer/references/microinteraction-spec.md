# Microinteraction Spec

## Saffer's model

| Part | Question |
|------|----------|
| Trigger | What starts it? User (tap, hover, key, gesture) or system (data arrives, time, location) |
| Rules | What happens, in what order, with what constraints? What can't happen? |
| Feedback | How does the user know: visual, text, motion, sound, haptic, screen reader |
| Loops and modes | Does it repeat or change over time? Does it have modes (edit mode)? What happens the 100th time? |

## Spec template

| Field | Content |
|-------|---------|
| Name | Copy link |
| Trigger | Click/tap "Copy link" button; Ctrl/Cmd+C when the link field is focused |
| Rules | Copies the URL to the clipboard; if the clipboard API fails, select the text and show "Press Ctrl+C to copy" |
| States | idle -> copied (2 s) -> idle |
| Visual feedback | Icon swaps link -> check; label "Copy link" -> "Copied" |
| Motion | Icon crossfade + scale 0.8 -> 1, `duration.fast` (150 ms), `easing.enter` |
| Screen reader | Polite live region: "Link copied" |
| Haptic | Light impact on mobile (optional) |
| Reduced motion | Crossfade only, no scale |
| Edge cases | Double click: stays in copied state, timer restarts; button width fixed so the label change doesn't shift layout |

## Worked examples

### Like / favourite
- Trigger: tap heart. Rules: optimistic toggle; request in background; on failure revert and show an inline error.
- Feedback: fill colour + scale pulse (1 -> 1.2 -> 1, 200-250 ms); count increments immediately.
- Accessible: `aria-pressed` toggles; label stays "Like".
- Loop: rapid repeated taps debounce to the final state.

### Toggle a setting
- Rules: applies immediately (it's a switch); if saving takes over 1 s, show a small spinner in the thumb; failure reverts with a message.
- Motion: thumb slides `duration.fast`, `easing.standard`; track colour transitions in parallel.

### Add to cart
- Rules: button -> loading (keep width) -> success state "Added" for 2 s; cart count increments.
- Motion: optional item thumbnail moves toward the cart icon (orientation), 300-400 ms `easing.standard`; cart icon
  bounces once.
- Reduced motion: no flying thumbnail; cart count change + "Added to cart" toast.
- Edge: out of stock between view and click -> inline error, button disabled with reason.

### Delete with undo
- Rules: remove immediately (optimistic), show toast "Deleted 'Q3 report'" with Undo for about 5-10 s (no auto-dismiss
  while focused or hovered); commit the deletion when the toast closes.
- Motion: row collapses (height via transform/scale or a FLIP technique), neighbours slide up, `duration.moderate`.
- Focus: moves to the next row (or previous/empty state).

### Pull to refresh (mobile)
- Trigger: overscroll at top beyond threshold. Rules: release past threshold refreshes; below threshold cancels.
- Feedback: indicator follows the finger with resistance, rotates while loading, success state or "Updated just now".
- Reduced motion: indicator appears without rotation; static "Refreshing..." text.

### Form submit
- Rules: validate; on error move focus to the error summary; on success show the result page or inline success.
- Feedback: button loading state within 100 ms; disable repeat submits.
