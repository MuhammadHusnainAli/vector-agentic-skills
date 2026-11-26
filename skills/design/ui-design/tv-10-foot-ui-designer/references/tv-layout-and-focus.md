# TV Layout and Focus

## Screen structures

| Screen | Structure | Notes |
|--------|-----------|-------|
| Home | Side navigation (collapsed to icons, expands on focus) or top tabs + hero + rows (shelves) | Few top destinations: Home, Search, Library, Settings |
| Browse | Rows of posters by category; one row focused at a time | Row titles; 5-7 items visible per row |
| Details | Backdrop, title, metadata, primary action (Play/Resume) focused on load | Secondary actions in a row; episodes below |
| Search | Voice first; on-screen keyboard with suggestions after 1-2 characters; recent searches | Results update as you type |
| Player | Full-screen; controls appear on any press, hide after a few seconds | Scrubbing with thumbnails; skip intro/recap; captions and audio quickly reachable |
| Settings | Simple list with values shown inline | Avoid deep trees |

## Focus design

| Element | Specification |
|---------|---------------|
| Focus indicator | Scale (1.05-1.15x) plus at least one strong cue: thick outline, glow, lift/shadow, colour inversion. Not colour change alone |
| Contrast | Focus indicator at least 3:1 against both the item and the background |
| Motion | Short ease-out (about 150-250 ms); parallax on tvOS posters is system-provided |
| Text on focus | Title and metadata may appear on focus; keep the item size stable so rows don't jump |
| Initial focus | Every screen defines it: the primary action (Play) or the first item of the first row |
| Focus memory | Each row and each screen remembers its last focused item; returning restores it |

## D-pad movement rules

- Spatial: pressing a direction moves to the nearest focusable item in that direction, aligned with the current item.
- Within a row: left/right moves along the row; at the end either stop (with a subtle bounce) or wrap. Pick one, be
  consistent; stopping is clearer for long rows.
- Between rows: up/down moves to the item in the next row closest to the current horizontal position, or to the row's
  remembered item.
- Never skip a row or land on something off-screen without scrolling it into view.
- No traps: every focusable item can be left in at least two directions, and Back always works.
- Long press or fast scrolling for long rows; "back to start of row" by pressing Back once is a common pattern.

## Press budgets

Count presses for the top tasks (from launching the app):

| Task | Path | Presses |
|------|------|---------|
| Resume what I was watching | Launch -> Continue Watching row focused -> OK | 1 |
| Play a show from search | Search (1) -> voice / type 3 letters with suggestions (~6) -> result (1) -> Play (1) | ~9 |
| Turn on captions during playback | Press (1) -> Captions control (2) -> choose language (2) | ~5 |

Aim: the most common task in 1-2 presses; anything regular under about 8-10. If a task exceeds that, move it up
(dedicated row, shortcut, remembered settings).

## Back and Home

- Back goes back one level, closes overlays, hides player controls, then stops playback, then returns to the previous
  screen.
- On the top-level screen, Back typically exits or goes to the platform home (platform rules differ: Android TV expects
  Back from the app's home to exit; tvOS Menu/Back goes to the system). Don't add "Are you sure you want to exit?" unless
  playback would be lost.
- Home is owned by the platform; never intercept it.

## Text input alternatives

| Need | Alternative |
|------|-------------|
| Sign in | Show a QR code and short code: user signs in on their phone (OAuth device authorisation flow); or platform account sign-in |
| Search | Voice search; suggestions after one or two letters; recent and trending searches |
| Payments | Platform purchase or phone handoff |
| Profiles | Pick from avatars, no typing |

## Accessibility

- Screen readers: tvOS VoiceOver, Android TV TalkBack; every focusable item has a label; announce row title on entering a row.
- Captions with size and background options; audio description tracks surfaced.
- High contrast / bold text settings respected; reduce motion stops autoplay previews and parallax.
- Don't autoplay trailers with sound on focus; if previews autoplay, mute and allow turning it off.
