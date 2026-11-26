# Triggers, Actions, Smart Animate and Transitions

## Triggers

| Trigger | Use | Notes |
|---------|-----|-------|
| On click / On tap | Most interactions | |
| On drag | Swipe, drag to dismiss, carousels | Fires on drag start; direction not controllable (use ProtoPie for directional logic) |
| While hovering | Hover states (desktop) | Reverts when the pointer leaves |
| While pressing | Pressed states | Reverts on release |
| Mouse enter / Mouse leave | Hover effects that should persist or chain | Doesn't revert automatically |
| Mouse down / Mouse up | Fine-grained press behaviour | |
| Key / Gamepad | Keyboard shortcuts, TV and console prototypes | Captured only when the prototype has focus |
| After delay | Splash screens, timed dismissals, auto-advance | Per frame or overlay, starts when it's shown |

## Actions

| Action | What it does |
|--------|--------------|
| Navigate to | Go to another top-level frame |
| Change to | Switch an instance to another variant (interactive components) |
| Back | Return to the previous frame in history |
| Scroll to | Scroll a scrolling frame to a layer |
| Open link | URL |
| Open overlay / Swap overlay / Close overlay | Menus, sheets, dialogs, toasts |
| Set variable | Change a variable's value (with expressions) |
| Conditional | If/else on variables, with actions in each branch |
| Set variable mode | Switch mode (theme, language) for the prototype |

Several actions can run from one trigger, in order (e.g. Set variable then Navigate to).

## Smart Animate matching rules

Smart Animate tweens layers that have the same name and the same position in the layer hierarchy in both frames or
variants. Animatable: position, size, rotation, opacity, fills, strokes, corner radius, some effects.

| Problem | Cause | Fix |
|---------|-------|-----|
| Element jumps instead of moving | Layer names differ ("Rectangle 12" vs "Rectangle 13") | Name layers identically |
| Element fades instead of moving | Different parent group/frame in each state | Same hierarchy in both |
| Text morphs weirdly | Different text content with same name | Crossfade instead, or keep text static |
| New element just appears | Exists in only one state | Add it to both, with opacity 0 in the "from" state |

## Transitions

| Transition | Use |
|------------|-----|
| Instant | Tabs, state changes where motion doesn't help |
| Dissolve | Swapping content in place |
| Smart animate | State changes within a component or between similar frames |
| Move in / Move out | Overlays and sheets entering and leaving |
| Push | Navigating forward/back in a stack (mobile drill-down) |
| Slide in / Slide out | Like move, with the old screen moving slightly |

## Easing and springs

- Ease out for things entering; ease in for leaving; ease in and out for moves on screen.
- Durations: 150-300 ms for components, 300-400 ms for screens; slower feels sluggish in tests.
- Spring presets (Gentle, Quick, Bouncy, Slow) or a custom spring; use Quick for UI, Bouncy only for playful moments.
- Match the production platform: iOS-style push for iOS prototypes, Material motion for Android.
