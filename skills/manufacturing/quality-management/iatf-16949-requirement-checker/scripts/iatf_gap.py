#!/usr/bin/env python3
"""IATF 16949:2016 gap check for the automotive requirements added on top of ISO 9001.

Two modes:
  --template            print a CSV worksheet of the IATF-specific requirements (paraphrased), with a row per
                        customer for customer-specific requirements (CSRs) when --customers is given
  <worksheet.csv>       score a filled worksheet (status met / partial / not-met / n/a, evidence)

Grading of gaps:
  IG001 major   required documented process missing (IATF expects these as written processes)
  IG002 major   customer-specific requirements of a customer not assessed or not met
  IG003 minor   other requirement not met (major for CSRs, MSA, control plans, process and product audits)
  IG004 minor   partially implemented
  IG005 check   met without evidence
  IG006 error   n/a where it cannot apply (only 7.1.5.3 internal lab, 7.2.4, 10.2.5 may be n/a)

The ISO 9001 base requirements must be met too: run the iso-9001-gap-analyzer worksheet alongside.

Usage:
    python iatf_gap.py --template --customers "Ford" "Stellantis" > iatf.csv
    python iatf_gap.py iatf.csv
    python iatf_gap.py --list-processes

Exit codes: 0 no major gaps, 1 major gaps or errors, 2 usage or read error.
"""

import argparse
import csv
import sys

