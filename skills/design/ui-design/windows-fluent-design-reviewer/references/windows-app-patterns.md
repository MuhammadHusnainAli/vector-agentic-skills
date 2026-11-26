# Windows App Patterns

## Title bar

- Standard height 32 epx; taller (48 epx) when it holds tabs or a search box.
- Custom title bars keep the caption buttons (minimise, maximise/restore, close) on the right, the system menu (Alt+Space),
  and drag regions; interactive elements in the title bar must be excluded from the drag region.
- Show the app icon and title (or the document title). Back button at the far left of the title bar when navigation uses it.
- Extend Mica into the title bar for a unified look.

## Navigation

| Control | Use |
|---------|-----|
| NavigationView, left | Apps with 5+ top-level sections; collapses to compact (icons) then minimal (hamburger) as the window narrows |
| NavigationView, top | 5 or fewer sections, content-first apps |
| TabView | Documents or multiple instances (browser-style tabs) |
| BreadcrumbBar | Deep hierarchies (file locations, settings paths) |
| Pivot / SelectorBar | Switching views within a page |

Settings conventionally sit at the bottom of the left NavigationView.

## Commands

- CommandBar for page-level commands (primary commands visible, secondary in the "..." overflow).
- Context menus (MenuFlyout) on right-click and Shift+F10 / Menu key, with the same commands available elsewhere.
- Keyboard accelerators for frequent commands, shown in tooltips and menus: Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Z/Y, Ctrl+F,
  F5 (refresh), Delete, F2 (rename).
- Access keys (Alt shows key tips) for keyboard users in command-heavy apps.

## Dialogs and notifications

| Need | Control | Notes |
|------|---------|-------|
| Blocking decision | ContentDialog | Up to three buttons: Primary, Secondary, Close. Primary is the left-most button; default button is the safe, expected one |
| Inline, persistent status | InfoBar | Informational, success, warning, error severities; optional action; doesn't block |
| Teaching a feature | TeachingTip | Points at the UI; dismissible; don't chain many |
| Transient contextual UI | Flyout | Light-dismiss |
| Outside-the-app alerts | App notifications (toasts) via Windows notifications | Actionable; respect Do not disturb |

## Window sizes and layout

| Size class | Effective width | Layout guidance |
|------------|-----------------|-----------------|
| Small | up to 640 epx | Single column; NavigationView minimal; snap to a third of the screen lands here |
| Medium | 641-1007 epx | NavigationView compact; two columns where useful |
| Large | 1008 epx and wider | NavigationView expanded; multi-pane layouts |

- Support snap layouts (half, third, quarter of the screen) and resizing; define a reasonable minimum window size.
- Use VisualStateManager with AdaptiveTrigger (or size-changed logic) to change layout by width.
- Remember window size and position between sessions.

## Keyboard

- Tab moves between groups of controls; arrow keys move within a group (lists, menus, toolbars, radio groups).
- F6 cycles between major panes (navigation, content, details).
- Escape closes dialogs and flyouts; Enter activates the default button.
- Every element shows a focus visual (WinUI system focus visuals: two-colour rectangle).

## Touch and pen

- Touch targets at least 40 x 40 epx; dense mouse-first UIs (32 epx rows) should have a touch-friendly density option.
- Pen: inking surfaces with InkCanvas, eraser and barrel button support; right-click via barrel button.
- Precision touchpad gestures (pinch zoom, two-finger scroll) work in scrollable and zoomable content.
