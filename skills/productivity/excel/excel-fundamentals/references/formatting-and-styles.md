# Formatting Reference

Complete guide to number formats, cell styles, borders, colors, and conditional formatting in Excel.

## Number Format Categories

### Built-in Categories

| Category | Description | Example |
|----------|-------------|---------|
| General | Default, no specific format | 1234.567 |
| Number | Decimal places, thousands separator | 1,234.57 |
| Currency | Currency symbol, decimals | $1,234.57 |
| Accounting | Aligned currency, negatives in parentheses | $ 1,234.57 |
| Date | Date formats | 1/15/2024 |
| Time | Time formats | 3:30 PM |
| Percentage | Multiply by 100, add % | 15.50% |
| Fraction | Display as fraction | 1/2 |
| Scientific | Exponential notation | 1.23E+03 |
| Text | Treat as text | 001234 |
| Special | ZIP codes, phone numbers, SSN | (555) 123-4567 |
| Custom | User-defined format | Custom |

### Number Format Options

| Option | Effect |
|--------|--------|
| Decimal places | 0-30 decimal positions |
| Use 1000 separator | Add commas (1,234) |
| Negative numbers | Red, parentheses, or minus sign |
| Display zeros | Show or hide zero values |

## Custom Number Format Codes

### Format Code Structure

```
positive;negative;zero;text
```

Up to four sections separated by semicolons:
1. Positive numbers
2. Negative numbers
3. Zero values
4. Text

### Basic Codes

| Code | Meaning | Example Input | Result |
|------|---------|---------------|--------|
| 0 | Display digit or zero | 0.00 with 1.5 | 1.50 |
| # | Display digit or nothing | #.## with 1.5 | 1.5 |
| ? | Display digit or space | ?.?? with 1.5 | 1.5  |
| . | Decimal point | 0.00 | 1.50 |
| , | Thousands separator | #,##0 | 1,234 |
| , | Scale by 1000 (at end) | #, | 1 (for 1234) |

### Text and Symbols

