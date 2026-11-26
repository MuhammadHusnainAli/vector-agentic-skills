# Figma Prototype Recipes

Figma UI names as of 2025; menu locations can move between releases.

## Toggle / checkbox (interactive component)
1. Component set with variants `State=Off` and `State=On` (plus `Hover` if needed).
2. In Prototype mode, on the Off variant: On click -> Change to -> On. On the On variant: On click -> Change to -> Off.
3. Animation: Smart animate, 150-200 ms, ease out (layers named the same in both variants so the thumb slides).
4. Every instance in every frame now toggles; no screen wiring needed.

## Hover and pressed states
- Variants `State=Default/Hover/Pressed`. On Default: While hovering -> Change to Hover. On Hover: While pressing -> Change to Pressed.
- "While" triggers revert automatically when the pointer leaves or the press ends.
- For touch prototypes skip hover; use While pressing only.

## Tabs
1. Tab bar component with a variant per selected tab (`Selected=Overview/Activity/Settings`).
2. Panel content: either a second component with the same variant property, or put tab bar + panels together in one
   component set so one Change to switches both.
3. On each tab layer inside each variant: On click -> Change to the matching variant.

## Accordion
- Component set `Expanded=false/true`; auto layout so expanding pushes content below.
- On the header: On click -> Change to the other variant. Smart animate for smooth height change.
- Parent frame must use auto layout (or the instances overlap when they grow).

## Dropdown / menu
- Menu as a separate frame or component. Trigger: On click -> Open overlay -> Menu frame, position Manual (anchored
  below the button), "Close when clicking outside" on.
- Each menu item: On click -> Close overlay, plus Set variable (selected value) if the button label should change.

## Bottom sheet
- Sheet frame. On click -> Open overlay, position Bottom center, add background (scrim), close on outside click.
- Animation: Move in from bottom, 250-300 ms, ease out. Close: Close overlay (Move out to bottom).
- For drag-to-dismiss: On drag on the sheet -> Close overlay.

## Toast with auto-dismiss
- Open overlay (toast frame, Top or Bottom center, no background, no outside-click close).
- Inside the toast frame: After delay 3000 ms -> Close overlay.
- Undo button in toast: On click -> Close overlay + Set variable to restore state.

## Carousel
- Frame with horizontal overflow scrolling; items in a horizontal auto layout wider than the frame.
- For snapping pages: component set with a variant per page; On drag -> Change to next/previous variant with Smart
  animate; dots bound to the same variant.

## Cart counter (variables)
1. Create a number variable `cartCount = 0`.
2. Bind the badge text to `cartCount`; bind badge visibility to the boolean expression `cartCount > 0` (or a boolean
   variable updated alongside).
3. Add to cart button: On click -> Set variable `cartCount` = `cartCount + 1`.
4. The value persists across all frames in the prototype session.

## Form validation (conditionals)
1. Boolean variable `emailFilled = false`; tapping the email field sets it true (and changes the field variant to Filled).
2. Continue button: On click -> Conditional: if `emailFilled` == true -> Navigate to next screen; else -> Change field
   to Error variant (or Set variable `showError = true` bound to the error text's visibility).

## Fake text input
- Figma prototypes have no real keyboard input. Options: tap the field -> Change to a "Filled" variant with the
  expected text; or After delay sequences that reveal characters; or use ProtoPie/code for tests where typing matters.
- Tell participants they can tap the field and the text will fill in.

## Sticky header and scroll-to
- Scrolling frame: Overflow -> Vertical. Header layer: Position -> Fixed (stays put) or Sticky (sticks when it reaches
  the top).
- Anchor links: On click -> Scroll to -> target layer (with an animation).

## Flows and starting points
- Select a frame -> add Flow starting point; name it after the task ("T2 Buy shoes").
- Each flow gets its own presentation link; use one per test task.
- Prototype settings: device frame and background; turn off hotspot hints for tests.
