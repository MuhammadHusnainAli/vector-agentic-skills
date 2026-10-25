---
name: warm-up-icebreaker-generator
description: "Suggest and write warmers and icebreakers for language classes by purpose (icebreaker for new groups, energiser, settler, review of last lesson's language, lead-in to today's topic), CEFR level, class size, time and online or in-person delivery, from a 34-warmer bank with seeded shuffling and an exclude list so warmers do not repeat across a term. Covers first-lesson routines, name learning, cultural and personal sensitivity, online versions with chat and polls, linking the warmer to the lesson, and adapting for level and class size. Use when a teacher needs a warmer, first-day icebreaker, energiser, review game or lead-in activity."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Warm-up and Icebreaker Generator

The right warmer depends on its job: build the group, change the energy, recycle language or lead into the topic.
`scripts/warmer_picker.py` picks warmers from [warmer-bank.md](references/warmer-bank.md) by purpose, level,
class size, time and online use, shuffles them reproducibly with `--seed`, and skips ones already used.

## Trigger Conditions

Activate this skill when the user:
- Needs a warmer, icebreaker, energiser or lead-in for a language lesson
- Is planning a first lesson with a new group
- Wants a game to review last lesson's vocabulary or grammar
- Teaches online and needs a warmer that works in a video call

Longer speaking activities: [communicative-activity-generator](../communicative-activity-generator/SKILL.md).
Children: [young-learner-esl-activity-generator](../young-learner-esl-activity-generator/SKILL.md).

## Workflow

```
1. PURPOSE  -> icebreaker / energiser / settler / review / lead-in
2. CLASS    -> level, size, minutes, online, last lesson's language, today's topic
3. PICK     -> python scripts/warmer_picker.py --purpose review --level B1 --minutes 10 --seed 3
4. ADAPT    -> fill it with the class's language or topic; prepare cards or slides
5. SAFETY   -> check personal topics, physical contact and movement (references/warmer-principles.md)
6. DELIVER  -> instructions, demo, timer; stop while it is still fun
```

## Output

For each warmer: name, purpose, time, materials written out (prompts, word lists, picture ideas), teacher
instructions, a lower-level and higher-level variation, and an online version. For review warmers, use the
learners' actual words from last lesson; for lead-ins, connect it explicitly to today's text or task.

Purposes, timing, first lessons, sensitivity, online tips and adaptation:
[warmer-principles.md](references/warmer-principles.md).

## Scripts

```bash
python scripts/warmer_picker.py --purpose icebreaker --level A2 --students 14 --minutes 10 [--online] \
    [--seed 7] [--exclude "Line up" "Human bingo"] [--show 3] [--bank file.md]
```
Purposes: icebreaker, energiser, settler, review, lead-in. Exit codes: 0 warmers found, 1 nothing matches,
2 bank unreadable or bad arguments.

## Additional Resources

| File | Content |
|------|---------|
| [warmer-bank.md](references/warmer-bank.md) | 34 warmers with purposes, levels, minimum class size, minutes, online use, prep and procedure |
| [warmer-principles.md](references/warmer-principles.md) | Choosing by purpose, timing, first lessons, cultural and personal sensitivity, online, linking to the lesson, adapting |
