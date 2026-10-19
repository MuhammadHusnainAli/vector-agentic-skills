# XLSX Formula Examples

Production-ready formula examples for common business scenarios.

## Lookup Scenarios

### Find Product Price from Catalog

Data layout: Product names in column A, prices in column B, lookup value in E1.

Modern approach:
```
=XLOOKUP(E1, A:A, B:B, "Not Found", 0)
```

Legacy approach:
```
=IFERROR(VLOOKUP(E1, A:B, 2, FALSE), "Not Found")
```

Flexible approach (works left or right):
```
=IFERROR(INDEX(B:B, MATCH(E1, A:A, 0)), "Not Found")
```

### Two-Way Lookup (Row and Column)

Data layout: Row headers in column A, column headers in row 1, data in B2:D10.

```
=INDEX(B2:D10, MATCH(G1, A2:A10, 0), MATCH(G2, B1:D1, 0))
```

With error handling:
```
=IFERROR(INDEX(B2:D10, MATCH(G1, A2:A10, 0), MATCH(G2, B1:D1, 0)), "Not Found")
```

### Multiple Criteria Lookup

Find value where Region="East" AND Product="Widget".

Using SUMIFS (if result is numeric and unique):
```
=SUMIFS(C:C, A:A, "East", B:B, "Widget")
```

Using INDEX/MATCH with array:
```
=INDEX(C:C, MATCH(1, (A:A="East")*(B:B="Widget"), 0))
```

Using FILTER (Excel 365+):
```
=FILTER(C:C, (A:A="East")*(B:B="Widget"), "Not Found")
```

### Return Multiple Columns

Get all data for a matching ID.

```
=XLOOKUP(E1, A:A, B:D)
```

This returns columns B, C, and D for the matching row.

### Approximate Match (Price Tiers)

Find applicable tier based on quantity. Tiers in A:A (ascending), discounts in B:B.

```
=XLOOKUP(E1, A:A, B:B, , -1)
```

Legacy:
```
=VLOOKUP(E1, A:B, 2, TRUE)
```

Ensure tier values are sorted ascending.

## Conditional Calculations

### Grade Assignment

Score in A1, assign letter grade.

Using IFS:
```
=IFS(A1>=90, "A", A1>=80, "B", A1>=70, "C", A1>=60, "D", TRUE, "F")
```

Using nested IF:
```
=IF(A1>=90, "A", IF(A1>=80, "B", IF(A1>=70, "C", IF(A1>=60, "D", "F"))))
```

### Status Based on Multiple Conditions

Project status based on completion and due date.

```
=IF(AND(B1=100, A1<=TODAY()), "Complete",
 IF(AND(B1<100, A1<TODAY()), "Overdue",
 IF(B1=100, "Complete Early", "In Progress")))
```

### Commission Calculation with Tiers

Sales in A1, tiered commission rates.

```
=IF(A1>=100000, A1*0.15,
 IF(A1>=50000, A1*0.10,
 IF(A1>=25000, A1*0.07, A1*0.05)))
```

Using formula with brackets:
```
=A1*IFS(A1>=100000, 0.15, A1>=50000, 0.10, A1>=25000, 0.07, TRUE, 0.05)
```

### Bonus Eligibility

Multiple criteria: performance rating AND years of service.

```
=IF(AND(A1>=4, B1>=2), "Eligible",
 IF(OR(A1>=5, B1>=5), "Review", "Not Eligible"))
```

## Aggregation with Conditions

### Sum by Category

Sum sales where category is "Electronics".

```
=SUMIF(A:A, "Electronics", B:B)
```

### Sum with Multiple Criteria

Sum sales where Region="East" AND Month="January".

```
=SUMIFS(C:C, A:A, "East", B:B, "January")
```

### Sum with Wildcards

Sum sales for products starting with "Pro".

```
=SUMIF(A:A, "Pro*", B:B)
```

### Sum Excluding Certain Values

Sum all except "Returns".

```
=SUMIF(A:A, "<>Returns", B:B)
```

### Count Unique Values

Count distinct entries in column A.

Modern (Excel 365+):
```
=COUNTA(UNIQUE(A2:A100))
```

Legacy:
```
=SUMPRODUCT(1/COUNTIF(A2:A100, A2:A100))
```

### Running Total

Running sum of column B, starting from row 2.

In cell C2:
```
=SUM($B$2:B2)
```

Copy down to create running total.

### Conditional Average Excluding Zeros

Average column B where values > 0.

```
=AVERAGEIF(B:B, ">0")
```

