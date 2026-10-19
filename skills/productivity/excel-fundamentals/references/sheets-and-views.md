# Workbook Structure Reference

Complete guide to sheet management, protection, view options, freeze panes, and print settings in Excel.

## Sheet Operations

### Adding Sheets

| Method | Action |
|--------|--------|
| + button | Click + next to sheet tabs |
| Keyboard | Shift+F11 |
| Right-click | Right-click tab > Insert |
| Ribbon | Home > Insert > Insert Sheet |

### Deleting Sheets

1. Right-click sheet tab
2. Select Delete
3. Confirm if sheet contains data

Note: Cannot undo sheet deletion.

### Renaming Sheets

| Method | Action |
|--------|--------|
| Double-click | Double-click tab, type new name |
| Right-click | Right-click > Rename |
| Keyboard | Alt+H, O, R |

Sheet name rules:
- Max 31 characters
- Cannot contain: \ / ? * [ ]
- Cannot be blank
- Cannot start/end with apostrophe

### Moving Sheets

Within workbook:
- Drag tab to new position
- Hold Ctrl while dragging to copy

To another workbook:
1. Right-click tab > Move or Copy
2. Select destination workbook
3. Choose position
4. Check "Create a copy" if needed

### Copying Sheets

Within workbook:
- Ctrl+drag tab

To another workbook:
1. Right-click > Move or Copy
2. Select destination
3. Check "Create a copy"

### Sheet Tab Color

1. Right-click sheet tab
2. Tab Color
3. Choose color from palette

Use for:
- Grouping related sheets
- Status indication
- Visual organization

### Selecting Multiple Sheets

| Selection | Method |
|-----------|--------|
| Adjacent | Shift+click first and last |
| Non-adjacent | Ctrl+click each tab |
| All sheets | Right-click > Select All Sheets |

Grouped sheets:
- Changes apply to all selected
- [Group] appears in title bar
- Click single tab to ungroup

### Sheet Navigation

| Shortcut | Action |
|----------|--------|
| Ctrl+Page Down | Next sheet |
| Ctrl+Page Up | Previous sheet |
| Navigation arrows | Scroll sheet tabs |
| Right-click arrows | List all sheets |

## Hide and Unhide

### Hide Sheets

1. Right-click sheet tab
2. Hide
3. Sheet disappears from tabs

### Unhide Sheets

1. Right-click any tab
2. Unhide
3. Select sheet from list
4. Click OK

### Very Hidden Sheets (VBA)

Only visible through VBA:
```vba
Sheets("Sheet1").Visible = xlSheetVeryHidden
```

Cannot unhide via normal menu.

### Hide/Unhide Rows

Hide:
1. Select row numbers
2. Right-click > Hide
3. Or Ctrl+9

Unhide:
1. Select rows surrounding hidden
2. Right-click > Unhide
3. Or Ctrl+Shift+9

### Hide/Unhide Columns

Hide:
1. Select column letters
2. Right-click > Hide
3. Or Ctrl+0

Unhide:
1. Select columns surrounding hidden
2. Right-click > Unhide
3. Or Ctrl+Shift+0

## Protection

### Sheet Protection

Protect sheet from changes:
1. Review > Protect Sheet
2. Set optional password
3. Choose allowed actions

Allowed actions:
| Option | Allows Users To |
|--------|-----------------|
| Select locked cells | Select protected cells |
| Select unlocked cells | Select editable cells |
| Format cells | Change formatting |
| Format columns | Change column width |
| Format rows | Change row height |
| Insert columns | Add columns |
| Insert rows | Add rows |
| Insert hyperlinks | Add hyperlinks |
| Delete columns | Remove columns |
| Delete rows | Remove rows |
| Sort | Sort data |
| Use AutoFilter | Filter data |
| Use PivotTable | Modify pivot tables |
| Edit objects | Change shapes/charts |
| Edit scenarios | Modify scenarios |

### Unlock Specific Cells

Before protecting:
1. Select cells to remain editable
2. Format Cells > Protection tab
3. Uncheck "Locked"
4. Then protect sheet

### Workbook Protection

Protect workbook structure:
1. Review > Protect Workbook
2. Choose protection options:
   - Structure: Prevent sheet changes
   - Windows: Prevent window changes (deprecated)

