# Control Plan Structure (AIAG Control Plan, IATF 16949 8.5.1.1 and Annex A)

## Phases

| Phase | When | Content |
|-------|------|---------|
| Prototype | Prototype builds | Dimensional measurements, material and performance tests |
| Pre-launch | After prototype, before production | Production controls plus extra inspection (safe launch), more frequent checks |
| Production | Mass production | Ongoing product and process controls |

## Columns

| Column | Content | Example |
|--------|---------|---------|
| Part / process number | From the process flow diagram | OP20 |
| Process name / operation | Step description | Finish bore |
| Machine, device, jig, tools | Equipment used | CNC lathe 3, boring bar BB-12 |
| Characteristic number | Cross-reference to drawing balloon / PFMEA | 7 |
| Product characteristic | Feature of the part | Bore diameter |
| Process characteristic | Process variable that drives the feature | Insert life, spindle speed |
| Special characteristic class | CC / SC or customer symbol | SC |
| Specification / tolerance | From drawing or process sheet | 12.000 +0.018/-0.000 mm |
| Evaluation / measurement technique | Gauge or method (with MSA) | Air gauge AG-07 |
| Sample size and frequency | How many, how often | 1 every 10 parts |
| Control method | How the process is controlled | X-bar/R chart, error-proofing, check sheet |
| Reaction plan | What happens on nonconformity or out-of-control | See reaction-plans.md |

## Rules auditors check

- Every special characteristic has a row with a strong control: SPC with reaction, 100% automatic inspection or
  error-proofing. Sampling with a check sheet alone is not enough for CC/SC.
- Every gauge in the plan has an MSA study (IATF 7.1.5.1.1).
- Controls match the PFMEA: every prevention and detection control in the PFMEA is in the plan and vice versa.
- Error-proofing devices are verified at a defined frequency (start of shift with a red rabbit), and the
  verification is itself in the plan (IATF 10.2.4).
- The plan is reviewed and updated on any change affecting product, process, measurement, logistics, supply
  sources, production volume or PFMEA (IATF 8.5.1.1).
- IATF Annex A lists the minimum content; customer CSRs may add more (e.g. layout frequency, packaging checks).

## Family control plans

One control plan may cover a family of parts made by a common process, if the characteristics and controls are
the same. Part-specific characteristics need part-specific rows.
