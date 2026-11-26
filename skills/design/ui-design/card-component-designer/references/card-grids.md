# Card Grids

## Auto-fill grid

```css
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr));
  gap: var(--space-6, 1.5rem);
}
```
- `min(100%, 17.5rem)` stops overflow when the container is narrower than the minimum.
- `auto-fill` keeps empty tracks so a single card doesn't stretch across the row; `auto-fit` collapses them and stretches
  the cards. Use auto-fill for collections, auto-fit for a known small set that should fill the row.

## Column math

```
columns = floor((container + gap) / (min_card + gap))
card    = (container - (columns - 1) x gap) / columns
```

Example, min card 280px, gap 24px:

| Container | Columns | Card width |
|-----------|---------|------------|
| 343 (phone) | 1 | 343 |
| 600 | 2 | 288 |
| 912 | 3 | 288 |
| 1216 | 4 | 286 |
| 1376 | 4 | 326 |

Check the widest card in each column count: at 1191px there are still 3 columns of 381px (4 columns start at 1192px), so the media crop and line
lengths must still work at 381px. If that's too wide, set an explicit max with
`minmax(min(100%, 17.5rem), 22rem)` and `justify-content: start`.

## Equal heights, actions at the bottom

```css
.card { display: flex; flex-direction: column; }
.card .actions { margin-top: auto; }
```
Grid rows already give equal heights per row. Pinning actions keeps them aligned across cards with different description
lengths. For aligned internal rows across cards (pricing tables), use `grid-template-rows: subgrid`.

## Masonry

For media of varying heights (inspiration boards). It breaks reading order for keyboard and screen-reader users if the
visual order differs from DOM order. Keep the DOM order the same as the visual order (column-first layouts read down
each column).

## Horizontal scrollers (carousels of cards)

- Show part of the next card so scrolling is discoverable.
- Scroll snap (`scroll-snap-type: x mandatory`), visible scroll buttons for pointer users, and keyboard scrolling.
- A heading and a "See all" link to the full collection. Never auto-advance.

## Loading and empty

- Skeleton cards in the grid with the same dimensions; the number of skeletons roughly matches the expected page.
- Empty collection: the grid region is replaced by an empty state with one action, not an empty grid.
- Infinite scroll: announce new items ("20 more products loaded") and keep a footer reachable, or use "Load more".
