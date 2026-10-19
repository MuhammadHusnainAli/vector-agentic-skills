# XLSX Functions Reference

Detailed documentation for Excel functions organized by category.

## Mathematical Functions

### SUM
Adds all numbers in a range.
```
=SUM(number1, [number2], ...)
=SUM(A1:A100)
=SUM(A1:A10, C1:C10, 100)
```
- Ignores text and logical values
- Empty cells treated as 0

### SUMPRODUCT
Multiplies corresponding components and returns the sum.
```
=SUMPRODUCT(array1, [array2], ...)
=SUMPRODUCT(A1:A10, B1:B10)
=SUMPRODUCT((A1:A10="East")*(B1:B10))
```
- Arrays must have same dimensions
- Useful for conditional calculations without SUMIFS

### AVERAGE
Returns arithmetic mean.
```
=AVERAGE(number1, [number2], ...)
=AVERAGE(A1:A100)
```
- Ignores empty cells
- Text values cause #VALUE! error

### AVERAGEIF / AVERAGEIFS
Conditional average.
```
=AVERAGEIF(range, criteria, [average_range])
=AVERAGEIFS(average_range, criteria_range1, criteria1, ...)
=AVERAGEIF(A:A, ">0", B:B)
```

### ROUND / ROUNDUP / ROUNDDOWN
Round to specified decimal places.
```
=ROUND(number, num_digits)
=ROUND(3.14159, 2)         // 3.14
=ROUNDUP(3.141, 2)         // 3.15
=ROUNDDOWN(3.149, 2)       // 3.14
```
- Negative num_digits rounds left of decimal

### CEILING / FLOOR
Round to nearest multiple.
```
=CEILING(number, significance)
=FLOOR(number, significance)
=CEILING(23, 5)            // 25
=FLOOR(23, 5)              // 20
```

### ABS
Returns absolute value.
```
=ABS(number)
=ABS(-5)                   // 5
```

### MOD
Returns remainder after division.
```
=MOD(number, divisor)
=MOD(10, 3)                // 1
```

### POWER / SQRT
Exponentiation and square root.
```
=POWER(number, power)
=POWER(2, 8)               // 256
=SQRT(16)                  // 4
```

### MIN / MAX
Returns minimum or maximum.
```
=MIN(number1, [number2], ...)
=MAX(number1, [number2], ...)
=MIN(A1:A100)
=MAX(B1:B100)
```

### MINIFS / MAXIFS
Conditional minimum/maximum.
```
=MINIFS(min_range, criteria_range1, criteria1, ...)
=MAXIFS(max_range, criteria_range1, criteria1, ...)
=MINIFS(B:B, A:A, "East")
```

## Logical Functions

### IF
Conditional evaluation.
```
=IF(logical_test, value_if_true, value_if_false)
=IF(A1>100, "Over", "Under")
=IF(A1="", "Empty", A1)
```

### IFS
Multiple conditions without nesting.
```
=IFS(condition1, value1, condition2, value2, ..., TRUE, default)
=IFS(A1>=90, "A", A1>=80, "B", A1>=70, "C", A1>=60, "D", TRUE, "F")
```
- Evaluates conditions in order
- Use TRUE as final condition for default

### SWITCH
Match value to list.
```
=SWITCH(expression, value1, result1, [value2, result2], ..., [default])
=SWITCH(A1, 1, "Jan", 2, "Feb", 3, "Mar", "Unknown")
```

### AND / OR / NOT
Logical operators.
```
=AND(logical1, [logical2], ...)
=OR(logical1, [logical2], ...)
=NOT(logical)
=AND(A1>0, B1>0)           // TRUE if both positive
=OR(A1="Yes", A1="Y")      // TRUE if either
=NOT(A1="No")              // TRUE if not "No"
```

### XOR
Exclusive OR - TRUE if odd number of arguments are TRUE.
```
=XOR(logical1, [logical2], ...)
=XOR(A1, B1)               // TRUE if exactly one is TRUE
```

### IFERROR / IFNA
Error handling.
```
=IFERROR(value, value_if_error)
=IFNA(value, value_if_na)
=IFERROR(A1/B1, 0)
=IFNA(VLOOKUP(E1, A:B, 2, FALSE), "Not Found")
```
- IFERROR catches all errors
- IFNA catches only #N/A