### Weighted Average

Values in A:A, weights in B:B.

```
=SUMPRODUCT(A2:A100, B2:B100)/SUM(B2:B100)
```

## Date Calculations

### Age Calculation

Birth date in A1.

```
=DATEDIF(A1, TODAY(), "Y")
```

Full age with months:
```
=DATEDIF(A1, TODAY(), "Y") & " years, " & DATEDIF(A1, TODAY(), "YM") & " months"
```

### Days Until Due Date

Due date in A1.

```
=A1-TODAY()
```

With status:
```
=IF(A1-TODAY()<0, "Overdue", IF(A1-TODAY()<=7, "Due Soon", "On Track"))
```

### Business Days Between Dates

Start in A1, end in B1, holidays in D:D.

```
=NETWORKDAYS(A1, B1, D:D)
```

### Add Business Days

Start date in A1, add 10 business days, holidays in D:D.

```
=WORKDAY(A1, 10, D:D)
```

### First/Last Day of Month

Date in A1.

First day:
```
=DATE(YEAR(A1), MONTH(A1), 1)
```

Last day:
```
=EOMONTH(A1, 0)
```

### Quarter from Date

Date in A1.

```
=ROUNDUP(MONTH(A1)/3, 0)
```

Or:
```
="Q" & ROUNDUP(MONTH(A1)/3, 0)
```

### Fiscal Year (Starting July)

Date in A1, fiscal year starts July 1.

```
=IF(MONTH(A1)>=7, YEAR(A1)+1, YEAR(A1))
```

## Text Manipulation

### Extract First/Last Name

Full name in A1 (format: "First Last").

First name:
```
=LEFT(A1, FIND(" ", A1)-1)
```

Last name:
```
=RIGHT(A1, LEN(A1)-FIND(" ", A1))
```

### Extract Domain from Email

Email in A1.

```
=MID(A1, FIND("@", A1)+1, LEN(A1))
```

### Clean Phone Number (Remove Non-Digits)

Phone in A1 with formatting like "(123) 456-7890".

Remove common characters:
```
=SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(A1, "(", ""), ")", ""), "-", ""), " ", "")
```

### Proper Case with Exceptions

Name in A1, handle "McDonald", "O'Brien".

```
=PROPER(A1)
```

Note: Manual correction needed for special cases.

### Pad Number with Leading Zeros

Number in A1, pad to 5 digits.

```
=TEXT(A1, "00000")
```

Or:
```
=RIGHT("00000" & A1, 5)
```

### Extract Numeric Value from Text

Text containing number in A1 (like "Order #12345").

```
=SUMPRODUCT(MID(0&A1, LARGE(INDEX(ISNUMBER(--MID(A1, ROW(INDIRECT("1:"&LEN(A1))), 1))*ROW(INDIRECT("1:"&LEN(A1))), 0), ROW(INDIRECT("1:"&LEN(A1))))+1, 1)*10^ROW(INDIRECT("1:"&LEN(A1)))/10)
```

Simpler if number position is known:
```
=VALUE(MID(A1, 8, 5))
```

### Concatenate with Delimiter

Join A1:A10 with commas.

```
=TEXTJOIN(", ", TRUE, A1:A10)
```

## Dynamic Array Examples (Excel 365+)

### Filter and Sort Combined

Filter sales over 1000 and sort descending.

```
=SORT(FILTER(A2:C100, B2:B100>1000), 2, -1)
```

### Top N Results

Top 5 sales with all columns.

```
=SORT(A2:C100, 2, -1)
```

Then use:
```
=INDEX(SORT(A2:C100, 2, -1), SEQUENCE(5), {1,2,3})
```

### Unique Values Sorted

Unique regions sorted alphabetically.

```
=SORT(UNIQUE(A2:A100))
```

### Dynamic Dependent Dropdown List

Unique values from column A where column B matches G1.

```
=SORT(UNIQUE(FILTER(A2:A100, B2:B100=G1)))
```

### Generate Date Series

Monthly dates for a year starting from A1.

```
=EDATE(A1, SEQUENCE(12, 1, 0, 1))
```

### Transpose Data

Convert A1:A10 to horizontal.

```
=TRANSPOSE(A1:A10)
```

### Running Total with SCAN

Values in A2:A10.

```
=SCAN(0, A2:A10, LAMBDA(a, b, a+b))
```

### Rank All Values

Rank each value in A2:A100.

```
=MAP(A2:A100, LAMBDA(x, RANK(x, A2:A100)))
```

## Error-Safe Patterns