### Password Guidelines

- Passwords are case-sensitive
- Use strong passwords
- Store passwords securely
- Cannot recover forgotten passwords

### Remove Protection

1. Review > Unprotect Sheet/Workbook
2. Enter password if set
3. Protection removed

### Protect Specific Ranges

Allow different users to edit ranges:
1. Review > Allow Users to Edit Ranges
2. Define ranges and permissions
3. Set passwords per range

## Freeze Panes

### Freeze Options

| Option | Effect |
|--------|--------|
| Freeze Panes | Freeze above and left of active cell |
| Freeze Top Row | Keep row 1 visible |
| Freeze First Column | Keep column A visible |

### Setting Freeze Panes

1. Select cell below and right of freeze point
2. View > Freeze Panes
3. Choose option

Examples:
| Active Cell | Freezes |
|-------------|---------|
| B2 | Row 1 and Column A |
| A3 | Rows 1-2 |
| C1 | Columns A-B |
| D5 | Rows 1-4 and Columns A-C |

### Unfreeze Panes

View > Freeze Panes > Unfreeze Panes

### Common Freeze Patterns

Header row only:
1. Select cell A2
2. Freeze Panes

Headers and row labels:
1. Select cell B2
2. Freeze Panes

Multiple header rows:
1. Select cell in row below last header
2. Freeze Panes

## Split View

### Creating Split

1. View > Split
2. Or drag split box on scrollbar
3. Divides window into panes

### Adjusting Split

- Drag split bar to resize
- Double-click to remove split
- View > Split to toggle off

### Split vs Freeze

| Feature | Split | Freeze |
|---------|-------|--------|
| Panes scroll | Independently | Top/left fixed |
| Multiple views | Same area | Different areas |
| Split bars | Visible, draggable | None |
| Use case | Compare within sheet | Keep headers visible |

## Window Options

### New Window

Open multiple views of same workbook:
1. View > New Window
2. Arrange windows as needed
3. Changes sync across windows

### Arrange Windows

| Option | Layout |
|--------|--------|
| Tiled | Equal-sized grid |
| Horizontal | Stacked horizontally |
| Vertical | Side by side |
| Cascade | Overlapping |

Windows of active workbook:
- Check "Windows of active workbook"
- Only arrange current file's windows

### View Side by Side

Compare two workbooks:
1. View > View Side by Side
2. Synchronous Scrolling (optional)
3. Reset Window Position

### Hide Window

View > Hide
- Hides window but keeps file open
- View > Unhide to restore

### Switch Windows

View > Switch Windows
- Lists all open workbooks
- Click to switch

## Page Layout

### Page Orientation

| Option | Best For |
|--------|----------|
| Portrait | Standard documents |
| Landscape | Wide data, many columns |

### Paper Size

Common sizes:
- Letter (8.5 x 11 in)
- Legal (8.5 x 14 in)
- A4 (210 x 297 mm)
- A3 (297 x 420 mm)

### Margins

| Preset | Top/Bottom | Left/Right |
|--------|------------|------------|
| Normal | 0.75" | 0.7" |
| Wide | 1" | 1" |
| Narrow | 0.75" | 0.25" |

Custom margins:
- Set exact values
- Center on page (horizontal/vertical)

### Print Area

Set specific range to print:
1. Select range
2. Page Layout > Print Area > Set Print Area

Clear print area:
- Page Layout > Print Area > Clear Print Area

Add to print area:
- Select additional range
- Add to Print Area

### Page Breaks

View page breaks:
- View > Page Break Preview
- Blue lines show breaks

Insert manual break:
1. Select cell
2. Page Layout > Breaks > Insert Page Break

Remove break:
- Page Layout > Breaks > Remove Page Break

Reset all:
- Page Layout > Breaks > Reset All Page Breaks

### Scale to Fit

| Option | Effect |
|--------|--------|
| Width | Fit to n pages wide |
| Height | Fit to n pages tall |
| Scale | Percentage of normal size |

Fit Sheet on One Page:
- Width: 1 page
- Height: 1 page

### Print Titles

