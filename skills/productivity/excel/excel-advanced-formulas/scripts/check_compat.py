#!/usr/bin/env python3
"""Report the minimum Excel version a formula needs.

Scans each formula for function calls and maps them to the first Excel
release that shipped them, so you can warn users on older versions before
they see #NAME?. No dependencies.

Usage:
    python check_compat.py '=LET(x,A1:A10,SUM(FILTER(x,x>0)))'
    python check_compat.py --file formulas.txt
    python check_compat.py --target 2019 '=XLOOKUP(A1,B:B,C:C)'   # exit 1 if too new

Exit code: 0 = compatible with --target (or no target given), 1 = not compatible.
"""

import argparse
import json
import re
import sys

ORDER = ["2007", "2010", "2013", "2016", "2019", "2021", "2024", "365"]

SINCE = {
    "2010": "AGGREGATE NETWORKDAYS.INTL WORKDAY.INTL STDEV.S STDEV.P VAR.S VAR.P RANK.EQ RANK.AVG "
            "PERCENTILE.INC PERCENTILE.EXC QUARTILE.INC QUARTILE.EXC MODE.SNGL MODE.MULT CEILING.PRECISE FLOOR.PRECISE",
    "2013": "IFNA XOR DAYS ISOWEEKNUM FORMULATEXT ISFORMULA SHEET SHEETS NUMBERVALUE UNICHAR UNICODE "
            "CEILING.MATH FLOOR.MATH ARABIC BASE DECIMAL ENCODEURL WEBSERVICE FILTERXML",
    "2016": "FORECAST.LINEAR FORECAST.ETS FORECAST.ETS.CONFINT FORECAST.ETS.SEASONALITY FORECAST.ETS.STAT",
    "2019": "CONCAT TEXTJOIN IFS SWITCH MAXIFS MINIFS",
    "2021": "XLOOKUP XMATCH FILTER SORT SORTBY UNIQUE SEQUENCE RANDARRAY LET",
    "2024": "LAMBDA MAP REDUCE SCAN BYROW BYCOL MAKEARRAY ISOMITTED TEXTSPLIT TEXTBEFORE TEXTAFTER "
            "VSTACK HSTACK TAKE DROP CHOOSEROWS CHOOSECOLS EXPAND TOCOL TOROW WRAPROWS WRAPCOLS "
            "ARRAYTOTEXT VALUETOTEXT IMAGE",
    "365": "GROUPBY PIVOTBY PERCENTOF REGEXTEST REGEXEXTRACT REGEXREPLACE TRIMRANGE TRANSLATE "
           "DETECTLANGUAGE PY COPILOT",
}
VERSION_OF = {fn: ver for ver, fns in SINCE.items() for fn in fns.split()}


def functions_in(formula):
    masked = re.sub(r'"(?:[^"]|"")*"', '""', formula)  # ignore text inside strings
    return {m.upper() for m in re.findall(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(", masked)}


def analyse(formula):
    needs = {fn: VERSION_OF.get(fn, "2007") for fn in functions_in(formula)}
    minimum = max(needs.values(), key=ORDER.index, default="2007")
    return {"formula": formula, "minimum_version": minimum,
            "functions": {fn: v for fn, v in sorted(needs.items()) if v != "2007"}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("formulas", nargs="*", help="formulas to check (quote them in the shell)")
    ap.add_argument("--file", help="file with one formula per line")
    ap.add_argument("--target", choices=ORDER, help="Excel version the user has")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    formulas = list(args.formulas)
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            formulas += [ln.rstrip("\n") for ln in fh if ln.strip()]
    if not formulas:
        ap.error("pass at least one formula or --file")

    results = [analyse(f) for f in formulas]
    ok = True
    for r in results:
        r["compatible"] = args.target is None or ORDER.index(r["minimum_version"]) <= ORDER.index(args.target)
        ok &= r["compatible"]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            label = "Excel 365 only" if r["minimum_version"] == "365" else f"Excel {r['minimum_version']}+"
            flag = "" if r["compatible"] else f"  <-- not available in Excel {args.target}"
            print(f"{label:<16} {r['formula']}{flag}")
            for fn, v in r["functions"].items():
                print(f"{'':16}   {fn}: {'365' if v == '365' else v + '+'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
