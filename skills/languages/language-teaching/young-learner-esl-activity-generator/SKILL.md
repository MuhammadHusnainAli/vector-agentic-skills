---
name: young-learner-esl-activity-generator
description: "Generate activities and lesson sequences for young language learners aged 3-12: songs, chants, TPR, Simon says, flashcard games, run and touch, what's missing, stories and acting out, colouring dictation, crafts, puppets, bingo, board games, treasure hunts, mini books and routines, each typed as stir (lively) or settle (calm) with ages, timing and target language. Builds a timed lesson that alternates stir and settle activities within the children's attention span, opening and closing with routines. Covers characteristics by age (pre-school, 6-8, 9-12), principles (here and now, routines, repetition, listening first, multisensory, context, positive atmosphere, L1 use), a sample lesson shape, classroom management with children, assessment and Cambridge Young Learners exams, and safeguarding. Use when a teacher plans English (or other language) lessons for children or needs a song, game or activity for a young learner class."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Young Learner ESL Activity Generator

Children learn languages through play, routine and repetition, in short activities that balance energy.
`scripts/yl_lesson_timer.py` builds a lesson that alternates stir and settle activities sized to the children's
attention span, from [yl-activity-bank.md](references/yl-activity-bank.md).

## Trigger Conditions

Activate this skill when the user:
- Teaches English or another language to children (3-12)
- Needs songs, games, TPR or craft activities for a topic or vocabulary set
- Wants a full young learner lesson plan with timings
- Struggles with energy levels or attention in a children's class

Teens and adults: [communicative-activity-generator](../communicative-activity-generator/SKILL.md). Vocabulary
games: [vocabulary-game-generator](../vocabulary-game-generator/SKILL.md). Behaviour:
[classroom-management-for-esl-coach](../classroom-management-for-esl-coach/SKILL.md).

## Workflow

```
1. CLASS    -> ages, level, class size, lesson length, topic and target language
2. SEQUENCE -> python scripts/yl_lesson_timer.py --age 6 --minutes 45 --seed 1
3. FILL     -> put the topic language into each activity (song words, flashcards, story, craft steps)
4. ROUTINES -> hello, review, tidy-up and goodbye routines (references/yl-principles.md)
5. MATERIALS-> flashcard list, song or chant lyrics, story choice, craft steps, worksheet
6. CHECK    -> each activity within the attention span; stir/settle alternate; listening before speaking
```

## Output

A timed lesson table (activity, type, language, how), the materials written out (chant lyrics, flashcard words,
story suggestion with refrain, craft steps), teacher language for instructions, and a note on assessment (what to
observe). Write songs and chants as original texts or name well-known traditional ones; do not reproduce
copyrighted lyrics in full.

## Scripts

```bash
python scripts/yl_lesson_timer.py --age 6 --minutes 45 [--seed 1] [--exclude "Board game"] [--bank file.md]
```
Exit codes: 0 sequence printed, 2 bad arguments or too few suitable activities.

## Additional Resources

| File | Content |
|------|---------|
| [yl-activity-bank.md](references/yl-activity-bank.md) | 28 young learner activities with stir/settle type, ages, minutes, language and procedure |
| [yl-principles.md](references/yl-principles.md) | Characteristics by age, principles, lesson shape, classroom management, assessment, safeguarding |
