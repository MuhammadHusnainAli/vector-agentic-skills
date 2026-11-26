# Game UI Accessibility

Guidelines to follow: Game Accessibility Guidelines (gameaccessibilityguidelines.com), Xbox Accessibility Guidelines
(XAGs), and platform accessibility tags (Xbox, PlayStation) that tell players which features exist.

## Subtitles and captions

| Option | Spec |
|--------|------|
| On by default (or asked at first launch) | Many players use them |
| Size | Several sizes; the default comfortably readable at TV distance |
| Background | Adjustable opacity backing box |
| Speaker names | Name or colour + name |
| Line length | About 2 lines, under about 40 characters per line |
| Captions | Important sounds ([explosion], [footsteps behind]) with direction if relevant |
| Timing | Synced with speech; enough time to read |

## Colour

- Never rely on colour alone: pair with shape, icon, pattern, or position (enemy vs ally markers with different shapes).
- Colour-blind options: preset palettes or adjustable colours for key elements (enemy highlight, team colours,
  rarity), not just full-screen filters.
- Test with deuteranopia, protanopia and tritanopia simulations.

## HUD and text

- HUD scale, text scale, opacity, toggles per element, and position presets.
- High-contrast mode for HUD and menus.
- Menu narration / screen reader support for menus (platform text-to-speech).
- Hold vs toggle options for actions shown in prompts; remappable controls with prompts updating to match.

## Input prompts

- Show glyphs for the device in use and switch instantly when the player changes device.
- Show remapped bindings, not defaults.
- Avoid timed prompts with very short windows; offer options (longer windows, hold-to-confirm alternatives).

## Photosensitivity and motion

- Avoid flashes more than 3 times per second, large saturated red flashes, and high-contrast flickering patterns
  (WCAG 2.3.1 principles; broadcast guidelines such as Ofcom/ITU for TV are stricter references).
- Options to reduce or disable: screen shake, camera bob, motion blur, chromatic aberration, flashing effects.
- Field-of-view slider on PC and where possible on consoles (motion sickness).

## Cognitive load

- Objective reminders on demand; tutorials replayable; glossary for terms.
- Pause anywhere in single-player; difficulty and assist options without shaming labels.
