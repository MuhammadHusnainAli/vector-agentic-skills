---
name: navigation-pattern-selector
description: "Choose and design the navigation system for an app or site from its information architecture rather than taste: number and frequency of top-level destinations, depth, platform and window size, and the user's main tasks decide between bottom tab bar, navigation rail, sidebar, drawer, top navigation, mega menu, hub-and-spoke, tabs, breadcrumbs, search-first and command palette. Covers iOS tab bars and sidebars, Material 3 navigation bar / rail / drawer by window size class, Fluent NavigationView, web header and sidebar patterns, responsive transitions between them, wayfinding (where am I, where can I go, how do I get back), label writing, and validating the IA with card sorting, tree testing and first-click tests. Reviews navigation for hidden primary destinations, too many top-level items, mixed tabs and links, vague or jargon labels, no current-location indicator, deep nesting and inconsistent back behaviour. Use when designing or restructuring an app's or site's navigation or information architecture."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Navigation Pattern Selector

Navigation follows from the information architecture. Teams that argue "hamburger vs tabs" usually haven't decided what the
top-level destinations are, how often people use each, and how deep the content goes. Once those are known, the pattern is
mostly chosen for you. This skill gets those facts, picks the pattern per platform and size, and checks the result for the
failures that show up in analytics: features nobody finds, users who don't know where they are, and back buttons that
surprise people.

## Trigger Conditions

Activate this skill when the user:
- Designs navigation for a new app, site, dashboard or admin tool
- Debates tab bar vs drawer vs sidebar, or adds a destination to a full tab bar
- Restructures an IA, merges products, or reports that users can't find features
- Needs navigation to adapt across phone, tablet and desktop

Breakpoints and layout per range: [responsive-breakpoint-layout-planner](../responsive-breakpoint-layout-planner/SKILL.md). Platform rules in depth:
[ios-human-interface-guidelines-checker](../ios-human-interface-guidelines-checker/SKILL.md), [material-design-3-compliance-reviewer](../material-design-3-compliance-reviewer/SKILL.md), [windows-fluent-design-reviewer](../windows-fluent-design-reviewer/SKILL.md).

## Workflow

```
1. DESTINATIONS -> list candidate top-level destinations with usage frequency (analytics or research), not org chart
2. SHAPE        -> count top-level items, max depth, breadth per level, cross-links (references/ia-validation.md)
3. TASKS        -> top 5 user tasks; each should start from a visible top-level destination or search
4. PICK         -> apply the selection table below per platform and window size
5. WAYFINDING   -> current location, hierarchy cues, back/up behaviour, deep-link landing
6. ADAPT        -> define how the pattern changes per window size (references/platform-navigation.md)
7. VALIDATE     -> tree test the structure, first-click test the design
8. REVIEW       -> run the checklist below
```

## Selection Table

| IA shape | Phone | Tablet / medium | Desktop / expanded |
|----------|-------|-----------------|--------------------|
| 3-5 frequent peer destinations | Bottom tab bar | Rail (Android) / tab bar or sidebar (iPad) | Rail, sidebar or top nav |
| 6-10 destinations, a few frequent | Tab bar with the top 4 + "More", or tab bar + drawer for the rest | Rail + drawer | Sidebar (collapsible) |
| Many sections, deep content (docs, e-commerce catalogue) | Header with search + menu sheet | Same, wider | Top nav + mega menu or sidebar tree, breadcrumbs |
| One main task with occasional settings | Single screen + header actions | Same | Same |
| Independent tools, one used at a time (utilities, kiosk) | Hub and spoke | Hub and spoke | Hub and spoke or sidebar |
| Power users, many objects and commands | Search-first | Sidebar + command palette | Sidebar + command palette (Cmd/Ctrl+K) |
| Linear process (checkout, onboarding) | Stepper, no global nav | Same | Same; minimal header |

Hidden navigation (hamburger/drawer) lowers discovery of whatever is inside it. Put frequent destinations on screen, and
use the drawer for the long tail.

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| NV001 | high | A frequent primary destination is hidden behind a hamburger or "More" while rarer ones are visible |
| NV002 | high | No current-location indicator (selected tab, highlighted item, `aria-current="page"`) |
| NV003 | high | Back or up behaviour is inconsistent (back exits the app from a deep link, tab switch resets the stack unexpectedly) |
| NV004 | medium | Tab bar over 5 items (iOS / Material navigation bar), or rail over 7 |
| NV005 | medium | Tabs used as page navigation, or navigation links using `role=menu` / tab semantics |
| NV006 | medium | Labels that are vague (Resources, Solutions, More), jargon, or internal team names |
| NV007 | medium | Icon-only primary navigation without labels |
| NV008 | medium | Depth over 3-4 levels with no search or breadcrumbs |
| NV009 | medium | Same destination reachable under two different labels, or two destinations with near-identical labels |
| NV010 | medium | Navigation pattern changes between sizes without preserving the selected destination |
| NV011 | low | No skip link to main content (web, WCAG 2.4.1); landmark `nav` missing or unlabeled when there are several |
| NV012 | low | Structure not validated with users (no tree test or first-click test) |

## Output

1. Destination table: destination, frequency, level, label, icon
2. Pattern per window size with the reason
3. Wayfinding rules: selected state, breadcrumbs, back/up, deep links, state preservation per tab
4. Validation plan: tree test tasks and success criteria
5. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [pattern-catalogue.md](references/pattern-catalogue.md) | Each pattern: strengths, limits, rules, accessibility markup |
| [platform-navigation.md](references/platform-navigation.md) | iOS, Android (Material 3), Windows (Fluent) and web conventions, adaptive transitions |
| [ia-validation.md](references/ia-validation.md) | Depth vs breadth, labels, card sorting, tree testing, first-click testing, wayfinding |
