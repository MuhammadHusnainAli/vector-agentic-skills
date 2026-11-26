# Page Templates

## Component page

```markdown
# Switch
Status: Stable | Since: 2.0 | Figma: <link> | Code: <link> | Last updated: 2026-11-26

A switch turns a single setting on or off immediately.

<live example>

## When to use
- Settings that take effect immediately (Notifications on/off)

## When not to use
- The change needs a Save button -> use a Checkbox
- Choosing between two options with different names -> use a Radio group or Segmented control
- Triggering an action -> use a Button

## Anatomy
1. Track  2. Thumb  3. Label  4. Optional state text

## Variants
| Variant | Use for |
|---------|---------|
| Default | Most settings |
| With description | Settings that need a sentence of context |

## Behaviour
- Takes effect on toggle; if saving fails, the switch reverts and an inline error explains why.
- Loading: show a spinner in the thumb for operations over 1 second.

## Content
- Label describes the setting, not the state: "Email notifications", not "Turn on email notifications".
- Don't add "On/Off" text when the label and visual state are clear; if you do, keep it outside the label.

## Accessibility
- Keyboard: Tab to focus, Space toggles.
- Screen readers announce: "Email notifications, switch, on".
- The label is part of the click target.
- State is shown by thumb position and track colour, plus an icon in the thumb (not colour alone).

## Do and don't
| Do | Don't |
|----|-------|
| <img> "Email notifications" switch that saves immediately | <img> Switch inside a form with a Save button |

## Props
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `checked` | boolean | - | Controlled state |
| `defaultChecked` | boolean | `false` | Uncontrolled initial state |
| `onCheckedChange` | (checked: boolean) => void | - | Fires on toggle |
| `disabled` | boolean | `false` | |

## Related
Checkbox, Radio group, Segmented control

## Changelog
- 2.3.0: Added `description` slot
- 2.0.0: Renamed `onChange` to `onCheckedChange`
```

## Foundation page (colour, type, spacing, elevation, motion, icons)

1. **Principle**: one paragraph on what this foundation is for in this brand
2. **Scale or palette**: the tokens, shown visually with names and values
3. **Semantic usage**: which tokens to use for what (text, surfaces, borders, feedback)
4. **Rules**: contrast pairs, minimum sizes, combinations that are not allowed
5. **Accessibility**: contrast, minimum sizes, reduced motion, colour-blind safe use
6. **Do and don't**
7. **Tokens reference**: full table with code names and Figma variable names
8. **Changelog**

## Pattern page (forms, empty states, errors, onboarding, search)

1. **Problem**: the user situation this solves
2. **Solution summary**: the recommended approach in two sentences
3. **Examples**: annotated screens from real products
4. **Building blocks**: components used and how they're configured
5. **Variations**: when the situation differs (mobile, first use, power users)
6. **Content**: wording patterns with examples
7. **Accessibility**: focus management, announcements across the whole flow
8. **Research and evidence**: what was tested, results
9. **Related patterns**
