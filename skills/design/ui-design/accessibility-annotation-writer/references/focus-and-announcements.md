# Focus Management and Announcements

## Focus rules for dynamic UI

| Event | Focus goes to | Notes |
|-------|---------------|-------|
| Dialog opens | First focusable element, or the dialog heading (tabindex -1) when content comes first; least destructive button for confirmations | Focus stays inside while open |
| Dialog closes | The element that opened it | If it no longer exists, the next logical element |
| Menu / popover opens | First item (menus) or the content (popovers) | Escape closes and returns focus |
| Drawer / side panel opens | Panel heading or first control | Same return rule |
| Item deleted from a list | Next item; previous if it was last; the empty state's action if none left | Never `<body>` |
| Inline edit saved | The edited item's display (or a success message) | |
| Form submitted with errors | Error summary | Summary links move focus to fields |
| Form submitted successfully | Success heading or the new page's h1 | |
| Route change in a single-page app | New page h1 (or a "skip" target) | Also update the document title |
| Content loaded on demand ("Load more") | First newly loaded item | Announce the count |
| Expanding a section | Keep focus on the trigger | Content follows in reading order |

## Live regions

| Politeness | Use | Example |
|------------|-----|---------|
| `role="status"` / `aria-live="polite"` | Updates that can wait for a pause | "24 results", "Saved", "Link copied", "3 items in cart" |
| `role="alert"` / `aria-live="assertive"` | Urgent, time-sensitive errors | "Connection lost. Changes aren't being saved." |
| `aria-busy="true"` on a region | Region is updating; announce once when done | Tables refreshing |

Rules:
- The live region must exist in the DOM before the update; inject text into it, don't create the region with the text.
- Announce outcomes, not every keystroke. Debounce search result counts (about 500 ms after typing stops).
- One announcement per event; avoid duplicates from both a toast and an inline message.
- Toasts: polite status; the toast itself doesn't take focus; actions in toasts need another way to reach them.

## Announcement wording

| Event | Wording |
|-------|---------|
| Filter applied | "24 results for 'linen', filtered by size M" |
| Item added | "Linen shirt added to cart. 3 items in cart." |
| Saved | "Changes saved" |
| Async error | "Couldn't save changes. Try again." |
| Loading started (long) | "Loading invoices" (then "24 invoices loaded") |
| Drag and drop | "Picked up Task 3. Position 3 of 8." ... "Dropped Task 3 at position 1 of 8." |

## Annotation format

`ANN 1 [polite] on filter change: "{count} results"`
`FOCUS 2 on dialog close -> 'Add filter' button`
`FOCUS 3 on row delete -> next row's name link; if none, 'Create invoice' button`
