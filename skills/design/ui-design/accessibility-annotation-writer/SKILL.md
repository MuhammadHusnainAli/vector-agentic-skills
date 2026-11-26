---
name: accessibility-annotation-writer
description: "Annotate designs with the accessibility decisions engineers can't see in a mockup: heading levels and page structure, landmarks, reading and focus order, accessible names for icon buttons and ambiguous links, roles and states for custom components, alt text decisions (informative, decorative, functional, complex), form labels, instructions, required fields and error associations, live-region announcements, keyboard interactions and shortcuts, focus management on open, close, delete and route change, target sizes, motion and reduced-motion notes, colour independence, tables, language changes, and gesture alternatives. Maps each annotation to the WCAG 2.2 criterion it satisfies and uses a consistent numbered notation with a legend. Reviews annotations for unnamed icon buttons, broken heading outlines, wrong focus order, missing announcements and focus plans, and missing alt decisions. Use when preparing designs for handoff, building an annotation kit, or reviewing a design for accessibility before build."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Accessibility Annotation Writer

Most accessibility bugs are decided in design and lost in handoff. Which text is the h1? What does a screen reader say
for the icon-only trash button? Where does focus go when the dialog closes? What's announced when the filter updates 40
results? Engineers can't infer any of that from pixels, so they guess, and the guesses become bugs. Annotations record
these decisions on the design. This skill writes them, tied to WCAG criteria, and reviews annotation sets for gaps.

## Trigger Conditions

Activate this skill when the user:
- Prepares designs for handoff and wants accessibility covered
- Asks what headings, labels, alt text, focus order or announcements a screen needs
- Builds an accessibility annotation kit or process for a team
- Reviews a design for accessibility before build

Component-level keyboard and ARIA: [ui-component-spec-writer](../ui-component-spec-writer/SKILL.md). Contrast: [dark-mode-palette-designer](../dark-mode-palette-designer/SKILL.md),
[button-state-variant-designer](../button-state-variant-designer/SKILL.md). Full handoff: [design-handoff-spec-generator](../design-handoff-spec-generator/SKILL.md).

## Workflow

```
1. STRUCTURE -> page title, landmarks, heading outline (one h1, no skipped levels) (references/annotation-categories.md)
2. ORDER     -> reading order and focus order; numbered markers on the design
3. NAMES     -> every interactive element: accessible name; icon buttons, repeated links ("Edit" -> "Edit address")
4. IMAGES    -> alt text decision per image (references/alt-text-decisions.md)
5. FORMS     -> labels, hints, required, errors and their association, autocomplete
6. DYNAMIC   -> announcements (live regions), focus management, loading and async updates (references/focus-and-announcements.md)
7. INPUT     -> keyboard interactions, shortcuts, gesture alternatives, target sizes
8. VISUAL    -> colour independence, contrast pairs, motion and reduced motion, zoom/reflow notes
9. REVIEW    -> checklist below; walk the flow with a screen reader mindset
```

## Notation

- Numbered markers by category colour (structure, focus order, names, images, forms, dynamic, keyboard).
- Focus order as a numbered sequence on interactive elements.
- Each note: what, then the WCAG criterion: "Icon button name: 'Delete invoice INV-1042' (4.1.2, 2.4.6)".
- A legend on every page; annotations beside the frame, not on top of it.

## Review Checklist

Report as `CODE [severity] frame/element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| AA001 | high | Icon-only or ambiguous controls with no accessible name defined (4.1.2) |
| AA002 | high | No focus plan for dialogs, menus, drawers: where focus goes on open and on close (2.4.3) |
| AA003 | high | Async changes (filter results, toasts, errors, loading) with no announcement defined (4.1.3) |
| AA004 | high | Form fields without labels, or errors not associated with fields (1.3.1, 3.3.1, 3.3.2) |
| AA005 | medium | Heading outline missing, more than one h1, or skipped levels (1.3.1, 2.4.6) |
| AA006 | medium | Focus order that doesn't follow the visual and logical order (2.4.3) |
| AA007 | medium | Images without an alt decision (informative / decorative / functional / complex) (1.1.1) |
| AA008 | medium | Information by colour alone (status, required, errors, chart series) (1.4.1) |
| AA009 | medium | Gestures (swipe, drag, pinch) without a single-pointer or button alternative (2.5.1, 2.5.7) |
| AA010 | medium | Repeated link or button text that's ambiguous out of context ("Edit", "Read more") (2.4.4) |
| AA011 | low | Landmarks not identified (header, nav, main, footer, complementary) |
| AA012 | low | No reduced-motion note for animated content (2.3.3, 2.2.2) |

## Output

Annotations per frame (marker, category, note, WCAG criterion), the heading outline, focus order list, announcement table,
and open questions. For reviews: findings and the missing annotations.

## Additional Resources

| File | Content |
|------|---------|
| [annotation-categories.md](references/annotation-categories.md) | Every category with what to specify, note templates and WCAG mapping |
| [alt-text-decisions.md](references/alt-text-decisions.md) | Decision tree for images, examples by image type, icons, charts, logos |
| [focus-and-announcements.md](references/focus-and-announcements.md) | Focus rules for dynamic UI, live region politeness, announcement wording, examples |
