---
name: reading-comprehension-text-adapter
description: "Adapt English reading texts to a target CEFR level and write comprehension tasks for them. Estimates text level from average sentence length and coverage by a high-frequency word list (plus Flesch reading ease), lists less frequent words and sentences too long for the target level, and guides simplification vs elaboration: splitting sentences, replacing or glossing rare words, un-nominalising, explaining idioms and cultural references, while keeping ideas, text type and target language. Writes graded versions for mixed classes and staged tasks (prediction, gist, detail, inference, vocabulary in context, personal response), and checks a question set for a missing or misplaced gist task, no inference at B1+, one-sided true/false keys and guessable yes/no questions. Use when a text is too hard or too easy for a class, or when a teacher needs reading comprehension questions."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Reading Comprehension Text Adapter

Learners read comfortably when they know about 95-98% of the words and sentences stay within their processing
range. `scripts/text_level.py` measures both and shows exactly what to adapt for a target level;
`scripts/question_mix.py` checks that the comprehension questions are staged and varied.

## Trigger Conditions

Activate this skill when the user:
- Has a text that is too hard (or too easy) for a class and wants it adapted
- Needs graded versions of one text for a mixed-level class
- Wants comprehension questions, T/F items or a reading lesson for a text
- Asks what CEFR level a text is

Real-world texts with minimal change: [authentic-material-lesson-adapter](../authentic-material-lesson-adapter/SKILL.md).
Mixed classes: [language-lesson-differentiation-planner](../language-lesson-differentiation-planner/SKILL.md).

## Workflow

```
1. MEASURE   -> python scripts/text_level.py original.txt --target B1
2. KEEP      -> main ideas, order, text type, target language, facts the tasks need
3. ADAPT     -> split long sentences, replace/gloss rare words, cut side points (references/adaptation-techniques.md)
4. RE-CHECK  -> run text_level.py again until "OK" and few long sentences remain; read aloud for naturalness
5. TASKS     -> prediction, gist, detail, inference, vocabulary, response (references/reading-task-design.md)
6. CHECK     -> python scripts/question_mix.py questions.txt --level B1 --key T F T NG
7. KEY       -> answers with paragraph/line evidence; credit "Adapted from ..."
```

The level estimate is an approximation from two measures; say so, and use teacher judgement for topic
familiarity, cultural load and text organisation, which the script cannot see.

## Review Codes (question_mix.py)

| Code | Severity | Problem |
|------|----------|---------|
| RQ001 | high | No gist task |
| RQ002 | medium | Gist task not first |
| RQ003 | medium | No inference or evaluation at B1+ |
| RQ004 | medium | True/false key all one answer |
| RQ005 | low | No personal response question |
| RQ006 | low | Yes/no question answerable without the text |

## Output Format

Deliver: the adapted text (with glosses marked), a before/after measure from `text_level.py`, a list of what was
changed and why, then the task sheet (pre-reading, gist, detail, inference, vocabulary, response) and the answer
key with evidence. For graded versions, give each version with its measure.

## Scripts

```bash
python scripts/text_level.py text.txt [--target A2] [--top 15] [--wordlist file.txt]
```
Exit codes: 0 at or below target (or no target), 1 above target, 2 read error or empty text.

```bash
python scripts/question_mix.py questions.txt [--level B1] [--key T F NG]
```
One question per line; tags like `[inference]` override detection. Exit codes: 0 no high findings, 1 high
findings, 2 read error or no questions.

## Additional Resources

| File | Content |
|------|---------|
| [adaptation-techniques.md](references/adaptation-techniques.md) | Text features by level, simplification vs elaboration, techniques with examples, process, graded versions |
| [reading-task-design.md](references/reading-task-design.md) | Lesson sequence, question taxonomy, writing questions and T/F items, number of questions, answer keys |
| [high-frequency-words.txt](references/high-frequency-words.txt) | About 1,000 high-frequency English base forms used by `text_level.py` |
