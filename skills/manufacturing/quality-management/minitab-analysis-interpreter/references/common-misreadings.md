# Common Misreadings of Minitab Output

| Misreading | Correct reading |
|------------|-----------------|
| "P = 0.20, so the groups are the same" | No evidence of a difference with this sample; check power / CI width |
| "P = 0.001, so the effect is big" | Significant only; the CI and effect size say how big |
| "R-sq 95%, great model" | Check R-sq(pred) and residuals; many terms inflate R-sq |
| "Cpk 1.35 so we are capable" | Check stability (control chart), normality, the CI of Cpk and Ppk |
| "%Contribution 5% means the gauge is 5% of tolerance" | %Contribution is a variance share; %Tolerance compares 6 SD to the tolerance |
| "Insignificant term: delete all of them at once" | Remove one term at a time (highest P first), respect hierarchy for interactions |
| "Normality test failed, so the analysis is invalid" | t-tests/ANOVA are robust with moderate n; capability and individual-value limits are not |
| "VIF 8 is fine because P is small" | Collinearity makes the coefficient unstable even if significant; redesign or drop a predictor |
| "Gage R&R acceptable, so the gauge is accurate" | R&R is precision; bias and linearity are separate studies |
| "ANOVA significant, so every group differs" | At least one differs; use Tukey / Hsu comparisons |
