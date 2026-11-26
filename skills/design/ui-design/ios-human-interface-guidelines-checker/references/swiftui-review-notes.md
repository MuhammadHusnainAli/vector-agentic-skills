# SwiftUI Review Notes

Patterns that break the HIG, and the fixes. Useful when the design review includes code.

| Pattern in code | Problem | Fix |
|-----------------|---------|-----|
| `.font(.system(size: 15))` | Fixed size; ignores Dynamic Type | `.font(.subheadline)`, or `.font(.custom("Brand", size: 15, relativeTo: .subheadline))` |
| `Color(red: 0.1, green: 0.1, blue: 0.1)` / hex extensions for text and backgrounds | Breaks dark mode and Increase Contrast | `Color.primary`, `.secondary`, `Color(.systemBackground)`, or asset-catalog colours with dark and high-contrast variants |
| `Image("trash").onTapGesture { ... }` | Not a button: no button trait, no highlight, no keyboard/Switch Control | `Button(action:) { Image(systemName: "trash") }.accessibilityLabel("Delete")` |
| `.frame(width: 30, height: 30)` on a tappable control | Below 44pt | `.frame(minWidth: 44, minHeight: 44)` or `.contentShape(Rectangle())` with padding |
| `.navigationBarBackButtonHidden(true)` + custom back button | Loses edge-swipe back and the standard behaviour | Keep the system back button; customise the title only |
| `withAnimation(.spring) { ... }` everywhere | Ignores Reduce Motion | Read `@Environment(\.accessibilityReduceMotion)` and use a fade or no animation |
| `.background(.ultraThinMaterial)` with small text | Legibility under Reduce Transparency and over busy content | Check legibility; use vibrancy-aware foreground styles (`.foregroundStyle(.secondary)`) |
| `Text` with `.lineLimit(1)` on important labels | Truncates at large sizes | Allow wrapping; use `ViewThatFits` or switch to a vertical stack at accessibility sizes |
| `HStack` of label + value with fixed widths | Overflows at large sizes | `@Environment(\.dynamicTypeSize)`; `if dynamicTypeSize.isAccessibilitySize { VStack } else { HStack }` |
| Decorative images without `.accessibilityHidden(true)` | VoiceOver noise | Hide decorative images; label informative ones |
| Several `Text` views in a row read separately | Choppy VoiceOver | `.accessibilityElement(children: .combine)` on the row |
| Custom toggle built from shapes | Missing trait and value | Use `Toggle` with a custom `ToggleStyle` |
| `.alert` with 4+ buttons | Too many choices for an alert | `confirmationDialog` or a sheet |
| `.sheet` with editable content and no dismissal guard | Swipe-down loses edits | `.interactiveDismissDisabled(hasChanges)` plus a confirmation |
| Asking for permissions in `onAppear` of the first screen | Prompt without context | Request when the feature is first used |

Check also:
- Previews or snapshot tests at `.dynamicTypeSize(.accessibility5)` and in dark mode.
- `accessibilityAddTraits(.isHeader)` on section titles.
- `accessibilityAction` for actions hidden in swipe or long-press gestures.