# (clause, title, requirement, documented process required)
REQS = [
    ("4.3.2", "Customer-specific requirements", "Evaluate CSRs and include them in the QMS scope (CSR matrix)", False),
    ("4.4.1.2", "Product safety", "Documented process for product-safety related products and processes", True),
    ("5.1.1.1", "Corporate responsibility", "Anti-bribery policy, code of conduct, ethics escalation (whistle-blowing) policy", False),
    ("5.3.2", "Responsibility for product requirements", "Persons responsible for conformity can stop shipment and production", False),
    ("6.1.2.1", "Risk analysis", "Risk analysis includes lessons learned from recalls, audits, field returns, complaints, scrap", False),
    ("6.1.2.2", "Preventive action", "Documented process to reduce the impact of risks and prevent recurrence", True),
    ("6.1.2.3", "Contingency plans", "Documented contingency plans for key equipment, supply, utilities, labour, IT/cyber-attack; tested; reviewed", True),
    ("6.2.2.1", "Quality objectives - supplemental", "Objectives cover customer requirements at relevant functions, levels and processes", False),
    ("7.1.3.1", "Plant, facility and equipment planning", "Multidisciplinary planning with risk, lean principles and capacity re-evaluation", False),
    ("7.1.5.1.1", "Measurement system analysis", "Statistical MSA for every inspection, measurement and test system in the control plan", False),
    ("7.1.5.2.1", "Calibration / verification records", "Documented process for calibration records, out-of-tolerance reaction and customer notification", True),
    ("7.1.5.3", "Laboratory requirements", "Internal lab scope and competence; external labs ISO/IEC 17025 accredited or customer-approved", False),
    ("7.2.1", "Competence - supplemental", "Documented process to identify training needs, including awareness of customer requirements", True),
    ("7.2.2", "On-the-job training", "OJT for new or changed jobs, including contract and agency staff", False),
    ("7.2.3", "Internal auditor competency", "Documented process to verify internal auditor competence (core tools, CSRs, process approach)", True),
    ("7.2.4", "Second-party auditor competency", "Competence of auditors who audit suppliers", False),
    ("7.3.2", "Employee motivation and empowerment", "Documented process to motivate employees and promote innovation", True),
    ("7.5.1.1", "QMS documentation", "Quality manual with processes, interactions, and a CSR matrix showing where CSRs are addressed", False),
    ("7.5.3.2.1", "Record retention", "Retain PPAP, tooling, design and PO records for the active part life plus one calendar year", False),
    ("7.5.3.2.2", "Engineering specifications", "Documented process to review customer engineering standards within 10 working days", True),
    ("8.2.3.1.2", "Customer-designated special characteristics", "Comply with customer requirements for designating and controlling special characteristics", False),
    ("8.2.3.1.3", "Manufacturing feasibility", "Multidisciplinary feasibility analysis for new or changed products and processes", False),
    ("8.3.1.1", "Design and development - supplemental", "Documented design process for product and manufacturing process design", True),
    ("8.3.3.3", "Special characteristics", "Documented process to identify, document and control special characteristics", True),
    ("8.3.4.4", "Product approval process", "Product and manufacturing approval process conforming to the customer's (e.g. PPAP)", True),
    ("8.4.1.2", "Supplier selection process", "Documented supplier selection process with risk assessment", True),
    ("8.4.2.1", "Type and extent of control", "Documented process to identify outsourced processes and select controls", True),
    ("8.4.2.2", "Statutory and regulatory requirements", "Documented process so purchased products meet statutory requirements in receiving and destination countries", True),
    ("8.4.2.3", "Supplier QMS development", "Suppliers certified to ISO 9001 at minimum, developing toward IATF 16949", False),
    ("8.4.2.4", "Supplier monitoring", "Documented process and criteria: delivered quality, disruptions, delivery, special status", True),
    ("8.5.1.1", "Control plan", "Control plans for pre-launch and production with reaction plans; updated on changes", False),
    ("8.5.1.3", "Verification of job set-ups", "Set-up verification with documented instructions and first/last-off comparison", False),
    ("8.5.1.5", "Total productive maintenance", "Documented TPM system: maintenance objectives, spare parts, predictive and preventive maintenance", True),
    ("8.5.2.1", "Identification and traceability", "Traceability analysis and plan for all automotive products", False),
    ("8.5.6.1", "Control of changes - supplemental", "Documented change-control process with validation and customer notification", True),
    ("8.5.6.1.1", "Temporary change of process controls", "Documented process and list of approved alternate controls, with verification and restart criteria", True),
    ("8.6.2", "Layout inspection and functional testing", "Layout and functional tests per control plan (typically annually)", False),
    ("8.7.1.4", "Control of reworked product", "Documented rework process with risk analysis and customer approval where required", True),
    ("8.7.1.5", "Control of repaired product", "Documented repair process with customer concession", True),
    ("8.7.1.7", "Nonconforming product disposition", "Documented process for disposition of nonconforming product not subject to rework or repair", True),
    ("9.1.1.1", "Monitoring manufacturing processes", "Process studies on new processes; maintain capability per customer requirements", False),
    ("9.1.2.1", "Customer satisfaction - supplemental", "Monitor delivered quality, disruptions, field returns, delivery, premium freight, customer notifications", False),
    ("9.2.2.1", "Internal audit programme", "Documented audit programme covering QMS, manufacturing process and product audits over 3 years", True),
    ("9.2.2.3", "Manufacturing process audit", "Audit every manufacturing process over 3 years, covering all shifts, using the process approach", False),
    ("9.2.2.4", "Product audit", "Audit products at appropriate stages for conformity to all requirements", False),
    ("9.3.2.1", "Management review inputs - supplemental", "Cost of poor quality, process effectiveness, field failures, warranty, potential failures from FMEA", False),
    ("10.2.3", "Problem solving", "Documented problem-solving process with containment, root cause, verified actions and lessons learned", True),
    ("10.2.4", "Error-proofing", "Documented process for error-proofing methodology, tested at defined intervals", True),
    ("10.2.5", "Warranty management systems", "Documented warranty management process when warranty applies, including no-trouble-found", True),
    ("10.3.1", "Continual improvement - supplemental", "Documented continual improvement process with methodologies and objectives", True),
]
MAY_NA = {"7.1.5.3", "7.2.4", "10.2.5"}
# not documented-process clauses whose total absence is still a system breakdown
CORE = {"4.3.2", "7.1.5.1.1", "8.5.1.1", "9.2.2.3", "9.2.2.4"}
SCORE = {"met": 1.0, "partial": 0.5, "not-met": 0.0}


