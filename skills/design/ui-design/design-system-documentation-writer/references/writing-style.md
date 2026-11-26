# Writing Style for Design System Docs

## Voice

- Direct and instructional: "Use", "Don't use", "Place", "Limit".
- Specific: numbers, names of alternatives, conditions.
- Neutral: no "beautiful", "powerful", "seamless", "delightful". Readers want rules, not a pitch.
- Second person for readers ("you"), present tense.

## Sentence rules

| Weak | Strong |
|------|--------|
| Buttons should be used appropriately. | Use one primary button per view. |
| Use tooltips sparingly. | Use a tooltip only to name an icon-only button. Put anything longer in helper text. |
| The modal can be used for many purposes. | Use a dialog when the user must respond before continuing. |
| It is recommended that labels are kept short. | Keep labels under 3 words. |
| Consider accessibility. | Give icon-only buttons an aria-label that names the action. |

## Do and don't

- Same scenario on both sides, one difference: what changed is the lesson.
- Caption each with the reason: "Don't: the error doesn't say how to fix it."
- Use real product content and context.
- Use colour plus a label (green check "Do", red cross "Don't"), not colour alone.

## Accessibility sections

Cover, in this order:
1. Keyboard: keys and what they do; focus order; where focus goes on open/close
2. Screen readers: what is announced (name, role, state, changes)
3. Visual: contrast, focus indicator, non-colour cues, target size
4. Motion: what animates and the reduced-motion behaviour
5. What the component handles vs what the product team must still do (e.g. "You must provide a label")

## Code examples

- Smallest working example first, then variations.
- Real imports from the package (`import { Switch } from "@acme/ui"`).
- Show accessible usage by default (labels, aria where needed); never an inaccessible example without marking it as a don't.
- Examples are tested or generated from stories so they don't go stale.

## Content guidelines in component docs

For each text slot: purpose, length limit, casing, punctuation, tone, examples (good and bad), and localisation notes
(expansion, plurals, dates and numbers).
