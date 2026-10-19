# Data Management Reference

Complete guide to sorting, filtering, tables, data validation, and data cleanup in Excel.

## Sorting

### Basic Sort

Single column sort:
1. Select any cell in the column
2. Data > Sort A to Z (ascending) or Z to A (descending)
3. Or use toolbar buttons

### Sort Options

| Option | Effect |
|--------|--------|
| Sort A to Z | Ascending (A-Z, 0-9, oldest-newest) |
| Sort Z to A | Descending (Z-A, 9-0, newest-oldest) |
| Sort by Color | Cell color or font color |
| Custom Sort | Multi-level, custom order |

### Multi-Level Sort

1. Data > Sort
2. Add Level for each sort column
3. Set order priority (top = primary)

Example:
```
Level 1: Region (A to Z)
Level 2: Date (Newest to Oldest)
Level 3: Amount (Largest to Smallest)
```

### Sort Settings

| Setting | Options |
|---------|---------|
| My data has headers | Include/exclude header row |
| Case sensitive | Distinguish A vs a |
| Sort left to right | Sort by rows instead of columns |
| Order | A to Z, Z to A, Custom List |

### Custom Sort Order

Built-in lists:
- Days of week (Sun, Mon, Tue...)
- Months (Jan, Feb, Mar...)

Create custom list:
1. File > Options > Advanced > Edit Custom Lists
2. Enter values or import from range
3. Use in Sort dialog

### Sort by Color

Sort based on:
- Cell fill color
- Font color
- Cell icon (from conditional formatting)

Order options:
- On Top
- On Bottom

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Sort ascending | Alt+A, S, A |
| Sort descending | Alt+A, S, D |
| Custom sort | Alt+A, S, S |

## Filtering

### AutoFilter

Enable filter dropdowns:
1. Select header row
2. Data > Filter
3. Or Ctrl+Shift+L

### Filter Types

| Type | Use For |
|------|---------|
| Text Filters | Text columns |
| Number Filters | Numeric columns |
| Date Filters | Date columns |
| Filter by Color | Colored cells |

### Text Filters

| Option | Matches |
|--------|---------|
| Equals | Exact match |
| Does Not Equal | Exclude exact match |
| Begins With | Starting text |
| Ends With | Ending text |
| Contains | Text anywhere |
| Does Not Contain | Exclude text |
| Custom Filter | Complex conditions |

### Number Filters

| Option | Condition |
|--------|-----------|
| Equals | = value |
| Does Not Equal | <> value |
| Greater Than | > value |
| Greater Than Or Equal | >= value |
| Less Than | < value |
| Less Than Or Equal | <= value |
| Between | range |
| Top 10 | Top/bottom n or % |
| Above Average | > mean |
| Below Average | < mean |

### Date Filters

| Category | Options |
|----------|---------|
| Specific | Equals, Before, After, Between |
| Relative | Today, Yesterday, Tomorrow |
| Period | This Week/Month/Quarter/Year |
| Dynamic | Last 7 Days, Year to Date, etc. |

### Filter by Selection

Quick filter methods:
- Right-click cell > Filter > Filter by Selected Cell's Value
- Filter by Color
- Filter by Icon

### Multiple Criteria

Within same column (OR):
- Check multiple items in dropdown
- Use Custom Filter with OR

Across columns (AND):
- Apply filters to multiple columns
- All conditions must match

### Advanced Filter

Data > Advanced for complex criteria:
- Filter in place or copy to location
- Criteria range with headers
- Unique records only

Criteria range format:
```
| Column1 | Column2 |
|---------|---------|
| >100    | ="East" |
| >200    |         |
```

### Clear Filters

| Action | Method |
|--------|--------|
| Clear single column | Click filter > Clear Filter |
| Clear all filters | Data > Clear |
| Remove AutoFilter | Data > Filter (toggle off) |

### Filter Indicators

| Indicator | Meaning |
|-----------|---------|
| Dropdown arrow | No filter applied |
| Funnel icon | Filter active on column |
| Row numbers blue | Rows are filtered |

## Tables

