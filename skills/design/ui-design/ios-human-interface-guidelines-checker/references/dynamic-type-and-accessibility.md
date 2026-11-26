# Dynamic Type and Accessibility

## Text styles (iOS, default "Large" content size)

| Style | Size (pt) | Weight | Typical use |
|-------|-----------|--------|-------------|
| Large Title | 34 | Regular | Root screen titles |
| Title 1 | 28 | Regular | Page titles |
| Title 2 | 22 | Regular | Section titles |
| Title 3 | 20 | Regular | Subsection titles |
| Headline | 17 | Semibold | Emphasised body, row titles |
| Body | 17 | Regular | Main text |
| Callout | 16 | Regular | Secondary explanatory text |
| Subheadline | 15 | Regular | Row subtitles |
| Footnote | 13 | Regular | Fine print, timestamps |
| Caption 1 | 12 | Regular | Captions |
| Caption 2 | 11 | Regular | Smallest captions |

- Users choose from seven standard sizes (xSmall to xxxLarge) plus five larger accessibility sizes (AX1-AX5). At AX5 Body
  is roughly three times its default size.
- Minimum text size Apple recommends: 11pt.
- Design at Large, then test at xxxLarge and AX5.

## Layout at large sizes

| Problem | Fix |
|---------|-----|
| Horizontal rows overflow | Stack label and value vertically at accessibility sizes |
| Text truncates in fixed-height cells | Self-sizing rows; no fixed heights |
| Icons stay tiny next to huge text | Scale SF Symbols with text (they do by default as text-relative) |
| Tab bar labels too long | Short labels; the system shows a large content viewer on long press |
| Buttons in a row overflow | Wrap or stack buttons vertically |

## Custom fonts

Brand typefaces must still scale: map each style to the custom font and scale it with the text style (UIFontMetrics in
UIKit, `.custom(_:size:relativeTo:)` in SwiftUI). A brand font that doesn't scale is an accessibility failure.

## VoiceOver

- Every interactive element has a concise label that names its purpose ("Delete", not "trash icon button").
- Traits: button, header, selected, link, adjustable, image. Headers let users jump between sections.
- Values for controls (toggle on/off, slider value); hints only when the action isn't obvious.
- Group related elements (a row with title, subtitle and value) into one element; hide decorative images.
- Custom actions (rotor actions) replace hidden swipe gestures.
- Focus order follows reading order; after a modal closes, focus returns to the element that opened it.

## Display and motion settings

| Setting | Design response |
|---------|-----------------|
| Dark mode | Semantic colours; check every screen in both appearances |
| Increase Contrast | Semantic colours adapt; custom colours need high-contrast variants |
| Reduce Transparency | Materials become more opaque; text on blur must still be legible |
| Reduce Motion | Replace slides, zooms and parallax with fades; no auto-playing motion |
| Bold Text | Layouts handle wider glyphs |
| Button Shapes | Text buttons gain underlines/shapes; don't rely on colour alone |
| Smart Invert | Mark images and video so they don't invert |

## Contrast

Apple recommends at least 4.5:1 for text (3:1 for large or bold text), in line with WCAG. Check light, dark and Increase
Contrast appearances, and text over materials and images.
