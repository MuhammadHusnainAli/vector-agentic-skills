# Text Parsing Functions Reference

Advanced text manipulation functions including TEXTSPLIT, TEXTBEFORE, TEXTAFTER, and regex functions for Excel 365/2024+.

## TEXTSPLIT

Split text string into array using delimiters.

### Syntax

```
=TEXTSPLIT(text, col_delimiter, [row_delimiter], [ignore_empty], [match_mode], [pad_with])
```

### Parameters

- text: Text to split
- col_delimiter: Delimiter(s) for columns (or array of delimiters)
- row_delimiter: Delimiter(s) for rows (optional)
- ignore_empty: TRUE to skip empty values (default FALSE)
- match_mode: 0 = case-sensitive (default), 1 = case-insensitive
- pad_with: Value for missing cells when row lengths differ

### Split by Single Delimiter

Space:
```
=TEXTSPLIT("John Smith Doe", " ")
```
Returns: {"John", "Smith", "Doe"} as row

Comma:
```
=TEXTSPLIT("apple,banana,cherry", ",")
```

Comma-space:
```
=TEXTSPLIT("apple, banana, cherry", ", ")
```

### Split by Multiple Delimiters

Split by comma OR semicolon:
```
=TEXTSPLIT("a,b;c,d", {",", ";"})
```
Returns: {"a", "b", "c", "d"}

### Split into Rows and Columns

CSV-like data:
```
=TEXTSPLIT("a,b,c;d,e,f;g,h,i", ",", ";")
```

Returns 3x3 array:
```
a  b  c
d  e  f
g  h  i
```

### Ignore Empty Values

With consecutive delimiters:
```
=TEXTSPLIT("a,,b,,,c", ",")
```
Returns: {"a", "", "b", "", "", "c"}

Ignore empty:
```
=TEXTSPLIT("a,,b,,,c", ",", , TRUE)
```
Returns: {"a", "b", "c"}

### Case-Insensitive Split

```
=TEXTSPLIT("aXbxCxd", "x", , , 1)
```
Returns: {"a", "b", "C", "d"}

### Padding Uneven Rows

```
=TEXTSPLIT("a,b,c;d,e", ",", ";", , , "-")
```

Returns:
```
a  b  c
d  e  -
```

### Practical Examples

Parse full address:
```
=TEXTSPLIT("123 Main St, City, State 12345", ", ")
```

Split multiline text:
```
=TEXTSPLIT(A1, , CHAR(10))
```

Parse key-value pairs:
```
=LET(
  pairs, TEXTSPLIT("name=John;age=30;city=NYC", ";"),
  MAP(pairs, LAMBDA(p, TEXTSPLIT(p, "=")))
)
```

Parse CSV cell:
```
=TEXTSPLIT(A1, ",", CHAR(10), TRUE)
```

## TEXTBEFORE

Extract text before a delimiter.

### Syntax

```
=TEXTBEFORE(text, delimiter, [instance_num], [match_mode], [match_end], [if_not_found])
```

### Parameters

