#!/usr/bin/env python3
"""Check a language teacher's CV (Markdown or plain text) for what recruiters in ELT look for.

Checks:
  CV001 high    no recognised teaching qualification (CELTA, CertTESOL, TESOL/TEFL certificate, Delta, DipTESOL,
                PGCE/QTS, MA TESOL/Applied Linguistics)
  CV002 medium  experience with no numbers (years, hours, class sizes, results)
  CV003 medium  no learner levels or age groups (A1-C2, young learners, teens, adults, business)
  CV004 medium  duty phrases ('responsible for', 'duties included') instead of action verbs
  CV005 low     no exam or specialist teaching mentioned (IELTS, Cambridge, TOEFL, business, EAP...)
  CV006 low     length outside about 250-900 words (1-2 pages)
  CV007 low     personal details that UK/US/IE/CA/AU recruiters advise leaving out (age, date of birth,
                marital status, photo) - only with --region uk|us|ie|ca|au
  CV008 low     no email address

Usage:
    python cv_check.py cv.md [--region uk]

Exit codes: 0 no high findings, 1 high findings, 2 read error or empty file.
"""

import argparse
import re
import sys

QUAL = re.compile(r"\b(CELTA|CertTESOL|Cert\s?TESOL|DELTA|Delta|DipTESOL|TESOL|TEFL|TESL|PGCE|QTS|MA (in )?(TESOL|"
                  r"Applied Linguistics|ELT)|CELTYL|TKT)\b")
LEVELS = re.compile(r"\b([ABC][12]|beginner|elementary|intermediate|advanced|young learners?|children|teens|"
                    r"teenagers|adults?|business|primary|secondary|kindergarten)\b", re.I)
EXAMS = re.compile(r"\b(IELTS|TOEFL|TOEIC|Cambridge (English|exams?)|FCE|CAE|KET|PET|B2 First|C1 Advanced|"
                   r"Duolingo|PTE|EAP|ESP|business English|DELE|DELF|Goethe)\b", re.I)
DUTY = re.compile(r"\b(responsible for|duties (included|include)|tasks included|in charge of|helped with)\b", re.I)
PERSONAL = re.compile(r"\b(date of birth|DOB|age:|aged \d+|\d{2} years old|marital status|married|single|"
                      r"religion|photo)\b", re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cv")
    ap.add_argument("--region", type=str.lower, help="target job market, e.g. uk, us, ie, ca, au, asia, middle-east")
    a = ap.parse_args()
    try:
        text = open(a.cv, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    words = len(text.split())
    if not words:
        print("error: empty CV", file=sys.stderr)
        return 2
    exp = re.search(r"^#+\s*(teaching )?experience.*?$(.*?)(?=^#+\s|\Z)", text, re.I | re.M | re.S)
    exp_text = exp.group(2) if exp else text
    f = []
    quals = sorted({m.group(0) for m in QUAL.finditer(text)})
    if not quals:
        f.append(("CV001", "high", "no teaching qualification found: most employers require CELTA/CertTESOL or equivalent"))
    if not re.search(r"\d", re.sub(r"\b(19|20)\d{2}\b", "", exp_text)):
        f.append(("CV002", "medium", "experience has no numbers: add hours, class sizes, levels, results"))
    if not LEVELS.search(text):
        f.append(("CV003", "medium", "say which levels and ages you have taught"))
    duty = sorted({m.group(0).lower() for m in DUTY.finditer(text)})
    if duty:
        f.append(("CV004", "medium", f"duty phrases ({', '.join(duty)}): start bullets with action verbs (taught, designed, prepared)"))
    if not EXAMS.search(text):
        f.append(("CV005", "low", "no exam or specialist teaching (IELTS, Cambridge, business, EAP) - add it if you have it"))
    if not 250 <= words <= 900:
        f.append(("CV006", "low", f"{words} words; 1-2 pages (about 250-900 words) suits most ELT jobs"))
    if a.region in ("uk", "us", "ie", "ca", "au"):
        personal = sorted({m.group(0).lower() for m in PERSONAL.finditer(text)})
        if personal:
            f.append(("CV007", "low", f"{a.region.upper()} recruiters usually do not expect: {', '.join(personal)}"))
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
        f.append(("CV008", "low", "no email address"))
    print(f"{words} words; qualifications found: {', '.join(quals) or 'none'}")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: qualifications, specific experience and contact details are clear")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
