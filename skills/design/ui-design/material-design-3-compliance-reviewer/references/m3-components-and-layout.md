# M3 Components and Layout

## Components: rules that reviews catch

| Component | Rules |
|-----------|-------|
| Buttons | Emphasis order: filled > filled tonal > elevated > outlined > text. One filled button per area. 40dp height, 48dp target |
| FAB | The single most important constructive action on a screen; one per screen; sizes FAB (56dp), large (96dp); extended FAB with label for clarity. Not for destructive or minor actions |
| Icon buttons | Standard, filled, tonal, outlined; 48dp target; toggle icon buttons show selected state |
| Top app bar | Small (64dp), medium (112dp), large (152dp); title + navigation icon + up to 3 actions, then overflow menu; changes tone on scroll |
| Navigation bar | Compact windows; 3-5 destinations; icons with labels; active indicator pill |
| Navigation rail | Medium and larger; 3-7 destinations; optional FAB/menu at the top |
| Navigation drawer | Modal (compact) or standard (expanded); for 5+ destinations or secondary destinations |
| Chips | Assist, filter, input, suggestion; 32dp height, 48dp target |
| Cards | Elevated, filled, outlined; one primary action or whole-card tap; don't nest cards |
| Dialogs | Basic (title, text, up to 2-3 actions, confirming action on the end) or full-screen on compact for complex tasks |
| Bottom sheets | Standard (coexists with content) or modal (scrim); drag handle; supports predictive back |
| Snackbars | Brief messages at the bottom; at most one action; one at a time; not for critical info; 4-10 seconds |
| Text fields | Filled or outlined, used consistently; label, supporting text, error text below; character counter |
| Lists | 1-, 2-, 3-line items; leading/trailing elements; 56/72/88dp heights |
| Search | Search bar (on surface) expanding into a search view |

## Window size classes and canonical layouts

| Class | Width (dp) | Navigation | Canonical layouts |
|-------|------------|------------|-------------------|
| Compact | < 600 | Navigation bar | Single pane |
| Medium | 600-839 | Navigation rail | Single pane; list-detail with care |
| Expanded | 840-1199 | Rail or standard drawer | List-detail, supporting pane, feed |
| Large / extra-large | 1200+ | Standard drawer or rail | Two or three panes |

Canonical layouts:
- **List-detail**: list and detail side by side on expanded; separate screens on compact (back returns to the list).
- **Supporting pane**: main content plus a pane with related content (comments, details).
- **Feed**: grid of cards that adds columns as width grows.

Foldables: treat the hinge as a separator; tabletop posture (half-open) puts content on top and controls below.

## System integration (Android)

- **Edge-to-edge**: apps targeting Android 15 (API 35) are drawn edge to edge by default. Handle window insets so content
  and controls avoid the status bar, navigation bar and display cutout; backgrounds extend behind them.
- **Predictive back**: system back shows a preview of the destination. Don't intercept back for custom animations that
  break it; use the predictive back APIs for in-app transitions and sheets.
- **Themed icons**: provide a monochrome layer in the adaptive icon so it follows the user's theme.
- **Font scale**: test at 200%.
- **Dark theme** and the high-contrast scheme.

## Jetpack Compose review notes

| Code | Problem | Fix |
|------|---------|-----|
| `Color(0xFF6750A4)` in a component | Bypasses the scheme | `MaterialTheme.colorScheme.primary` |
| `fontSize = 14.sp` on Text | Bypasses the type scale | `style = MaterialTheme.typography.bodyMedium` |
| `RoundedCornerShape(10.dp)` | Off the shape scale | `MaterialTheme.shapes.medium` |
| `Modifier.size(32.dp).clickable {}` | Target below 48dp | `Modifier.minimumInteractiveComponentSize()` or 48dp size; use IconButton |
| `dynamicColor = false` with no reason | Loses personalisation | Decide deliberately; document brand reason |
| Missing `contentDescription` on icons that act | No TalkBack label | Describe the action; `null` only for decorative icons |
| Custom `BackHandler` with its own animation | Breaks predictive back | `PredictiveBackHandler` |
| No `WindowInsets` handling | Content under system bars when edge-to-edge | `Scaffold` insets, `windowInsetsPadding` |
| Layout branching on screen width in px | Breaks on foldables/multi-window | `currentWindowAdaptiveInfo().windowSizeClass` |
