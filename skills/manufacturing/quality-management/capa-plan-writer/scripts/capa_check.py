#!/usr/bin/env python3
"""Review a corrective action (CAPA) plan against ISO 9001 10.2 and the action-strength hierarchy.

CAPA JSON keys: capa_id, source, problem, correction, root_causes (list of {id, cause, verified, evidence}),
actions (list of {action, type corrective/preventive/correction, cause_id, owner, due}),
effectiveness ({criteria, method, due}), similar_check, updates (FMEA, control plan, procedures, risks)

Checks:
  CP001 high    no root cause, or the root cause is a symptom or blames a person ('operator error', 'not trained')
  CP002 high    no corrective action that changes the system: only correction (sort, rework, scrap, replace)
  CP003 high    no measurable effectiveness criteria, method and due date
  CP004 medium  weak actions only (retrain, remind, warn, re-brief): add error-proofing or a design/process change
  CP005 medium  action without owner or due date
  CP006 medium  root cause with no action, or action linked to no root cause
  CP007 medium  root cause not verified (switched on/off, reproduced, or data-confirmed)
  CP008 low     no check for similar nonconformities elsewhere (10.2.1 b 3)
  CP009 low     no update to risks, FMEA, control plan or documents (10.2.1 e, f)

Action strength (highest first): eliminate > error-proof > automate/detect > standardise > train > remind.

Usage:
    python capa_check.py capa.json

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import re
import sys

BLAME = re.compile(r"\b(operator|human|worker|inspector)\s+(error|mistake|fault)|\bnot (properly )?trained|\bcareless|\black of (attention|care|training|awareness)|\bdid not follow|\bforgot\b|\bmistake\b|\bnegligen", re.I)
SYMPTOM = re.compile(r"^\s*(part|parts|dimension|bore|hole)\b.*\b(out of (spec|tolerance)|oversize|undersize|wrong)\b", re.I)
CORRECTION = re.compile(r"\b(sort(ed)?|rework(ed)?|scrap(ped)?|replace(d)?|re-?inspect(ed)?|repaired|returned|credited|segregat)", re.I)
STRENGTH = [  # (rank, label, pattern)
    (5, "eliminate", r"\b(redesign|eliminat|remove the (step|need)|change (the )?(design|material|supplier))"),
    (4, "error-proof", r"\b(poka[- ]?yoke|error[- ]?proof|mistake[- ]?proof|fixture|interlock|sensor|go/?no-?go|physical stop|keyed)"),
    (3, "automate / detect", r"\b(automat|vision|in-?process (gauge|measurement)|100% (check|inspection)|alarm|spc|control chart|tool life (counter|monitor))"),
    (2, "standardise", r"\b(procedure|work instruction|wi-|standard work|checklist|control plan|setup sheet|update (the )?(sop|instruction))"),
    (1, "train", r"\b(train|retrain|coach|re-?brief|educat)"),
    (0, "remind", r"\b(remind|warn|toolbox talk|memo|be (more )?careful|awareness|email)"),
]


def strength(text):
    for rank, label, pat in STRENGTH:
        if re.search(pat, text, re.I):
            return rank, label
    return 2, "other"


def check(c):
    f = []
    causes = c.get("root_causes") or []
    if isinstance(causes, str):
        causes = [{"id": "RC1", "cause": causes}]
    actions = c.get("actions") or []
    if not causes:
        f.append(("CP001", "high", "no root cause stated"))
    for rc in causes:
        txt = str(rc.get("cause", ""))
        if BLAME.search(txt):
            f.append(("CP001", "high", f"{rc.get('id', '')} '{txt[:60]}' blames a person: ask why the process allowed it"))
        elif SYMPTOM.search(txt):
            f.append(("CP001", "high", f"{rc.get('id', '')} '{txt[:60]}' restates the symptom, not its cause"))
        if not rc.get("verified"):
            f.append(("CP007", "medium", f"{rc.get('id', '')} not verified: reproduce it, switch it on/off, or confirm with data"))
    real = [x for x in actions if str(x.get("type", "corrective")).lower() != "correction" and not
            (CORRECTION.search(str(x.get("action", ""))) and strength(str(x.get("action", "")))[0] <= 2 and
             not re.search(r"procedure|instruction|fixture|design|process", str(x.get("action", "")), re.I))]
    if not real:
        f.append(("CP002", "high", "only corrections (sort/rework/scrap/replace): add actions that remove the cause"))
    ranks = [(strength(str(x.get("action", ""))), x) for x in real]
    best = max((r[0][0] for r in ranks), default=-1)
    if real and best <= 1:
        f.append(("CP004", "medium", "strongest action is training/reminder: add error-proofing, automation or a design change"))
    for (rank, label), x in ranks:
        if not (x.get("owner") and x.get("due")):
            f.append(("CP005", "medium", f"'{str(x.get('action'))[:50]}' has no owner or due date"))
    ids = {str(rc.get("id")) for rc in causes if rc.get("id")}
    linked = {str(x.get("cause_id")) for x in real if x.get("cause_id")}
    for i in sorted(ids - linked):
        f.append(("CP006", "medium", f"root cause {i} has no corrective action"))
    for x in real:
        if x.get("cause_id") and str(x["cause_id"]) not in ids:
            f.append(("CP006", "medium", f"action '{str(x.get('action'))[:40]}' points to unknown cause {x['cause_id']}"))
    eff = c.get("effectiveness") or {}
    if not (eff.get("criteria") and re.search(r"\d", str(eff.get("criteria"))) and eff.get("method") and eff.get("due")):
        f.append(("CP003", "high", "effectiveness check needs a measurable criterion, a method and a date"))
    if not c.get("similar_check"):
        f.append(("CP008", "low", "record whether similar products, machines or sites have the same cause"))
    if not c.get("updates"):
        f.append(("CP009", "low", "update PFMEA, control plan, procedures or the risk register as needed"))
    return f, ranks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capa", help="CAPA JSON, or - for stdin")
    a = ap.parse_args()
    try:
        c = json.load(sys.stdin if a.capa == "-" else open(a.capa, encoding="utf-8"))
        if not isinstance(c, dict):
            raise ValueError("CAPA JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f, ranks = check(c)
    print(f"{c.get('capa_id', '(no id)')}: {c.get('problem', '')[:80]}")
    if ranks:
        print("Action strength:")
        for (rank, label), x in sorted(ranks, key=lambda r: -r[0][0]):
            print(f"  [{rank}] {label:<18}{str(x.get('action'))[:70]}")
    print()
    for code, sev, msg in f:
        print(f"{code} [{sev}] {msg}")
    print(f"\n{len(f)} issue(s)" if f else "Plan meets 10.2 and uses strong actions.")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
