# Edge-Case Catalogue

Walk each row with the component in front of you. Use real worst-case content, not lorem ipsum.

## Content
| Case | What to specify |
|------|-----------------|
| Longest realistic label | Wrap, truncate with full text available (tooltip or title is not enough on touch), or hard limit |
| Translation growth | German/Finnish run 30-40% longer than English for short UI strings; short labels can double |
| No content | Missing title, image, avatar, count: fallback or collapse |
| Numbers | 0, 1, 1,000,000, negative, localized separators; plural rules |
| User-generated text | Emoji, unbroken URLs and long words (`overflow-wrap: anywhere`), mixed scripts |
| Names | Single-word names, very long names, non-Latin names |

## Layout
| Case | What to specify |
|------|-----------------|
| 320 CSS px wide | Reflow without horizontal scrolling (WCAG 1.4.10) |
| 200% text size | No clipped text, no overlaps (WCAG 1.4.4); fixed heights break here |
| Text spacing | Line height 1.5, paragraph spacing 2x, letter 0.12em, word 0.16em still fit (WCAG 1.4.12) |
| RTL | Mirror layout and directional icons (back arrows), not logos or media controls |
| Container sizes | Behaviour in narrow sidebar vs full width (container queries) |

## State
| Case | What to specify |
|------|-----------------|
| Loading | Skeleton vs spinner; keep dimensions to avoid layout shift |
| Error | Inline message, recovery action, what is preserved |
| Async failure after optimistic UI | Revert plus message (switch toggled but save failed) |
| Rapid repeat input | Double submit, double click, key repeat |
| Stale data | Timestamp or refresh affordance |
| Permissions | Hidden vs disabled-with-reason vs read-only |

## Input and platform
| Case | What to specify |
|------|-----------------|
| Keyboard only | Every action reachable; visible focus; no traps |
| Touch | No hover-dependent information; target sizes |
| Screen reader | Name, role, state and changes announced |
| Forced colors (Windows high contrast) | States shown with borders/outlines, not background colour only |
| Reduced motion | Non-animated alternative for every transition |
| Pointer cancellation | Action fires on up-event, can be aborted by moving away (WCAG 2.5.2) |
| Dragging | Single-pointer alternative (WCAG 2.5.7) |
