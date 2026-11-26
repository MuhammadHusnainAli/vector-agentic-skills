# Troubleshooting Figma Prototypes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Clicking does nothing | Hotspot on a layer covered by another layer; interaction on the main component overridden in the instance; prototype started from the wrong flow | Move the interaction to the top layer or the instance; check flow start |
| Interactive component doesn't change | Interaction set on the instance instead of inside the component set; variants missing the same property values | Wire Change to inside the component set's variants |
| Hover state sticks | Mouse enter used without Mouse leave | Use While hovering, or add the leave interaction |
| Overlay won't close | No Close overlay action and outside-click close off | Add both |
| Overlay appears in the wrong place | Position set to Center when it should be Manual (anchored) | Set Manual and drag into place relative to the trigger |
| Smart Animate jumps | Layer names or hierarchy differ | Rename and restructure to match |
| Content doesn't scroll | Frame not set to overflow scroll, or content not larger than the frame | Clip content on, Overflow vertical/horizontal, content taller than frame |
| Header scrolls away | Not set to fixed or sticky | Position: Fixed / Sticky in the Design panel |
| Variable value doesn't show | Text not bound to the variable, or variable set in a different collection mode | Bind the text property; check the mode |
| Conditional always takes the else branch | Comparing a number variable to a string, or variable never set | Check types and that a previous action sets it |
| Back goes to the wrong place | Back follows history; overlays and flows change history | Use explicit Navigate to where back must be predictable |
| Prototype is slow to load or lags | Huge frames, high-res images, hundreds of frames in one page | Compress images, split into pages per flow, delete unused frames |
| Video doesn't play | Plan or file limits on video; unsupported format | Check plan support; use MP4/MOV/WebM, keep files small |
| Mobile mirror looks blurry or wrong size | Device frame or frame size mismatch | Frame size = device size in points; set device in prototype settings |

## Performance tips

- One page per flow or study; keep design exploration on other pages.
- Replace screenshots and photos with compressed images.
- Prefer interactive components and variables over duplicated frames (fewer frames, smaller file).
- Preload: open every flow once before a session.
