# Choosing an Experimental Design

## By goal

| Goal | Factors | Design | Runs |
|------|---------|--------|------|
| Screening: which of many factors matter? | 5-8+ | Resolution III or IV fraction, or Plackett-Burman | 8-16 |
| Characterise: main effects and 2-factor interactions | 3-5 | Full factorial or resolution V | 8-32 |
| Optimise: find the best setting with curvature | 2-4 | Response surface (central composite, Box-Behnken) | 13-30 |
| Robustness: make the process insensitive to noise | control + noise | Crossed or combined arrays | varies |

## Two-level fractional factorials (standard generators)

| k | Runs | Design | Generators | Resolution |
|---|------|--------|------------|------------|
| 3 | 4 | 2^(3-1) | C = AB | III |
| 4 | 8 | 2^(4-1) | D = ABC | IV |
| 5 | 8 | 2^(5-2) | D = AB, E = AC | III |
| 5 | 16 | 2^(5-1) | E = ABCD | V |
| 6 | 8 | 2^(6-3) | D = AB, E = AC, F = BC | III |
| 6 | 16 | 2^(6-2) | E = ABC, F = BCD | IV |
| 6 | 32 | 2^(6-1) | F = ABCDE | VI |
| 7 | 8 | 2^(7-4) | D = AB, E = AC, F = BC, G = ABC | III |
| 7 | 16 | 2^(7-3) | E = ABC, F = BCD, G = ACD | IV |
| 7 | 32 | 2^(7-2) | F = ABCD, G = ABDE | IV |
| 8 | 16 | 2^(8-4) | E = BCD, F = ACD, G = ABC, H = ABD | IV |

| Resolution | Meaning |
|------------|---------|
| III | Main effects aliased with 2-factor interactions: screening only, follow up with a fold-over |
| IV | Main effects clear of 2FIs; 2FIs aliased with each other |
| V | Main effects and 2FIs clear (aliased only with higher-order terms) |

## Planning checklist

1. **Response:** measurable, with a capable measurement system (Gage R&R); state the goal (max, min, target).
2. **Factors and levels:** levels far enough apart to see an effect but within safe operating range.
3. **Hold constant** everything else (material lot, machine, operator) or block on it.
4. **Randomise** run order (`doe_design.py` does) to protect against drift.
5. **Replicates or centre points** to estimate pure error and curvature.
6. **Sample size:** to detect an effect of delta with noise sigma, total factorial runs N ~ (4 (z_a/2 + z_b) sigma / delta)^2;
   for delta = 2 sigma at 5% / 80% power that is about 16 runs.
7. **Run sheet** with actual settings; record anything unusual during each run.
