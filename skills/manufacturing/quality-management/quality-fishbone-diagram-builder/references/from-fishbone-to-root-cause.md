# From Fishbone to Verified Root Cause

A fishbone lists **possible** causes. It never proves one. Use it to organise the brainstorm, then narrow and test.

## Session (45-60 minutes)

1. Write the effect at the head: factual, specific ("Scratches 5-12 mm on HS-110 face A, 15% of 2 lots").
2. Silent brainstorm on sticky notes (5 minutes), then place each on a bone.
3. Use the prompts for empty bones; ask "why" once or twice on big causes to add sub-causes.
4. Remove duplicates; reword solutions and blame as conditions.
5. Use data you already have to rule out causes (is / is-not, lot history): mark them ruled out with the reason.
6. Multi-vote (each person 3 votes) to pick the likely causes.
7. Plan a test for each likely cause.

## Verification plan

| Cause | Test | Expected if true | Owner | Due | Result |
|-------|------|------------------|-------|-----|--------|
| Open trays, no dividers | Transport 40 parts with and without dividers | Scratches only without dividers | Process engineer | 2 days | 14/40 vs 0/40 -> verified |
| Inspection light < 1000 lux | Measure lux; re-inspect 50 parts under 1500 lux | More scratches found under good light | Quality | 1 day | ... |
| Forklift vibration | Accelerometer on pallet over joints | Peaks match scratch locations | Maintenance | 3 days | ... |

Mark each cause `verified`, `ruled-out` or `likely` in the CSV and rerun `fishbone.py` to keep the diagram as the
investigation record.

## Next tools

| Need | Tool |
|------|------|
| Chain from a verified cause to the system cause | 5 Why (occurrence and escape legs) |
| Several interacting factors | Design of experiments |
| Pattern in variation (within part, part-to-part, time) | Multi-vari study |
| Which cause matters most | Pareto of defect data by cause |
