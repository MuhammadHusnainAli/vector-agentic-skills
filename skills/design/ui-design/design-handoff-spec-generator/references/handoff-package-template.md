# Handoff Package Template

```markdown
# <Feature> - design handoff
Status: Ready for dev | Version: 1.0 | Designer: | Engineering lead: | QA: | Date:
Links: Figma (ready-for-dev page) | PRD | Research | Epic/tickets

## 1. Goal and scope
- Goal: <user outcome + business outcome>
- In scope: <list>
- Out of scope: <list, with where it's tracked>
- Platforms and breakpoints: web 360 / 768 / 1280+, iOS, Android

## 2. Flows
<Mermaid flow diagram with screen IDs; entry points; exits>

## 3. Screens
| ID | Screen | Breakpoints | Figma link | Notes |
|----|--------|-------------|------------|-------|
| S01 | Order list | 360, 768, 1280 | <link> | |

## 4. Components
| Component | Type | Props / variant | Notes |
|-----------|------|-----------------|-------|
| Button | Existing DS | variant=primary, size=md | |
| DataTable | Existing DS, modified | new `density="compact"` | Spec: <link>; DS team informed |
| RefundSummary | New, feature-only | - | Spec in section 6 |

## 5. States and edge cases
<State matrix per screen: default, loading, empty, error, partial, no permission, offline>
<Edge cases: long names, 0 / 1 / many items, max values, past/future dates, RTL>

## 6. Behaviour
- Interactions: <what each control does; navigation; overlays>
- Motion: <transition, duration token, easing token, reduced motion>
- Focus: <on open, on close, after delete, after submit>
- Keyboard: <shortcuts, Escape, Enter>
- Responsive: <what changes per range: layout, hidden columns, navigation>

## 7. Data
| Field | Source | Format / display | Validation | Empty / error display |
|-------|--------|------------------|------------|-----------------------|
| Refund amount | orders API `amount_cents` | Locale currency, 2 decimals | <= order total | "-" |
Sorting: <default, options>. Pagination: <page size, infinite/paged>. Limits: <max items, max chars>.
Error codes -> messages: <table>

## 8. Content
<Final strings with IDs, max lengths, plural forms, localisation notes; link to the copy doc>

## 9. Accessibility
<Headings, landmarks, focus order, names for icon buttons, live announcements; link to annotations>

## 10. Analytics
| Event | Trigger | Properties |
|-------|---------|------------|
| refund_started | Tap "Refund" | order_id, items_count |

## 11. Assets
<Icons (from the set or new), illustrations, images: formats and names>

## 12. Acceptance criteria
<Per story, Given/When/Then>

## 13. Open questions
| Question | Owner | Due | Decision |
|----------|-------|-----|----------|
```

## Notes on each section

- **Components:** the most valuable table. Engineers decide build effort from it; the design system team learns about new
  needs early.
- **States:** a screen without its empty, loading and error states isn't ready.
- **Data:** formats and limits are design decisions; if they're left open, engineers make them.
- **Open questions:** shipping with open questions is fine; shipping with unowned ones isn't.
