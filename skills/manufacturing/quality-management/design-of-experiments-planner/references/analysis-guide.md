# Analysing a Two-Level Experiment

## Effects

Effect = mean response at the high level - mean response at the low level. In coded units the regression
coefficient is half the effect. Interaction AB = (effect of A at B high - effect of A at B low) / 2.

## Which effects are real?

| Situation | Method |
|-----------|--------|
| Replicated runs | t-test of each effect: SE(effect) = 2 s / sqrt(N), df from pure error |
| Unreplicated | Lenth's method: PSE = 1.5 x median of |effects| below 2.5 s0 (s0 = 1.5 median |effect|); ME = t(0.975, m/3) x PSE |
| Visual | Half-normal plot: real effects fall off the line through the small ones |

Lenth relies on effect sparsity: most effects are noise. With few factors (2-3) and no replicates there is not
enough information; replicate.

## Curvature

Centre points compare the centre mean with the factorial mean. Significant curvature means the response is not
linear in at least one factor: add axial points (central composite design) to find the optimum.

## Aliases

In a fraction, each estimated effect is a sum of aliased effects (AB = CD in a 2^(4-1)). Use process knowledge
(hierarchy: interactions usually involve factors with large main effects) or a fold-over run set to separate them.

## From model to action

1. Keep significant terms (and the main effects of any significant interaction).
2. Interpret interactions with an interaction plot: the best level of A depends on B.
3. Predict the response at the proposed settings; check it against the specification.
4. **Confirmation runs** at the chosen settings: 3-5 runs whose mean falls within the prediction interval.
5. Update the control plan with the new settings and their tolerances.