Repeat rows/columns on every page:
1. Page Layout > Print Titles
2. Rows to repeat at top: $1:$2
3. Columns to repeat at left: $A:$A

## Headers and Footers

### Adding Headers/Footers

1. Insert > Header & Footer
2. Or Page Layout view
3. Click header/footer area

### Header/Footer Sections

| Section | Alignment |
|---------|-----------|
| Left | Left-aligned |
| Center | Centered |
| Right | Right-aligned |

### Built-in Elements

| Code | Inserts |
|------|---------|
| &[Page] | Page number |
| &[Pages] | Total pages |
| &[Date] | Current date |
| &[Time] | Current time |
| &[File] | File name |
| &[Path] | File path |
| &[Tab] | Sheet name |
| &[Picture] | Image |

### Header/Footer Options

| Option | Effect |
|--------|--------|
| Different First Page | Unique first page header |
| Different Odd & Even | Alternating headers |
| Scale with Document | Resize with scaling |
| Align with Page Margins | Match page margins |

## Print Settings

### Print Preview

Ctrl+P or File > Print:
- See how pages will print
- Navigate between pages
- Access print settings

### Print Selection

| Option | Prints |
|--------|--------|
| Active Sheets | Currently selected sheets |
| Entire Workbook | All sheets |
| Selection | Highlighted range only |

### Print Options

| Setting | Description |
|---------|-------------|
| Copies | Number of copies |
| Collated | Complete sets in order |
| Pages | Specific page range |
| One-sided/Two-sided | Duplex printing |

### Page Setup Options

| Option | Effect |
|--------|--------|
| Gridlines | Print cell gridlines |
| Row and column headings | Print A, B, C and 1, 2, 3 |
| Black and white | No colors |
| Draft quality | Faster, lower quality |
| Comments | Print where displayed or at end |
| Cell errors | Print as displayed, blank, --, or #N/A |

### Print Order

| Option | Sequence |
|--------|----------|
| Down, then over | Print columns first |
| Over, then down | Print rows first |

## View Options

### Normal View

Default editing view:
- Standard cell editing
- Full ribbon access
- Formula bar visible

### Page Layout View

See pages as they will print:
- Rulers visible
- Headers/footers editable
- Page margins shown

### Page Break Preview

See and adjust page breaks:
- Blue lines = automatic breaks
- Solid lines = manual breaks
- Drag to adjust

### Workbook Views

| View | Purpose |
|------|---------|
| Normal | Standard editing |
| Page Break Preview | Manage pagination |
| Page Layout | Print preview editing |
| Custom Views | Saved view settings |

### Custom Views

Save view settings:
1. View > Custom Views
2. Add
3. Name the view
4. Choose settings to save

Settings saved:
- Print settings
- Hidden rows/columns
- Filter settings
- Window settings

### Show/Hide Elements

| Element | Toggle Location |
|---------|-----------------|
| Ruler | View > Ruler |
| Gridlines | View > Gridlines |
| Formula Bar | View > Formula Bar |
| Headings | View > Headings |
| Zoom | View > Zoom |

### Zoom Options

| Method | Action |
|--------|--------|
| Slider | Drag zoom slider |
| Ctrl + scroll | Mouse wheel zoom |
| View > Zoom | Zoom dialog |
| Zoom to selection | Fit selection in window |

Zoom range: 10% to 400%

## Keyboard Shortcuts Summary

| Action | Windows | Mac |
|--------|---------|-----|
| New sheet | Shift+F11 | Shift+F11 |
| Next sheet | Ctrl+Page Down | Ctrl+Page Down |
| Previous sheet | Ctrl+Page Up | Ctrl+Page Up |
| Move to A1 | Ctrl+Home | Cmd+Home |
| Move to last cell | Ctrl+End | Cmd+End |
| Hide rows | Ctrl+9 | Cmd+9 |
| Unhide rows | Ctrl+Shift+9 | Cmd+Shift+9 |
| Hide columns | Ctrl+0 | Cmd+0 |
| Unhide columns | Ctrl+Shift+0 | Cmd+Shift+0 |
| Print preview | Ctrl+P | Cmd+P |
| Page Break Preview | Alt+W, I | |
| Normal View | Alt+W, L | |
