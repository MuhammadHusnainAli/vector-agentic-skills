# Chart Patterns and Typical Manufacturing Causes

| Pattern | Rule | Typical causes | First checks |
|---------|------|----------------|--------------|
| Single point out | WE1 | Measurement error, wrong part, broken tool, material defect, data entry | Re-measure the part; check gauge; check the record |
| Sudden shift | WE2, WE4 / N2 | Offset or setting change, new material lot, new operator or shift, after maintenance, new tool | What changed at the first point of the run? Check the change log |
| Gradual shift | WE3 | Warm-up, small offset drift, fixture loosening | Time since start-up, temperature log |
| Trend | N3 | Tool wear, abrasive wear, chemical bath depletion, heating | Tool life counter, bath analysis; set tool change or replenishment |
| Saw-tooth / alternating | N4 | Operator adjusting after every point (tampering), two spindles or cavities alternating | Adjustment log; chart streams separately |
| Hugging the centre | N7 | Subgroups mix streams (limits too wide), limits from an old, worse baseline, data edited | How subgroups are formed; recalculate limits from current data |
| Points avoid the centre | N8 | Two populations: two machines, two material sources, two gauges | Stratify by source |
| Cycles | (visual) | Shift patterns, ambient temperature, maintenance cycle | Overlay time of day / shift |

## Responding

1. **Stop and contain** if the signal could mean nonconforming parts (follow the control plan reaction plan).
2. **Find what changed** at the start of the pattern (who, what, when, which machine or lot).
3. **Fix the cause**, not the symptom: adjusting the offset back without knowing why it moved is tampering.
4. **Annotate the chart** with the cause and action; unexplained signals are worth more investigation than
   explained ones.
5. **Do not recalculate limits** to make signals disappear; recalculate only after a deliberate, verified process
   improvement.
