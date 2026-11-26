# Card Anatomy

## Slots (top to bottom)

| Slot | Content | Limit | Fallback |
|------|---------|-------|----------|
| Media | Image, video poster, illustration, map | Fixed aspect ratio per grid (16:9, 4:3, 1:1) | Neutral placeholder with icon or initials; don't collapse the slot in a grid |
| Eyebrow | Category, type, status | 1 line, 1-3 words | Omit |
| Title | The item's name | 2 lines, line-clamp | Required |
| Meta | Date, author, duration, location | 1 line | Omit parts, not the line |
| Description | Summary | 2-3 lines, line-clamp | Omit; card keeps alignment via flex |
| Attributes | Price, rating, tags, badges | 1-2 rows; at most 2-3 badges | Omit |
| Actions | Primary link (title), secondary buttons | 1 row, pinned to bottom | - |

Order by scanning priority for the task: shoppers scan image -> price -> title; readers scan title -> meta; project lists
scan title -> status -> owner.

## Truncation

```css
.card-title { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
```
- Full text must be reachable: the detail page, or the title attribute / tooltip on desktop and the detail page on touch.
- Never truncate prices, dates or anything legally meaningful.
- Truncate at the content level (summary written for the card) when you control the content; it reads better than an ellipsis.

## Media

- One aspect ratio per grid; `object-fit: cover` with a focal point set by the content team for important crops.
- `width`/`height` or `aspect-ratio` attributes to stop layout shift; `loading="lazy"` below the fold.
- Alt text: describes the image when it adds information (product photo -> "Blue linen shirt, front view"). If the image
  only repeats the title, use `alt=""`.

## Badges

- At most 2-3; each has a job (status, discount, new). Text labels, not colour alone.
- Position consistently (top-left over media, or in the eyebrow).

## Product card specifics

- Price with currency and the original price struck through for discounts (with visually hidden "Was" / "Now" text).
- Rating: stars + numeric value + count ("4.6 (1,203 reviews)").
- Add-to-cart as a separate button, not the card link; quantity and variant selection usually belong on the detail page.
- Out of stock: keep the card, show status text, change the action.

## Pricing plan cards

- Same rows in the same order in every plan card so features line up; show differences, not 40 identical ticks.
- One recommended plan, visually emphasised, with the reason ("Most teams choose").
- Price unit and billing period next to the price ("$12 per user / month, billed annually").
