# Clickable Cards

## The problem

Wrapping the whole card in `<a>`:
- is invalid when the card contains buttons or other links (interactive content inside `<a>`),
- makes screen readers read the entire card as one long link name,
- breaks text selection.

## Stretched-link pattern

One real link on the title; a pseudo-element stretches its hit area over the card. Secondary actions sit above it.

```html
<article class="card">
  <img src="shirt.jpg" alt="">
  <h3 class="card-title"><a href="/products/linen-shirt">Linen shirt</a></h3>
  <p>Relaxed fit, 100% linen</p>
  <p class="price">$59</p>
  <button class="card-action" type="button">Save to wishlist</button>
</article>
```

```css
.card { position: relative; }
.card-title a::after { content: ""; position: absolute; inset: 0; }      /* the whole card is the link target */
.card-action { position: relative; z-index: 1; }                         /* secondary actions stay clickable */
.card:has(a:focus-visible) { outline: 2px solid var(--focus-ring-color); outline-offset: 2px; }
.card-title a:focus-visible { outline: none; }                           /* ring is drawn on the card instead */
.card:hover { box-shadow: var(--elevation-2); }                         /* no size change */
```

Notes:
- `:has()` is supported in all current evergreen browsers. Without it, put the outline on the `::after` element.
- The link name is just the title. Screen-reader users get a short, meaningful link list.
- Text selection inside the card is blocked by the overlay. If users need to copy text, limit the overlay to the media
  and title area.
- Don't add `cursor: pointer` to non-link areas when the overlay is limited.

## Redundant links

Image, title and "Read more" pointing to the same URL make three tab stops and three identical links. Keep one (title
with stretched area). If a visible "Read more" is required by design, make it `aria-hidden="true"` and `tabindex="-1"`,
or give it context with visually hidden text ("Read more <span class="visually-hidden">about linen care</span>").

## Selectable cards (choose one or many)

Cards as choices (plans, delivery options, answers) are radios or checkboxes, not links:

```html
<fieldset class="choice-cards">
  <legend>Choose a delivery speed</legend>
  <label class="choice-card">
    <input type="radio" name="delivery" value="express">
    <span class="title">Express</span> <span>Tomorrow, $9.99</span>
  </label>
</fieldset>
```
Selected state: border + check icon + background, not colour alone. Keyboard: arrows within the radio group.

## Keyboard and screen reader checks

- Tab order: card link, then each secondary action, then next card.
- Each card is an `article` (or `li` in a `ul`) with a heading; screen-reader users can jump by heading.
- Focus ring visible on the whole card or the title; never clipped by `overflow: hidden` on the card (use `outline-offset`
  inside, or no overflow clipping on the card itself).
