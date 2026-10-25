# Worked 5 Why Examples

## Machining: bore oversize

Weak (stops at a person):
1. Why oversize? The setter did not change the insert in time.
2. Why? He forgot.
-> "Retrain setter." Will recur.

Strong:
| Leg | Why chain | Action |
|-----|-----------|--------|
| Occurrence | Insert worn beyond limit -> change interval 400 but new grade lasts ~250 -> interval not re-validated after grade change -> tooling changes not in change control | Tool-life counter with interlock at 220; add tooling to change control |
| Escape | Check 1 in 50 -> frequency based on old wear rate -> control plan has no review trigger after changes | Air gauge every 10th part with SPC; review trigger in control plan procedure |

## Assembly: missing clip

| Why | Answer |
|-----|--------|
| 1 | The clip was not fitted on 6 harnesses |
| 2 | The operator fits clips from a mixed bin and can skip a position without noticing |
| 3 | The station has no presence check for clip positions |
| 4 | The PFMEA rated detection as 3 assuming a visual check that is not in the work instruction |
| Root (system) | PFMEA detection ratings are not verified against the actual controls |
| Action | Fixture with clip presence sensors; PFMEA review rule: detection rating must cite the control plan line |

## Office / service: late invoices

| Why | Answer |
|-----|--------|
| 1 | 12% of invoices were sent more than 5 days after delivery |
| 2 | Delivery notes reach accounts only when drivers return them at week end |
| 3 | Drivers' proof of delivery is paper-only |
| 4 | The delivery app was never configured for e-POD |
| Action | Enable e-POD in the app; invoice triggers automatically on POD |

## Common traps

| Trap | Example | Fix |
|------|---------|-----|
| Repeating the problem | "Parts were packed badly" -> "packed badly by the packer" | Ask what specifically happened |
| Jumping to a solution | "Because we have no vision system" | Ask what condition the solution would remove |
| Ending outside your control | "Supplier sent bad material" | Why did our receiving or specification allow it? |
| Blame | "Operator forgot" | What in the process makes forgetting possible and undetected? |
