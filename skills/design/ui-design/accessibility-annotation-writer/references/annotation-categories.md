# Annotation Categories

| Category | Specify | Note template | WCAG |
|----------|---------|---------------|------|
| Page title | Unique, descriptive title per page/route | "Title: 'Invoices - Acme Billing'" | 2.4.2 |
| Landmarks | header/banner, nav (with labels if several), main, aside/complementary, footer/contentinfo, search, form | "nav aria-label='Account'" | 1.3.1 |
| Headings | Outline with levels; one h1 | "H1 Invoices / H2 Overdue / H2 Paid" | 1.3.1, 2.4.6 |
| Reading order | Order content is read when it differs from visual guesses (multi-column, cards) | Numbered markers | 1.3.2 |
| Focus order | Sequence of interactive elements | Numbered markers 1..n | 2.4.3 |
| Accessible names | Name for each control without a visible text label, or whose visible label is ambiguous | "Button name: 'Remove Linen shirt from cart'" | 4.1.2, 2.4.6, 2.5.3 (label in name) |
| Roles | Custom components and what they are | "Tabs (tablist/tab/tabpanel)" | 4.1.2 |
| States | Expanded, selected, checked, pressed, current, invalid, busy | "aria-expanded on 'Filters' button" | 4.1.2 |
| Images | Alt decision (see alt-text-decisions.md) | "Decorative: alt=''" / "Alt: 'Line chart: revenue up 8%...'" | 1.1.1 |
| Forms | Label, hint, required, format, error text, autocomplete token, grouping | "Group 'Delivery address' fieldset; postcode autocomplete=postal-code" | 1.3.1, 1.3.5, 3.3.1, 3.3.2 |
| Errors | Inline error association, summary, focus on submit | "Error summary receives focus; links to fields" | 3.3.1, 3.3.3 |
| Announcements | Text and politeness for dynamic updates | "Polite: '24 results'" | 4.1.3 |
| Focus management | Focus target on open, close, delete, route change | "On close, focus returns to 'Add filter'" | 2.4.3 |
| Keyboard | Keys for custom widgets; shortcuts and how to turn them off | "Arrow keys move between tabs" | 2.1.1, 2.1.4 |
| Gestures | Alternatives to multipoint or path gestures and dragging | "Swipe to delete also via row menu 'Delete'" | 2.5.1, 2.5.7 |
| Target size | Controls smaller than 24 x 24 CSS px or tightly spaced | "Icon buttons 32 x 32 hit area" | 2.5.8 |
| Colour | Non-colour cue for meaning | "Status uses icon + text, not colour only" | 1.4.1 |
| Contrast | Pairs that need checking (text on images, brand colours) | "Text on hero image: scrim to 4.5:1" | 1.4.3, 1.4.11 |
| Motion | Animated content, auto-play, reduced-motion behaviour | "Carousel doesn't auto-advance; reduced motion = no slide" | 2.2.2, 2.3.3 |
| Reflow / zoom | Behaviour at 320 CSS px and 200% text | "Table scrolls horizontally in its region at 320" | 1.4.4, 1.4.10 |
| Language | Parts in another language | "lang='fr' on the French quote" | 3.1.2 |
| Tables | Caption, header cells, scope, sortable columns' state | "Column headers th scope=col; aria-sort on sorted column" | 1.3.1 |
| Timeouts | Warnings and extensions | "Warn 2 min before session expiry with 'Stay signed in'" | 2.2.1 |
| Authentication | No cognitive tests; paste and password managers allowed | "OTP field allows paste; no CAPTCHA puzzles" | 3.3.8 |

## Heading outline example

```
H1  Invoices
  H2  Overdue (3)
  H2  Due this month
  H2  Paid
Dialog: H2 Send reminder (dialog labelled by its heading)
```

## Focus order example

```
1 Skip to main content
2 Logo (link: Home)
3 Main nav: Dashboard, Invoices (current), Customers, Settings
4 Search
5 Account menu button
6 H1 region: 'New invoice' button
7 Filters button (aria-expanded)
8 Invoice table: first row link ... row actions menu buttons
9 Pagination
```
