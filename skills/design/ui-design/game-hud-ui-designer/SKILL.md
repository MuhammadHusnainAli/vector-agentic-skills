---
name: game-hud-ui-designer
description: "Design game HUDs and in-game UI that support play instead of covering it: the diegetic, non-diegetic, spatial and meta taxonomy, information hierarchy by what the player needs at each moment (critical, situational, ambient), placement in screen corners and the periphery, safe areas for TVs and consoles, scaling across resolutions and aspect ratios (16:9, 21:9 ultrawide, 16:10 handhelds like Steam Deck), text size from viewing distance, legibility over busy scenes (outlines, backing plates), contextual and fading elements, input prompts that match the active controller, damage and direction indicators, subtitles, colour-blind support, HUD customisation (scale, opacity, toggles, presets), photosensitivity and motion options, and platform requirements. Reviews HUDs for clutter, colour-only cues, small text, unsafe-area elements, stretched ultrawide layouts and missing accessibility options. Use when designing, reviewing or porting a game HUD, menus or in-game UI."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Game HUD UI Designer

A HUD is information the player needs without looking away from the action. Each element competes with the game for
attention and screen space, and the best HUDs show the least: health only when it matters, ammo when reloading is close,
the objective when the player hesitates. They're also readable on a 50-inch TV across the room, on a 7-inch handheld and
on a 34-inch ultrawide. This skill designs the hierarchy, placement and scaling of a HUD, plus the accessibility options
players now expect, and reviews existing HUDs.

## Trigger Conditions

Activate this skill when the user:
- Designs a HUD, in-game overlay, menus or game UI system
- Ports a game to consoles, handhelds or ultrawide monitors
- Has players missing critical information, or complaining about clutter or small text
- Adds accessibility options (subtitles, colour-blind modes, HUD scaling)

TV distance sizing: [tv-10-foot-ui-designer](../tv-10-foot-ui-designer/SKILL.md). Motion and flashing guidance: [ui-microinteraction-designer](../ui-microinteraction-designer/SKILL.md).

## Workflow

```
1. INFO      -> list everything the player could need; for each: when, how urgent, how often it changes
2. HIERARCHY -> critical / situational / ambient; diegetic options for each (references/hud-taxonomy-and-hierarchy.md)
3. PLACE     -> corners and edges by priority; keep the centre for the action and reticle
4. SAFE      -> safe areas, aspect ratios, anchoring and scaling (references/layout-safe-areas-scaling.md)
5. LEGIBLE   -> text sizes per platform; outlines or plates on busy scenes; icon + number pairs
6. DYNAMIC   -> what appears, fades or hides in context; transitions
7. ACCESS    -> subtitles, colour-blind support, scale, toggles, photosensitivity (references/game-ui-accessibility.md)
8. TEST      -> real hardware and distances, busiest scenes, colour-blind simulation, new players
9. REVIEW    -> checklist below
```

## Review Checklist

Report as `CODE [severity] element: problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| GH001 | high | Critical state (low health, incoming damage, objective) communicated only by colour or only visually |
| GH002 | high | Text or prompts too small for the target platform and distance (TV, handheld) |
| GH003 | high | HUD elements outside the safe area, or the safe area not adjustable on console |
| GH004 | high | Flashing or strobing effects with no option to reduce them; no motion-reduction options (screen shake, blur) |
| GH005 | medium | Clutter: many always-on elements that matter only occasionally |
| GH006 | medium | Elements covering the centre of action or the reticle area |
| GH007 | medium | Text unreadable over bright or busy backgrounds (no outline, shadow or backing) |
| GH008 | medium | Ultrawide: elements stretched to the far edges, or the HUD scaled incorrectly at other aspect ratios |
| GH009 | medium | Input prompts not matching the active device (keyboard glyphs while using a controller) |
| GH010 | medium | No subtitle options (size, background, speaker names) or subtitles that are too long per line |
| GH011 | low | No HUD scale, opacity or element toggles |
| GH012 | low | Inconsistent icon language across HUD, menus and tutorials |

## Output

1. Information inventory with hierarchy and display rule (always, contextual, on demand)
2. HUD layout per aspect ratio with anchoring and safe areas
3. Typography and icon specs per platform
4. Accessibility options list
5. Review findings, if reviewing

## Additional Resources

| File | Content |
|------|---------|
| [hud-taxonomy-and-hierarchy.md](references/hud-taxonomy-and-hierarchy.md) | Diegetic/non-diegetic/spatial/meta, hierarchy, contextual display, indicators, genre patterns |
| [layout-safe-areas-scaling.md](references/layout-safe-areas-scaling.md) | Placement zones, safe areas, aspect ratios, anchoring, resolution scaling, text sizes per platform |
| [game-ui-accessibility.md](references/game-ui-accessibility.md) | Subtitles, colour-blind support, scaling, remapping prompts, photosensitivity, motion, guidelines to follow |
