# Metrics and Targets

## Choosing metrics

| Question | Metric | Source |
|----------|--------|--------|
| Are teams building with it? | Adoption % per app/team | adoption_scan.mjs |
| Are they on a current version? | Major-version lag; apps on each version | package.json / lockfiles |
| Are styles coming from tokens? | Token share; hard-coded colour count | adoption_scan.mjs, CSS stats |
| Are designers using the library? | Insertions, detaches, detach rate per component | Figma library analytics |
| Is the experience consistent? | Coverage of audited key screens | Manual audit of top 20 screens per product |
| Is it worth it? | Time to build a standard screen; UI bug count; accessibility defects | Delivery data, bug tracker |

Avoid vanity metrics: number of components in the library, npm downloads, docs page views alone.

## Figma library analytics

Available on Organization and Enterprise plans for published libraries:
- Insertions and detachments per component over time, by team and file.
- A component with high detaches tells you what's missing (a variant, flexibility, a bug).
- Variables and styles usage show token adoption on the design side.

## Setting targets

1. Baseline every group.
2. Classify groups: new builds (should start at a high bar), active products (steady increase), legacy (maintenance only;
   maybe exempt).
3. Targets as change, not absolutes, for groups far behind: "+15 points this quarter" beats "reach 80%" for a 20% app.
4. Tie targets to work that causes adoption (component available, codemod shipped, migration pairing), not to the metric.

Example OKR:
- Objective: Customer-facing apps feel like one product.
  - KR1: Web checkout adoption 62% -> 80%
  - KR2: No app more than one major version behind (currently 3 apps on v1)
  - KR3: Hard-coded colours in customer apps down 70%

## Report template

```
Design system adoption - 2026 Q4
Overall: 58% (+9 pts since Q3)      Token share: 71%      Apps on latest major: 5 of 8

| App | Adoption | Change | Version | Biggest gap |
|-----|----------|--------|---------|-------------|
| web | 80% | +10 | 3.1 | - |
| admin | 14% | +4 | 2.4 | MUI DataGrid (no DS table yet); raw <button> |

Wins: Dialog migration finished in 4 apps (codemod).
Blockers: no data table component; admin team has no front-end capacity in Q1.
Next quarter: ship Table (beta), pair with admin team for 2 sprints, deprecate v2.
```

## Pitfalls

- Instance counts reward many small DS elements; complement with screen coverage for high-traffic screens.
- Teams game a single metric (wrapping a div in a DS Box). Spot-check and talk to teams.
- Third-party UI may be legitimate where the DS has no equivalent (rich text editor, charts): list exemptions explicitly.
- Monorepo vs polyrepo: run the scan per repo with the same flags and merge the CSVs.
