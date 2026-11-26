---
name: design-system-governance-process-designer
description: "Design how a design system is run so it stays trusted and used: operating model (solitary, centralized, federated, hybrid) chosen from org size and product count, team composition and funding, contribution tiers (fix, enhancement, new component, pattern) with an intake RFC, decision criteria for what enters the system (reuse across products, not one team's need), the path from proposal to release (triage, design critique, build, accessibility review, docs, release) with service levels, RACI, definition of done, semantic versioning, release cadence, breaking-change and deprecation policy with migration support, communication (release notes, office hours, champions), and health metrics. Reviews existing governance for no intake path, no decision criteria, central team as bottleneck, breaking changes in minor releases, deprecations without dates or migration, undefined ownership and no feedback loop. Use when setting up or fixing design system governance, contribution, release or deprecation processes."
metadata:
  category: design
  subcategory: ui-design
  version: "1.0.0"
---

# Design System Governance Process Designer

Design systems rarely fail because of their components. They fail because product teams can't get what they need in
time, so they build around the system. Governance is how requests come in, how decisions get made, how changes ship
without breaking products, and who's accountable. It has to be quick enough that working with the system beats working
around it. This skill designs that process for the organisation's size and reviews processes that have stalled.

## Trigger Conditions

Activate this skill when the user:
- Sets up a design system team or process, or scales one beyond a single product
- Has product teams detaching components, forking the library, or waiting weeks for changes
- Needs a contribution model, RFC template, release cadence or deprecation policy
- Has to justify design system staffing or show its health to leadership

Measuring adoption: [design-system-adoption-tracker](../design-system-adoption-tracker/SKILL.md). Docs and release notes: [design-system-documentation-writer](../design-system-documentation-writer/SKILL.md).
Inventory before consolidating: [component-library-inventory-auditor](../component-library-inventory-auditor/SKILL.md).

## Workflow

```
1. CONTEXT   -> number of products/teams, designers/engineers, platforms, current pain (requests waiting? forks?)
2. MODEL     -> pick the operating model (references/operating-models.md); staff it
3. INTAKE    -> one front door: request form/RFC, triage cadence, response SLA
4. CRITERIA  -> what belongs in the system vs stays in a product (decision tree in references/contribution-process.md)
5. PATH      -> stages from proposal to release with owners, reviews, definition of done
6. RELEASE   -> versioning, cadence, breaking-change and deprecation policy (references/release-and-deprecation.md)
7. COMMS     -> release notes, office hours, champions network, roadmap visibility
8. MEASURE   -> health metrics and a quarterly review; adjust the process when the bottleneck moves
```

## Principles

| Principle | Practice |
|-----------|----------|
| Faster than working around it | Triage within 2 working days; small fixes ship within the next release |
| Clear criteria, not opinions | A documented test for "does this belong in the system?" |
| Contributions are welcome and supported | Contributors get pairing and review, not a gate |
| Product teams aren't blocked | Teams may build locally while a proposal is reviewed, with a plan to converge |
| Breaking changes are rare and scheduled | Majors on a known cadence, with codemods and migration guides |
| Everything has an owner | Each component and foundation has a named maintainer |

## Review Checklist

Report as `CODE [severity] problem -> fix`.

| Code | Severity | Check |
|------|----------|-------|
| GV001 | high | No single intake path; requests arrive via DMs and get lost |
| GV002 | high | No written criteria for what enters the system |
| GV003 | high | Breaking changes shipped in minor/patch releases, or without migration notes |
| GV004 | high | Central team is the only route to change and the queue exceeds about one quarter |
| GV005 | medium | Deprecations without replacement, removal version or date |
| GV006 | medium | No definition of done (accessibility, docs, Figma, tests, tokens) |
| GV007 | medium | No response SLA; contributors don't know when they'll hear back |
| GV008 | medium | Components without owners |
| GV009 | medium | No release notes or communication channel |
| GV010 | medium | No metrics on adoption, contribution and support load |
| GV011 | low | No regular forum (office hours, critique) for product teams |
| GV012 | low | Roadmap not visible to product teams |

## Output

1. Operating model with team composition and responsibilities
2. Contribution guide: tiers, intake form/RFC template, criteria, stages, SLAs, RACI, definition of done
3. Release policy: semver rules, cadence, deprecation timeline, migration support
4. Communication plan and rituals
5. Health metrics dashboard definition
6. Review findings, if assessing an existing process

## Additional Resources

| File | Content |
|------|---------|
| [operating-models.md](references/operating-models.md) | Solitary, centralized, federated, hybrid: when each fits, staffing, funding, failure modes |
| [contribution-process.md](references/contribution-process.md) | Contribution tiers, decision tree, RFC template, stages, RACI, definition of done |
| [release-and-deprecation.md](references/release-and-deprecation.md) | Semver for design systems, cadence, deprecation timeline, migration support, health metrics |
