---
name: recast-and-prompt-technique-coach
description: "Coach language teachers in oral corrective feedback moves: recasts (full, partial, stressed, recast plus prompt, didactic), prompts (elicitation, metalinguistic clues and questions, clarification requests, repetition, gestures) and explicit correction, with teacher language for each, a prompt-to-correction sequence with wait time and learner repair, when to choose recasts or prompts, habits to change, and a self-observation cycle (record, transcribe, code, set a goal, practise, re-record). Codes the teacher's feedback in a classroom transcript where learner error turns are marked, counts each move with learner uptake and repair, and flags over-reliance on recasts, untreated errors in accuracy stages and prompts that rarely lead to repair. Use when a teacher wants to improve how they correct speaking errors, analyse a lesson recording, or practise recasts and prompts."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Recast and Prompt Technique Coach

Most teachers rely on recasts that learners often do not notice. This skill builds a wider repertoire of feedback
moves and checks it against real classroom data. `scripts/feedback_coder.py` codes the teacher moves in a marked
transcript and reports uptake and repair.

## Trigger Conditions

Activate this skill when the user:
- Wants to improve how they correct learners' spoken errors
- Has a lesson recording or transcript and wants feedback analysed
- Asks what to say instead of just giving the right answer
- Is preparing for an observation where error correction is a focus

What and when to correct: [l2-error-correction-strategy-advisor](../l2-error-correction-strategy-advisor/SKILL.md).
Observation forms: [language-teacher-observation-form-builder](../language-teacher-observation-form-builder/SKILL.md).

## Workflow

```
1. RECORD    -> 10-15 min of a speaking or practice stage (with consent)
2. MARK      -> transcript with "T:" and "Name:" turns; learner turns with errors end in " *"
3. CODE      -> python scripts/feedback_coder.py transcript.txt --stage accuracy
4. REVIEW    -> check the coding; which moves, how much repair (references/self-observation.md)
5. GOAL      -> one change (e.g. turn recasts into prompts in controlled practice)
6. PRACTISE  -> four moves for each sample error (references/feedback-moves.md)
7. RE-RECORD -> compare after two weeks
```

## Coaching a teacher

When the user shares an exchange, rewrite the teacher's move as each alternative (partial recast, elicitation,
metalinguistic clue, repetition, explicit correction), say which fits the stage and learner, and script the follow
up that gets the learner to say the corrected sentence.

## Findings (feedback_coder.py)

| Code | Severity | Finding |
|------|----------|---------|
| CF001 | medium | Over 70% of feedback is recasts |
| CF002 | medium | Over half the errors untreated in an accuracy stage |
| CF003 | low | Prompts rarely lead to repair |

The coding is pattern-based; review it before drawing conclusions.

## Scripts

```bash
python scripts/feedback_coder.py transcript.txt [--stage accuracy|fluency]
```
Exit codes: 0 printed, 2 read error or no marked learner errors.

## Additional Resources

| File | Content |
|------|---------|
| [feedback-moves.md](references/feedback-moves.md) | Recast kinds, prompt moves with teacher language, explicit correction, a feedback sequence, choosing moves, habits to change |
| [self-observation.md](references/self-observation.md) | Record, transcribe in the script's format, code, set a goal, practice errors, re-record |
