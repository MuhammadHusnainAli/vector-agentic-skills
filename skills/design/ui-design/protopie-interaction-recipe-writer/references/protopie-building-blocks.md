# ProtoPie Building Blocks

Names follow ProtoPie Studio 8-9; check the current docs if a menu item has moved.

## Structure

| Concept | What it is | Tips |
|---------|-----------|------|
| Pie | The prototype file | One pie per tested product area keeps it fast |
| Scene | A screen-level canvas | Jump between scenes; scene variables reset when leaving a scene |
| Layer | Shape, text, image, video, input, container | Name every layer you reference in formulas |
| Container | Groups layers; can be a scroll or paging container | Scroll containers for lists; paging for carousels |
| Input layer | Real text input with the device keyboard | The way to prototype typing, search, forms |
| Component | Reusable piece with its own interactions | Communicate with the parent using Send/Receive messages |

## Interactions

An interaction = trigger + one or more responses (+ optional conditions).

Common triggers:
| Group | Triggers |
|-------|----------|
| Touch / mouse | Tap, Double Tap, Long Press, Touch Down, Touch Up, Drag, Fling, Pinch, Rotate, Hover (mouse in/out) |
| Value-driven | Chain (link a property to another layer's property), Range (fires when a property enters a range), Detect (fires when a property or variable changes) |
| Scene and messages | Start (scene starts), Receive (message from a component, another scene or another device) |
| Input | Keyboard, Return key / focus events on input layers, Voice command |
| Sensors | Tilt, Sound, Compass and others, on devices that have them |

Common responses: Move, Scale, Rotate, Opacity, Color, Border, Shadow, Radius, Resize, Reorder, Text (set text),
Image, Jump (to scene), Scroll (container to position), Play/Pause/Seek (media), Assign (set a variable), Send
(message), Vibrate, Sound, Speech, Focus/Blur (input), Stop, Reset.

## Conditions

- Attach conditions to an interaction (or individual responses) to branch: `if variable == value`, comparisons on layer
  properties, text length, etc.
- Use Else branches for the alternative path instead of a second interaction with the inverse condition.

## Variables

| Type | Examples |
|------|----------|
| Number | cartCount, sliderValue, step |
| Text | userName, enteredCode, selectedPlan |
| Color | themeAccent |

Scope: **this scene** (resets on leaving) or **all scenes** (global, persists across scenes). Variables can be shown
directly in text layers and changed with Assign.

## Multi-device and hardware

- ProtoPie Connect relays messages between pies on different devices and to hardware and plugins (e.g. a phone remote
  controlling a TV pie, a steering-wheel controller driving a car HMI pie).
- Send a message with a value; the other pie's Receive trigger reads it into a variable.
- ProtoPie Player (iOS/Android app) runs pies on real devices with real sensors and keyboards.
