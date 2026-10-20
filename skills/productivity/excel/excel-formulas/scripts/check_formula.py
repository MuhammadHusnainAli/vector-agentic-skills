#!/usr/bin/env python3
"""Lint Excel formulas before handing them to a user.

Checks: leading '=', balanced parentheses, unterminated strings, smart quotes,
nesting depth (Excel limit 64), unknown function names (#NAME? risk),
volatile functions, VLOOKUP/HLOOKUP without an explicit match mode, and
locale semicolon separators. No dependencies.

Usage:
    python check_formula.py '=IF(A1>0,"yes","no")'
    python check_formula.py --file formulas.txt      # one formula per line
    python check_formula.py --json '=SUM(A1:A10'

Exit code: 0 = no errors, 1 = at least one formula has errors.
"""

import argparse
import json
import re
import sys

KNOWN = set("""
ABS ACOS AGGREGATE AND ARRAYTOTEXT ASIN ATAN ATAN2 AVERAGE AVERAGEA AVERAGEIF AVERAGEIFS
BYCOL BYROW CEILING CEILING.MATH CELL CHAR CHOOSE CHOOSECOLS CHOOSEROWS CLEAN CODE COLUMN COLUMNS
CONCAT CONCATENATE CORREL COS COUNT COUNTA COUNTBLANK COUNTIF COUNTIFS COVARIANCE.S DATE DATEDIF
DATEVALUE DAY DAYS DROP EDATE EOMONTH EXACT EXP EXPAND FALSE FILTER FIND FIXED FLOOR FLOOR.MATH
FORECAST FORECAST.LINEAR FORMULATEXT FREQUENCY FV GROUPBY HLOOKUP HOUR HSTACK HYPERLINK IF IFERROR
IFNA IFS IMAGE INDEX INDIRECT INFO INT IPMT IRR ISBLANK ISERR ISERROR ISEVEN ISFORMULA ISLOGICAL
ISNA ISNONTEXT ISNUMBER ISODD ISOMITTED ISOWEEKNUM ISREF ISTEXT LAMBDA LARGE LEFT LEN LET LINEST
LN LOG LOG10 LOOKUP LOWER MAKEARRAY MAP MATCH MAX MAXA MAXIFS MEDIAN MID MIN MINA MINIFS MINUTE
MOD MODE MODE.SNGL MONTH MROUND N NA NETWORKDAYS NETWORKDAYS.INTL NOT NOW NPER NPV NUMBERVALUE
OFFSET OR PERCENTILE PERCENTILE.EXC PERCENTILE.INC PERCENTOF PERCENTRANK PI PIVOTBY PMT POWER PPMT
PRODUCT PROPER PV QUARTILE QUARTILE.INC QUOTIENT RADIANS RAND RANDARRAY RANDBETWEEN RANK RANK.AVG
RANK.EQ RATE REDUCE REGEXEXTRACT REGEXREPLACE REGEXTEST REPLACE REPT RIGHT ROUND ROUNDDOWN ROUNDUP
ROW ROWS SCAN SEARCH SECOND SEQUENCE SHEET SHEETS SIGN SIN SLOPE SMALL SORT SORTBY SQRT STDEV
STDEV.P STDEV.S STDEVA SUBSTITUTE SUBTOTAL SUM SUMIF SUMIFS SUMPRODUCT SUMSQ SWITCH T TAKE TAN
TEXT TEXTAFTER TEXTBEFORE TEXTJOIN TEXTSPLIT TIME TIMEVALUE TOCOL TODAY TOROW TRANSPOSE TREND
TRIM TRIMRANGE TRUE TRUNC TYPE UNICHAR UNICODE UNIQUE UPPER VALUE VALUETOTEXT VAR VAR.P VAR.S
VLOOKUP VSTACK WEEKDAY WEEKNUM WORKDAY WORKDAY.INTL WRAPCOLS WRAPROWS XIRR XLOOKUP XMATCH XNPV
XOR YEAR YEARFRAC
""".split())
VOLATILE = {"NOW", "TODAY", "RAND", "RANDBETWEEN", "RANDARRAY", "OFFSET", "INDIRECT", "INFO", "CELL"}
MAX_NESTING = 64