- text: Source text
- delimiter: String to find
- instance_num: Which occurrence (default 1, negative counts from end)
- match_mode: 0 = case-sensitive (default), 1 = case-insensitive
- match_end: 0 = don't match end (default), 1 = treat end as delimiter
- if_not_found: Value if delimiter not found (default #N/A)

### Basic Examples

First name:
```
=TEXTBEFORE("John Smith", " ")
```
Returns: "John"

Before second space:
```
=TEXTBEFORE("John William Smith", " ", 2)
```
Returns: "John William"

### Instance Number

First occurrence:
```
=TEXTBEFORE("a-b-c-d", "-", 1)
```
Returns: "a"

Second occurrence:
```
=TEXTBEFORE("a-b-c-d", "-", 2)
```
Returns: "a-b"

From end (last delimiter):
```
=TEXTBEFORE("a-b-c-d", "-", -1)
```
Returns: "a-b-c"

Second from end:
```
=TEXTBEFORE("a-b-c-d", "-", -2)
```
Returns: "a-b"

### Handle Not Found

Default (returns #N/A):
```
=TEXTBEFORE("abc", "x")
```

Custom fallback:
```
=TEXTBEFORE("abc", "x", , , , "Not found")
```

Return original if not found:
```
=TEXTBEFORE("abc", "x", , , , "abc")
```

### Case-Insensitive

```
=TEXTBEFORE("HelloXworld", "x", 1, 1)
```
Returns: "Hello"

### Practical Examples

Extract domain from URL:
```
=TEXTBEFORE(TEXTAFTER(A1, "://"), "/")
```

Get file name from path:
```
=TEXTAFTER(A1, "\", -1)
```

Protocol from URL:
```
=TEXTBEFORE("https://example.com/page", "://")
```

Username from email:
```
=TEXTBEFORE("user@example.com", "@")
```

## TEXTAFTER

Extract text after a delimiter.

### Syntax

```
=TEXTAFTER(text, delimiter, [instance_num], [match_mode], [match_end], [if_not_found])
```

### Parameters

Same as TEXTBEFORE.

### Basic Examples

Last name:
```
=TEXTAFTER("John Smith", " ")
```
Returns: "Smith"

After second space:
```
=TEXTAFTER("John William Smith", " ", 2)
```
Returns: "Smith"

### Instance Number

After first delimiter:
```
=TEXTAFTER("a-b-c-d", "-", 1)
```
Returns: "b-c-d"

After last delimiter:
```
=TEXTAFTER("a-b-c-d", "-", -1)
```
Returns: "d"

### Practical Examples

File extension:
```
=TEXTAFTER("document.pdf", ".")
```

Domain from email:
```
=TEXTAFTER("user@example.com", "@")
```

Query string from URL:
```
=TEXTAFTER("https://site.com/page?id=123", "?")
```

Last folder in path:
```
=TEXTAFTER("C:\Users\John\Documents", "\", -1)
```

### Combined TEXTBEFORE and TEXTAFTER

Extract middle portion:
```
=TEXTBEFORE(TEXTAFTER("prefix_value_suffix", "_"), "_")
```
Returns: "value"

Parse structured string:
```
=LET(
  text, "Name: John Smith | Age: 30 | City: NYC",
  name_part, TEXTBEFORE(text, " | "),
  name, TEXTAFTER(name_part, ": "),
  name
)
```

## REGEXTEST

Test if text matches a regular expression pattern.

### Syntax

```
=REGEXTEST(text, pattern, [case_sensitivity])
```

### Parameters

- text: Text to test
- pattern: PCRE2 regex pattern
- case_sensitivity: 0 = case-sensitive (default), 1 = case-insensitive

### Returns

TRUE if pattern matches, FALSE otherwise.

### Basic Patterns

Contains digits:
```
=REGEXTEST("abc123", "\d")
```
Returns: TRUE

Starts with letter:
```
=REGEXTEST("Hello", "^[A-Za-z]")
```
Returns: TRUE

Ends with number:
```
=REGEXTEST("Item5", "\d$")
```
Returns: TRUE

### Common Validation Patterns

Email format:
```
=REGEXTEST(A1, "^[\w.-]+@[\w.-]+\.\w{2,}$")
```

Phone (US format):
```
=REGEXTEST(A1, "^\d{3}-\d{3}-\d{4}$")
```

Phone (flexible):
```
=REGEXTEST(A1, "^\+?[\d\s()-]{10,}$")
```

Date (YYYY-MM-DD):
```
=REGEXTEST(A1, "^\d{4}-\d{2}-\d{2}$")
```

ZIP code (US):
```
=REGEXTEST(A1, "^\d{5}(-\d{4})?$")
```

URL:
```
=REGEXTEST(A1, "^https?://[\w.-]+\.\w{2,}")
```

IP address (basic):
```
=REGEXTEST(A1, "^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
```

### Case-Insensitive

```
=REGEXTEST("Hello World", "hello", 1)
```
Returns: TRUE

### With Conditional

```
=IF(REGEXTEST(A1, "^\d+$"), "Valid ID", "Invalid")
```

## REGEXEXTRACT

Extract text matching a regular expression pattern.

### Syntax

```
=REGEXEXTRACT(text, pattern, [return_mode], [case_sensitivity])
```

### Parameters

- text: Source text
- pattern: PCRE2 regex pattern
- return_mode: 0 = first match (default), 1 = all matches as array
- case_sensitivity: 0 = case-sensitive (default), 1 = case-insensitive

### Extract First Match

First number:
```
=REGEXEXTRACT("Price: $123.45", "\d+")
```
Returns: "123"

First word:
```
=REGEXEXTRACT("Hello World", "\w+")
```
Returns: "Hello"

### Extract All Matches

All numbers:
```
=REGEXEXTRACT("a1b2c3d4", "\d+", 1)
```
Returns: {"1", "2", "3", "4"} as array

All words:
```
=REGEXEXTRACT("Hello, World!", "\w+", 1)
```
Returns: {"Hello", "World"}

All email addresses:
```
=REGEXEXTRACT(A1, "[\w.-]+@[\w.-]+\.\w+", 1)
```

### Capture Groups

Extract captured portion:
```
=REGEXEXTRACT("Name: John", "Name: (\w+)")
```
Returns: "John"

Multiple groups:
```
=REGEXEXTRACT("John Smith, 30", "(\w+) (\w+), (\d+)")
```
Returns array of captured groups.

### Practical Examples

Extract price:
```
=REGEXEXTRACT("Total: $1,234.56", "\$[\d,]+\.?\d*")
```

Extract hashtags:
```
=REGEXEXTRACT(A1, "#\w+", 1)
```

Extract dates:
```
=REGEXEXTRACT(A1, "\d{1,2}/\d{1,2}/\d{2,4}", 1)
```

Extract URLs:
```
=REGEXEXTRACT(A1, "https?://[^\s]+", 1)
```

Phone numbers:
```
=REGEXEXTRACT(A1, "\d{3}[-.]?\d{3}[-.]?\d{4}", 1)
```

### Convert to Number

```
=VALUE(REGEXEXTRACT("Order #12345", "\d+"))
```

## REGEXREPLACE

Replace text matching a pattern.

### Syntax

```
=REGEXREPLACE(text, pattern, replacement, [occurrence], [case_sensitivity])
```

### Parameters

- text: Source text
- pattern: PCRE2 regex pattern
- replacement: Replacement text (can use backreferences)
- occurrence: Which match to replace (0 = all, default)
- case_sensitivity: 0 = case-sensitive (default), 1 = case-insensitive

### Basic Replacement

Remove all digits:
```
=REGEXREPLACE("abc123def456", "\d+", "")
```
Returns: "abcdef"

Replace digits with X:
```
=REGEXREPLACE("abc123def456", "\d", "X")
```
Returns: "abcXXXdefXXX"

### Replace Specific Occurrence

Replace first match only:
```
=REGEXREPLACE("a1b2c3", "\d", "X", 1)
```
Returns: "aXb2c3"

Replace second match:
```
=REGEXREPLACE("a1b2c3", "\d", "X", 2)
```
Returns: "a1bXc3"

### Using Backreferences

Swap order with $1, $2:
```
=REGEXREPLACE("Smith, John", "(\w+), (\w+)", "$2 $1")
```
Returns: "John Smith"

Wrap matches:
```
=REGEXREPLACE("cat and dog", "\w+", "[$0]")
```
Returns: "[cat] [and] [dog]"

### Practical Examples

Normalize whitespace:
```
=REGEXREPLACE(A1, "\s+", " ")
```

Remove special characters:
```
=REGEXREPLACE(A1, "[^a-zA-Z0-9\s]", "")
```

Mask credit card:
```
=REGEXREPLACE(A1, "\d(?=\d{4})", "*")
```

Format phone number:
```
=REGEXREPLACE("1234567890", "(\d{3})(\d{3})(\d{4})", "($1) $2-$3")
```

Clean HTML tags:
```
=REGEXREPLACE(A1, "<[^>]+>", "")
```

Normalize date format:
```
=REGEXREPLACE("12/31/2024", "(\d{2})/(\d{2})/(\d{4})", "$3-$1-$2")
```

Title case first letter:
```
=REGEXREPLACE(LOWER(A1), "(?:^|\s)(\w)", UPPER("$1"))
```

### Case-Insensitive Replacement

```
=REGEXREPLACE("Hello HELLO hello", "hello", "hi", 0, 1)
```
Returns: "hi hi hi"

## Common Regex Patterns

### Character Classes

| Pattern | Matches |
|---------|---------|
| `\d` | Digit (0-9) |
| `\D` | Non-digit |
| `\w` | Word character (a-z, A-Z, 0-9, _) |
| `\W` | Non-word character |
| `\s` | Whitespace |
| `\S` | Non-whitespace |
| `.` | Any character except newline |

### Quantifiers

| Pattern | Matches |
|---------|---------|
| `*` | 0 or more |
| `+` | 1 or more |
| `?` | 0 or 1 |
| `{n}` | Exactly n |
| `{n,}` | n or more |
| `{n,m}` | Between n and m |

### Anchors

| Pattern | Matches |
|---------|---------|
| `^` | Start of string |
| `$` | End of string |
| `\b` | Word boundary |

### Groups

| Pattern | Purpose |
|---------|---------|
| `(...)` | Capture group |
| `(?:...)` | Non-capturing group |
| `(?=...)` | Positive lookahead |
| `(?!...)` | Negative lookahead |

### Common Patterns Reference

| Use Case | Pattern |
|----------|---------|
| Email | `[\w.-]+@[\w.-]+\.\w{2,}` |
| URL | `https?://[^\s]+` |
| Phone (US) | `\d{3}[-.]?\d{3}[-.]?\d{4}` |
| Date (ISO) | `\d{4}-\d{2}-\d{2}` |
| Time (24h) | `\d{2}:\d{2}(:\d{2})?` |
| IP Address | `\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}` |
| Hex Color | `#[0-9A-Fa-f]{6}` |
| Credit Card | `\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}` |
| ZIP (US) | `\d{5}(-\d{4})?` |
| SSN | `\d{3}-\d{2}-\d{4}` |

## Combining Text Functions

### Parse Complex String

```
=LET(
  raw, "John Smith <john@example.com> (Manager)",
  name, TEXTBEFORE(raw, " <"),
  email, TEXTBEFORE(TEXTAFTER(raw, "<"), ">"),
  role, TEXTBEFORE(TEXTAFTER(raw, "("), ")"),
  HSTACK(name, email, role)
)
```

### Validate and Extract

```
=LET(
  text, A1,
  is_valid, REGEXTEST(text, "^\d{3}-\d{3}-\d{4}$"),
  IF(is_valid, REGEXREPLACE(text, "-", ""), "Invalid")
)
```

### Split and Transform

```
=LET(
  parts, TEXTSPLIT("apple,BANANA,Cherry", ","),
  MAP(parts, LAMBDA(p, PROPER(TRIM(p))))
)
```

### Extract Multiple Patterns

```
=LET(
  text, "Contact: john@email.com or 555-123-4567",
  email, REGEXEXTRACT(text, "[\w.-]+@[\w.-]+\.\w+"),
  phone, REGEXEXTRACT(text, "\d{3}-\d{3}-\d{4}"),
  HSTACK(email, phone)
)
```

## Error Handling

### Safe TEXTSPLIT

```
=IFERROR(TEXTSPLIT(A1, ","), A1)
```

### Safe TEXTBEFORE/TEXTAFTER

```
=TEXTBEFORE(A1, "@", , , , A1)
```

### Safe Regex

```
=IFERROR(REGEXEXTRACT(A1, "\d+"), "No match")
```

### Validate Before Extract

```
=IF(REGEXTEST(A1, "\d+"), REGEXEXTRACT(A1, "\d+"), "N/A")
```
