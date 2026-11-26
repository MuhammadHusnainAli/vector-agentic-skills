# Adoption Playbook

## Why teams don't adopt

| Reason | Signal | Intervention |
|--------|--------|--------------|
| Missing component or variant | Third-party or local components for the same job; high Figma detach rate | Ship it, or a beta, or document the approved third-party exemption |
| Doesn't fit real cases | Detaches; local wrappers that override styles | Add flexibility (slots, variants) based on the actual cases |
| Migration cost | Old major version; "no time" | Codemods, migration pairing, upgrade sprints planned with the team's PM |
| Don't know it exists / how to use it | Raw HTML for basic elements; questions in support | Onboarding, docs, office hours, examples in their stack |
| Trust (bugs, breaking changes) | Pinned old versions; forks | Fix quality, stable release cadence, migration guides |
| Performance or bundle concerns | Copied components to avoid the package | Tree-shaking, per-component entry points, measured bundle impact |
| Different platform needs | Low adoption on one platform | Platform-specific implementation or exemption |

## Diagnosis interview (30 minutes, one designer + one engineer per team)

1. Walk me through the last feature you built. Where did you use the system, where not, and why?
2. What did you build yourselves that you expected to find in the system?
3. When did the system slow you down?
4. What would make the next upgrade painless?
5. What do you wish the system team knew about your product?

Combine with the scan: the raw HTML and third-party lists per group show where to probe.

## Interventions by leverage

| Intervention | Effort | Effect |
|--------------|--------|--------|
| Ship the top missing component (from the scan's third-party/raw list) | Medium | High |
| Codemod for a common migration | Medium | High; makes migration a one-PR job |
| Lint rule: `no-restricted-imports` for deprecated/third-party equivalents, `react/forbid-elements` for raw `<button>` | Low | Prevents regression |
| Pairing: DS engineer embedded in a team for 1-2 sprints | High | High for lagging teams |
| Starter templates and app scaffolds pre-wired with the DS | Medium | High for new builds |
| Champions network and showcase of migrated screens | Low | Medium; social proof |
| Executive targets | Low | Mixed; pair with support or it breeds gaming |

## Migration campaign template

| Week | Activity |
|------|----------|
| 0 | Announce: why, what changes, support offered, timeline; run baseline scan |
| 1-2 | Codemods available; office hours twice a week; pairing slots booked |
| 3-6 | Teams migrate; weekly scan shared in the channel (progress, not shaming) |
| 7 | Deprecation warnings become lint errors in CI for new code |
| 8 | Report results; remove deprecated code in the next major |
