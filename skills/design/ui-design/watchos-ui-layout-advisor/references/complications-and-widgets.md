# Complications and Smart Stack Widgets

Complications and widgets are built with WidgetKit using accessory families. They're often the most-used part of a watch
app: people see them every time they check the time.

## Families

| Family | Shape | Content | Good for |
|--------|-------|---------|----------|
| accessoryCircular | Small circle | Icon, short value, gauge or progress ring | A single value with progress (steps, battery, AQI) |
| accessoryRectangular | Wide rectangle | Up to about three lines of text, or a small chart | Next event, delivery status, short forecast |
| accessoryInline | Single line of text (near the time) | Short text + optional small symbol | One short fact ("Gate B12", "Rain at 3 PM") |
| accessoryCorner | Corner of certain faces | Small icon/value with curved text or gauge | Compact value with a label |
| Smart Stack widget (rectangular) | Card in the stack | Rich, timely info | Context-dependent info that rises when relevant |

Face colouring: on many faces the system tints complications to match the face (vibrant or accented rendering modes). Use
template images and design for monochrome tinting; don't rely on brand colours.

## Content rules

- One idea per complication. The value first, the unit or label second.
- Abbreviate deliberately and consistently ("Tmrw", "12m"); test the longest values (prices, names) at the largest
  Dynamic Type size.
- Gauges: show min/max context; a ring without meaning is decoration.
- Show freshness when data can be stale ("5m ago"), or design so stale data is obviously old.
- Placeholder (redacted) state while data loads; privacy redaction when the watch is locked.

## Updates and relevance

- Timelines: provide future entries (calendar events, forecasts) so the system can show correct data without waking the
  app.
- Update budgets are limited; use push or background refresh for important changes, not constant polling.
- Smart Stack relevance: declare when the widget matters (time window, location, ongoing activity) so it surfaces at the
  right moment.
- Tapping a complication opens the app straight to the related view (deep link), not the home screen.

## Review checklist for complications

- [ ] Each family looks right in full colour and tinted rendering
- [ ] Longest real value fits at large text sizes
- [ ] Freshness visible or implied
- [ ] Redacted and locked states defined
- [ ] Tap opens the matching detail
- [ ] Timeline entries keep it correct without the app running
