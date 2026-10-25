#!/usr/bin/env python3
"""Lint a model card (Markdown) for missing sections, unsupported claims and missing evidence.

Rules:
  MC001 high    a core section is missing: model details/description, intended use, out-of-scope use,
                training data, evaluation data, metrics/evaluation, limitations, ethical considerations
  MC002 high    placeholder text left in (TODO, TBD, FIXME, lorem ipsum, "fill in", "<...>")
  MC003 high    the metrics/evaluation section contains no numbers
  MC004 medium  no uncertainty anywhere (confidence interval, CI, +/-, std, standard error)
  MC005 medium  no performance broken down by group/slice/segment
  MC006 medium  overclaiming language: unbiased, bias-free, fair (as a blanket claim), 100% accurate,
                guaranteed, state of the art, never fails, works for everyone, perfectly
  MC007 medium  no dates or period for the data (a year such as 2025, or "period", "from ... to")
  MC008 low     no baseline or comparison model
  MC009 low     a classifier card that never mentions the decision threshold
  MC010 low     no owner/contact, version or date
  MC011 low     no monitoring / maintenance / retraining section

Usage:
    python card_lint.py MODEL_CARD.md
    python card_lint.py README.md --json

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import json
import re
import sys

SECTIONS = {
    "model details or description": r"model details|overview|description|summary",
    "intended use": r"intended use|use cases?|primary uses?|purpose",
    "out-of-scope use": r"out[- ]of[- ]scope|misuse|not intended|prohibited uses?|limitations of use",
    "training data": r"training data|data used for training|training set|datasets?",
    "evaluation data": r"evaluation data|test data|validation data|evaluation set|holdout",
    "metrics / evaluation": r"metrics|evaluation|performance|results",
    "limitations": r"limitations?|known issues|failure modes|weaknesses",
    "ethical considerations": r"ethic|fairness|bias|responsible|harms?|risks?",
}
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|lorem ipsum|fill (this )?in|<[a-z _-]+>|\[insert", re.I)
OVERCLAIM = re.compile(r"\b(unbiased|bias[- ]free|100\s?% accura\w*|guarantee[ds]?|state[- ]of[- ]the[- ]art|"
                       r"never fails|works for everyone|perfectly (accurate|fair)|completely fair|fully fair|"
                       r"no bias)\b", re.I)
UNCERTAINTY = re.compile(r"confidence interval|\bCI\b|±|\+/-|\bstd\b|standard (error|deviation)|"
                         r"\[\s*0?\.\d+\s*,\s*0?\.\d+\s*\]|\d\.\d+\s*-\s*\d\.\d+", re.I)
SLICES = re.compile(r"slice|subgroup|segment|by group|per group|across groups|demographic|cohort|"
                    r"disaggregated|\|\s*\w+\s*=\s*\w+", re.I)
DATES = re.compile(r"\b(19|20)\d{2}\b|\bperiod\b|from .{3,30} to ", re.I)
BASELINE = re.compile(r"baseline|compared (to|with)|previous (model|version)|benchmark|heuristic|rule[- ]based", re.I)
CLASSIFIER = re.compile(r"classif|probability|binary|auc|precision|recall", re.I)
THRESHOLD = re.compile(r"threshold|cut[- ]?off|operating point", re.I)
OWNER = re.compile(r"owner|contact|maintainer|author|team", re.I)
VERSION = re.compile(r"\bversion\b|\bv\d+(\.\d+)*\b", re.I)
MONITOR = re.compile(r"monitor|maintenance|retrain|drift", re.I)


def headings(text):
    return [(m.start(), m.group(2).strip()) for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.M)]


def section_text(text, pattern):
    hs = headings(text)
    out = []
    for i, (pos, title) in enumerate(hs):
        if re.search(pattern, title, re.I):
            end = hs[i + 1][0] if i + 1 < len(hs) else len(text)
            out.append(text[pos:end])
    return "\n".join(out)


def lint(text, path):
    out = []

    def add(code, sev, msg, line=0):
        out.append({"file": path, "line": line, "code": code, "severity": sev, "message": msg})

    titles = " | ".join(t for _, t in headings(text))
    for name, pat in SECTIONS.items():
        if not re.search(pat, titles, re.I):
            add("MC001", "high", f"missing section: {name}")
    for i, ln in enumerate(text.splitlines(), 1):
        if PLACEHOLDER.search(ln):
            add("MC002", "high", f"placeholder left in: {ln.strip()[:80]}", i)
        for m in OVERCLAIM.finditer(ln):
            add("MC006", "medium", f"overclaiming '{m.group(0)}': state what was measured instead", i)
    metrics = section_text(text, SECTIONS["metrics / evaluation"])
    if metrics and not re.search(r"\d\.\d|\d+\s?%", metrics):
        add("MC003", "high", "metrics/evaluation section has no numbers")
    if not UNCERTAINTY.search(text):
        add("MC004", "medium", "no uncertainty reported (confidence intervals, +/-, std)")
    if not SLICES.search(text):
        add("MC005", "medium", "no performance broken down by group or slice")
    if not DATES.search(text):
        add("MC007", "medium", "no dates or time period for the data")
    if not BASELINE.search(text):
        add("MC008", "low", "no baseline or comparison model")
    if CLASSIFIER.search(text) and not THRESHOLD.search(text):
        add("MC009", "low", "classifier card without a decision threshold")
    missing = [w for w, rx in (("owner/contact", OWNER), ("version", VERSION)) if not rx.search(text)]
    if missing:
        add("MC010", "low", "missing " + " and ".join(missing))
    if not MONITOR.search(text):
        add("MC011", "low", "no monitoring / maintenance / retraining information")
    return out


def main():
    ap = argparse.ArgumentParser(description="Lint a model card.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.card == "-" else open(a.card, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = lint(text, a.card)
    high = sum(f["severity"] == "high" for f in findings)
    if a.json:
        print(json.dumps({"findings": findings, "high": high}, indent=2))
    else:
        for f in findings:
            loc = f":{f['line']}" if f["line"] else ""
            print(f"{f['file']}{loc}: {f['code']} [{f['severity']}] {f['message']}")
        print(f"\n{len(findings)} finding(s), {high} high" + ("" if findings else ": the card covers the essentials"))
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
