#!/usr/bin/env python3
"""Read pasted Minitab session output, extract the key numbers and flag what they mean.

Recognises: Process Capability (Cp, Cpk, Pp, Ppk, PPM), Gage R&R (%Study Var, %Tolerance, ndc), Regression
(coefficients, P-values, VIF, R-sq, R-sq(adj), R-sq(pred)), one-way ANOVA, t-tests (P-value, CI), normality
tests (AD, P-Value) and DOE coded coefficients. Text copied from the Session window or a report works; the
layout only needs the usual Minitab labels.

Flags (examples):
  capability  Cpk < 1.33; Ppk much below Cpk (shifts/drift); observed PPM far above expected
  gage r&r    %Study Var / %Tolerance > 10 or > 30; ndc < 5; significant Part*Operator
  regression  R-sq(pred) far below R-sq (overfitting); terms with P > 0.05; VIF > 5 (multicollinearity)
  tests       p-value vs alpha; confidence interval containing 0

Usage:
    python parse_minitab.py output.txt
    pbpaste | python parse_minitab.py - --alpha 0.05

Lines are marked WARN (a problem with the analysis or the process) or RESULT (the test conclusion).
Exit codes: 0 parsed, no warnings; 1 parsed with warnings; 2 nothing recognised or read error.
"""

import argparse
import re
import sys

NUM = r"(-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)"


def grab(text, label):
    m = re.search(rf"^\s*{label}\s+{NUM}\s*$", text, re.M)
    return float(m.group(1)) if m else None


def capability(t, out):
    v = {k: grab(t, k) for k in ("Cp", "Cpk", "Pp", "Ppk")}
    if v["Cpk"] is None and v["Ppk"] is None:
        return False
    out.append(("info", "Process capability: " + "  ".join(f"{k} {x:.2f}" for k, x in v.items() if x is not None)))
    m = re.search(rf"PPM Total\s+{NUM}\s+{NUM}\s+{NUM}", t)
    if m:
        obs, exp_o, exp_w = map(float, m.groups())
        out.append(("info", f"PPM total: observed {obs:,.0f}, expected overall {exp_o:,.0f}, expected within {exp_w:,.0f}"))
        if obs > 3 * max(exp_o, 1) and obs > 0:
            out.append(("warn", "observed PPM far above the normal-model prediction: special causes or non-normal tails"))
    if v["Cpk"] is not None and v["Cpk"] < 1.33:
        out.append(("warn", f"Cpk {v['Cpk']:.2f} < 1.33: not capable for most customer requirements"))
    if v["Cpk"] and v["Ppk"] and v["Ppk"] < 0.85 * v["Cpk"]:
        out.append(("warn", f"Ppk {v['Ppk']:.2f} well below Cpk {v['Cpk']:.2f}: between-subgroup shifts or drift - check the control chart"))
    if v["Cp"] and v["Cpk"] and v["Cpk"] < 0.75 * v["Cp"]:
        out.append(("warn", "Cpk much lower than Cp: process off centre"))
    return True


def gage(t, out):
    m = re.search(rf"Total Gage R&R\s+{NUM}\s+{NUM}\s+{NUM}(?:\s+{NUM})?", t)
    ndc = re.search(r"Number of Distinct Categories\s*=\s*(\d+)", t)
    if not m:
        return False
    sv, tol = float(m.group(3)), (float(m.group(4)) if m.group(4) else None)
    out.append(("info", f"Gage R&R: %Study Var {sv:.1f}%" + (f", %Tolerance {tol:.1f}%" if tol is not None else "")
                + (f", ndc {ndc.group(1)}" if ndc else "")))
    for name, val in (("%Study Var", sv), ("%Tolerance", tol)):
        if val is None:
            continue
        if val > 30:
            out.append(("warn", f"{name} {val:.1f}% > 30%: measurement system not acceptable"))
        elif val > 10:
            out.append(("warn", f"{name} {val:.1f}% between 10 and 30%: conditionally acceptable"))
    if ndc and int(ndc.group(1)) < 5:
        out.append(("warn", f"ndc {ndc.group(1)} < 5: gauge cannot distinguish enough part categories"))
    inter = re.search(rf"Part \* Operator\s+\d+\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}", t)
    if inter and float(inter.group(4)) < 0.05:
        out.append(("warn", "Part*Operator interaction significant: some operators measure some parts differently"))
    rep = re.search(rf"^\s+Repeatability\s+{NUM}", t, re.M)
    rpr = re.search(rf"^\s+Reproducibility\s+{NUM}", t, re.M)
    if rep and rpr:
        a, b = float(rep.group(1)), float(rpr.group(1))
        out.append(("info", "dominant component: " + ("repeatability (gauge / fixture)" if a > b else "reproducibility (operators / method)")))
    return True


