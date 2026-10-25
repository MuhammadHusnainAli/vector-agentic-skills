---
name: esl-worksheet-generator
description: "Create ESL/EFL and other language worksheets that move from recognition to controlled to freer practice: gap-fills with shuffled word banks, distractors and first-letter hints, open cloze, matching (word-definition, sentence halves, question-answer, collocations) with no item left opposite its partner, multiple choice, transformations, word formation, reordering, error correction and personalised tasks, each with an instruction, example, numbered items and an answer key. Covers difficulty dials, item counts and timing by level, layout and dyslexia-friendly accessibility, digital worksheets and copyright. Use when a teacher needs a worksheet, handout or practice exercise for grammar or vocabulary, or wants to turn a text or word list into exercises."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# ESL Worksheet Generator

A worksheet works when every exercise practises the lesson's target language, items have one clear answer, and
the sequence moves from noticing to using. `scripts/gap_fill.py` turns a text into a gap-fill or cloze with a
word bank and key; `scripts/matching.py` turns pairs into a shuffled matching exercise with a key.

## Trigger Conditions

Activate this skill when the user:
- Asks for a worksheet, handout, homework or practice exercises
- Has a text or word list and wants exercises from it
- Needs a gap-fill, cloze, matching, transformation or error-correction exercise
- Wants an easier or harder version of an exercise

Reading texts and questions: [reading-comprehension-text-adapter](../reading-comprehension-text-adapter/SKILL.md).
Games: [vocabulary-game-generator](../vocabulary-game-generator/SKILL.md). Quizzes for marks:
[language-quiz-generator](../language-quiz-generator/SKILL.md).

## Workflow

```
1. BRIEF    -> level, target language, topic, time, print or digital
2. CONTEXT  -> write or take a short text that uses the target language naturally
3. SEQUENCE -> recognition -> controlled -> freer (references/exercise-types.md)
4. BUILD    -> python scripts/gap_fill.py text.txt --words ...    python scripts/matching.py pairs.csv
5. WRITE    -> instructions, example item 0, personalised task, "I can" self-check
6. CHECK    -> one answer per item, level of content language, layout (references/worksheet-design.md)
7. KEY      -> full answer key with alternatives
```

## Difficulty dials

| Easier | Harder |
|--------|--------|
| Word bank (`gap_fill.py` default) | `--no-bank` |
| `--hint` first letters | No hints |
| Bank without distractors | `--distractors` from common learner errors (*goed*, *seen*) |
| Matching with 5 pairs | 10 pairs |
| Gaps on target words | Open cloze `--every 7` |

## Output Format

A ready-to-print worksheet: header (title, level, name), aim, 3-5 exercises with instructions, examples and
numbered items, a personalised task, self-check, then the answer key on a separate section.

## Scripts

```bash
python scripts/gap_fill.py text.txt --words went saw "used to" [--all] [--distractors goed seen] [--hint] [--no-bank] [--seed 1]
python scripts/gap_fill.py text.txt --every 7 [--skip-first 1]
```
Exit codes: 0 exercise printed, 1 a target word is not in the text, 2 read error or nothing to gap.

```bash
python scripts/matching.py pairs.csv [--title "..."] [--markdown] [--seed 1]
```
Two columns, optional header, CSV or TSV, 3-26 pairs. Exit codes: 0 printed, 2 read error or wrong number of pairs.

## Additional Resources

| File | Content |
|------|---------|
| [exercise-types.md](references/exercise-types.md) | 18 exercise types by stage with design rules, instructions, answer keys, difficulty dials |
| [worksheet-design.md](references/worksheet-design.md) | Structure, length by level, language, layout and accessibility, digital worksheets, copyright, quality check |
