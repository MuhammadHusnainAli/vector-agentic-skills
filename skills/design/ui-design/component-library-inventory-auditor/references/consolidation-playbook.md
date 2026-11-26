# Consolidation Playbook

## Choose the canonical component per family

| Criterion | Prefer the implementation that... |
|-----------|-----------------------------------|
| Accessibility | Uses the right semantics and keyboard model (often the deciding factor) |
| API | Has the cleanest props (variant enum, not booleans), supports controlled/uncontrolled |
| Usage | Is already used most (less migration) |
| Tokens | Uses tokens rather than hard-coded values |
| Tests and docs | Has tests and stories |
| Ownership | Has an owner who will maintain it |

If none is good enough, build the canonical one in the design system and treat all existing ones as legacy.

## Variant mapping

For each legacy implementation, map how it becomes the canonical one:

| Legacy | Canonical | Mapping | Notes |
|--------|-----------|---------|-------|
| `<Btn color="blue">` | `<Button variant="primary">` | color=blue -> primary; color=grey -> secondary | |
| `<PrimaryButton>` | `<Button variant="primary">` | rename | Codemod |
| `<Modal>` | `<Dialog>` | open -> open; onClose -> onOpenChange(false) | Focus handling changes: QA |
| `<RedButton>` | `<Button variant="danger">` | | Check it's actually destructive |

Visual differences with no product reason are dropped. Differences with a reason become variants, if they pass the variant
test (same anatomy and behaviour).

## Prioritisation score

```
priority = usage_count_weight x inconsistency x (1 + defects) / effort
```
Practical version, each 1-3:

| Family | Usage | Inconsistency | Defects / a11y issues | Effort | Score (U x I x D / E) |
|--------|-------|---------------|-----------------------|--------|-----------------------|
| Button | 3 | 3 | 2 | 1 | 18 |
| Modal | 2 | 3 | 3 | 2 | 9 |
| Date picker | 1 | 2 | 3 | 3 | 2 |

Start with high-usage, low-effort families: visible wins build trust for the harder ones.

## Migration mechanics

1. **Ship the canonical component** with docs and the variant mapping.
2. **Codemods** for mechanical renames and prop mappings (jscodeshift / ts-morph); run per repo, reviewed by the owning team.
3. **Lint rule** to stop new usages of legacy components (`no-restricted-imports` with a message naming the replacement).
4. **Deprecate** legacy components: development-time console warning, docs banner, removal date.
5. **Visual regression** tests on key screens before and after.
6. **Delete** legacy code once usage reaches zero (re-run `inventory_scan.mjs`).

## Reporting

| Metric | Before | Target | Source |
|--------|--------|--------|--------|
| Implementations per family (button, modal, ...) | 5 | 1 | inventory_scan IN001 |
| Design-system usage share | 22% | 80% | inventory_scan --ds |
| Unique colours in CSS | 214 | < 40 | CSS statistics |
| Hard-coded colour hotspots | 31 files | 0 | IN004 |
| Accessibility defects in components | 47 | 0 known | audit backlog |

Report quarterly with the adoption tracker; tie wins to outcomes (faster feature delivery, fewer UI bugs, accessibility
compliance).
