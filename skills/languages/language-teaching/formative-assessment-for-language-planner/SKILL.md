---
name: formative-assessment-for-language-planner
description: "Plan formative assessment for language lessons and units: Wiliam's five strategies, success criteria, a bank of quick checks (exit tickets, mini whiteboards, ABCD cards, hinge questions with misconception distractors, traffic lights, no-hands-up questioning, monitoring checklists, 3-2-1, self-assessment against can-dos, peer checklists, error logs), where to place checks in a lesson, and feedback that moves learning forward. Turns exit-ticket or quick-check results into next-lesson decisions per objective (reteach the whole class, small-group reteach with named students, or move on), and lists students who missed most objectives and those ready for extension. Use when a teacher wants to check understanding during or after lessons, design exit tickets or hinge questions, or decide what to reteach."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Formative Assessment for Language Planner

Formative assessment only counts when the result changes what happens next. The skill plans checks into the
lesson and `scripts/exit_ticket_tally.py` turns their results into reteach, group or move-on decisions.

## Trigger Conditions

Activate this skill when the user:
- Wants to check learners' understanding during or at the end of a lesson
- Needs an exit ticket, hinge question or self-assessment for a lesson aim
- Has quick-check results and wants to know what to reteach and to whom
- Wants learners to self- or peer-assess against criteria

Graded quizzes: [language-quiz-generator](../language-quiz-generator/SKILL.md). Can-do criteria:
[can-do-statement-writer](../can-do-statement-writer/SKILL.md). Feedback on errors:
[l2-error-correction-strategy-advisor](../l2-error-correction-strategy-advisor/SKILL.md).

## Workflow

```
1. CRITERIA -> lesson aim as 2-4 checkable objectives (success criteria)
2. PLACE    -> checks after clarification, mid-lesson hinge, during practice, at the end
3. DESIGN   -> exit ticket / hinge question / checklist (references/formative-techniques.md)
4. COLLECT  -> mark 1/0 or 0-2 per objective in a CSV
5. DECIDE   -> python scripts/exit_ticket_tally.py ticket.csv [--max 2 --pass 2]
6. ACT      -> next lesson: whole-class reteach, group reteach, extension, one-to-one check-ins
```

## Decisions (exit_ticket_tally.py)

| Share who met the objective | Decision |
|-----------------------------|----------|
| Under 70% | RETEACH the whole class, differently |
| 70-89% | GROUP: reteach the listed students; others practise or extend |
| 90%+ | MOVE ON: individual follow-up |

The thresholds are a starting rule; adjust for the importance of the objective and how much time is left.

## Output Format

For planning: objectives as success criteria, the checks placed in the lesson stages, the exit ticket or hinge
question written out with answers and the misconception behind each distractor. For results: the decision table
and a next-lesson plan (warmer, group tasks, extension).

## Scripts

```bash
python scripts/exit_ticket_tally.py ticket.csv [--max 1] [--pass 1]
```
Columns: student, then one per objective; values 1/0, Y/N or scores. Exit codes: 0 printed, 2 read error or bad
values.

## Additional Resources

| File | Content |
|------|---------|
| [formative-techniques.md](references/formative-techniques.md) | Five strategies, 14 techniques with language-class examples, hinge questions, exit ticket design, feedback, placing checks in a lesson |