def template(customers):
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["clause", "title", "requirement", "documented_process", "status", "evidence"])
    for c, t, req, dp in REQS:
        w.writerow([c, t, req, "yes" if dp else "", "", ""])
    for cust in customers:
        w.writerow([f"CSR:{cust}", f"{cust} customer-specific requirements", "Latest CSR document reviewed, mapped in the CSR matrix and implemented", "", "", ""])
    return 0


def score(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"clause", "status"} <= set(rows[0]):
        print("error: worksheet needs clause and status columns (make it with --template)", file=sys.stderr)
        return 2
    by = {c: (t, dp) for c, t, _, dp in REQS}
    findings, scores, seen = [], [], set()
    for r in rows:
        c = r["clause"].strip()
        st = (r.get("status") or "").strip().lower().replace("not met", "not-met")
        ev = (r.get("evidence") or "").strip()
        seen.add(c)
        if c.startswith("CSR:"):
            if st != "met":
                findings.append(("IG002", "major", c, f"{c[4:]} CSRs are {st or 'not assessed'}: CSRs are audited as requirements"))
            scores.append(SCORE.get(st, 0.0))
            continue
        if c not in by:
            continue
        title, dp = by[c]
        label = f"{c} {title}"
        if st == "n/a":
            if c not in MAY_NA:
                findings.append(("IG006", "error", label, "cannot be not applicable"))
            continue
        if st not in SCORE:
            findings.append(("IG005", "check", label, f"status {st or 'blank'!r}"))
            continue
        scores.append(SCORE[st])
        if st == "not-met":
            if dp:
                findings.append(("IG001", "major", label, "required documented process missing"))
            elif c in CORE:
                findings.append(("IG003", "major", label, "not implemented: a core automotive control is absent"))
            else:
                findings.append(("IG003", "minor", label, "not implemented"))
        elif st == "partial":
            findings.append(("IG004", "minor", label, f"partial{' (documented process required)' if dp else ''}: {ev or 'no detail'}"))
        elif not ev:
            findings.append(("IG005", "check", label, "met without evidence"))
    for c, t, _, _ in REQS:
        if c not in seen:
            findings.append(("IG005", "check", f"{c} {t}", "missing from the worksheet"))
    if not any(c.startswith("CSR:") for c in seen):
        findings.append(("IG002", "major", "4.3.2", "no customer rows: list each customer's CSRs (--template --customers ...)"))
    pct = 100 * sum(scores) / len(scores) if scores else 0
    rank = {"error": 0, "major": 1, "minor": 2, "check": 3}
    findings.sort(key=lambda f: rank[f[1]])
    n = {k: sum(f[1] == k for f in findings) for k in rank}
    print(f"IATF-specific readiness: {pct:.1f}% ({len(scores)} rows)  majors {n['major']}, minors {n['minor']}, errors {n['error']}, checks {n['check']}\n")
    for code, sev, label, msg in findings:
        print(f"{code} [{sev}] {label}: {msg}")
    return 1 if n["major"] or n["error"] else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worksheet", nargs="?", help="filled worksheet CSV to score")
    ap.add_argument("--template", action="store_true", help="print the worksheet")
    ap.add_argument("--customers", nargs="*", default=[], help="customers whose CSRs need a row")
    ap.add_argument("--list-processes", action="store_true", help="list the required documented processes")
    a = ap.parse_args()
    if a.list_processes:
        for c, t, _, dp in REQS:
            if dp:
                print(f"{c:<11}{t}")
        print(f"\n{sum(1 for r in REQS if r[3])} documented processes")
        return 0
    if a.template:
        return template(a.customers)
    if not a.worksheet:
        ap.print_usage(sys.stderr)
        return 2
    return score(a.worksheet)


if __name__ == "__main__":
    sys.exit(main())
