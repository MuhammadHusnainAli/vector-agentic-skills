# Alt Text Decisions

## Decision tree

```
Does the image contain text?
  yes -> Is the text also in the page? yes: alt="" (decorative)   no: alt = the text (better: don't use images of text)
Is the image the only content of a link or button?
  yes -> alt describes the destination or action, not the picture ("Home", "Search", "Acme logo - home")
Does the image add information not in the surrounding text?
  yes -> Is it simple (photo, icon with meaning)? -> short alt describing the information
         Is it complex (chart, diagram, map)? -> short alt + full description nearby or a data table
  no  -> decorative: alt="" (or CSS background, or aria-hidden on SVG)
```

## Examples

| Image | Context | Alt |
|-------|---------|-----|
| Product photo | Product page, name in heading | "Blue linen shirt, front view" (detail the name doesn't give) |
| Same photo | Product card, title link already says "Blue linen shirt" | "" (redundant) |
| Avatar | Next to the person's name | "" |
| Avatar | Alone, identifies the account menu | Part of the button name: "Account menu, Dana Lee" |
| Logo | Header, links home | "Acme home" |
| Icon with visible label | Button "Delete" with trash icon | Icon alt="" / aria-hidden; the button text names it |
| Icon without label | Icon-only button | Button name "Delete invoice INV-1042" |
| Status icon | "Overdue" text next to it | "" |
| Status icon | No text | "Overdue" |
| Chart | Revenue trend | Short: "Revenue by month, Jan-Nov 2026: up 8%, peak in October." + data table or link |
| Illustration | Empty state, headline explains it | "" |
| Screenshot in docs | Showing a setting | "Settings page with 'Two-factor authentication' switched on" |
| Decorative divider or background | - | "" / CSS |

## Writing alt text

- Describe the purpose and information, not "image of" / "picture of".
- Keep it short (often under about 125 characters); put long descriptions in visible text or a linked description.
- Use the language of the page; include text in the image verbatim if it matters.
- Different contexts can need different alt for the same image: annotate per placement.

## Annotation format

`IMG 3 [informative] alt="Blue linen shirt, front view"`
`IMG 4 [decorative] alt=""`
`IMG 5 [complex] alt="Revenue by month..." + data table below the chart`
