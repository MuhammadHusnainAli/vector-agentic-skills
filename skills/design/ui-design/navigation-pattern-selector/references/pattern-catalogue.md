# Navigation Pattern Catalogue

## Bottom tab bar / navigation bar
- 3-5 destinations of equal importance, used often. Always visible, one tap to switch.
- Each tab keeps its own navigation stack; tapping the active tab scrolls to top or pops to root.
- Labels under icons. Don't use it for actions (a "+" tab that opens a sheet is a known exception; make it look different).
- Hide only when scrolling content in immersive views, and bring it back on scroll up.

## Navigation rail
- Vertical bar on the leading edge for medium and expanded widths; 3-7 destinations; optional FAB/menu at the top.
- Replaces the bottom bar when the window widens; keeps the same destinations and selection.

## Sidebar (persistent)
- Web apps, admin tools, iPad and desktop apps with many sections. Can hold groups, counts and nested items.
- Collapsible to icons (with tooltips and labels on expand); remember the collapsed state.
- Nesting deeper than 2 levels in a sidebar becomes a file tree: provide search.

## Drawer (modal)
- For the long tail on small screens, or as the compact form of a sidebar.
- Lowers discoverability of its contents. Never put the top tasks only in the drawer.
- Opens with focus on the first item, closes on Escape and scrim tap, returns focus to the menu button.

## Top navigation (web header)
- Content sites and marketing; about 5-7 items fits without crowding.
- Becomes a menu button below the medium breakpoint; keep search visible if search matters.
- Dropdowns open on click (and hover only as an enhancement); keyboard: Enter/Space open, Escape closes.

## Mega menu
- Large catalogues (retail, universities, documentation). Groups with headings; shows the breadth at a glance.
- Open on click or with a hover delay (about 300 ms) to avoid flicker. Must be keyboard-operable and use links, not `role=menu`.

## Hub and spoke
- A home screen of tools; each spoke is self-contained and returns to the hub.
- Good for utilities, kiosks, settings, setup flows. Poor for frequent switching between tools.

## Tabs (in-page)
- Switch views of the same object or section ("Overview, Activity, Settings"). Not site navigation.
- On the web they can be links styled as tabs when each tab has its own URL. Then use `aria-current`, not `role=tab`.

## Breadcrumbs
- Show location in a hierarchy of 3+ levels; each crumb a link except the current page (`aria-current="page"`).
- Complement, never replace, primary navigation. On mobile, show only the parent ("< Category").

## Search-first and command palette
- Search as the main navigation for content-heavy or expert tools; needs good results, synonyms and recent items.
- Command palette (Cmd/Ctrl+K) for power users: navigation + actions. Always also reachable through visible UI.

## Accessibility markup (web)

```html
<a class="skip-link" href="#main">Skip to main content</a>
<nav aria-label="Main">
  <ul>
    <li><a href="/projects" aria-current="page">Projects</a></li>
    <li><a href="/reports">Reports</a></li>
  </ul>
</nav>
<nav aria-label="Breadcrumb"><ol>...</ol></nav>
<main id="main">...</main>
```
Several `nav` landmarks need distinct `aria-label`s. Disclosure-style dropdowns use `aria-expanded` on a button, not
`role=menu`.
