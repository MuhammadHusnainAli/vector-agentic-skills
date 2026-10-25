#!/usr/bin/env python3
"""AS9100D / EN 9100:2018 gap check for the aviation, space and defence requirements added to ISO 9001.

Two modes:
  --template          print a CSV worksheet of the AS9100-specific requirements (paraphrased)
  <worksheet.csv>     score a filled worksheet (status met / partial / not-met / n/a, evidence)

Grading:
  AG001 major   core aerospace control not met: operational risk, configuration management, product safety,
                counterfeit prevention, FAI, special processes, external provider register, nonconforming
                product control, FOD prevention
  AG002 minor   other requirement not met
  AG003 minor   partially implemented
  AG004 check   met without evidence, missing row or invalid status
  AG005 error   n/a where it cannot apply (only 8.3.4.1 design testing and 8.5.5 in-service data when
                no design / post-delivery responsibility)

Run the iso-9001-gap-analyzer worksheet alongside: the ISO 9001 text is part of AS9100.

Usage:
    python as9100_gap.py --template > as9100.csv
    python as9100_gap.py as9100.csv

Exit codes: 0 no major gaps, 1 major gaps or errors, 2 usage or read error.
"""

import argparse
import csv
import sys

# (clause, title, requirement, core)
REQS = [
    ("5.1.2", "Customer focus", "Product and service conformity and on-time delivery performance measured and acted on", False),
    ("5.3", "Management representative", "A management representative appointed with authority over the QMS", False),
    ("7.1.5.2", "Measurement traceability", "Register of monitoring and measuring equipment with calibration method, frequency and acceptance; recall process", False),
    ("7.2", "Competence", "Competence including product safety and human factors where relevant", False),
    ("7.3", "Awareness", "Awareness of contribution to product conformity, product safety and ethical behaviour", False),
    ("7.5.1", "QMS documentation", "Documented information describing interested parties, scope, processes and their interaction, responsibilities", False),
    ("7.5.3.2", "Data protection", "Protect documented information from loss, unauthorized changes, corruption; control of data", False),
    ("8.1", "Operational planning", "Plan for personal and product safety, producibility, inspectability, reliability, maintainability; key characteristics; work transfer control", False),
    ("8.1.1", "Operational risk management", "Process to identify, assess, mitigate, accept and communicate operational risks", True),
    ("8.1.2", "Configuration management", "Process for configuration identification, change control, status accounting and audits", True),
    ("8.1.3", "Product safety", "Process to assure product safety across the life cycle: hazards, critical items, reporting of events", True),
    ("8.1.4", "Prevention of counterfeit parts", "Process for counterfeit-part prevention: training, sourcing from OEM/authorized channels, verification, reporting, quarantine", True),
    ("8.2.2", "Special requirements and critical items", "Identify special requirements, critical items and key characteristics in requirements review", False),
    ("8.2.3", "Review of requirements", "Review includes special requirements and risks; coordinate with customer on unresolved items", False),
    ("8.3.4.1", "Verification and validation testing", "Test plans, specifications and acceptance criteria for design verification and validation", False),
    ("8.3.5", "Design outputs", "Outputs specify key characteristics, critical items and data to produce, inspect, install and maintain", False),
    ("8.4.1", "External providers", "Register of external providers with approval status and scope; periodic performance review (conformity, OTD); customer-designated sources", True),
    ("8.4.2", "Verification of external provision", "Verification including source inspection, test report validation, and customer verification at provider", False),
    ("8.4.3", "Information for external providers", "Flow-down of requirements: key characteristics, test specs, right of access, records retention, counterfeit prevention, ethics", False),
    ("8.5.1", "Production control - FOD", "Prevention, detection and removal of foreign objects (FOD); control of tooling, critical items and environment", True),
    ("8.5.1.1", "Equipment, tools and software programs", "Validate and control production equipment, tools and NC programs; storage and periodic inspection", False),
    ("8.5.1.2", "Special processes", "Validate special processes: qualified equipment and people, approved methods, records, revalidation", True),
    ("8.5.1.3", "Production process verification (FAI)", "First article inspection per AS9102 on the first production run and after changes", True),
    ("8.5.2", "Identification and traceability", "Traceability through product life: lot/serial, as-built configuration, records", False),
    ("8.5.4", "Preservation", "Includes FOD prevention, shelf-life control, hazardous material handling, special handling", False),
    ("8.5.5", "Post-delivery activities", "Collect and analyse in-service data; technical documentation; repairs and maintenance", False),
    ("8.5.6", "Control of changes", "Persons authorized to approve production process changes; customer notification where required", False),
    ("8.6", "Release of products", "Authorized release, required documentation accompanies product, inspection and test records", False),
    ("8.7.1", "Nonconforming outputs", "MRB authority; customer approval for use-as-is or repair on customer designs; scrap made unusable; counterfeit or suspect parts controlled and reported", True),
    ("9.1.2", "Customer satisfaction", "Monitor conformity, on-time delivery, complaints and corrective action requests; improvement plans", False),
    ("9.3.2", "Management review inputs", "On-time delivery performance included", False),
    ("10.2.1", "Corrective action", "Flow corrective action to providers when they are responsible; human factors in root cause; act when actions are not timely or effective", False),
]
MAY_NA = {"8.3.4.1", "8.3.5", "8.5.5"}
SCORE = {"met": 1.0, "partial": 0.5, "not-met": 0.0}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worksheet", nargs="?")
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    if a.template:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["clause", "title", "requirement", "core", "status", "evidence"])
        for c, t, r, core in REQS:
            w.writerow([c, t, r, "yes" if core else "", "", ""])
        return 0
    if not a.worksheet:
        ap.print_usage(sys.stderr)
        return 2
    try:
        with open(a.worksheet, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"clause", "status"} <= set(rows[0]):
        print("error: worksheet needs clause and status columns (make it with --template)", file=sys.stderr)
        return 2
    by = {c: (t, core) for c, t, _, core in REQS}
    findings, scores, seen = [], [], set()
    for r in rows:
        c = r["clause"].strip()
        if c not in by:
            continue
        seen.add(c)
        title, core = by[c]
        label = f"{c} {title}"
        st = (r.get("status") or "").strip().lower().replace("not met", "not-met")
        ev = (r.get("evidence") or "").strip()
        if st == "n/a":
            if c not in MAY_NA:
                findings.append(("AG005", "error", label, "cannot be not applicable"))
            continue
        if st not in SCORE:
            findings.append(("AG004", "check", label, f"status {st or 'blank'!r}"))
            continue
        scores.append(SCORE[st])
        if st == "not-met":
            findings.append(("AG001", "major", label, "core aerospace control missing") if core else
                            ("AG002", "minor", label, "not implemented"))
        elif st == "partial":
            findings.append(("AG003", "minor", label, f"partial: {ev or 'no detail'}"))
        elif not ev:
            findings.append(("AG004", "check", label, "met without evidence"))
    for c, t, _, _ in REQS:
        if c not in seen:
            findings.append(("AG004", "check", f"{c} {t}", "missing from the worksheet"))
    rank = {"error": 0, "major": 1, "minor": 2, "check": 3}
    findings.sort(key=lambda f: rank[f[1]])
    n = {k: sum(f[1] == k for f in findings) for k in rank}
    pct = 100 * sum(scores) / len(scores) if scores else 0
    print(f"AS9100-specific readiness: {pct:.1f}% ({len(scores)} rows)  majors {n['major']}, minors {n['minor']}, errors {n['error']}, checks {n['check']}\n")
    for code, sev, label, msg in findings:
        print(f"{code} [{sev}] {label}: {msg}")
    return 1 if n["major"] or n["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
