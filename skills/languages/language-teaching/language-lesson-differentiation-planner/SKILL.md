---
name: language-lesson-differentiation-planner
description: "Plan differentiation for mixed-level language classes: tiered tasks (must/should/could, same text with different questions, graded texts, choice boards, open-ended tasks), different outcomes, scaffolds that do not stigmatise, same-level and mixed-level grouping by stage, roles, time and fast-finisher extensions, questioning for different levels, and adjustments for dyslexia, low literacy, anxiety and very strong learners. Groups a class list into mixed-level groups (spreading learners who share an L1) or same-level groups for tiered work, and flags learners far from the class median for support or extension. Use when a teacher has a mixed-ability class, needs a tiered version of a task, or wants to group learners for a lesson."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Language Lesson Differentiation Planner

Differentiating well means choosing one or two stages where the class gap matters most and varying the task,
outcome, support, grouping, time or role there. `scripts/group_learners.py` builds mixed-level or same-level
groups from a class list and flags learners who need support or extension.

## Trigger Conditions

Activate this skill when the user:
- Has a mixed-level or mixed-ability language class
- Needs a tiered version of a worksheet, reading task or writing task
- Wants to group learners (by level, mixing L1s, for peer teaching)
- Has fast finishers who get bored or learners who cannot finish

Full plan: [language-lesson-plan-builder](../language-lesson-plan-builder/SKILL.md). Graded versions of a text:
[reading-comprehension-text-adapter](../reading-comprehension-text-adapter/SKILL.md).

## Workflow

```
1. PROFILE   -> levels per skill, L1s, needs (SpLD, literacy, anxiety), class list as CSV
2. GAP       -> which stages of this lesson does the gap affect most?
3. LEVER     -> task, outcome, support, grouping, time or role (references/differentiation-strategies.md)
4. GROUP     -> python scripts/group_learners.py class.csv --size 4 --mode mixed   (or --mode same)
5. MATERIALS -> tiered task versions, scaffolds, extension, minimum task
6. CHECK     -> how every learner shows they reached the main aim
```

## Output

| Part | Content |
|------|---------|
| Class gaps | Where the levels differ, by skill |
| Differentiated stages | Stage, lever, what each tier does |
| Materials | Tier 1/2/3 tasks or must/should/could, scaffolds (sentence starters, word bank, model) |
| Grouping | Groups per stage from `group_learners.py`, with roles |
| Fast finishers / minimum | Extension task; minimum expected outcome |
| Specific needs | Adjustments for named needs |

Keep tiers anonymous (colours, not "weak group") and change groupings across the week.

## Scripts

```bash
python scripts/group_learners.py class.csv --size 4 --mode mixed|same
```
Columns: name, level (A1-C2 with optional +, or a 0-100 score), l1 (optional). Mixed mode snake-drafts by level
so each group spans the class and spreads same-L1 learners; same mode groups similar levels. Exit codes: 0 groups
printed, 2 read error or bad CSV.

## Additional Resources

| File | Content |
|------|---------|
| [differentiation-strategies.md](references/differentiation-strategies.md) | Six levers, tiered task patterns, scaffolds, grouping by stage, questioning, specific needs, plan checklist |
