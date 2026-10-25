# Controls That Keep Purchasing Inside the ASL

| Control | How |
|---------|-----|
| ERP block | Supplier master status drives PO creation: disqualified / pending cannot receive POs; scope codes restrict commodities |
| PO requirements | Drawing and revision, specification, quality clauses (certificates, right of access, flow-down, notification of changes, counterfeit prevention), approved special-process sources |
| Receiving check | Receiving verifies the supplier and scope against the ASL before acceptance |
| Monthly audit | `asl_audit.py --pos` on last month's POs: any AL001 / AL002 is a nonconformity against 8.4 |
| Change notification | Suppliers must notify changes of site, process, sub-supplier, material, ownership; trigger re-approval / PPAP |
| Certificate watch | Expiry dates tracked; request renewals 60 days ahead; suspended certificates move the supplier to conditional |

## Handling an off-list purchase

1. Quarantine material received from the off-list supplier.
2. Raise an NCR against the purchasing process (internal), not against the supplier.
3. Decide: approve the supplier through the normal process, or return / scrap.
4. Correct the system gap (ERP block missing, emergency buy procedure unclear).

## Emergency purchases

Allow them only through a documented route: quality approval before the PO, enhanced receiving inspection,
retrospective evaluation within a set time. Record every emergency buy and review the count at management review.
