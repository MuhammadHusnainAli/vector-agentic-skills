# Navigation and Interaction (watchOS 10+)

## Structures

| Structure | Use | Notes |
|-----------|-----|-------|
| Single scrolling view | One task or one piece of information | Most watch apps should start here |
| Vertical page TabView | A few related views of the same thing (summary, details, controls) | Pages scroll vertically with the Digital Crown; replaced horizontal paging from earlier watchOS |
| NavigationStack (list -> detail) | Collections (messages, recipes, routes) | Keep to 2 levels |
| NavigationSplitView | Source list with detail; detail shown first with the list behind | For apps with a clear list of items and a main detail |

## Toolbars and buttons

- Toolbar placements: `topBarLeading`, `topBarTrailing` (small round buttons beside the time) and `bottomBar` (up to
  three buttons over the bottom of the content).
- Primary action: a prominent full-width button in the content, or the bottom bar's centre button.
- Destructive actions confirm with a short alert or need a deliberate gesture.

## Digital Crown

- Scrolling lists and pages.
- Adjusting values (volume, quantity, time) with haptic detents; show the value large while turning.
- Don't hijack it for unrelated actions.

## Double tap

On supported models (Series 9+, Ultra 2+), double tap (index finger and thumb) triggers the primary action of the current
view: answer, snooze, scroll widgets, start/stop. Designate one primary action per screen so it's predictable.

## Haptics

Use the system haptic types for their meaning (success, failure, retry, start, stop, click, notification). One haptic per
event; never constant. Haptics replace sound for confirmation on the wrist.

## Input

| Input | Use |
|-------|-----|
| Buttons and pickers | Default; offer choices instead of typing |
| Digital Crown pickers | Numbers, times, short lists |
| Suggested replies | Messages and responses |
| Dictation / Scribble / keyboard (larger models) | Only when free text is unavoidable |
| iPhone handoff | Long input, setup, settings |

## Notifications

- **Short look**: app icon, app name and a title, shown briefly when the wrist is raised. Make the title meaningful alone.
- **Long look**: appears if the user keeps looking. Custom interface with the key info and up to a few actions.
- Actions finish the job on the watch (Reply, Snooze, Mark done). Don't send people to the phone.
- Group and limit: every notification taps a wrist.

## Workouts and sessions

Long-running sessions (workouts, navigation, timers) need large live metrics, simple controls (pause, end, lock), water
lock for swimming, and always-on screens that keep the main metric readable.
