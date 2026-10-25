---
name: ppp-lesson-structure-planner
description: "Plan presentation-practice-production (PPP) language lessons: a context that makes meaning clear, clarification of meaning, form and pronunciation with concept-checking questions (CCQs), timelines and drills, controlled practice with feedback, personalised freer practice and delayed error correction, timed to the lesson length and level. Includes a CCQ and timeline bank for tenses, modals, conditionals, passive, comparatives, reported speech, relative clauses, lexis and functions. Checks a target language analysis for missing meaning/form/pronunciation, CCQs that repeat the target language or ask 'Do you understand?', no context, and 'freer' tasks that are really gap-fills. Use when teaching new grammar, vocabulary or functional language with PPP, writing CCQs, or timing a PPP lesson."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# PPP Lesson Structure Planner

PPP works when the context makes the meaning obvious, clarification covers meaning before form, and freer
practice is the longest stage. `scripts/ppp_timing.py` times the stages for the lesson length and level;
`scripts/ppp_check.py` checks the target language analysis (TLA) and practice tasks.

## Trigger Conditions

Activate this skill when the user:
- Is planning a lesson that introduces new grammar, a lexical set or functional exponents
- Needs CCQs, a timeline or a drill for a language point
- Wants a PPP lesson timed for 45, 60 or 90 minutes
- Has a PPP lesson where learners "got it" in practice but cannot use it

Whole-plan format and review: [language-lesson-plan-builder](../language-lesson-plan-builder/SKILL.md). For
language learners half-know or fluency goals, consider
[task-based-language-lesson-designer](../task-based-language-lesson-designer/SKILL.md).

## Workflow

```
1. TIME      -> python scripts/ppp_timing.py --minutes 60 --level A2
2. CONTEXT   -> a text, dialogue or situation that needs the target language
3. MEANING   -> concept parts -> CCQs (references/ccq-bank.md), timeline, contrast
4. FORM      -> model sentence, positive/negative/question, irregulars, spelling
5. PRON      -> stress, weak forms, contractions, linking, intonation; drill plan
6. PRACTICE  -> controlled task (one right answer) -> pair check -> feedback
7. PRODUCE   -> personalised, communicative freer task; monitor for delayed correction
8. CHECK     -> python scripts/ppp_check.py tla.json
```

`ppp_timing.py --json` prints stages that drop straight into the lesson plan builder's `plan_scaffold.py`.

## Writing CCQs

Break the concept into parts, ask one simple question per part, never include the target language, and never ask
"Do you understand?".

```
I used to live in a village.
  Did I live in a village in the past?   (yes)
  Once or for a long time?               (a long time)
  Do I live there now?                   (no)
```

The full bank (tenses, modals, conditionals, passive, comparison, reported speech, relative clauses, lexis,
functions) and timeline conventions: [ccq-bank.md](references/ccq-bank.md). Stage techniques, drills,
controlled vs freer tasks, criticisms of PPP: [ppp-stages.md](references/ppp-stages.md).

## Review Codes (ppp_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| PP001 | high | Item without meaning, form or pronunciation |
| PP002 | high | Item without CCQs |
| PP003 | medium | CCQ repeats the target language |
| PP004 | medium | CCQ is "Do you understand?" or similar |
| PP005 | medium | No context |
| PP006 | medium | No controlled or no freer practice |
| PP007 | medium | Freer task is a controlled exercise |
| PP008 | low | Only one CCQ |
| PP009 | low | Pronunciation has no stress / weak form / connected speech |

## Output Format

Deliver: timed stage table, the context, a TLA table per item (meaning, CCQs with answers, form, pronunciation,
anticipated problems), the drill sequence, controlled task with answer key, freer task with instructions and
ICQs, delayed error correction plan. Then the `ppp_check.py` result.

## Scripts

```bash
python scripts/ppp_timing.py --minutes 60 --level A2 [--json]
```
Exit codes: 0 printed, 2 bad arguments.

```bash
python scripts/ppp_check.py tla.json
```
Keys: context, items (item, meaning, form, pronunciation, ccqs), controlled, freer. Exit codes: 0 no high
findings, 1 high findings, 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [ppp-stages.md](references/ppp-stages.md) | Each stage with techniques, MFP clarification, drilling, controlled and freer task types, criticisms |
| [ccq-bank.md](references/ccq-bank.md) | CCQs with answers for tenses, modals, conditionals, passive, comparison, reported speech, relatives, lexis, functions; timelines |