### ISERROR / ISNA / ISBLANK
Error and state checking.
```
=ISERROR(value)
=ISNA(value)
=ISBLANK(value)
=ISNUMBER(value)
=ISTEXT(value)
```

## Lookup Functions

### XLOOKUP (Excel 365/2021+)
Modern lookup function.
```
=XLOOKUP(lookup_value, lookup_array, return_array, [if_not_found], [match_mode], [search_mode])
```

Parameters:
- lookup_value: Value to find
- lookup_array: Range to search
- return_array: Range to return from
- if_not_found: Value if not found (optional)
- match_mode: 0=exact, -1=exact or next smaller, 1=exact or next larger, 2=wildcard
- search_mode: 1=first-to-last, -1=last-to-first, 2=binary ascending, -2=binary descending

```
=XLOOKUP(E1, A:A, B:B, "Not Found", 0)
=XLOOKUP(E1, A:A, B:C, , 0)           // returns multiple columns
```

### XMATCH (Excel 365/2021+)
Returns position of value.
```
=XMATCH(lookup_value, lookup_array, [match_mode], [search_mode])
=XMATCH("Apple", A:A, 0)
```

### VLOOKUP
Vertical lookup (legacy).
```
=VLOOKUP(lookup_value, table_array, col_index_num, [range_lookup])
```
- lookup_value: Value to find in first column
- table_array: Table range
- col_index_num: Column number to return (1-based)
- range_lookup: FALSE for exact match, TRUE for approximate

```
=VLOOKUP(E1, A1:C100, 2, FALSE)
```

Limitations:
- Only searches leftmost column
- Column index breaks if columns inserted
- Cannot look left

### HLOOKUP
Horizontal lookup.
```
=HLOOKUP(lookup_value, table_array, row_index_num, [range_lookup])
=HLOOKUP("Q1", A1:D5, 2, FALSE)
```

### INDEX
Returns value at intersection.
```
=INDEX(array, row_num, [col_num])
=INDEX(A1:C10, 5, 2)               // row 5, column 2
=INDEX(A:A, 5)                     // row 5 of column A
```

### MATCH
Returns position of value.
```
=MATCH(lookup_value, lookup_array, [match_type])
```
- match_type: 0=exact, 1=less than or equal (sorted asc), -1=greater than or equal (sorted desc)

```
=MATCH("Apple", A:A, 0)
```

### INDEX + MATCH Combined
Flexible lookup in any direction.
```
=INDEX(return_range, MATCH(lookup_value, lookup_range, 0))
=INDEX(B:B, MATCH(E1, A:A, 0))
```

Two-way lookup:
```
=INDEX(B2:D10, MATCH(G1, A2:A10, 0), MATCH(G2, B1:D1, 0))
```

### OFFSET
Returns reference offset from starting point.
```
=OFFSET(reference, rows, cols, [height], [width])
=OFFSET(A1, 2, 3)                  // 2 rows down, 3 cols right
=SUM(OFFSET(A1, 0, 0, 10, 1))     // dynamic range
```

### INDIRECT
Returns reference specified by text string.
```
=INDIRECT(ref_text, [a1])
=INDIRECT("A" & B1)
=SUM(INDIRECT("Sheet2!A1:A10"))
```

### CHOOSE
Returns value from list by index.
```
=CHOOSE(index_num, value1, [value2], ...)
=CHOOSE(A1, "Jan", "Feb", "Mar", "Apr")
```

## Text Functions

### CONCAT / TEXTJOIN
Combine text.
```
=CONCAT(text1, [text2], ...)
=CONCAT(A1, " ", B1)

=TEXTJOIN(delimiter, ignore_empty, text1, [text2], ...)
=TEXTJOIN(", ", TRUE, A1:A10)
```

### LEFT / RIGHT / MID
Extract text portions.
```
=LEFT(text, [num_chars])
=RIGHT(text, [num_chars])
=MID(text, start_num, num_chars)
=LEFT("Hello", 2)                  // "He"
=RIGHT("Hello", 2)                 // "lo"
=MID("Hello", 2, 3)                // "ell"
```

### LEN
Returns text length.
```
=LEN(text)
=LEN("Hello")                      // 5
```

