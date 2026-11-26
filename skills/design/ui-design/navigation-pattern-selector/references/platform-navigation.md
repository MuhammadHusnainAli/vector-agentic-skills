# Platform Navigation Conventions

## iOS / iPadOS (Apple HIG)
- Tab bar for top-level sections in iPhone apps; Apple recommends keeping the number of tabs small (up to 5 on iPhone
  before overflow to More). Tabs switch sections; they never perform actions.
- Navigation stack inside each tab: large title at the root, back button with the previous title at the left.
- iPad: sidebar (split view) for apps with many sections; tab bars can convert to a sidebar. Respect compact width in
  Split View and Slide Over.
- Swipe from the left edge goes back. Don't put interactive content that conflicts with that gesture at the edge.
- Modality: sheets for focused tasks with Cancel/Done; don't stack navigation inside sheets deeply.

## Android (Material 3)
| Window size class | Component |
|-------------------|-----------|
| Compact (< 600dp) | Navigation bar (3-5 destinations) or modal navigation drawer |
| Medium (600-839dp) | Navigation rail (3-7 destinations), modal drawer for more |
| Expanded and larger (>= 840dp) | Navigation rail or standard (persistent) navigation drawer |

- System back (gesture or button) goes back through the app's history; predictive back shows a preview. The top app bar
  up arrow goes to the logical parent.
- Each destination in a navigation bar keeps its own back stack; reselecting a destination returns it to its start.
- Material adaptive navigation suites switch between bar, rail and drawer automatically by window size class.

## Windows (Fluent 2 / WinUI)
- NavigationView: left pane (expanded, compact icon-only, or minimal hamburger) adapting to window width; or top pane for
  5 or fewer top-level items.
- Back button in the title bar area; settings at the bottom of the pane by convention.
- Keyboard: arrow keys in the pane, Alt+Left for back.

## Web
- Header + top nav for content sites; sidebar for apps; a menu button with a full-height sheet on narrow screens.
- Every destination has a URL; browser back always works; deep links land with navigation showing the location.
- Keep the selected state server-rendered (`aria-current="page"`), not only after JavaScript runs.

## Adaptive transitions

| From (compact) | To (medium) | To (expanded) | Keep |
|----------------|-------------|---------------|------|
| Bottom bar | Rail | Rail or sidebar | Same destinations, order, selected item, per-tab stacks |
| Header + menu sheet | Header + menu sheet | Top nav or sidebar | Search position |
| List -> detail screens | Same or list-detail | List-detail side by side | Selected item; back closes detail only on compact |

Rotation or window resize must never lose the user's place or form input.