### Creating a Table

1. Select data range (including headers)
2. Insert > Table
3. Or Ctrl+T
4. Confirm "My table has headers"

### Table Benefits

| Feature | Description |
|---------|-------------|
| Auto-expand | New rows/columns included automatically |
| Structured references | [@Column] syntax in formulas |
| Auto-fill formulas | Formulas copy to new rows |
| Built-in styles | Banded rows, header formatting |
| Filter buttons | AutoFilter enabled by default |
| Total row | Summary calculations |
| Remove duplicates | Built-in tool |

### Table Parts

| Part | Description |
|------|-------------|
| Header Row | Column names (always visible) |
| Data Body | Data rows |
| Total Row | Optional summary row |
| First Column | Optional special formatting |
| Last Column | Optional special formatting |
| Banded Rows | Alternating row colors |
| Banded Columns | Alternating column colors |

### Structured References

Reference table data by name:

| Reference | Meaning |
|-----------|---------|
| TableName | Entire table |
| TableName[Column] | Single column |
| TableName[[Column1]:[Column2]] | Column range |
| TableName[#All] | Entire table with headers |
| TableName[#Data] | Data only (no headers) |
| TableName[#Headers] | Header row |
| TableName[#Totals] | Total row |
| [@Column] | This row's value in Column |
| [@[Column Name]] | Brackets for names with spaces |

### Total Row Functions

| Function | Calculates |
|----------|------------|
| None | No calculation |
| Average | Mean value |
| Count | Count of values |
| Count Numbers | Count numeric only |
| Max | Maximum value |
| Min | Minimum value |
| Sum | Total |
| StdDev | Standard deviation |
| Var | Variance |
| More Functions | Custom formula |

### Table Styles

Built-in styles:
- Light (21 styles)
- Medium (28 styles)
- Dark (11 styles)

Custom style:
1. Table Design > More > New Table Style
2. Format each element
3. Set as default (optional)

### Convert Table to Range

1. Select table
2. Table Design > Convert to Range
3. Keeps data and formatting
4. Loses table features

### Resize Table

1. Table Design > Resize Table
2. Or drag corner handle
3. Adjust range reference

## Data Validation

### Creating Validation Rules

1. Select cells
2. Data > Data Validation
3. Set criteria, input message, error alert

### Validation Types

| Type | Restricts To |
|------|--------------|
| Any value | No restriction |
| Whole number | Integers |
| Decimal | Numbers with decimals |
| List | Predefined options |
| Date | Date range |
| Time | Time range |
| Text length | Character count |
| Custom | Formula-based |

### Criteria Options

| Operator | Meaning |
|----------|---------|
| between | Min and Max |
| not between | Outside range |
| equal to | Exact value |
| not equal to | Not exact value |
| greater than | > value |
| less than | < value |
| greater than or equal to | >= value |
| less than or equal to | <= value |

### List Validation (Dropdown)

From range:
```
Source: =$A$1:$A$10
Source: =Categories
```

Direct entry:
```
Source: Yes,No,Maybe
Source: North,South,East,West
```

Options:
- In-cell dropdown
- Ignore blank

### Input Message

| Setting | Purpose |
|---------|---------|
| Title | Message box title |
| Input message | Help text for user |
| Show when selected | Enable/disable message |

### Error Alert

| Style | Behavior |
|-------|----------|
| Stop | Reject invalid entry |
| Warning | Allow with warning |
| Information | Allow with info |

| Setting | Purpose |
|---------|---------|
| Title | Error box title |
| Error message | Explanation text |

### Formula-Based Validation

Examples:
```
=A1>B1                    A must be greater than B
=LEN(A1)<=10              Max 10 characters
=ISNUMBER(A1)             Must be number
=A1<TODAY()               Must be past date
=COUNTIF($A:$A,A1)=1      No duplicates
=MOD(A1,1)=0              Whole numbers only
=AND(A1>=1,A1<=100)       Between 1 and 100
```

### Circle Invalid Data

Highlight cells failing validation:
1. Data > Data Validation > Circle Invalid Data
2. Red circles appear on invalid cells
3. Data > Clear Validation Circles to remove

### Copy Validation

1. Copy cell with validation
2. Paste Special > Validation

### Remove Validation

1. Select cells
2. Data > Data Validation > Clear All

## Data Cleanup

### Remove Duplicates

1. Select range or table
2. Data > Remove Duplicates
3. Choose columns to check
4. Click OK

Options:
- Check all columns
- Select specific columns
- My data has headers

### Text to Columns

Split text into multiple columns:
1. Select column
2. Data > Text to Columns
3. Choose delimiter or fixed width

Delimiters:
- Tab
- Semicolon
- Comma
- Space
- Other (custom)

Fixed width:
- Set break lines manually
- Preview result

### Trim Spaces

Remove extra spaces:
```
=TRIM(A1)
```

Removes:
- Leading spaces
- Trailing spaces
- Multiple spaces between words

### Clean Non-Printable Characters

```
=CLEAN(A1)
```

Removes ASCII characters 0-31.

### Change Case

| Formula | Result |
|---------|--------|
| =UPPER(A1) | UPPERCASE |
| =LOWER(A1) | lowercase |
| =PROPER(A1) | Title Case |

### Find and Replace

Ctrl+H for Replace dialog:
- Find what: Text to find
- Replace with: Replacement text
- Match case: Case sensitive
- Match entire cell contents: Exact match
- Use wildcards: * and ?

Special replacements:
- ^p = Paragraph mark
- ^t = Tab character
- ^? = Any character
- ^# = Any digit
- ^$ = Any letter

### Flash Fill

Automatically fill based on pattern:
1. Enter example in adjacent column
2. Press Ctrl+E
3. Or Data > Flash Fill

Use for:
- Extracting parts of text
- Combining text
- Reformatting data
- Standardizing formats

### Fill Blank Cells

1. Select range with blanks
2. Go To Special > Blanks (Ctrl+G > Special)
3. Type formula (e.g., =A2)
4. Ctrl+Enter to fill all

### Consolidate Data

Combine data from multiple ranges:
1. Data > Consolidate
2. Choose function (Sum, Average, Count, etc.)
3. Add source ranges
4. Options: Top row, Left column labels

## Data Tools

### Goal Seek

Find input value for desired result:
1. Data > What-If Analysis > Goal Seek
2. Set cell: Result cell
3. To value: Desired result
4. By changing cell: Input cell

### Scenario Manager

Save multiple input sets:
1. Data > What-If Analysis > Scenario Manager
2. Add scenarios
3. Show different scenarios
4. Create summary report

### Data Table

One-variable:
1. Set up formula and input values
2. Data > What-If Analysis > Data Table
3. Column/Row input cell

Two-variable:
1. Row inputs across, column inputs down
2. Formula in corner
3. Both input cells specified

### Group and Outline

Group rows/columns:
1. Select rows/columns
2. Data > Group
3. Or Alt+Shift+Right

Auto Outline:
1. Data > Group > Auto Outline
2. Creates groups from formulas

Controls:
- +/- buttons to expand/collapse
- Level buttons (1, 2, 3...)

### Subtotals

Add automatic subtotals:
1. Sort by grouping column
2. Data > Subtotal
3. At each change in: Grouping column
4. Use function: Sum, Count, etc.
5. Add subtotal to: Value columns

Remove:
- Data > Subtotal > Remove All

## Import/Export

### Import Data

Data > Get Data:
- From File (Excel, CSV, XML, JSON)
- From Database
- From Online Services
- From Other Sources

### Text Import

Delimited files:
- Set delimiter
- Choose data formats
- Specify start row

Fixed width:
- Set column breaks
- Preview data

### Export to CSV

Save As > CSV (Comma delimited)

Note:
- Single sheet only
- Loses formatting
- No formulas (values only)

### Copy/Paste Options

Paste Special (Ctrl+Alt+V):
- Values
- Formulas
- Formats
- Column widths
- Validation
- Comments
- Transpose
- Skip blanks
- Operations (Add, Subtract, Multiply, Divide)
