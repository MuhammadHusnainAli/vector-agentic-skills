# Shadow Recipes

## Why layer shadows

A real object casts a tight, darker contact shadow (key light) and a wide, faint shadow (ambient light). One big blurred
shadow looks like a glow; layering two or three looks like depth.

## Formula (one light source above, slightly in front)

For level n (1-5):
```
key:      0  y=n         blur=2n      spread=0     alpha≈0.10-0.12
ambient:  0  y=2n..3n    blur=4n..6n  spread=-n/2  alpha≈0.06-0.08
```
- x offset is always 0 (light from straight above) or the same small value for every shadow.
- Negative spread on the ambient shadow keeps it from spilling out the sides.
- Alpha stays low; depth comes from size and blur, not darkness.

## Light theme tokens (5 levels)

```css
:root {
  --shadow-color: 220 40% 15%;      /* tinted toward the UI's hue, not pure black */
  --elevation-1: 0 1px 2px hsl(var(--shadow-color) / 0.10), 0 1px 3px -1px hsl(var(--shadow-color) / 0.08);
  --elevation-2: 0 2px 4px hsl(var(--shadow-color) / 0.10), 0 4px 8px -2px hsl(var(--shadow-color) / 0.08);
  --elevation-3: 0 4px 8px hsl(var(--shadow-color) / 0.10), 0 8px 16px -4px hsl(var(--shadow-color) / 0.10);
  --elevation-4: 0 8px 16px hsl(var(--shadow-color) / 0.12), 0 16px 32px -8px hsl(var(--shadow-color) / 0.12);
  --elevation-5: 0 12px 24px hsl(var(--shadow-color) / 0.14), 0 24px 48px -12px hsl(var(--shadow-color) / 0.16);
}
```

## Dark theme

Shadows barely register on dark surfaces. Elevation comes from lighter surfaces and borders; floating layers keep a
darker, softer shadow to separate them from the content beneath.

```css
[data-theme="dark"] {
  --shadow-color: 220 40% 2%;
  --elevation-1: 0 0 0 1px hsl(0 0% 100% / 0.06);
  --elevation-2: 0 0 0 1px hsl(0 0% 100% / 0.08);
  --elevation-3: 0 0 0 1px hsl(0 0% 100% / 0.08), 0 8px 16px hsl(var(--shadow-color) / 0.50);
  --elevation-4: 0 0 0 1px hsl(0 0% 100% / 0.10), 0 16px 32px hsl(var(--shadow-color) / 0.60);
  --elevation-5: 0 0 0 1px hsl(0 0% 100% / 0.10), 0 24px 48px hsl(var(--shadow-color) / 0.70);
  /* pair each level with its surface token: --surface-raised-1 ... --surface-raised-5 */
}
```

## Tinted shadows

On coloured backgrounds, use a darker, desaturated version of the background hue as the shadow colour. Grey shadows on a
blue or beige surface look dirty.

## Animation

Animating `box-shadow` repaints on every frame. For hover lifts on many cards:
```css
.card { position: relative; transition: transform 150ms ease-out; }
.card::after { content: ""; position: absolute; inset: 0; border-radius: inherit;
               box-shadow: var(--elevation-3); opacity: 0; transition: opacity 150ms ease-out; }
.card:hover { transform: translateY(-2px); }
.card:hover::after { opacity: 1; }
@media (prefers-reduced-motion: reduce) { .card, .card::after { transition: none; } .card:hover { transform: none; } }
```

## Forced colors (Windows high contrast)

Shadows are removed in forced-colors mode. Anything that relied on a shadow to show its edge needs a border:
```css
@media (forced-colors: active) { .card, .menu, .dialog { border: 1px solid CanvasText; } }
```
A transparent 1px border in normal mode (`border: 1px solid transparent`) becomes visible automatically in forced colors.

## Figma

Create effect styles (or variables where supported) named `elevation/1` ... `elevation/5` with the same layers and values,
and a dark-mode set. Designers pick a level, never type shadow values.
