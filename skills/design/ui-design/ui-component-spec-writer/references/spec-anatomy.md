# Spec Anatomy

Each section answers a question that otherwise comes back as a Slack thread during the build.

| Section | Question it answers | Weak version | Strong version |
|---------|---------------------|--------------|----------------|
| Purpose | What job does it do? | "A flexible button component" | "Triggers an action in the current view. Navigation uses Link." |
| Usage | When is it the wrong choice? | Omitted | "Do not use for page navigation (Link), for more than 2 actions in a row (Menu), for on/off settings (Switch)." |
| Anatomy | What are the named parts? | A screenshot | Numbered parts matching the token and prop names |
| API | What can engineers configure? | List of Figma properties | Props with type, default, description; impossible combinations ruled out |
| Matrix | What does every state look like? | Default + hover | Every variant x state with token references; disabled and focus included |
| Sizes | How big, and is it tappable? | Pixel height | Height, padding, type token, target size vs 24px / 44pt / 48dp |
| Keyboard | How does it work without a mouse? | "Accessible" | Key -> action table; where focus goes on open, close, delete |
| Accessibility | What do assistive technologies get? | "Add aria labels" | Role, name source, states, relationships, live announcements |
| Content | What text fits? | Lorem ipsum | Max characters per slot, overflow rule, tone, examples of good and bad labels |
| Tokens | Which values, by name? | Hex codes | Semantic token per role; no raw values |
| Motion | How does it change? | "Smooth" | Duration and easing tokens, reduced-motion alternative |
| Edge cases | What breaks it? | Omitted | Checklist walked with real worst-case content |

## Focus management (often forgotten)

Say where focus goes for every transition:
- Open (dialog, menu, popover): first focusable element, or the least destructive action in a confirmation
- Close: back to the element that opened it; if that element is gone (deleted row), to the next logical item, never `<body>`
- Delete in a list: next item, or previous when the last item was deleted, or the list's empty-state action
- Route change in an SPA: the new page's `h1` or main region

## Worked example: "dropdown" is three different components

| What the design shows | APG pattern | Why it matters |
|-----------------------|-------------|----------------|
| A list of actions (Edit, Duplicate, Delete) | Menu button | Arrow keys, type-ahead, `role=menu`; items are actions |
| Choose one value for a form field | Listbox (or native `<select>`) | Selection semantics, form value |
| Type to filter and choose a value | Combobox | DOM focus stays in the input; `aria-activedescendant` |

Using one "Dropdown" component for all three means at least two of them get the wrong keyboard model.

## Sign-off checklist

- [ ] Engineering: API reviewed, no impossible prop combinations, controlled and uncontrolled behaviour defined
- [ ] Accessibility: keyboard table complete, name/role/state for every part, focus return defined, contrast checked per cell
- [ ] Content design: limits per slot tested with the longest real string and with German/Finnish translations
- [ ] QA: every matrix cell and edge case is a test case
- [ ] Design system: tokens exist (no new raw values), naming follows the system's conventions
