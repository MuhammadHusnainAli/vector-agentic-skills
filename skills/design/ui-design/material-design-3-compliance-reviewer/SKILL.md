---
name: material-design-3-compliance-reviewer
description: "Review Android and web designs against Material Design 3 (Material You, including M3 Expressive) like a senior Android design lead: colour roles and tonal palettes (primary, on-primary, containers, surface containers, outline, inverse), light/dark schemes and dynamic colour from the wallpaper, contrast by tone difference, the type scale (Display to Label), shape scale, elevation by tonal surfaces, state layers, 48dp touch targets, components (buttons, FABs, top app bars, navigation bar, rail and drawer, chips, cards, dialogs, bottom sheets, snackbars, lists, text fields), window size classes and canonical layouts (list-detail, supporting pane, feed), edge-to-edge and predictive back on Android 15+, themed icons, and motion. Also checks Jetpack Compose code for hard-coded colours, sizes and styles that bypass MaterialTheme. Use when designing or reviewing an Android app or a Material-based web app, building a Material theme, or adapting a design for tablets and foldables."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Material Design 3 Compliance Reviewer

Material 3 is a theming system as much as a component library. The scheme is generated from a source colour into colour
roles, every component reads those roles, and the result follows the user's wallpaper, dark theme and contrast settings.
Designs break it in two ways: picking hex values for components instead of roles, and copying phone layouts onto tablets.
This skill reviews screens, themes and Compose code against M3 and says what to change.

## Trigger Conditions

Activate this skill when the user:
- Shares Android or Material-based screens, a Material theme or Compose code for review
- Builds an M3 colour scheme, type scale or shape scale for a brand
- Adapts an app for tablets, foldables or ChromeOS (window size classes)
- Ports an iOS design to Android

iOS equivalent: `ios-human-interface-guidelines-checker`. Navigation choice: `navigation-pattern-selector`. Adaptive
icons: `android-adaptive-icon-designer`.

## Workflow

```
1. THEME     -> source colour, scheme (light/dark, contrast levels), dynamic colour on/off (references/m3-color-system.md)
2. ROLES     -> every colour in the design maps to a role; on-X used on X; pairs checked for contrast
3. TYPE      -> text uses scale roles; brand type mapped to the scale (references/m3-type-shape-motion.md)
4. SHAPE     -> component corners from the shape scale; consistent families
5. LAYOUT    -> window size classes, canonical layouts, navigation per class (references/m3-components-and-layout.md)
6. COMPONENTS-> each component used per its guidelines; touch targets 48dp
7. SYSTEM    -> edge-to-edge insets, predictive back, themed icon, dark theme, font scale up to 200%
8. CODE      -> Compose: MaterialTheme.colorScheme / typography / shapes, no literals
9. REPORT    -> findings with severity and fix
```

## Review Checklist

Report as `CODE [severity] screen/element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| MD001 | blocker | Touch targets under 48x48dp |
| MD002 | blocker | Text below 4.5:1 against its surface (role pairs mixed up, e.g. onSurfaceVariant text on primaryContainer) |
| MD003 | blocker | Layout breaks at font scale 200% (fixed heights, truncated labels) |
| MD004 | major | Hard-coded colours instead of roles; breaks dark theme and dynamic colour |
| MD005 | major | Content hidden behind system bars, or not drawn edge-to-edge on Android 15+ (missing insets handling) |
| MD006 | major | Phone layout stretched on medium/expanded windows (no rail, no list-detail or supporting pane) |
| MD007 | major | Navigation bar with fewer than 3 or more than 5 destinations; rail with more than 7 |
| MD008 | major | More than one FAB on a screen, or a FAB for a minor/destructive action |
| MD009 | major | Custom back handling that breaks predictive back |
| MD010 | minor | Text styles outside the type scale; shapes outside the shape scale |
| MD011 | minor | Elevation shown with heavy shadows instead of surface container tones |
| MD012 | minor | Snackbars stacked, carrying critical info, or with more than one action |
| MD013 | minor | iOS patterns: back chevron with text in the top-left, iOS switches, action sheets instead of bottom sheets/menus |
| MD014 | suggestion | No monochrome layer for themed app icons |

## Output

Findings grouped by area (theme, type, shape, layout, components, system, code), the top three changes, and a theme
specification (role table for light and dark) when the theme itself needs rework.

## Additional Resources

| File | Content |
|------|---------|
| [m3-color-system.md](references/m3-color-system.md) | Colour roles, tone mapping for light and dark, surface containers, contrast by tone, dynamic colour, brand colours |
| [m3-type-shape-motion.md](references/m3-type-shape-motion.md) | Type scale table, shape scale, elevation levels, state layers, motion |
| [m3-components-and-layout.md](references/m3-components-and-layout.md) | Components and their rules, window size classes, canonical layouts, edge-to-edge, Compose review notes |
