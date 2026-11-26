---
name: windows-fluent-design-reviewer
description: "Review Windows 11 app designs and WinUI 3 / XAML against Fluent 2 like a Windows design lead: Segoe UI Variable type ramp (Caption to Display), 4px spacing grid, corner radii (4px controls, 8px top-level surfaces), materials used for the right layer (Mica for the base window, Mica Alt for tabbed title bars, Acrylic for transient surfaces, Smoke behind dialogs), light, dark and contrast themes through ThemeResource, Segoe Fluent Icons, custom title bars that keep caption buttons and drag regions, NavigationView (left, top, compact), CommandBar, TabView, ContentDialog, InfoBar, TeachingTip, flyouts, window size breakpoints and snap layouts, keyboard (access keys, accelerators, F6 between panes), pen and touch with 40x40 epx targets, and Narrator through UI Automation names. Reviews XAML for hard-coded colours and sizes, missing automation names, broken contrast themes and fixed layouts. Use when designing, porting or reviewing a Windows desktop app or a Fluent-based product."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Windows Fluent Design Reviewer

A Windows 11 app feels native when it uses the system's layers correctly: Mica behind the window so the wallpaper tint
shows through, Acrylic only on transient flyouts, the system type ramp, and title bar, navigation and commands where
Windows users expect them. It also has to keep working with a keyboard alone, in contrast themes and at any window size.
Desktop apps ported from the web or macOS tend to miss all of these. This skill reviews designs and XAML against Fluent 2
and the Windows app guidelines.

## Trigger Conditions

Activate this skill when the user:
- Designs or reviews a Windows 11 desktop app (WinUI 3, Windows App SDK, WPF with Fluent styles, Electron targeting Windows)
- Ports a macOS or web app to Windows
- Asks about Mica, Acrylic, title bars, NavigationView, Fluent type ramp or contrast themes
- Shares XAML for a design review

macOS/iOS: [ios-human-interface-guidelines-checker](../ios-human-interface-guidelines-checker/SKILL.md). Android: [material-design-3-compliance-reviewer](../material-design-3-compliance-reviewer/SKILL.md). Button order per
platform: [button-state-variant-designer](../button-state-variant-designer/SKILL.md).

## Workflow

```
1. CONTEXT   -> framework (WinUI 3, WPF, Electron), window sizes supported, input (mouse/keyboard, touch, pen)
2. SHELL     -> title bar, window material, navigation model (references/windows-app-patterns.md)
3. FOUNDATION-> type ramp, spacing grid, radii, iconography, colour and themes (references/fluent-foundations.md)
4. CONTROLS  -> use WinUI controls; commands, dialogs, notifications per guidance
5. SIZES     -> small, medium, large window layouts; snap layouts; minimum size
6. INPUT     -> keyboard model (Tab, arrows, F6, access keys, accelerators), touch targets, pen
7. ACCESS    -> Narrator names, contrast themes, text scaling, focus visuals
8. CODE      -> XAML review notes (references/xaml-review-notes.md)
9. REPORT    -> findings by severity with fixes
```

## Review Checklist

Report as `CODE [severity] screen/element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| WF001 | blocker | Not fully keyboard operable: missing focus visuals, unreachable panes, no F6 / arrow navigation in lists and menus |
| WF002 | blocker | Breaks in contrast themes (hard-coded colours, images of text, information by colour only) |
| WF003 | blocker | Interactive elements without accessible names for Narrator |
| WF004 | major | Custom title bar without caption buttons, drag region or system menu behaviour |
| WF005 | major | Materials on the wrong layer: Acrylic as the whole window background, Mica on transient flyouts, opaque custom backgrounds that hide Mica |
| WF006 | major | Fixed layout that breaks when snapped to half or a third of the screen |
| WF007 | major | Non-Windows patterns: macOS-style traffic lights, primary button on the right of dialogs, web-style modals instead of ContentDialog |
| WF008 | major | Touch targets under 40x40 epx in touch-capable apps |
| WF009 | minor | Text outside the type ramp, spacing off the 4px grid, radii other than 4/8px |
| WF010 | minor | Icons not from Segoe Fluent Icons (or inconsistent with it) at mismatched sizes |
| WF011 | minor | No keyboard accelerators for frequent commands, or non-standard ones (Ctrl+S, Ctrl+Z, Ctrl+F, F5) |
| WF012 | suggestion | Doesn't respect text scaling (Settings > Accessibility > Text size) |

## Output

Findings grouped by area (shell, foundations, controls, layout, input, accessibility, code), the three most important
changes, and corrected XAML snippets where code was reviewed.

## Additional Resources

| File | Content |
|------|---------|
| [fluent-foundations.md](references/fluent-foundations.md) | Type ramp, spacing, radii, materials, colour and themes, iconography, motion |
| [windows-app-patterns.md](references/windows-app-patterns.md) | Title bar, navigation, commands, dialogs and notifications, window sizes, keyboard, touch and pen |
| [xaml-review-notes.md](references/xaml-review-notes.md) | XAML patterns that break Fluent or accessibility, with fixes |
