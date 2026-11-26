# Component Vocabulary

Pick one term per concept and list the others as search aliases. These are common choices, with definitions that keep
concepts apart.

| Preferred | Aliases | Definition | Not to be confused with |
|-----------|---------|------------|-------------------------|
| Dialog | Modal, popup, lightbox | A window over the page that needs a response or holds a focused task; modal blocks the page | Popover (non-modal, anchored) |
| Alert dialog | Confirm, confirmation modal | A dialog that interrupts to confirm or warn | Alert / banner |
| Popover | Popup, flyout, overlay | Non-modal content anchored to a trigger; may contain interactive content | Tooltip (text only) |
| Tooltip | Hint, title | Short text label/description on hover and focus; no interactive content | Popover |
| Toast | Snackbar, notification | Brief, non-blocking message about a completed process; may have one action | Banner (persistent, page-level) |
| Banner | Alert, notice, callout bar | Persistent page- or section-level message | Toast |
| Inline message | Alert, callout | Message inside the content flow tied to a section or field | Banner |
| Select | Dropdown, picker | Choose one value from a list (form value) | Menu (actions), Combobox (typing) |
| Combobox | Autocomplete, typeahead | Text input with a list of suggestions | Select |
| Menu | Dropdown menu, actions menu, overflow | List of actions opened from a button | Select, Navigation |
| Tabs | Tab bar (in-page), segmented tabs | Switch between views of the same context | Navigation bar, Segmented control |
| Segmented control | Toggle group, button group | Choose one of 2-5 options that changes a view or setting immediately | Tabs, Radio group |
| Switch | Toggle | On/off setting that applies immediately | Checkbox |
| Checkbox | Tick box | Select options, applied on submit | Switch |
| Tag | Chip, label, pill | Label for categorising; may be removable | Badge |
| Chip | Filter chip, input chip | Interactive compact element for filters, choices or entered values | Tag (static), Button |
| Badge | Counter, indicator, dot | Small status or count attached to another element | Tag |
| Text field | Input, text input | Single-line text entry | Text area |
| Text area | Multiline input | Multi-line text entry | |
| Drawer | Side sheet, panel, off-canvas | Panel sliding from an edge | Dialog |
| Sheet | Bottom sheet, action sheet | Panel from the bottom (mobile) | Drawer |
| Accordion | Collapse, expander group | Stacked headers that show/hide sections | Disclosure (single) |
| Disclosure | Expander, show more | One button that shows/hides one region | Accordion |
| Skeleton | Placeholder, shimmer | Loading placeholder in the shape of content | Spinner |
| Spinner | Loader, progress circle (indeterminate) | Indeterminate activity indicator | Progress bar |
| Empty state | Zero state, blank slate | Content shown when there is nothing to show | Error state |

Record the decision with a one-line reason ("Dialog, because it matches the HTML element and ARIA role").