def regression(t, out, alpha):
    ms = re.search(rf"R-sq\s+R-sq\(adj\)\s+R-sq\(pred\)\s*\n\s*{NUM}\s+{NUM}%\s+{NUM}%\s+{NUM}%", t)
    coef = re.search(r"Term\s+Coef\s+SE Coef\s+T-Value\s+P-Value(\s+VIF)?\n(.*?)(?:\n\s*\n|\Z)", t, re.S)
    if not (ms or coef) or "Regression" not in t:
        return False
    if ms:
        s, r2, r2a, r2p = map(float, ms.groups())
        out.append(("info", f"Regression: S {s:g}, R-sq {r2:.1f}%, R-sq(adj) {r2a:.1f}%, R-sq(pred) {r2p:.1f}%"))
        if r2 - r2p > 10:
            out.append(("warn", f"R-sq(pred) {r2p:.1f}% is {r2 - r2p:.0f} points below R-sq: the model is over-fitted; remove weak terms"))
    if coef:
        for line in coef.group(2).splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0] == "Constant":
                continue
            try:
                p = float(parts[4])
            except ValueError:
                continue
            vif = float(parts[5]) if len(parts) > 5 else None
            if p > alpha:
                out.append(("warn", f"term {parts[0]}: P-Value {p:.3f} > {alpha:g}: not significant; consider removing (one at a time)"))
            if vif and vif > 5:
                out.append(("warn", f"term {parts[0]}: VIF {vif:.1f} > 5: correlated with other predictors; coefficients unstable"))
    return True


def anova(t, out, alpha):
    if "Regression" in t or "Gage R&R" in t:
        return False
    m = re.search(rf"^\s*(Factor|[A-Za-z_]+)\s+(\d+)\s+{NUM}\s+{NUM}\s+{NUM}\s+{NUM}\s*$", t, re.M)
    if not (m and "Analysis of Variance" in t):
        return False
    f, p = float(m.group(5)), float(m.group(6))
    out.append(("info", f"One-way ANOVA: F {f:g}, P {p:g}"))
    out.append(("result", "at least one mean differs - run Tukey comparisons" if p < alpha
                else "no evidence that the means differ"))
    return True


def ttest(t, out, alpha):
    m = re.search(rf"T-Value\s+DF\s+P-Value\s*\n\s*{NUM}\s+{NUM}\s+{NUM}", t)
    if not m:
        return False
    tv, df, p = map(float, m.groups())
    out.append(("info", f"t-test: T {tv:g}, DF {df:g}, P-Value {p:g}"))
    ci = re.search(rf"\(\s*{NUM},\s*{NUM}\s*\)", t)
    if ci:
        lo, hi = float(ci.group(1)), float(ci.group(2))
        out.append(("info", f"confidence interval ({lo:g}, {hi:g}) " + ("contains 0: no difference shown" if lo <= 0 <= hi else "excludes 0: difference shown")))
    out.append(("result", f"P-Value {p:g} {'<' if p < alpha else '>='} {alpha:g}: " +
                ("reject H0 - the difference is statistically significant; judge whether its size matters" if p < alpha
                 else "fail to reject H0 - check the sample size before concluding there is no difference")))
    return True


def normality(t, out, alpha):
    m = re.search(rf"\bAD\s+{NUM}.*?P-Value\s+[<>]?\s*{NUM}", t, re.S)
    if not m or "Cpk" in t:
        return False
    ad, p = float(m.group(1)), float(m.group(2))
    out.append(("warn" if p < alpha else "info", f"Normality (Anderson-Darling): AD {ad:g}, P {p:g} -> " +
                ("not normal: find the cause or use non-normal methods" if p < alpha else "no evidence against normality")))
    return True


def doe(t, out, alpha):
    m = re.search(r"Coded Coefficients\s*\n\s*Term\s+Effect\s+Coef.*?P-Value.*?\n(.*?)(?:\n\s*\n|\Z)", t, re.S)
    if not m:
        return False
    sig = []
    for line in m.group(1).splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0] != "Constant":
            try:
                if float(parts[5]) < alpha:
                    sig.append(f"{parts[0]} (effect {parts[1]})")
            except ValueError:
                pass
    out.append(("info", "DOE significant terms: " + (", ".join(sig) if sig else "none")))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="text file with Minitab output, or - for stdin")
    ap.add_argument("--alpha", type=float, default=0.05)
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    text = text.replace("\t", "  ").replace("\r", "")
    out = []
    found = [name for name, fn in (("capability", lambda: capability(text, out)), ("gage", lambda: gage(text, out)),
                                   ("regression", lambda: regression(text, out, a.alpha)), ("anova", lambda: anova(text, out, a.alpha)),
                                   ("t-test", lambda: ttest(text, out, a.alpha)), ("normality", lambda: normality(text, out, a.alpha)),
                                   ("doe", lambda: doe(text, out, a.alpha))) if fn()]
    if not found:
        print("error: no recognised Minitab output (capability, Gage R&R, regression, ANOVA, t-test, normality, DOE)", file=sys.stderr)
        return 2
    print(f"Recognised: {', '.join(found)}\n")
    for kind, msg in out:
        print({"warn": "WARN    ", "result": "RESULT  "}.get(kind, "        ") + msg)
    return 1 if any(k == "warn" for k, _ in out) else 0


if __name__ == "__main__":
    sys.exit(main())
