# Interface Inventory Method

An interface inventory (Brad Frost's method) is a categorised collection of every distinct UI piece in a product,
captured from the live product rather than from design files.

## Steps

1. **Assemble the team.** Designers and engineers from each product; 2-3 hours per product for the first pass.
2. **Pick categories** (below) and assign each person a few.
3. **Capture.** Screenshot every distinct instance in the live product, including logged-in, error, empty and admin
   screens. One instance per visual difference; note the URL/screen.
4. **Collect on a board** (FigJam, Miro, slides): one frame per category, look-alikes side by side.
5. **Present** to the team and stakeholders. The wall of 14 button styles does the persuading.
6. **Record** each family in a spreadsheet using the capture template.

## Categories

| Group | Categories |
|-------|------------|
| Foundations | Colours in use, typography (sizes, weights, families), spacing, radii, shadows, icons, illustrations, imagery |
| Actions | Buttons, links, icon buttons, menus, toggles |
| Inputs | Text fields, selects, comboboxes, checkboxes, radios, switches, date pickers, file upload, sliders, search |
| Containers | Cards, panels, accordions, tabs, modals/dialogs, drawers, popovers, tooltips |
| Navigation | Headers, sidebars, tab bars, breadcrumbs, pagination, steppers |
| Feedback | Alerts, banners, toasts, inline messages, badges, progress, spinners, skeletons, empty states |
| Data | Tables, lists, charts, stat tiles, avatars, tags |
| Media | Image treatments, video players, carousels |

## Capture template

| Family | Variant / instance | Screen / URL | Code component (if known) | Repo | Visual differences | Defects seen | Notes |
|--------|--------------------|--------------|---------------------------|------|--------------------|--------------|-------|
| Button | Blue filled, 36px, radius 4 | /settings | `Btn` | web-app | Different blue, no focus ring | Focus invisible | |

## Foundations counts (quick, persuasive)

- Unique text colours, background colours, font sizes, border radii, box shadows in the CSS: browser tools or a CSS
  statistics tool give these in minutes. "214 unique colours, 38 font sizes" is a strong opening slide.
- Hard-coded colour hotspots from `inventory_scan.mjs` (IN004).

## Figma library audit

| Check | How |
|-------|-----|
| Components per library and their usage (insertions, detaches) | Figma library analytics (Organization/Enterprise plans) |
| Detached instances | High detach rate = component doesn't meet needs |
| Local (unpublished) components in product files | Search files for local components with the same names as library ones |
| Name parity with code | Compare the library component list with the code inventory (component-naming-convention-checker) |
| Variants in Figma but not in code, or the reverse | Mark as gaps in the inventory |
