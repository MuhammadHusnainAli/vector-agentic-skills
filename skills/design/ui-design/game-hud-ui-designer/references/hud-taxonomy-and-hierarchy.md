# HUD Taxonomy and Hierarchy

## Taxonomy (Fagerholt and Lorentzon, 2009)

| Type | In the game world? | In the game's fiction? | Example |
|------|--------------------|-------------------------|---------|
| Diegetic | Yes | Yes | Health shown on the character's suit, ammo on the gun |
| Non-diegetic | No | No | Classic health bar and minimap overlay |
| Spatial | Yes (placed in 3D) | No | Waypoint markers, outlines through walls |
| Meta | No | Yes | Blood splatter on screen for damage, cracked visor |

Diegetic and meta UI increase immersion but can be harder to read quickly; competitive games favour clear non-diegetic
HUDs. Mix deliberately: critical information must stay readable in the busiest moment.

## Hierarchy

| Level | Examples | Display rule |
|-------|----------|--------------|
| Critical | Health when low, incoming damage direction, current objective when stuck, timer in timed modes | Always readable; multimodal (visual + audio + haptic) |
| Situational | Ammo, ability cooldowns, interaction prompts, nearby loot | Shown when relevant; fade when not |
| Ambient | Score, currency, minimap details, achievements | Minimal, peripheral, or on demand (button hold) |

Rule of thumb: if the player doesn't act on it within the next few seconds, it doesn't need to be on screen now.

## Contextual display

- Fade out stable values (full health, full ammo) after a few seconds; bring them back on change.
- Show prompts near the object (spatial) and in a consistent screen position for the button glyph.
- "Hold to show HUD" for ambient information in immersive games.
- Combat vs exploration HUD modes.

## Indicators

| Need | Pattern |
|------|---------|
| Damage direction | Arc segments around the centre or screen-edge wedges; intensity by damage |
| Off-screen objectives | Edge-clamped markers with distance; arrows at the screen edge |
| Threat awareness | Audio cues plus visual radar/compass pings |
| Low health | Vignette and heartbeat sound, plus the health bar itself (meta + non-diegetic) |
| Cooldowns | Radial fill + number for the last few seconds |

## Genre patterns

| Genre | Typical HUD |
|-------|-------------|
| Shooter | Reticle centre; health bottom-left; ammo bottom-right; minimap or compass top; kill feed top-right |
| Action RPG | Health/stamina bars top-left; abilities bottom-centre or bottom-right; quest tracker right |
| Racing | Speed, gear, position, lap times at the edges; minimap; minimal centre |
| Strategy | Dense panels at screen edges; resource bar top; minimap corner |
| Platformer / narrative | Minimal or diegetic; appears only when needed |
