# Green Belt Formula Sheet

## Defects and yield
DPU = D / U; DPO = D / (U x O); DPMO = DPO x 10^6; FTY = units passing first time / units in;
RTY = product of step FTYs (~ e^-DPU for Poisson defects); sigma (short term) = Phi^-1(1 - DPMO/10^6) + 1.5.

## Lean
Takt = available time / customer demand; Little's law: lead time = WIP / throughput; OEE = availability x
performance x quality.

## Basic statistics
mean, s = sqrt(sum (x - mean)^2 / (n - 1)); standard error = s / sqrt(n); 95% CI for the mean ~ mean +/- t s / sqrt(n).

## Capability
Cp = (USL - LSL) / 6 sigma_within; Cpk = min(USL - mean, mean - LSL) / 3 sigma_within; Pp, Ppk the same with
overall s; sigma_within = R-bar / d2 or MR-bar / 1.128.

## MSA
%Study Var = 100 sigma_GRR / sigma_total; %Tolerance = 100 x 6 sigma_GRR / (USL - LSL);
ndc = 1.41 sigma_parts / sigma_GRR; criteria < 10% good, 10-30% conditional, > 30% bad; ndc >= 5.

## Control charts
X-bar: X-double-bar +/- A2 R-bar; R: D3 R-bar, D4 R-bar; I: x-bar +/- 2.66 MR-bar; MR UCL = 3.267 MR-bar;
p: p-bar +/- 3 sqrt(p-bar (1 - p-bar) / n); c: c-bar +/- 3 sqrt(c-bar); u: u-bar +/- 3 sqrt(u-bar / n).
Constants n = 5: A2 0.577, D3 0, D4 2.114, d2 2.326.

## Hypothesis tests
t (1-sample) = (mean - mu0) / (s / sqrt(n)); 2-sample Welch t = (m1 - m2) / sqrt(s1^2/n1 + s2^2/n2);
chi-square = sum (O - E)^2 / E; F = s1^2 / s2^2; reject H0 when p < alpha.

## Regression
r = cov(x, y) / (s_x s_y); R-sq = r^2 (simple regression); slope b1 = r s_y / s_x; b0 = y-bar - b1 x-bar.

## DOE
Runs = 2^(k - p); effect = mean(+) - mean(-); coefficient = effect / 2; resolution = length of the shortest word
in the defining relation.
