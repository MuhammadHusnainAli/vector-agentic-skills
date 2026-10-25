#!/usr/bin/env python3
"""Lint an ML project scoping document (Markdown) for missing sections and vague commitments.

Checks (codes):
  SC001 error    required section missing (summary, problem/decision, success criteria, data, approach,
                 scope, milestones, risks)
  SC002 error    no out-of-scope list: scope without "won't do" grows forever
  SC003 error    no baseline or current process mentioned
  SC004 warning  success criteria contain no number (target, threshold, percentage)
  SC005 warning  metric named without an operating point or split (e.g. "accuracy", "AUC" alone)
  SC006 warning  milestones without dates
  SC007 warning  risks section without mitigations
  SC008 warning  vague language: "leverage AI", "optimize", "real-time" without a latency, "insights",
                 "state-of-the-art", "as soon as possible"
  SC009 warning  no go/no-go or kill criteria
  SC010 info     unresolved TODO / TBD markers

Usage:
    python scope_lint.py SCOPE.md
    python scope_lint.py SCOPE.md --json
    cat SCOPE.md | python scope_lint.py -

Exit codes: 0 no errors, 1 errors found, 2 read error.
"""

import argparse
import json
import re
import sys

SECTIONS = {
    "summary": r"summary|overview|tl;?dr",
    "problem/decision": r"problem|decision|background|motivation",
    "success criteria": r"success|metric|kpi|objective",
    "data": r"\bdata\b|labels?",
    "approach": r"approach|method|solution|plan",
    "scope": r"scope",
    "milestones": r"milestone|timeline|schedule|phases?",
    "risks": r"risk",
}
VAGUE = [
    (r"\bleverag\w* (ai|ml|machine learning)\b", "say which prediction and which decision"),
    (r"\boptimi[sz]e\b(?![^.\n]*\b(by|to|from)\b)", "optimise what, by how much, measured how?"),
    (r"\breal[- ]time\b(?![^.\n]*\d+\s*(ms|milliseconds?|s|seconds?|minutes?))", "give the latency budget"),
    (r"\binsights?\b", "insights are not a deliverable; name the decision or report"),
    (r"\bstate[- ]of[- ]the[- ]art\b", "name the model and the baseline it must beat"),
    (r"\bas soon as possible\b|\basap\b", "give a date"),
    (r"\b(world[- ]class|best[- ]in[- ]class|cutting[- ]edge)\b", "replace with a measurable target"),
]
BARE_METRIC = re.compile(r"\b(accuracy|auc|roc[- ]?auc|f1|rmse|mape|r2|r²)\b", re.I)


def sections(text):
    """[(heading, body)] for ##/### headings."""
    parts, cur, body = [], None, []
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(.*)", line)
        if m:
            if cur is not None:
                parts.append((cur, "\n".join(body)))
            cur, body = m.group(1).strip(), []
        elif cur is not None:
            body.append(line)
    if cur is not None:
        parts.append((cur, "\n".join(body)))
    return parts


def lint(text):
    out = []

    def add(code, sev, msg):
        out.append({"code": code, "severity": sev, "message": msg})

    secs = sections(text)
    found = {}
    for name, pat in SECTIONS.items():
        for h, b in secs:
            if re.search(pat, h, re.I):
                found.setdefault(name, b)
        if name not in found:
            add("SC001", "error", f"missing section: {name}")
    low = text.lower()
    if not re.search(r"out[- ]of[- ]scope|not in scope|non[- ]goals?|won'?t do", low):
        add("SC002", "error", "no out-of-scope list (non-goals)")
    if not re.search(r"baseline|current (process|rule|approach|system)|today\b|status quo", low):
        add("SC003", "error", "no baseline or current process to compare against")
    succ = found.get("success criteria", "")
    if succ and not re.search(r"\d", succ):
        add("SC004", "warning", "success criteria contain no number (target, threshold or percentage)")
    for m in BARE_METRIC.finditer(succ):
        ctx = succ[max(0, m.start() - 80): m.end() + 80].lower()
        if not re.search(r"@|\bat\b|top[- ]?\d|holdout|split|threshold|>=|<=|\d", ctx):
            add("SC005", "warning", f"metric '{m.group(0)}' has no operating point, target or evaluation split")
            break
    ms = found.get("milestones", "")
    if ms and not re.search(r"\d{4}-\d{2}(-\d{2})?|\b(q[1-4]|week \d+|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", ms, re.I):
        add("SC006", "warning", "milestones have no dates")
    rk = found.get("risks", "")
    if rk and not re.search(r"mitigat|fallback|contingency|plan:|we will", rk, re.I):
        add("SC007", "warning", "risks listed without mitigations")
    # Things listed as out of scope may be vague on purpose ("real-time scoring"): skip the Scope section.
    prose = "\n".join(f"{h}\n{b}" for h, b in secs if not re.search(SECTIONS["scope"], h, re.I)) or text
    for pat, fix in VAGUE:
        m = re.search(pat, prose, re.I)
        if m:
            add("SC008", "warning", f"vague: '{m.group(0)}' - {fix}")
    if not re.search(r"go/no[- ]go|go / no[- ]go|kill criteria|stop criteria|exit criteri", low):
        add("SC009", "warning", "no go/no-go or kill criteria")
    todos = len(re.findall(r"\bTODO\b|\bTBD\b", text))
    if todos:
        add("SC010", "info", f"{todos} TODO/TBD marker(s) unresolved")
    return out


def main():
    ap = argparse.ArgumentParser(description="Lint an ML scoping document.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc", help="Markdown file or - for stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.doc == "-" else open(a.doc, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = lint(text)
    errors = sum(f["severity"] == "error" for f in findings)
    if a.json:
        print(json.dumps({"errors": errors, "findings": findings}, indent=2))
    else:
        for f in findings:
            print(f"{f['code']} [{f['severity']}] {f['message']}")
        print(f"\n{len(findings)} finding(s), {errors} error(s)" + ("" if findings else ": scope document looks complete"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
