# HIG Review Areas

## Layout

- Respect safe areas: the status bar, Dynamic Island / notch, home indicator and rounded corners. Backgrounds may extend
  edge to edge; content and controls stay inside.
- Use the system layout margins (typically 16pt on compact width, 20pt on wider) and readable content guides for text.
- Size classes, not devices: iPhone portrait is compact width; iPad can be compact width in Split View and Slide Over.
- iPad: support all orientations and multitasking sizes; use sidebars and multi-column layouts instead of a stretched
  phone layout.
- Minimum hit target 44x44pt, even when the visible control is smaller.

## Navigation

| Pattern | Use | Rules |
|---------|-----|-------|
| Tab bar | Top-level sections | Up to 5 on iPhone (more go to a More tab); tabs never perform actions; keep it visible on top-level screens; each tab keeps its navigation stack |
| Navigation stack | Drill-down hierarchy | Back button top-left showing the previous title; edge-swipe back always works; large title on root screens |
| Sidebar (iPad, Mac) | Many sections | Can collapse; tab bars can adapt into a sidebar on iPad |
| Search | Content-heavy apps | Search field in the navigation bar or a dedicated tab; scope bars for filters |

Since iOS 26, system bars and controls use the Liquid Glass material: tab bars float above content and minimise on
scroll. Let content scroll under bars, don't paint opaque custom backgrounds behind them, and use system components so
they adopt it automatically.

## Modality

| Presentation | Use | Notes |
|--------------|-----|-------|
| Sheet | Focused task that relates to the current context | Detents (medium/large) for partial height; swipe down to dismiss; confirm before discarding edits |
| Full-screen cover | Immersive or complex multi-step task | Needs explicit Done/Cancel |
| Alert | Critical info needing a decision | Short title, optional message, 1-3 buttons; Cancel style for cancel; destructive style for destructive |
| Confirmation dialog (action sheet) | Choices about an action the user started | Cancel button included; destructive option marked |
| Popover (iPad) | Contextual content anchored to a control | Becomes a sheet on compact width |

## Controls

- Prefer system controls: Button styles, Toggle, Picker (menu, wheel, segmented), Stepper, Slider, DatePicker, Menu.
- Context menus (long press) for secondary actions on content; swipe actions on list rows for frequent actions (Delete
  at the trailing edge, destructive style).
- Pull to refresh for content that updates; edit mode for multi-select in lists.
- Toggles take effect immediately; use them for on/off settings only.

## Feedback

- Inline feedback near the content; avoid Android-style snackbars/toasts. For transient status, a brief HUD-like overlay
  or banner sparingly.
- Activity indicators for indeterminate waits; progress views when duration is known.
- Haptics through system feedback generators (selection, impact, notification) matching the meaning; never constant.

## Colour, materials, icons

- Semantic colours: `label`, `secondaryLabel`, `tertiaryLabel`, `systemBackground`, `secondarySystemBackground`,
  `separator`, `tint`. They adapt to dark mode and Increase Contrast automatically.
- One tint (accent) colour for interactive elements; don't use it for non-interactive text.
- SF Symbols: match the symbol's weight and scale to adjacent text; use rendering modes (monochrome, hierarchical,
  palette, multicolor) consistently.
- App icon: 1024x1024 source, no transparency in the base layer, no text where avoidable; provide dark and tinted
  appearances (iOS 18+); layered icons via Icon Composer for the Liquid Glass look (iOS 26).

## Permissions and privacy

- Ask in context, when the feature is used, after explaining the benefit; never a stack of prompts at launch.
- Purpose strings say what the data is used for in plain language.
- Respect "Ask App Not to Track"; offer limited photo library access paths.

## Common port-from-Android problems

| Android habit | iOS equivalent |
|---------------|----------------|
| FAB | Primary action in the navigation bar (top-right) or a toolbar |
| Hamburger drawer | Tab bar (+ More), or sidebar on iPad |
| Top tabs for sections | Segmented control within a screen, or tab bar for sections |
| Snackbar | Inline status, undo via shake/menu, or a brief banner |
| Overflow ⋮ menu | `ellipsis.circle` Menu button in the navigation bar |
| System back button | Back button top-left + edge-swipe |
| Ripple feedback | Highlight states (system controls do this) |
