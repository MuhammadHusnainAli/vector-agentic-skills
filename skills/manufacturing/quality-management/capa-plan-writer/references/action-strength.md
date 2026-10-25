# Action Strength Hierarchy

Actions differ in how reliably they prevent recurrence. Rank them and aim for at least one action in the top three
for every verified root cause.

| Rank | Type | Reliability | Examples |
|------|------|-------------|----------|
| 5 | Eliminate | Removes the failure mode | Redesign the part so it cannot be assembled wrong; remove the manual step; change material or supplier |
| 4 | Error-proof (poka-yoke) | Makes the error impossible | Fixture that only accepts the correct orientation; interlock that stops the machine at tool-life limit; keyed connectors |
| 3 | Automate / detect | Catches it immediately | Vision check; in-process gauge with automatic stop; SPC with reaction plan; tool-life counter alarm |
| 2 | Standardise | Reduces variation | Updated work instruction with photos; setup sheet; checklist; control plan change |
| 1 | Train | Depends on memory | Retraining with competence test |
| 0 | Remind | Fades in weeks | Memo, toolbox talk, "be careful", warning sign |

Training is still needed when instructions change, but alone it is a weak corrective action: auditors and customers
(especially in automotive 8Ds) will reject "retrain the operator" as the only action.

## Turning weak actions into strong ones

| Weak action | Stronger alternative |
|-------------|----------------------|
| Retrain operators on packing | Dividers in the packaging so parts cannot touch; packaging spec with drop test |
| Remind setters to check offsets | Tool-life counter with interlock; automatic probing after insert change |
| Inspector to check more carefully | Go/no-go gauge or vision system; second check on the CMM for the critical feature |
| Update the procedure | Update the procedure **and** add a system check that enforces it (ERP block, checklist gate) |
| Warn the supplier | SCAR with supplier root cause; source inspection until effectiveness is shown |

## Linking actions to causes

Every verified root cause (occurrence and escape) gets at least one action; every action names the cause it
addresses. Actions without a cause are guesses; causes without an action will recur.
