# The Eight Disciplines

| D | Name | Content | Typical customer deadline | Why customers reject it |
|---|------|---------|---------------------------|-------------------------|
| D0 | Prepare / emergency response | Is an 8D needed? Immediate safety or line-stop actions | Same day | - |
| D1 | Team | Champion with authority + cross-functional team (quality, process, production, design, supplier) | 24 h | Quality engineer alone |
| D2 | Problem description | 5W2H and is / is-not; the effect only, no cause | 24 h | Vague ("bad parts"), cause in the statement |
| D3 | Interim containment | Protect the customer now: sort stock, WIP, transit, customer; clean-point identification; verify it works | 24 h | Not verified; customer stock forgotten |
| D4 | Root cause | Occurrence cause **and** escape (non-detection) cause, each verified; systemic cause recommended | 5-10 working days | Human error; one cause only; not verified |
| D5 | Permanent corrective actions | One action per verified cause; chosen and verified (trial) before implementation | 10-15 working days | Training only; no action for escape |
| D6 | Implement and validate | Implement, validate with production data, then remove D3 containment | 30-60 days | No data; containment left forever or removed too early |
| D7 | Prevent recurrence | PFMEA, control plan, work instructions, similar products and sites (read-across), lessons learned | With D6 | No FMEA update; no read-across |
| D8 | Close and recognise | Confirm with customer; recognise the team | 60 days | Closed without customer agreement |

## Occurrence, escape, systemic

| Leg | Question | Example |
|-----|----------|---------|
| Occurrence | Why was the defect made? | Tray has no dividers; parts rub in transport |
| Escape (non-detection) | Why did our controls not catch it? | Visual inspection is before packing |
| Systemic | Why did our system allow both? | APQP checklist has no packaging validation |

Each leg gets its own 5 Why chain and its own action. Most OEM templates (VDA, Ford Global 8D, GM, Stellantis)
require at least occurrence and escape.

## Verification vs validation

- **D5 verification:** before full implementation, prove the action removes the cause (trial run, capability study,
  switch the cause on and off).
- **D6 validation:** after implementation, prove the problem is gone in production over enough volume and time
  (zero defects over N parts, Cpk, customer feedback).

## Clean point

Mark the first shipment made after containment (label, lot number, date) so the customer knows which parts are
certified. Keep marking until D6 validation is complete.
