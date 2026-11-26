# Contribution Process

## Contribution tiers

| Tier | Example | Path | Target time |
|------|---------|------|-------------|
| Fix | Bug, a11y defect, docs typo | Issue -> PR -> review -> next release | Days |
| Small enhancement | New icon, new prop, new variant within existing anatomy | Issue -> short design review -> PR | 1-2 weeks |
| New component | Date range picker | RFC -> critique -> build -> a11y review -> docs -> release | Weeks to a quarter |
| New pattern | Bulk editing pattern | RFC -> research evidence -> pattern page + examples | Weeks |
| Foundation change | New colour role, type scale change | RFC with impact analysis across products -> major/minor plan | Quarter |

## Does it belong in the system? (decision tree)

```
Is it needed by 2+ products/teams now, or clearly will be?
  no  -> keep it in the product (document as a product-level component); revisit if a second team asks
  yes -> Can an existing component or variant cover it?
           yes -> extend that component (enhancement), don't add a new one
           no  -> Is the need stable (not an experiment)?
                    no  -> build in product, flag as candidate, review after the experiment
                    yes -> new component RFC
```

## RFC template

```markdown
# RFC: <Component or change>
Author / team: | Date: | Status: Draft / In review / Accepted / Declined

## Problem
What user and product problem; screenshots of current workarounds.

## Evidence of need
Products and screens that need it; how they solve it today; usage estimate.

## Proposal
Anatomy, variants, behaviour, API sketch. Alternatives considered (including extending an existing component).

## Accessibility
Keyboard model, screen reader behaviour, APG pattern.

## Impact
Affected components and tokens; breaking changes; migration.

## Open questions
```

## Stages and owners

| Stage | Owner | Exit criteria |
|-------|-------|---------------|
| Intake / triage | DS product manager | Classified by tier; response within 2 working days |
| Design | Contributor + DS designer | Design critique passed; Figma component with variants and properties |
| Build | Contributor + DS engineer | Code reviewed; tokens only; tests; stories |
| Accessibility review | Accessibility specialist | Keyboard, screen reader, contrast, target size checked |
| Docs | Contributor + DS (docs writer) | Component page complete (design-system-documentation-writer checklist) |
| Release | DS engineer | Versioned, changelog, announcement |

## RACI (new component)

| Activity | DS lead | DS designer | DS engineer | Contributor | A11y | Product team lead |
|----------|---------|-------------|-------------|-------------|------|-------------------|
| Accept RFC | A | C | C | R | C | I |
| Design | I | A | C | R | C | I |
| Build | I | C | A | R | C | I |
| Accessibility sign-off | I | C | C | C | A/R | I |
| Release | A | I | R | I | I | I |

## Definition of done (component)

- [ ] Figma: component with variants, properties, auto layout, descriptions, linked to docs
- [ ] Code: uses tokens only; props match Figma property names; controlled/uncontrolled where relevant
- [ ] Accessibility: APG keyboard model, names/roles/states, contrast, focus visible, target size, reduced motion
- [ ] Tests: unit, interaction and visual regression; stories for every variant and state
- [ ] Docs: usage, when not to use, content, accessibility, props, do/don't
- [ ] Release: changelog entry, version bump, announcement
