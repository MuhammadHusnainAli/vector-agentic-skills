# Layered Process Audit System Design (AIAG CQI-8)

An LPA is a short, frequent check by several management layers that the **critical process controls** are in place
at the point of use. It finds drift before it becomes defects and puts leaders on the floor. Automotive OEMs
(e.g. GM BIQS, Stellantis) require LPAs from suppliers; IATF 16949 manufacturing process audits (9.2.2.3) and
CQI-8 describe the practice.

## Layers and frequency

| Layer | Who | Frequency | Scope |
|-------|-----|-----------|-------|
| 1 | Team leaders, supervisors | Every shift or daily, own area | All stations over the week |
| 2 | Area / department managers, engineers | Weekly, rotating areas | Different area each week |
| 3 | Plant manager, quality manager, staff heads | Monthly, rotating | Whole plant over a quarter |
| 4 (optional) | Executives | Quarterly | High-risk areas |

Higher layers audit less often but use the **same questions**: differences in results between layers reveal
whether layer-1 audits are rigorous.

## Design rules

1. **5-15 questions, 10-15 minutes.** Long checklists kill frequency.
2. **Yes/no answers about controls**, verified by looking, not asking.
3. **Questions from risk:** high-RPN / high-AP PFMEA lines, control plan reaction plans, special characteristics,
   recent customer complaints and escapes, recent NCRs.
4. **Fix on the spot when possible** and record it; otherwise record the action, owner and date.
5. **Escalate repeats** to corrective action (`lpa_results.py` LR001).
6. **Rotate questions:** a question passed 20+ times in a row is replaced by one on a current risk; keep a core set
   (instructions current, first-off done, error-proofing verified, reaction plan known, nonconforming product controlled).
7. **Track completion** (planned vs done by layer) and compliance on a visible board; review monthly.

## Metrics

| Metric | Target |
|--------|--------|
| Completion (done / planned) | >= 95% per layer |
| Compliance (pass / answered) | Track trend; 100% everywhere means the questions are too easy |
| Open actions > 30 days | 0 |
| Layer gap (L1 vs L2+ compliance) | < 15 points |

## Rollout

Pilot one line for 4 weeks -> train auditors on what "pass" looks like (photos of correct state) -> extend area by
area -> monthly review with plant leadership -> link failures to the CAPA system. Digital LPA apps help with
scheduling and photos, but paper cards on a board work for small plants.
