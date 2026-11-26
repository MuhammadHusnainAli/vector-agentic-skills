# XAML Review Notes

| Pattern in XAML | Problem | Fix |
|-----------------|---------|-----|
| `Foreground="#333333"` / `Background="White"` | Breaks dark and contrast themes | `{ThemeResource TextFillColorPrimaryBrush}`, `{ThemeResource LayerFillColorDefaultBrush}` |
| `FontSize="15"` on TextBlock | Off the type ramp | `Style="{StaticResource BodyTextBlockStyle}"` |
| `<Button><FontIcon Glyph="&#xE74D;"/></Button>` with no name | Narrator says "button" | `AutomationProperties.Name="Delete"` and a ToolTip |
| `<Image Source="title.png"/>` containing text | Images of text don't scale or theme | Real text |
| `Background="{ThemeResource AcrylicBackgroundFillColorDefaultBrush}"` on the root Grid | Acrylic as the app background | Mica on the window (`SystemBackdrop = new MicaBackdrop()`), transparent root background |
| Root `Grid Background="..."` opaque | Hides Mica | Transparent background; use layer brushes for content areas |
| `CornerRadius="10"` | Off the radius scale | `{StaticResource ControlCornerRadius}` (4) or `{StaticResource OverlayCornerRadius}` (8) |
| `Width="1200"` on the root layout | Breaks snapped windows | Star sizing, VisualStateManager with AdaptiveTrigger |
| `IsTabStop="False"` on interactive controls | Unreachable by keyboard | Remove; fix the tab order with TabIndex only when needed |
| `UseSystemFocusVisuals="False"` with nothing else | No visible focus | Keep system focus visuals |
| Custom title bar `SetTitleBar(myGrid)` covering buttons | Buttons become drag areas, not clickable | Set a dedicated drag region; exclude interactive elements (passthrough regions) |
| Colour-only status (`Fill="Red"`) | Lost in contrast themes and for colour-blind users | Icon + text; `InfoBar` severity |
| No `<ResourceDictionary x:Key="HighContrast">` for custom brushes | Custom brushes ignore contrast themes | Add HighContrast theme dictionary mapping to `SystemColor*` resources |
| `KeyboardAccelerators` missing on frequent commands | Slow for keyboard users | `<KeyboardAccelerator Modifiers="Control" Key="S"/>` |
| ContentDialog with primary on the right | Not the Windows order | Primary first (left), Close last |

## Test pass

- Navigate the whole app with Tab, arrows, F6, Escape, Enter; check focus visuals.
- Switch Light, Dark, and a contrast theme (Settings > Accessibility > Contrast themes).
- Turn transparency effects off; check Mica/Acrylic fallbacks.
- Set text size to 200% (Settings > Accessibility > Text size).
- Snap the window to a third of the screen.
- Run Narrator over key flows; Accessibility Insights for Windows for automated checks.
