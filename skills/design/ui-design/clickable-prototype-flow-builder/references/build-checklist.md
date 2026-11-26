# Build Checklist

## Before wiring

- [ ] Frames named with screen IDs from the flow map
- [ ] One persona and data set: name, avatar, address, items, prices, totals, dates (all consistent and current)
- [ ] Real copy for everything on task paths; content reviewed for the region (currency, date formats)
- [ ] Components and variants used, so interactive states (hover, pressed, selected) come for free
- [ ] Device frame and size chosen (test on the participant's real device class)

## Wiring

| Element | Approach |
|---------|----------|
| Navigation | Hotspots on the actual controls; hit area at least the visible control |
| Overlays | Menus, sheets, dialogs as overlays with close on outside click and an explicit close |
| Scroll | Scrolling frames for long content; fixed headers and bottom bars |
| State | Variables or component variants for cart count, selections, toggles; avoid duplicating screens per state when the tool supports variables |
| Inputs | Pre-filled or "type anything" fields (real input in ProtoPie/code; in Figma, a tap fills the value) |
| Errors | One realistic error per risky step (declined card, unavailable slot), triggered by a specific action |
| Off-path | Global overlay "This isn't available in the prototype" on non-built areas, dismissible |
| Back | Back buttons wired; on mobile also consider the system back gesture expectation |
| Transitions | Use transitions that match the real product (push, slide up, dissolve); no showy effects |

## Tool notes

| Tool | Good for | Watch out for |
|------|----------|---------------|
| Figma | Most flows; interactive components, variables, conditionals | Text input is faked; complex logic gets unwieldy |
| ProtoPie | Real input, sensors, conditions, multi-device | Build time; separate file from the design source |
| Framer / code | Real data, real scrolling, responsive behaviour | Engineering effort; scope creep |
| Slides / static | Concept walkthroughs, very early ideas | Not for task-based testing |

## Versioning

- Freeze the prototype before a study (duplicate the file/page, or a versioned link). Changing it mid-study invalidates
  comparisons, unless you're running rapid iterative testing on purpose (RITE) and log each change.
- Name versions with date and change ("v3 2026-11-26 moved Add to cart above fold").
