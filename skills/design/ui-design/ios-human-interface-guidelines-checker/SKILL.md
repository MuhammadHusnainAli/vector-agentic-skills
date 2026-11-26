---
name: ios-human-interface-guidelines-checker
description: "Review iPhone and iPad designs and SwiftUI code against Apple's Human Interface Guidelines the way an experienced iOS design lead would: layout with safe areas and layout margins, size classes and iPad multitasking, 44x44pt hit targets, Dynamic Type text styles (Large Title 34pt to Caption 2 11pt) and accessibility sizes, SF Pro and SF Symbols, semantic system colours and dark mode, materials and Liquid Glass bars, navigation (tab bars, navigation stacks, sidebars, search), modality (sheets with detents, alerts, action sheets, full-screen covers), controls (buttons, toggles, pickers, menus, context menus, swipe actions), feedback and haptics, permissions in context, app icons, and accessibility (VoiceOver labels and traits, Reduce Motion, Reduce Transparency, Increase Contrast, Bold Text). Separates platform conventions from taste in its findings. Use when designing or reviewing an iOS or iPadOS app, porting an Android or web design to iOS, or preparing for App Store review."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# iOS Human Interface Guidelines Checker

iOS users have strong expectations: back is top-left and edge-swipe, tabs switch sections and never act as buttons, sheets
pull down to dismiss, text follows the system size. Designs that break these feel foreign, even when nobody can say why.
Android or web designs ported straight across break them most. This skill reviews screens and SwiftUI code against the
HIG. It separates what users rely on (conventions) from what Apple only suggests, so review time goes where it counts.

## Trigger Conditions

Activate this skill when the user:
- Shares iPhone or iPad screens, a Figma file description or SwiftUI code for review
- Ports an Android or web product to iOS
- Asks about iOS navigation, sheets, tab bars, Dynamic Type, SF Symbols or system colours
- Prepares an app for App Store review or an accessibility audit

Android equivalent: `material-design-3-compliance-reviewer`. watchOS: `watchos-ui-layout-advisor`. Navigation choice:
`navigation-pattern-selector`.

## Workflow

```
1. CONTEXT   -> device classes (iPhone, iPad, both), orientation, iOS version floor, SwiftUI or UIKit
2. STRUCTURE -> navigation model: tab bar + stacks, sidebar on iPad, modality (references/hig-review-areas.md)
3. LAYOUT    -> safe areas, margins, size classes, iPad multitasking widths
4. TEXT      -> Dynamic Type styles, largest accessibility size, truncation (references/dynamic-type-and-accessibility.md)
5. VISUALS   -> system colours, dark mode, materials, SF Symbols, icon
6. CONTROLS  -> system controls first; custom ones need the same behaviour
7. ACCESS    -> VoiceOver, Reduce Motion/Transparency, Increase Contrast, Bold Text
8. CODE      -> SwiftUI review notes when code is shared (references/swiftui-review-notes.md)
9. REPORT    -> findings by severity with the HIG area and the fix
```

## Severity Model

| Severity | Meaning | Example |
|----------|---------|---------|
| Blocker | Breaks a platform convention users rely on, or an accessibility failure | Custom back button that disables edge-swipe; text that doesn't scale; 30pt targets |
| Major | Clearly non-native; users notice friction | Android-style FAB and top tabs; hamburger drawer as main navigation; toasts instead of inline feedback |
| Minor | Polish | SF Symbol weight doesn't match adjacent text; custom colours where semantic ones exist |
| Suggestion | Taste or newer-API opportunity | Use a sheet detent; adopt a context menu |

## Review Checklist

Report as `CODE [severity] screen/element: problem -> fix (HIG area)`.

| Code | Severity | Check |
|------|----------|-------|
| IH001 | blocker | Tap targets under 44x44pt |
| IH002 | blocker | Text that doesn't support Dynamic Type, or layouts that clip at accessibility sizes |
| IH003 | blocker | Back navigation broken: custom back control without edge-swipe, or no way back |
| IH004 | blocker | Interactive elements without VoiceOver labels; images of text |
| IH005 | major | Tab bar used for actions, more than 5 tabs on iPhone, or tab bar hidden on top-level screens |
| IH006 | major | Content under the status bar, Dynamic Island or home indicator (safe-area violations) |
| IH007 | major | Android patterns: FAB, snackbars, top app bar with hamburger as primary navigation, overflow ⋮ menus |
| IH008 | major | Hard-coded colours that break in dark mode or Increase Contrast |
| IH009 | major | Modal misuse: full-screen cover for a quick task, sheet without a way to save/cancel, alerts with more than 3 buttons |
| IH010 | major | Animations that ignore Reduce Motion; translucency that ignores Reduce Transparency |
| IH011 | minor | Custom controls where a system control exists (toggles, pickers, segmented controls, menus) |
| IH012 | minor | Icons that aren't SF Symbols (or don't match their weight and scale) next to text |
| IH013 | minor | Permission requests at launch with no context |
| IH014 | suggestion | Missing iPad adaptation (stretched phone layout instead of sidebar / multi-column) |

## Output

Findings table grouped by screen, then a summary: blockers count, the three changes with the most impact, and anything
that needs a platform decision (e.g. keep brand typeface vs SF Pro with Dynamic Type support).

## Additional Resources

| File | Content |
|------|---------|
| [hig-review-areas.md](references/hig-review-areas.md) | Layout, navigation, modality, controls, feedback, colour, icons, permissions: rules and common violations |
| [dynamic-type-and-accessibility.md](references/dynamic-type-and-accessibility.md) | Text style table, accessibility sizes, custom fonts, VoiceOver, display settings |
| [swiftui-review-notes.md](references/swiftui-review-notes.md) | SwiftUI patterns that break the HIG and their fixes |
