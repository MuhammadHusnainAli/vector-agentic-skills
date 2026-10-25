# Reaction Plans That Protect the Customer

A reaction plan tells the operator exactly what to do when a check fails or a chart goes out of control. It must
**contain** suspect product, **correct** the process, **verify** the correction and **record** what happened.

## Template

```
1. Stop the process (or the station).
2. Quarantine all parts since the last good check (red tag, hold in ERP).
3. Notify the team leader and quality within <time>.
4. 100% inspect quarantined parts for the characteristic; segregate nonconforming parts.
5. Correct the cause (adjust offset, change tool, repair fixture) per <work instruction>.
6. Verify: first piece after correction approved; restart.
7. Record on the NCR / reaction log; quality decides on further action.
```

## Weak -> strong

| Weak | Strong |
|------|--------|
| Notify supervisor | Stop; quarantine parts since last good check; notify team leader within 15 min; 100% inspect; correct; first-off approval to restart; NCR |
| Adjust machine | Stop; quarantine since last good chart point; adjust offset per WI-20; verify 3 consecutive parts in the middle third; record on chart |
| Remove part to red bin | Stop; quarantine all parts since the last successful red-rabbit check; verify sensor with master; record |
| Re-check | Re-check with a second gauge; if confirmed, follow the full reaction plan |

## Out-of-control vs out-of-specification

| Signal | Reaction |
|--------|----------|
| Point outside control limits or a run rule (process changed) | Stop and investigate the cause; parts may still be in specification; contain if the change could have produced nonconforming parts |
| Part outside specification | Full reaction: contain since last good check, 100% inspect, correct, NCR |
| Error-proofing device fails verification | Contain all parts since the last successful verification; repair; re-verify before restart |