### FIND / SEARCH
Find position of substring.
```
=FIND(find_text, within_text, [start_num])
=SEARCH(find_text, within_text, [start_num])
=FIND("o", "Hello")                // 5
```
- FIND is case-sensitive
- SEARCH allows wildcards, case-insensitive

### SUBSTITUTE / REPLACE
Replace text.
```
=SUBSTITUTE(text, old_text, new_text, [instance_num])
=SUBSTITUTE("Hello", "l", "L")     // "HeLLo"
=SUBSTITUTE("Hello", "l", "L", 1)  // "HeLlo"

=REPLACE(old_text, start_num, num_chars, new_text)
=REPLACE("Hello", 2, 3, "XX")      // "HXXo"
```

### TRIM / CLEAN
Clean text.
```
=TRIM(text)                        // removes extra spaces
=CLEAN(text)                       // removes non-printable chars
```

### UPPER / LOWER / PROPER
Change case.
```
=UPPER("hello")                    // "HELLO"
=LOWER("HELLO")                    // "hello"
=PROPER("hello world")             // "Hello World"
```

### TEXT
Format number as text.
```
=TEXT(value, format_text)
=TEXT(A1, "0.00")                  // "123.45"
=TEXT(A1, "$#,##0.00")             // "$1,234.56"
=TEXT(A1, "yyyy-mm-dd")            // "2024-01-15"
```

### VALUE
Convert text to number.
```
=VALUE(text)
=VALUE("123.45")                   // 123.45
```

### REPT
Repeat text.
```
=REPT(text, number_times)
=REPT("*", 5)                      // "*****"
```

## Date and Time Functions

### TODAY / NOW
Current date/time.
```
=TODAY()                           // current date (no time)
=NOW()                             // current date and time
```

### DATE / TIME
Create date/time from components.
```
=DATE(year, month, day)
=DATE(2024, 1, 15)

=TIME(hour, minute, second)
=TIME(14, 30, 0)
```

### YEAR / MONTH / DAY
Extract date components.
```
=YEAR(date)
=MONTH(date)
=DAY(date)
=YEAR(A1)                          // extracts year
```

### HOUR / MINUTE / SECOND
Extract time components.
```
=HOUR(time)
=MINUTE(time)
=SECOND(time)
```

### DATEDIF
Calculate date difference.
```
=DATEDIF(start_date, end_date, unit)
```
Units:
- "Y" = complete years
- "M" = complete months
- "D" = days
- "YM" = months ignoring years
- "YD" = days ignoring years
- "MD" = days ignoring months and years

```
=DATEDIF(A1, B1, "Y")              // years between dates
```

### EDATE / EOMONTH
Add months to date.
```
=EDATE(start_date, months)
=EOMONTH(start_date, months)       // end of resulting month
=EDATE(A1, 3)                      // 3 months later
=EOMONTH(A1, 0)                    // end of current month
```

### WEEKDAY / WEEKNUM
Week information.
```
=WEEKDAY(date, [return_type])
=WEEKNUM(date, [return_type])
=WEEKDAY(A1, 2)                    // 1=Monday, 7=Sunday
```

### NETWORKDAYS / WORKDAY
Business day calculations.
```
=NETWORKDAYS(start_date, end_date, [holidays])
=WORKDAY(start_date, days, [holidays])
=NETWORKDAYS(A1, B1, C1:C10)       // excludes weekends and holidays
=WORKDAY(A1, 10, C1:C10)           // 10 business days later
```

## Statistical Functions

### COUNT / COUNTA / COUNTBLANK
Count cells.
```
=COUNT(value1, [value2], ...)      // counts numbers
=COUNTA(value1, [value2], ...)     // counts non-empty
=COUNTBLANK(range)                 // counts empty
```

### COUNTIF / COUNTIFS
Conditional count.
```
=COUNTIF(range, criteria)
=COUNTIFS(criteria_range1, criteria1, [criteria_range2, criteria2], ...)

=COUNTIF(A:A, ">100")
=COUNTIF(A:A, "Apple")
=COUNTIF(A:A, "A*")                // wildcard
=COUNTIFS(A:A, "East", B:B, ">1000")
```

