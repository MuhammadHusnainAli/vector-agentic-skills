#!/usr/bin/env python3
"""Inspect an .xlsx/.xlsm workbook without Excel or third-party libraries.

Reports each sheet's visibility, used range, cell/formula/error counts, frozen
panes, merged ranges, Excel tables, data validations, conditional formats and
autofilters, plus workbook-level defined names, external links and macros.
Use it to understand a workbook before answering questions about it, or to
spot structural problems (hidden sheets, broken #REF! names, merged cells in
data ranges, external links).

Usage:
    python inspect_workbook.py report.xlsx
    python inspect_workbook.py report.xlsx --sheet Data --sample 5    # also print the first 5 rows
    python inspect_workbook.py report.xlsx --json

Reads the Office Open XML parts with zipfile/ElementTree. Legacy .xls files
are not supported (save as .xlsx first).
"""

import argparse
import json
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
R_ID = f"{{{NS['r']}}}id"


def read_xml(z, path):
    try:
        return ET.fromstring(z.read(path))
    except KeyError:
        return None


def rels(z, part):
    folder, name = posixpath.split(part)
    root = read_xml(z, posixpath.join(folder, "_rels", name + ".rels"))
    out = {}
    if root is None:
        return out
    for r in root.findall("rel:Relationship", NS):
        target = r.get("Target")
        if r.get("TargetMode") != "External":
            target = posixpath.normpath(posixpath.join(folder, target)) if not target.startswith("/") else target.lstrip("/")
        out[r.get("Id")] = {"target": target, "type": r.get("Type", "").rsplit("/", 1)[-1]}
    return out


def col_to_num(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def shared_strings(z):
    root = read_xml(z, "xl/sharedStrings.xml")
    if root is None:
        return []
    return ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in root.findall("m:si", NS)]


def cell_value(c, strings):
    t = c.get("t")
    v = c.find("m:v", NS)
    if t == "s" and v is not None:
        return strings[int(v.text)]
    if t == "inlineStr":
        return "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
    if t == "b" and v is not None:
        return v.text == "1"
    return v.text if v is not None else None


def inspect(path, sample_sheet=None, sample_rows=0):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        wb = read_xml(z, "xl/workbook.xml")
        if wb is None:
            raise ValueError("not an Excel workbook (xl/workbook.xml missing)")
        wb_rels = rels(z, "xl/workbook.xml")
        strings = shared_strings(z)

        defined = []
        for dn in wb.findall("m:definedNames/m:definedName", NS):
            ref = dn.text or ""
            defined.append({"name": dn.get("name"), "refers_to": ref, "hidden": dn.get("hidden") == "1",
                            "broken": "#REF!" in ref})

        sheets = []
        for s in wb.findall("m:sheets/m:sheet", NS):
            target = wb_rels.get(s.get(R_ID), {}).get("target")
            info = {"name": s.get("name"), "state": s.get("state", "visible"), "kind": "worksheet"}
            if not target or target not in names or "worksheets" not in target:
                info["kind"] = "chartsheet" if target and "chartsheets" in target else "other"
                sheets.append(info)
                continue
            root = read_xml(z, target)
            dim = root.find("m:dimension", NS)
            cells = root.findall(".//m:sheetData/m:row/m:c", NS)
            pane = root.find(".//m:sheetView/m:pane", NS)
            sheet_rels = rels(z, target)
            tables = []
            for tp in root.findall("m:tableParts/m:tablePart", NS):
                tpath = sheet_rels.get(tp.get(R_ID), {}).get("target")
                troot = read_xml(z, tpath) if tpath else None
                if troot is not None:
                    tables.append({"name": troot.get("displayName") or troot.get("name"), "ref": troot.get("ref"),
                                   "columns": [c.get("name") for c in troot.findall("m:tableColumns/m:tableColumn", NS)]})
            info.update({
                "used_range": dim.get("ref") if dim is not None else None,
                "cells": len(cells),
                "formulas": sum(c.find("m:f", NS) is not None for c in cells),
                "errors": sum(c.get("t") == "e" for c in cells),
                "frozen": pane.get("topLeftCell") if pane is not None and pane.get("state") in ("frozen", "frozenSplit") else None,
                "merged": [m.get("ref") for m in root.findall("m:mergeCells/m:mergeCell", NS)],
                "tables": tables,
                "data_validations": len(root.findall("m:dataValidations/m:dataValidation", NS)),
                "conditional_formats": len(root.findall("m:conditionalFormatting", NS)),
                "autofilter": (root.find("m:autoFilter", NS).get("ref") if root.find("m:autoFilter", NS) is not None else None),
                "protected": root.find("m:sheetProtection", NS) is not None,
            })
            if sample_rows and (sample_sheet in (None, s.get("name"))):
                rows = []
                for row in root.findall("m:sheetData/m:row", NS)[:sample_rows]:
                    vals = {}
                    for c in row.findall("m:c", NS):
                        col = re.match(r"[A-Z]+", c.get("r", "A")).group()
                        f = c.find("m:f", NS)
                        vals[col_to_num(col)] = f"={f.text}" if f is not None and f.text else cell_value(c, strings)
                    width = max(vals, default=0)
                    rows.append([vals.get(i) for i in range(1, width + 1)])
                info["sample"] = rows
            sheets.append(info)

        return {
            "file": path,
            "macros": "xl/vbaProject.bin" in names,
            "external_links": sorted(n for n in names if n.startswith("xl/externalLinks/") and n.endswith(".xml")),
            "defined_names": defined,
            "sheets": sheets,
        }


def render(r):
    print(f"{r['file']}: {len(r['sheets'])} sheet(s)"
          + (", contains macros" if r["macros"] else "")
          + (f", {len(r['external_links'])} external link(s)" if r["external_links"] else ""))
    for s in r["sheets"]:
        flag = "" if s["state"] == "visible" else f" [{s['state']}]"
        if s["kind"] != "worksheet":
            print(f"\n- {s['name']}{flag} ({s['kind']})")
            continue
        print(f"\n- {s['name']}{flag}: range {s['used_range']}, {s['cells']} cells, {s['formulas']} formulas"
              + (f", {s['errors']} error values" if s["errors"] else ""))
        details = []
        if s["frozen"]:
            details.append(f"frozen at {s['frozen']}")
        if s["autofilter"]:
            details.append(f"autofilter {s['autofilter']}")
        if s["merged"]:
            details.append(f"{len(s['merged'])} merged range(s): {', '.join(s['merged'][:5])}")
        if s["data_validations"]:
            details.append(f"{s['data_validations']} data validation rule(s)")
        if s["conditional_formats"]:
            details.append(f"{s['conditional_formats']} conditional format(s)")
        if s["protected"]:
            details.append("sheet protected")
        for d in details:
            print(f"    {d}")
        for t in s["tables"]:
            print(f"    table {t['name']} {t['ref']}: {', '.join(t['columns'])}")
        for row in s.get("sample", []):
            print("    | " + " | ".join("" if v is None else str(v) for v in row))
    if r["defined_names"]:
        print("\nDefined names:")
        for d in r["defined_names"]:
            print(f"    {d['name']} = {d['refers_to']}" + ("  <-- broken" if d["broken"] else "") + ("  (hidden)" if d["hidden"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help=".xlsx or .xlsm file")
    ap.add_argument("--sheet", help="limit --sample to this sheet")
    ap.add_argument("--sample", type=int, default=0, help="print the first N rows of each (or --sheet) sheet")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()
    try:
        report = inspect(args.file, args.sheet, args.sample)
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        render(report)


if __name__ == "__main__":
    main()
