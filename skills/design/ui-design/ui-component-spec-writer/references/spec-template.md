# <Component> - component spec

Status: Draft | Pattern: <APG pattern> | Owner: <name> | Version: 0.1 | Figma: <link>

## Purpose
<One sentence: the job it does.>

## Usage
- Use when: <situation>
- Do not use when: <situation> -> use <other component>

## Anatomy
1. <part> (name matches the token and prop names)
2. ...

## API
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `variant` | 'primary' \| 'secondary' | `'primary'` | Visual emphasis |
| `size` | 'sm' \| 'md' \| 'lg' | `'md'` | |
| `onChange` | (value) => void | - | Fires on <keystroke / commit / blur> |

Impossible combinations: <e.g. `loading` with `disabled`>.

## Variant x state matrix
<variants x states = N cells.> Each cell: background / foreground / border token. Check contrast per cell: text 4.5:1
(3:1 for 18.66px bold / 24px), non-text and focus indicator 3:1 against adjacent colours.

| Variant | default | hover | focus-visible | pressed | disabled |
|---------|---------|-------|---------------|---------|----------|
| primary | | | | | |

## Sizes
| Size | Height | Padding | Type token | Target |
|------|--------|---------|------------|--------|
| md | | | | >= 24x24 CSS px (WCAG 2.5.8); 44pt iOS / 48dp Android |

## Keyboard interaction
| Key | Action |
|-----|--------|
| | |

Focus: on open -> <element>; on close -> <trigger>; after delete -> <next item>.

## Accessibility
| Attribute / rule | Requirement |
|------------------|-------------|
| Role | |
| Accessible name | <source: visible label / aria-label> |
| States | |
| Announcements | <live region text, politeness> |

## Content
| Slot | Max | Overflow | Notes |
|------|-----|----------|-------|
| label | <n> chars | wrap / truncate + full text available / clamp <n> lines | <tone, casing, examples> |

## Tokens
| Role | Token |
|------|-------|
| container.background | `color.action.primary.bg` |

## Motion
| Transition | Duration token | Easing token | Reduced motion |
|------------|----------------|--------------|----------------|

## Edge cases
- [ ] Longest real label and +40% translation
- [ ] 200% text, 320 CSS px reflow, text spacing overrides
- [ ] RTL, forced colors, reduced motion
- [ ] Empty, loading, error, async failure after optimistic update
- [ ] Keyboard only, screen reader, touch
- [ ] <pattern-specific cases from apg-patterns.md>

## Open questions
- <question> (owner, due)
