# Redesign Method

## 1. Inventory (keep what works)

| Keep | Change |
|------|--------|
| Content that's true and useful; the information architecture if tasks work | Visual system (type, colour, surfaces, motion) |
| Functionality, routes, components' behaviour | Copy that's generic, template proof |
| Brand assets the company actually owns (logo, name, brand colour if real) | Decorative effects |
| Accessibility that works | Layout patterns chosen by template |

List the page's jobs: what the visitor must understand, believe and do, in order.

## 2. Brief (one page)

- Product in one sentence, without adjectives.
- Audience: role, context, what they compare you with, what they distrust.
- The single most important message, and the action.
- Brand attributes as trade-offs ("precise over playful", "warm over corporate").
- Real proof available: customers, numbers, screenshots, certifications.

## 3. Art direction (pick one, write it as a sentence)

| Direction | Feels like | Type | Colour | Layout |
|-----------|-----------|------|--------|--------|
| Editorial | A good magazine | Serif display + humanist sans | Warm paper neutrals, one deep accent | Asymmetric grid, generous measure, rules |
| Swiss / utilitarian | Precise, trustworthy | Grotesk (one family, several weights) | Near-monochrome, one signal colour | Strict grid, left-aligned, dense information |
| Technical | Built by engineers for engineers | Mono for data + clean sans | Dark or light neutrals, syntax-like accents | Panels, tables, real code/data |
| Warm human | Friendly, approachable | Rounded or soft sans + friendly serif | Earthy or pastel palette with dark text | Photography of real people, looser rhythm |
| Bold brand | Confident, memorable | Distinctive display face, large scale | A saturated brand colour used decisively | Big type, colour blocks, few elements |

Example sentence: "Editorial and precise: a finance publication, not a startup landing page." Collect 5-10 references from
real, well-designed products and print (not other AI-generated sites).

## 4. System

**Type**
- Pair a display face with a text face (or one family with strong weight contrast). Examples: Fraunces + IBM Plex Sans;
  Söhne/Inter Tight-like grotesk alone with weight contrast; GT/Lyon-style serif + neutral sans; JetBrains Mono for data.
- Scale with clear steps (e.g. 14/16/20/28/40/56), tight leading for display (1.05-1.15), 1.5-1.6 for body, measure
  60-75ch.
- Tracking: slightly negative for large display sizes, default for body, positive for small caps/labels.

**Colour**
- Neutrals first: a tinted paper and ink (not pure #fff and #000), 3-5 grey steps for text and rules.
- One accent for actions and emphasis, derived from the brand; a second colour only if it has a job.
- Check every pair with `dark-mode-palette-designer/scripts/contrast_matrix.mjs`.

**Spacing, radius, elevation, motion**
- Spacing scale (4/8 base) and grouping by proximity (`ui-spacing-scale-consistency-checker`).
- Radius: 2-6 px for controls in precise directions, larger only with a reason; consistent.
- Elevation: mostly flat; borders and tone separate surfaces; shadows for overlays only.
- Motion: feedback and transitions, 150-250 ms, reduced-motion support.

## 5. Layout moves

- Lead with the one message and a real product view (screenshot, short video, live demo) instead of decoration.
- Give space by importance: the key feature gets a full-width section; minor ones share a list.
- Vary section rhythm: wide, narrow, split, list, quote. Not five identical centred blocks.
- Left-align reading text; centre only short, symmetric moments.
- Use a 12-column grid with asymmetric splits (7/5, 8/4) instead of thirds everywhere.
- Replace icon cards with definition lists, annotated screenshots or comparison tables.

## 6. Worked before/after

Before (scores 100/100): purple gradient hero, gradient headline "🚀 Unlock the Power of AI ✨", glow blob, three glass
cards with emoji icons, "Trusted by 10,000+ teams · 99.9% uptime", "John Doe, CEO at Acme ★★★★★", Inter only.

After (scores 0/100; all text pairs pass WCAG AA and APCA):
- Direction: editorial and precise; Fraunces display + IBM Plex Sans; paper `#faf8f3`, ink `#1c1b18`, accent `#1f5f4a`.
- Hero: audience line ("For finance teams of 5 to 50"), headline with the outcome ("Close the month in three days, with
  every number traced to its source"), one-sentence explanation with a number, one primary action ("Book a 20-minute
  demo") and one secondary link.
- Product screenshot of the exceptions queue with a caption, instead of a blob.
- Features as a two-column definition list with specifics (banks supported, audit trail).
- One named customer quote with a specific result and the customer's role and team size.

In the vector-agentic-skills source repository, `tests/fixtures/ui/slop/after/Landing.tsx` is this redesign in code.

## 7. Verify

- `slop_scan.mjs` after: under 15.
- Contrast matrix for every text/surface pair; focus states visible.
- Screens at 375, 768 and 1440 px; long content; empty and error states.
- Five-second test: can someone say what it is and for whom?
- Side-by-side with the "before" for the team, with the brief, so the change is judged against goals, not taste.
