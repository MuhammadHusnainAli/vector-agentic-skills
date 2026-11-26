# Capture Setup

A pixel diff is only meaningful when both images show the same thing at the same scale.

## Match these

| Factor | Design side | Build side |
|--------|-------------|------------|
| Size | Frame at the target viewport width (e.g. 390 x full height) | Same viewport width |
| Scale | Export at 1x (or 2x) | Device pixel ratio 1 (or 2) to match |
| Content | Same data as the build's test account | Seed data matching the design (names, counts, dates) |
| State | The frame for that state | Same state (hover via DevTools force state, error triggered) |
| Fonts | Fonts as in the design | Web fonts loaded before capture |
| Motion | Static frame | Animations and transitions disabled; carets hidden |
| Scrollbars | None | Hidden, or overlay scrollbars |
| Dynamic content | Fixed | Freeze clocks, random content, avatars, ads |

## Figma export

- Select the frame -> Export -> PNG at 1x (or the scale matching DPR), "Include bounding box" off.
- Use the same frame size as the viewport; export full height for full-page comparisons.
- Hide annotations and redline layers before export.

## Browser capture (manual)

- Chrome DevTools: device toolbar at the exact width, DPR set in device settings, then Command Menu
  -> "Capture full size screenshot" (or "Capture node screenshot" for a component).
- Force element state (:hover, :focus-visible) in the Styles panel before capturing.

## Playwright capture (repeatable)

```js
// capture.mjs  (npm i -D playwright)
import { chromium } from "playwright";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, reducedMotion: "reduce" });
await page.goto("http://localhost:3000/orders?seed=qa");
await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}" });
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: "build-orders-390.png", fullPage: true });
await browser.close();
```

## Comparing a component, not a page

Crop both images to the component (Figma: export the component instance; browser: node screenshot) so unrelated page
differences don't drown the signal.

## Expected differences

- Font rendering (hinting, anti-aliasing) differs between Figma, macOS, Windows and Linux: raise `--tolerance` to about
  24-40 for text-heavy comparisons, and judge text by measurement, not pixels.
- Sub-pixel layout rounding can shift edges by 1px: use `--min-region` to ignore thin slivers, then measure in DevTools.
