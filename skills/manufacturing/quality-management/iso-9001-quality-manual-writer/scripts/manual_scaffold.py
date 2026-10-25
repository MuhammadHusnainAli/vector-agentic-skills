#!/usr/bin/env python3
"""Generate an ISO 9001:2015 quality manual draft in Markdown from a JSON company profile.

The manual is built around the company's own processes (process map, interaction table, owners, KPIs)
rather than repeating the standard, and ends with a clause cross-reference so an auditor can find each
requirement. Placeholders the user must complete are marked TODO.

Profile (JSON):
  {
    "company": "Acme Precision Ltd",
    "sites": ["Unit 4, Leeds, UK"],
    "products": "CNC-machined aluminium and steel components to customer drawings",
    "exclusions": [{"clause": "8.3", "justification": "All parts are made to customer-owned designs"}],
    "policy": "We supply parts that ...",
    "processes": [
      {"name": "Sales and contract review", "type": "core", "owner": "Sales manager",
       "inputs": "RFQ, drawings", "outputs": "Accepted order", "kpi": "Quote turnaround < 3 days",
       "documents": ["QP-02 Contract review"], "clauses": ["8.2"]}
    ],
    "approved_by": "Managing Director", "revision": "A"
  }
Process "type" is core, support or management.

Usage:
    python manual_scaffold.py profile.json > quality-manual.md
    cat profile.json | python manual_scaffold.py -

Exit codes: 0 written, 1 profile has an invalid exclusion, 2 read or JSON error.
"""

import argparse
import json
import sys

MAY_NOT_APPLY = {"7.1.5": "Monitoring and measuring resources", "8.3": "Design and development",
                 "8.5.3": "Property belonging to customers or external providers", "8.5.5": "Post-delivery activities"}
SECTIONS = [  # (clause, title) for the cross-reference
    ("4", "Context of the organization"), ("5", "Leadership"), ("6", "Planning"), ("7", "Support"),
    ("8", "Operation"), ("9", "Performance evaluation"), ("10", "Improvement")]
DEFAULT_LINKS = {"4": "Section 2-3", "5": "Section 4-5", "6": "Section 6", "7": "Section 7",
                 "9": "Section 9", "10": "Section 10"}


def load(path):
    fh = sys.stdin if path == "-" else open(path, encoding="utf-8")
    with fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not data.get("company"):
        raise ValueError("profile must be a JSON object with at least 'company'")
    return data


def check_exclusions(p):
    errors = []
    for e in p.get("exclusions", []):
        c = str(e.get("clause", ""))
        if c not in MAY_NOT_APPLY:
            errors.append(f"clause {c} cannot be excluded; only {', '.join(MAY_NOT_APPLY)} may be declared not applicable")
        elif len(e.get("justification", "").split()) < 5:
            errors.append(f"clause {c}: justification is missing or too short to convince an auditor")
    return errors


def process_table(procs):
    rows = ["| Process | Type | Owner | Inputs | Outputs | KPI | Documented information |",
            "|---------|------|-------|--------|---------|-----|------------------------|"]
    for pr in procs:
        rows.append(f"| {pr.get('name', 'TODO')} | {pr.get('type', 'core')} | {pr.get('owner', 'TODO')} | "
                    f"{pr.get('inputs', 'TODO')} | {pr.get('outputs', 'TODO')} | {pr.get('kpi', 'TODO')} | "
                    f"{', '.join(pr.get('documents', [])) or 'TODO'} |")
    return "\n".join(rows)


def interaction(procs):
    core = [pr["name"] for pr in procs if pr.get("type", "core") == "core"]
    other = [pr["name"] for pr in procs if pr.get("type", "core") != "core"]
    flow = " -> ".join(core) if core else "TODO"
    return (f"Customer requirements -> {flow} -> Satisfied customer\n\n"
            f"Support and management processes ({', '.join(other) or 'TODO'}) supply resources, "
            "monitoring and improvement to every core process.")


def crossref(p):
    by_clause = {}
    for pr in p.get("processes", []):
        for c in pr.get("clauses", []):
            by_clause.setdefault(str(c).split(".")[0], []).append(pr["name"])
    excluded = {e["clause"] for e in p.get("exclusions", [])}
    rows = ["| ISO 9001 clause | Where it is addressed |", "|-----------------|-----------------------|"]
    for num, title in SECTIONS:
        where = by_clause.get(num) or ([DEFAULT_LINKS[num]] if num in DEFAULT_LINKS else ["TODO"])
        rows.append(f"| {num} {title} | {', '.join(where)} |")
    for c in sorted(excluded):
        rows.append(f"| {c} {MAY_NOT_APPLY[c]} | Not applicable - see Section 1.2 |")
    return "\n".join(rows)


def render(p):
    procs = p.get("processes", [])
    excl = p.get("exclusions", [])
    excl_text = "\n".join(f"- **{e['clause']} {MAY_NOT_APPLY[e['clause']]}** - {e['justification']}" for e in excl) \
        or "- None. All requirements of ISO 9001:2015 apply."
    sites = "\n".join(f"- {s}" for s in p.get("sites", [])) or "- TODO list every site in scope"
    return f"""# {p['company']} - Quality Manual

| Revision | Approved by | Date |
|----------|-------------|------|
| {p.get('revision', 'A')} | {p.get('approved_by', 'TODO')} | TODO |

## 1. Scope of the quality management system (4.3)

### 1.1 Products, services and sites
{p['company']} supplies:
{p.get('products', 'TODO describe products and services')}

Sites:
{sites}

### 1.2 Requirements not applicable
{excl_text}

## 2. Context of the organization (4.1, 4.2)
Internal and external issues, including whether climate change is a relevant issue, are recorded in TODO
(issue register) and reviewed at every management review. Interested parties and their relevant requirements
are recorded in TODO (interested-party register).

## 3. Processes and their interaction (4.4)
{process_table(procs)}

{interaction(procs)}

## 4. Quality policy (5.2)
{p.get('policy', 'TODO insert the approved quality policy')}

## 5. Leadership, roles and responsibilities (5.1, 5.3)
TODO: organization chart reference; who reports QMS performance to top management; who has authority to
stop production and release product.

## 6. Planning (6.1, 6.2, 6.3)
Risks and opportunities: TODO (register reference). Quality objectives and plans: TODO (objectives register).
Changes to the QMS are planned through TODO (change procedure or management review).

## 7. Support (7.1-7.5)
Resources, infrastructure maintenance, calibration, competence, awareness, communication and control of
documented information: TODO reference the procedures and registers that apply.

## 8. Operation (8.1-8.7)
Operational processes are listed in Section 3. TODO add any operational controls not covered there
(special processes, customer property, preservation, release, nonconforming output).

## 9. Performance evaluation (9.1-9.3)
KPIs per process (Section 3), customer satisfaction method TODO, internal audit programme TODO,
management review at least TODO times per year.

## 10. Improvement (10.1-10.3)
Nonconformities and corrective actions are handled through TODO (NCR/CAPA procedure); improvement projects
are selected at management review.

## Appendix A - ISO 9001:2015 cross-reference
{crossref(p)}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profile", help="JSON company profile, or - for stdin")
    a = ap.parse_args()
    try:
        p = load(a.profile)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errors = check_exclusions(p)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    print(render(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