### SUMIF / SUMIFS
Conditional sum.
```
=SUMIF(range, criteria, [sum_range])
=SUMIFS(sum_range, criteria_range1, criteria1, ...)

=SUMIF(A:A, "East", B:B)
=SUMIFS(C:C, A:A, "East", B:B, ">1000")
```

### MEDIAN
Returns middle value.
```
=MEDIAN(number1, [number2], ...)
=MEDIAN(A1:A100)
```

### MODE
Returns most frequent value.
```
=MODE(number1, [number2], ...)
=MODE.SNGL(A1:A100)                // single mode
=MODE.MULT(A1:A100)                // array of modes
```

### STDEV / VAR
Standard deviation and variance.
```
=STDEV.S(number1, [number2], ...)  // sample
=STDEV.P(number1, [number2], ...)  // population
=VAR.S(number1, [number2], ...)
=VAR.P(number1, [number2], ...)
```

### PERCENTILE / QUARTILE
Distribution analysis.
```
=PERCENTILE.INC(array, k)
=QUARTILE.INC(array, quart)
=PERCENTILE.INC(A1:A100, 0.9)      // 90th percentile
=QUARTILE.INC(A1:A100, 1)          // first quartile
```

### RANK
Returns rank of number.
```
=RANK.EQ(number, ref, [order])
=RANK.AVG(number, ref, [order])
=RANK.EQ(A1, A:A, 0)               // 0=descending, 1=ascending
```

### LARGE / SMALL
Returns nth largest/smallest.
```
=LARGE(array, k)
=SMALL(array, k)
=LARGE(A1:A100, 1)                 // largest
=LARGE(A1:A100, 3)                 // third largest
```

## Dynamic Array Functions (Excel 365/2021+)

### FILTER
Filter array by condition.
```
=FILTER(array, include, [if_empty])
=FILTER(A2:D100, B2:B100>1000)
=FILTER(A2:D100, (B2:B100>1000)*(C2:C100="East"))  // AND
=FILTER(A2:D100, (B2:B100>1000)+(C2:C100="East"))  // OR
=FILTER(A2:D100, B2:B100>1000, "No results")
```

### SORT
Sort array.
```
=SORT(array, [sort_index], [sort_order], [by_col])
=SORT(A2:C100)                     // sort by first column ascending
=SORT(A2:C100, 2, -1)              // sort by column 2 descending
=SORT(A2:C100, {2,1}, {-1,1})      // multi-level sort
```

### SORTBY
Sort by another array.
```
=SORTBY(array, by_array1, [sort_order1], ...)
=SORTBY(A2:C100, D2:D100, -1)      // sort A:C by D descending
```

### UNIQUE
Extract unique values.
```
=UNIQUE(array, [by_col], [exactly_once])
=UNIQUE(A2:A100)                   // unique values
=UNIQUE(A2:A100, , TRUE)           // values appearing exactly once
```

### SEQUENCE
Generate number sequence.
```
=SEQUENCE(rows, [columns], [start], [step])
=SEQUENCE(10)                      // 1-10
=SEQUENCE(5, 3)                    // 5 rows, 3 columns
=SEQUENCE(10, 1, 0, 0.5)           // 0, 0.5, 1, 1.5, ...
```

### RANDARRAY
Generate random numbers.
```
=RANDARRAY([rows], [columns], [min], [max], [integer])
=RANDARRAY(5, 3)                   // 5x3 random decimals 0-1
=RANDARRAY(10, 1, 1, 100, TRUE)    // 10 random integers 1-100
```

### Spill Range Operator (#)
Reference entire spill range.
```
=SUM(A2#)                          // sum entire spill range starting at A2
=COUNTA(A2#)                       // count spill range
```

## Information Functions

### ISNUMBER / ISTEXT / ISBLANK
Type checking.
```
=ISNUMBER(value)
=ISTEXT(value)
=ISBLANK(value)
=ISLOGICAL(value)
=ISFORMULA(reference)
```

### TYPE
Returns type number.
```
=TYPE(value)
```
Returns: 1=number, 2=text, 4=logical, 16=error, 64=array

### CELL / INFO
Cell and system information.
```
=CELL("type", A1)                  // cell properties
=INFO("osversion")                 // system info
```

### NA
Returns #N/A error.
```
=NA()
```
Useful for placeholder values in charts.
