#!/usr/bin/env python3
"""Pick the right hypothesis test from the data types and the question (Six Sigma roadmap).

Answers: test, null hypothesis, assumptions to check, non-parametric alternative, run_test.py command and
the Minitab menu path.

Usage:
    python pick_test.py --y continuous --x 2-groups
    python pick_test.py --y continuous --x 2-groups --paired --not-normal
    python pick_test.py --y proportion --x k-groups
    python pick_test.py --y continuous --x none --compare variance
    python pick_test.py --y continuous --x continuous

Y: continuous | proportion (pass/fail) | count (defects)
X: none (compare with a target) | 2-groups | k-groups | continuous
Exit codes: 0 recommendation printed, 2 combination not covered.
"""

import argparse
import sys

T = {
    ("continuous", "none", "mean"): ("1-sample t-test", "mean = target", "normal data (or n >= 30), independent",
                                     "1-sample Wilcoxon / sign test (median)", "t1", "Stat > Basic Statistics > 1-Sample t"),
    ("continuous", "none", "variance"): ("Chi-square test for one variance", "sigma = target", "normal data (sensitive to non-normality)",
                                         "Bonett method (Minitab 1 Variance)", None, "Stat > Basic Statistics > 1 Variance"),
    ("continuous", "2-groups", "mean"): ("2-sample t-test (Welch, unequal variances)", "mean1 = mean2", "normal in each group (or n >= 15 each), independent groups",
                                         "Mann-Whitney test (medians)", "t2", "Stat > Basic Statistics > 2-Sample t"),
    ("continuous", "2-groups-paired", "mean"): ("Paired t-test", "mean difference = 0", "differences approximately normal; same units measured twice",
                                                "Wilcoxon signed-rank on the differences", "paired", "Stat > Basic Statistics > Paired t"),
    ("continuous", "2-groups", "variance"): ("F-test for two variances (normal) or Levene's test", "sigma1 = sigma2", "F-test needs normal data; Levene is robust",
                                             "Levene / Brown-Forsythe", "var2", "Stat > Basic Statistics > 2 Variances"),
    ("continuous", "k-groups", "mean"): ("One-way ANOVA", "all means equal", "normal residuals, equal variances (check with Levene), independent",
                                         "Kruskal-Wallis (or Mood's median for outliers)", "anova", "Stat > ANOVA > One-Way"),
    ("continuous", "k-groups", "variance"): ("Bartlett's (normal) or Levene's test", "all variances equal", "Bartlett needs normal data",
                                             "Levene", None, "Stat > ANOVA > Test for Equal Variances"),
    ("continuous", "continuous", "mean"): ("Correlation and simple regression", "slope = 0 (no linear relation)", "linear relation, normal residuals with constant variance",
                                           "Spearman rank correlation", None, "Stat > Regression > Fitted Line Plot"),
    ("proportion", "none", "mean"): ("1-proportion test (exact binomial)", "p = target", "independent trials, fixed n",
                                     "-", None, "Stat > Basic Statistics > 1 Proportion"),
    ("proportion", "2-groups", "mean"): ("2-proportion test (Fisher's exact for small counts)", "p1 = p2", "independent samples; n*p >= 5 for the normal approximation",
                                         "Fisher's exact test", "prop2", "Stat > Basic Statistics > 2 Proportions"),
    ("proportion", "2-groups-paired", "mean"): ("McNemar's test", "no change in proportion", "same units classified twice",
                                                "-", None, "Stat > Tables > Cross Tabulation (McNemar)"),
    ("proportion", "k-groups", "mean"): ("Chi-square test of association", "proportion independent of group", "expected count >= 5 in at least 80% of cells",
                                         "Fisher's exact (2x2) / combine categories", "chi2", "Stat > Tables > Chi-Square Test for Association"),
    ("proportion", "continuous", "mean"): ("Binary logistic regression", "X has no effect on the odds", "independent observations, enough events",
                                           "-", None, "Stat > Regression > Binary Logistic Regression"),
    ("count", "none", "mean"): ("1-sample Poisson rate test", "rate = target", "counts per equal opportunity, independent events",
                                "-", None, "Stat > Basic Statistics > 1-Sample Poisson Rate"),
    ("count", "2-groups", "mean"): ("2-sample Poisson rate test", "rate1 = rate2", "Poisson counts, known exposure",
                                    "-", None, "Stat > Basic Statistics > 2-Sample Poisson Rate"),
    ("count", "k-groups", "mean"): ("Chi-square goodness of fit / Poisson regression", "rates equal across groups", "expected counts >= 5",
                                    "-", "chi2", "Stat > Tables > Chi-Square Goodness-of-Fit"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--y", required=True, choices=["continuous", "proportion", "count"])
    ap.add_argument("--x", required=True, choices=["none", "2-groups", "k-groups", "continuous"])
    ap.add_argument("--compare", choices=["mean", "variance"], default="mean", help="location (mean/median) or spread")
    ap.add_argument("--paired", action="store_true", help="the same units measured under both conditions")
    ap.add_argument("--not-normal", action="store_true", help="data are clearly non-normal / small samples with outliers")
    a = ap.parse_args()
    x = a.x + ("-paired" if a.paired and a.x == "2-groups" else "")
    key = (a.y, x, a.compare if a.y == "continuous" else "mean")
    if key not in T:
        print(f"error: no standard test for Y={a.y}, X={x}, compare={a.compare}", file=sys.stderr)
        return 2
    test, h0, assume, alt, cmd, menu = T[key]
    if a.not_normal and alt not in ("-", "") and a.y == "continuous":
        print(f"Recommended: {alt}   (non-normal data; parametric choice would be {test})")
    else:
        print(f"Recommended: {test}")
    print(f"  H0: {h0}   (H1: not equal, or one-sided if the question is directional and fixed before the data)")
    print(f"  Assumptions: {assume}")
    print(f"  Non-parametric alternative: {alt}")
    print(f"  Minitab: {menu}")
    if cmd:
        print(f"  Run it: python scripts/run_test.py {cmd} ...")
    print("  Report the effect size and confidence interval, not only the p-value; check the sample size is enough "
          "to detect the difference that matters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