def mask_strings(f):
    """Replace the contents of "string" literals and 'sheet names' with spaces."""
    out, i, unterminated = list(f), 0, False
    while i < len(f):
        q = f[i]
        if q in "\"'":
            j = i + 1
            while j < len(f):
                if f[j] == q:
                    if j + 1 < len(f) and f[j + 1] == q:
                        j += 2
                        continue
                    break
                j += 1
            if j >= len(f) and q == '"':
                unterminated = True
            out[i + 1:j] = " " * (min(j, len(f)) - i - 1)
            i = j + 1
        else:
            i += 1
    return "".join(out), unterminated


def lint(formula):
    errors, warnings = [], []
    f = formula.strip()
    if not f.startswith("="):
        errors.append("Formula must start with '='")
    if re.search("[“”‘’]", f):
        errors.append("Smart quotes found; use straight quotes \" and '")

    masked, unterminated = mask_strings(f)
    if unterminated:
        errors.append('Unterminated text string (odd number of ")')
    # Array constants like {1,2;3,4} use , and ; as element separators, not arguments.
    masked = re.sub(r"\{[^}]*\}", lambda m: "{" + " " * (len(m.group()) - 2) + "}", masked)

    # Walk parentheses, tracking each function call's argument count.
    stack, depth_max = [], 0
    calls = []
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_.]*)?\(|\)|,", masked):
        tok = m.group()
        if tok.endswith("("):
            name = (m.group(1) or "").upper()
            stack.append({"name": name, "args": 0, "start": m.end()})
            depth_max = max(depth_max, len(stack))
        elif tok == ",":
            if stack:
                stack[-1]["args"] += 1
        else:
            if not stack:
                errors.append(f"Unmatched ')' at position {m.start() + 1}")
                continue
            call = stack.pop()
            has_body = masked[call["start"]:m.start()].strip() != "" or call["args"] > 0
            call["args"] = call["args"] + 1 if has_body else 0
            calls.append(call)
    if stack:
        errors.append(f"{len(stack)} unclosed '(' - add {len(stack)} ')'")
    if depth_max > MAX_NESTING:
        errors.append(f"Nesting depth {depth_max} exceeds Excel's limit of {MAX_NESTING}")
    elif depth_max > 7:
        warnings.append(f"Nesting depth {depth_max}; consider LET or IFS for readability")

    names = {c["name"] for c in calls if c["name"]}
    unknown = sorted(n for n in names if n not in KNOWN and not n.startswith(("_XLFN.", "_XLWS.")))
    if unknown:
        warnings.append(f"Unrecognised function(s) {', '.join(unknown)} - check spelling (#NAME?) unless they are named LAMBDAs")
    volatile = sorted(names & VOLATILE)
    if volatile:
        warnings.append(f"Volatile function(s) {', '.join(volatile)} recalculate on every change")
    for c in calls:
        if c["name"] in ("VLOOKUP", "HLOOKUP") and c["args"] == 3:
            warnings.append(f"{c['name']} has no range_lookup argument; it defaults to approximate match - add FALSE for exact")
    if ";" in masked and "," not in masked:
        warnings.append("Semicolon separators detected (European locale); English Excel expects commas")
    return {"formula": formula, "valid": not errors, "errors": errors, "warnings": warnings,
            "functions": sorted(names), "max_nesting": depth_max}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("formulas", nargs="*", help="formulas to check (quote them in the shell)")
    ap.add_argument("--file", help="file with one formula per line")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    formulas = list(args.formulas)
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            formulas += [ln.rstrip("\n") for ln in fh if ln.strip()]
    if not formulas:
        ap.error("pass at least one formula or --file")

    results = [lint(f) for f in formulas]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{'OK   ' if r['valid'] else 'ERROR'} {r['formula']}")
            for e in r["errors"]:
                print(f"      error:   {e}")
            for w in r["warnings"]:
                print(f"      warning: {w}")
    sys.exit(0 if all(r["valid"] for r in results) else 1)


if __name__ == "__main__":
    main()