### Division with Zero Check

```
=IFERROR(A1/B1, 0)
```

Or explicit check:
```
=IF(B1=0, 0, A1/B1)
```

### Lookup with Multiple Fallbacks

Try XLOOKUP, then VLOOKUP backup, then default.

```
=IFERROR(XLOOKUP(E1, A:A, B:B), IFERROR(VLOOKUP(E1, D:E, 2, FALSE), "Not Found"))
```

### Empty Cell Handling

Return blank instead of 0 for empty inputs.

```
=IF(A1="", "", A1*B1)
```

### Percentage with Zero Denominator

```
=IFERROR(A1/B1, 0)
```

Formatted:
```
=TEXT(IFERROR(A1/B1, 0), "0.0%")
```

### Nested IFERROR Chain

Try multiple lookups in sequence.

```
=IFERROR(VLOOKUP(E1, Table1, 2, FALSE),
 IFERROR(VLOOKUP(E1, Table2, 2, FALSE),
 IFERROR(VLOOKUP(E1, Table3, 2, FALSE), "Not Found")))
```

## Data Validation Formulas

### Validate Email Format

Check if A1 contains @ and . after @.

```
=AND(ISNUMBER(FIND("@", A1)), ISNUMBER(FIND(".", A1, FIND("@", A1))))
```

### Check Date is Weekday

Date in A1, TRUE if weekday.

```
=AND(WEEKDAY(A1, 2)<=5)
```

### Value Within Range

A1 must be between 1 and 100.

```
=AND(A1>=1, A1<=100)
```

### No Duplicates Check

Check if A1 is unique in column A.

```
=COUNTIF(A:A, A1)=1
```

### Future Date Only

A1 must be after today.

```
=A1>TODAY()
```

### Text Length Validation

A1 must be exactly 10 characters.

```
=LEN(A1)=10
```

## Financial Calculations

### Compound Interest

Principal in A1, rate in B1 (annual), years in C1.

```
=A1*(1+B1)^C1
```

### Monthly Payment (Loan)

Loan amount in A1, annual rate in B1, years in C1.

```
=PMT(B1/12, C1*12, -A1)
```

### Net Present Value

Rate in A1, cash flows in B1:B10.

```
=NPV(A1, B1:B10)
```

### Internal Rate of Return

Cash flows in A1:A10 (first value is initial investment, negative).

```
=IRR(A1:A10)
```

### Depreciation (Straight Line)

Cost in A1, salvage in B1, life in C1.

```
=SLN(A1, B1, C1)
```

## Array Formula Patterns

### Count Cells Meeting Multiple OR Conditions

Count where A:A is "East" OR "West".

```
=SUMPRODUCT((A2:A100="East")+(A2:A100="West")>0)
```

### Sum Where Any Condition Met

Sum B:B where A:A contains "Apple" OR "Orange".

```
=SUMPRODUCT(((A2:A100="Apple")+(A2:A100="Orange"))*B2:B100)
```

### Return Nth Match

Find 3rd occurrence of "Error" in A:A, return corresponding B value.

```
=INDEX(B:B, SMALL(IF(A2:A100="Error", ROW(A2:A100)), 3))
```

Note: May require Ctrl+Shift+Enter in older Excel versions.

### Conditional Concatenation

Join all values in B:B where A:A matches E1.

```
=TEXTJOIN(", ", TRUE, IF(A2:A100=E1, B2:B100, ""))
```

Excel 365+, or Ctrl+Shift+Enter in older versions.

## Performance Tips

### Use Tables for Auto-Expanding Ranges

Instead of:
```
=SUM(A:A)
```

Use structured references:
```
=SUM(Table1[Sales])
```

### Avoid Volatile Functions in Large Datasets

Volatile functions (TODAY, NOW, RAND, OFFSET, INDIRECT) recalculate constantly.

Replace:
```
=SUMIF(INDIRECT("A:A"), "East", INDIRECT("B:B"))
```

With:
```
=SUMIF(A:A, "East", B:B)
```

### Use SUMIFS Instead of SUMPRODUCT for Simple Conditions

More efficient:
```
=SUMIFS(C:C, A:A, "East", B:B, ">1000")
```

Less efficient:
```
=SUMPRODUCT((A2:A1000="East")*(B2:B1000>1000)*C2:C1000)
```

### Limit Range References

Instead of entire columns:
```
=VLOOKUP(E1, A:B, 2, FALSE)
```

Use defined ranges:
```
=VLOOKUP(E1, A1:B1000, 2, FALSE)
```