| Code | Meaning | Example |
|------|---------|---------|
| "text" | Literal text | 0 "units" -> "5 units" |
| @ | Text placeholder | @ " items" |
| * | Repeat character | *-0 -> ----5 |
| _ | Skip width of character | _( for alignment |
| \ | Escape next character | \$ -> $ |

### Color Codes

| Code | Color |
|------|-------|
| [Black] | Black |
| [Blue] | Blue |
| [Cyan] | Cyan |
| [Green] | Green |
| [Magenta] | Magenta |
| [Red] | Red |
| [White] | White |
| [Yellow] | Yellow |
| [Color n] | Color from palette (1-56) |

Example:
```
[Green]#,##0;[Red]-#,##0;0
```

### Condition Codes

| Code | Meaning |
|------|---------|
| [>100] | Value greater than 100 |
| [<0] | Value less than 0 |
| [>=50] | Value greater than or equal |
| [<=50] | Value less than or equal |
| [=0] | Value equals 0 |
| [<>0] | Value not equal to 0 |

Example:
```
[>=1000]#,##0,"K";[>=1]#,##0;0
```

### Common Custom Formats

| Purpose | Format Code |
|---------|-------------|
| Phone number | (###) ###-#### |
| Social Security | ###-##-#### |
| ZIP+4 | #####-#### |
| Thousands (K) | #,##0,"K" |
| Millions (M) | #,##0.0,,"M" |
| Hide values | ;;; |
| Hide zeros | #,##0;-#,##0;; |
| Leading zeros | 00000 |
| Positive/negative symbols | +#,##0;-#,##0;0 |
| Text prefix | "ID-"0000 |

## Date and Time Formats

### Date Codes

| Code | Meaning | Example |
|------|---------|---------|
| d | Day (1-31) | 5 |
| dd | Day (01-31) | 05 |
| ddd | Day abbreviation | Mon |
| dddd | Day full name | Monday |
| m | Month (1-12) | 1 |
| mm | Month (01-12) | 01 |
| mmm | Month abbreviation | Jan |
| mmmm | Month full name | January |
| mmmmm | Month letter | J |
| yy | Year (00-99) | 24 |
| yyyy | Year (1900-9999) | 2024 |

### Time Codes

| Code | Meaning | Example |
|------|---------|---------|
| h | Hour (0-23) | 3 |
| hh | Hour (00-23) | 03 |
| m | Minute (0-59) | 5 |
| mm | Minute (00-59) | 05 |
| s | Second (0-59) | 7 |
| ss | Second (00-59) | 07 |
| AM/PM | 12-hour with AM/PM | 3:05 PM |
| am/pm | 12-hour with am/pm | 3:05 pm |
| A/P | 12-hour with A/P | 3:05 P |
| [h] | Elapsed hours | [h]:mm |
| [m] | Elapsed minutes | [m]:ss |
| [s] | Elapsed seconds | [s] |

### Common Date/Time Formats

| Purpose | Format Code | Result |
|---------|-------------|--------|
| Short date | m/d/yyyy | 1/15/2024 |
| Long date | mmmm d, yyyy | January 15, 2024 |
| ISO date | yyyy-mm-dd | 2024-01-15 |
| Month-Year | mmm-yyyy | Jan-2024 |
| Quarter | "Q"q | Q1 |
| Time 12h | h:mm AM/PM | 3:30 PM |
| Time 24h | hh:mm | 15:30 |
| Duration | [h]:mm:ss | 25:30:00 |
| Timestamp | yyyy-mm-dd hh:mm:ss | 2024-01-15 15:30:00 |

## Font Formatting

### Font Properties

| Property | Options |
|----------|---------|
| Font name | Arial, Calibri, Times New Roman, etc. |
| Font size | 1-409 points |
| Font style | Regular, Bold, Italic, Bold Italic |
| Underline | Single, Double, Single Accounting, Double Accounting |
| Strikethrough | Line through text |
| Superscript | Raised text |
| Subscript | Lowered text |
| Color | Font color from palette |

### Default Fonts

| Element | Default |
|---------|---------|
| Body | Calibri 11pt |
| Headings | Calibri Light |
| Comments | Tahoma 9pt |

## Cell Styles

### Built-in Styles

| Category | Styles |
|----------|--------|
| Good, Bad, Neutral | Data quality indicators |
| Normal | Default cell style |
| Input | User input cells |
| Output | Calculated cells |
| Calculation | Formula cells |
| Check Cell | Verification cells |
| Linked Cell | External links |
| Note | Information cells |
| Warning Text | Alert text |
| Heading 1-4 | Header hierarchy |
| Title | Main title |
| Total | Summary rows |

### Creating Custom Styles

1. Home > Cell Styles > New Cell Style
2. Name the style
3. Format: Number, Alignment, Font, Border, Fill, Protection
4. Click OK

### Modifying Styles

1. Home > Cell Styles
2. Right-click style > Modify
3. Change format settings
4. All cells using style update automatically

## Borders

### Border Positions

| Position | Description |
|----------|-------------|
| Bottom | Bottom edge only |
| Top | Top edge only |
| Left | Left edge only |
| Right | Right edge only |
| No Border | Remove all borders |
| All Borders | Grid around all cells |
| Outside Borders | Border around selection |
| Thick Box Border | Heavy outside border |

### Border Styles

| Style | Appearance |
|-------|------------|
| None | No border |
| Thin | Hairline |
| Medium | Standard weight |
| Thick | Heavy weight |
| Double | Two parallel lines |
| Hair | Thinnest visible |
| Dotted | Dot pattern |
| Dashed | Dash pattern |
| Dash-Dot | Alternating |
| Dash-Dot-Dot | Complex pattern |
| Slant Dash-Dot | Diagonal pattern |

### Border Colors

- Select from theme colors
- Standard colors
- Custom RGB/HSL colors

### Draw Borders

1. Home > Borders dropdown > Draw Border
2. Select line style and color
3. Click and drag on cells

## Fill (Background)

### Solid Fill

- Single background color
- Most common fill type
- Theme or custom colors

### Pattern Fill

| Pattern | Use Case |
|---------|----------|
| None | No pattern |
| Solid | Standard fill |
| 75% Gray | Heavy shading |
| 50% Gray | Medium shading |
| 25% Gray | Light shading |
| 12.5% Gray | Very light |
| Horizontal Stripe | Row emphasis |
| Vertical Stripe | Column emphasis |
| Diagonal Stripe | Direction indicator |

### Gradient Fill

1. Format Cells > Fill > Fill Effects
2. Choose two colors
3. Select gradient style:
   - Horizontal
   - Vertical
   - Diagonal Up
   - Diagonal Down
   - From Corner
   - From Center

## Alignment

### Horizontal Alignment

| Option | Effect |
|--------|--------|
| General | Numbers right, text left |
| Left | Align to left edge |
| Center | Center in cell |
| Right | Align to right edge |
| Fill | Repeat to fill cell |
| Justify | Spread text evenly |
| Center Across Selection | Center without merging |
| Distributed | Space between characters |

### Vertical Alignment

| Option | Effect |
|--------|--------|
| Top | Align to top edge |
| Center | Center vertically |
| Bottom | Align to bottom edge |
| Justify | Spread text vertically |
| Distributed | Even vertical spacing |

### Text Control

| Option | Effect |
|--------|--------|
| Wrap Text | Multiple lines within cell |
| Shrink to Fit | Reduce font to fit |
| Merge Cells | Combine selected cells |

### Text Direction

| Option | Degrees |
|--------|---------|
| Horizontal | 0 |
| Vertical | 90 or -90 |
| Angle | -90 to 90 |
| Stacked | Vertical letters |

### Indent

- Increase/decrease left margin
- 0-15 character widths
- Works with left or right alignment

## Conditional Formatting

### Rule Types

| Type | Description |
|------|-------------|
| Highlight Cells Rules | Based on cell value |
| Top/Bottom Rules | Rank-based formatting |
| Data Bars | Bar length shows value |
| Color Scales | Gradient based on value |
| Icon Sets | Symbols based on value |
| Formula-based | Custom formula condition |

### Highlight Cells Rules

| Rule | Example |
|------|---------|
| Greater Than | > 100 |
| Less Than | < 50 |
| Between | 50 and 100 |
| Equal To | = "Done" |
| Text That Contains | Contains "Error" |
| A Date Occurring | Today, Last Week, etc. |
| Duplicate Values | Highlight duplicates |
| Unique Values | Highlight unique |

### Top/Bottom Rules

| Rule | Description |
|------|-------------|
| Top 10 Items | Highest N values |
| Top 10% | Top percentage |
| Bottom 10 Items | Lowest N values |
| Bottom 10% | Bottom percentage |
| Above Average | Above mean |
| Below Average | Below mean |

### Data Bars

Options:
- Gradient or solid fill
- Positive/negative colors
- Show or hide bar only
- Minimum/maximum values
- Bar direction

### Color Scales

| Type | Description |
|------|-------------|
| 2-Color | Two-point gradient |
| 3-Color | Three-point gradient (with midpoint) |

Settings:
- Minimum color and type
- Midpoint color and type (3-color)
- Maximum color and type

### Icon Sets

| Category | Examples |
|----------|----------|
| Directional | Arrows, triangles |
| Shapes | Traffic lights, flags |
| Indicators | Stars, checkmarks |
| Ratings | Bars, quarters |

Options:
- Show icon only
- Reverse icon order
- Custom thresholds

### Formula-Based Rules

Use formulas returning TRUE/FALSE:

```
=A1>100                          Value condition
=A1>AVERAGE($A:$A)               Compare to average
=ISBLANK(A1)                     Check for blanks
=MOD(ROW(),2)=0                  Alternate rows
=A1<>B1                          Compare columns
=COUNTIF($A:$A,A1)>1             Highlight duplicates
```

### Managing Rules

1. Home > Conditional Formatting > Manage Rules
2. View all rules for sheet or selection
3. Edit, delete, or change order
4. Stop If True option

### Rule Precedence

- Rules evaluated top to bottom
- First matching rule applies (unless continue)
- "Stop If True" prevents further evaluation

## Format Painter

### Using Format Painter

1. Select cell with desired format
2. Click Format Painter (Home tab)
3. Click or drag over target cells

### Multiple Applications

- Double-click Format Painter to lock
- Apply to multiple ranges
- Press Esc to deactivate

### What Gets Copied

- Number format
- Font properties
- Fill color
- Borders
- Alignment
- Conditional formatting

## Themes

### Theme Components

| Component | Controls |
|-----------|----------|
| Colors | 12-color palette |
| Fonts | Heading and body fonts |
| Effects | Shape and chart effects |

### Applying Themes

1. Page Layout > Themes
2. Choose built-in theme
3. Or customize individual components

### Theme Colors

| Position | Usage |
|----------|-------|
| 1-2 | Text/background (light/dark) |
| 3-4 | Text/background (dark/light) |
| 5-10 | Accent colors |
| 11-12 | Hyperlink colors |

## Clear Formatting

### Clear Options

| Option | Removes |
|--------|---------|
| Clear All | Contents, formatting, comments |
| Clear Formats | Only formatting |
| Clear Contents | Only values/formulas |
| Clear Comments | Only comments |
| Clear Hyperlinks | Only hyperlinks |

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Clear contents | Delete |
| Clear all | Ctrl+Shift+Delete |
| Paste special (formats) | Ctrl+Alt+V, then T |
