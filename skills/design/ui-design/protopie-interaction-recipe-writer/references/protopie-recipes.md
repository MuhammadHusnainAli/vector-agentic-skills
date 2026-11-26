# ProtoPie Recipes

## Email field with validation
```
Layers:    Email input (Input layer), Error text (opacity 0), Continue button
Variables: none
I1 Trigger: Detect on "Email input" text
   Condition: text contains "@" and "."  -> Opacity "Error text" 0; Color "Continue button" = enabled colour
   Else:                                  -> Color "Continue button" = disabled colour
I2 Trigger: Tap "Continue button"
   Condition: `Email input`.text does not contain "@" -> Opacity "Error text" 1; Text "Error text" = "Enter an email address like name@example.com"
   Else: Jump to scene "Password"
```

## One-time code (6 digits, one real input)
```
Layers:    Hidden Input layer (numeric keyboard), 6 digit boxes (text layers), caret
Variables: code (text)
I1 Start -> Focus "Code input"
I2 Detect "Code input" text -> Assign code = `Code input`.text; set each box text with left/right formulas (box n shows the nth character)
I3 Detect code, Condition: length(code) = 6 -> Jump to "Verified" (or show error if code != "123456")
Why one input: paste and SMS autofill work; six separate inputs break both.
```

## Slider tied to a value
```
Layers:    Track, Thumb, Value label
Variables: value (number)
I1 Drag on "Thumb", axis X, limited to track bounds
I2 Chain/Detect on `Thumb`.x -> Assign value = round((`Thumb`.x - `Track`.x) / `Track`.width * 100)
   Text "Value label" = value
I3 Range on `Thumb`.x near steps -> Vibrate (light) for detents (optional)
```

## Drag and drop with snapping
```
Layers:    Card, Drop zone A, Drop zone B
I1 Drag on "Card" (free)
I2 Touch Up on "Card"
   Condition: Card centre inside Drop zone A -> Move Card to zone A position, 200 ms Ease Out
   Else if inside B -> Move to B
   Else -> Move back to origin (spring)
```

## Pull to refresh
```
Layers:    Scroll container "List", Spinner above content
I1 Range on `List`.scrollY < -64 (overscroll) -> Opacity Spinner 1; Rotate Spinner (loop)
I2 Touch Up when `List`.scrollY < -64 -> Assign refreshing = 1; after delay 1200 ms Text "Updated" + reset spinner
```

## Paging carousel with dots
```
Layers:    Paging container "Carousel" (horizontal), Dots
I1 Detect `Carousel` current page (or scrollX) -> Assign page = round(`Carousel`.scrollX / `Carousel`.width)
I2 Detect page -> Color dot[page] active, others inactive
```

## Cart counter across scenes
```
Variables: cartCount (number, all scenes, initial 0)
I1 Tap "Add to cart" -> Assign cartCount = cartCount + 1; Scale "Cart icon" 1.2 then 1 (bounce)
Badge text layer bound to cartCount; badge opacity condition cartCount > 0
```

## Countdown timer
```
Variables: seconds (number, 60)
I1 Start -> repeat every 1000 ms (Detect on a looping animation, or chained Delay) Assign seconds = seconds - 1
I2 Detect seconds, Condition seconds = 0 -> Jump "Time's up"
Text "Timer" = floor(seconds / 60) + ":" + (seconds mod 60 padded)
```

## Phone remote controlling a TV (ProtoPie Connect)
```
Phone pie: Tap "Right" -> Send message "move" with value "right" (to Connect)
TV pie:    Receive "move" -> Condition value = "right" -> Move focus ring to next tile; Assign focusIndex = focusIndex + 1
Run both pies through ProtoPie Connect on the same network; TV pie on the TV/computer, phone pie in ProtoPie Player.
```

## Tilt parallax (sensor)
```
I1 Tilt trigger (device) -> Chain "Background".x to tilt X with a small factor (e.g. x = tiltX * 4)
Provide a reduced-motion version (no parallax) for tests with sensitive participants.
```
