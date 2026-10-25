---
name: listening-task-builder
description: "Build listening lessons and tasks from audio or video transcripts: checks speech rate (words per minute), length, number of speakers and plays against the CEFR level, suggests pause points with approximate timestamps, and stages the lesson (lead-in, pre-teach, gist, specific information and detail tasks set before each play, pair checks, inference, transcript work, language focus, response). Includes task types by sub-skill, rules for writing listening questions, accent variety and recording choice, and bottom-up decoding activities for weak forms, linking, elision, assimilation, contractions and chunks (micro-dictation, word counting, shadowing). Use when a teacher has a recording or video to exploit, needs listening comprehension questions, or wants to know if a recording suits a level."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Listening Task Builder

A listening lesson succeeds when the recording suits the level (or the task is graded to it), each task is set
before learners listen, and some time goes on decoding connected speech. `scripts/transcript_stats.py` checks
speed, length and speakers for a level and suggests pause points.

## Trigger Conditions

Activate this skill when the user:
- Has a recording, podcast or video clip to use in class
- Needs listening comprehension questions or a listening lesson plan
- Asks whether a recording is too fast or too long for a class
- Wants activities for learners who "can't understand native speakers"

Real-world clips: [authentic-material-lesson-adapter](../authentic-material-lesson-adapter/SKILL.md). Writing a
script to record: [dialogue-for-classroom-writer](../dialogue-for-classroom-writer/SKILL.md).

## Workflow

```
1. MEASURE  -> python scripts/transcript_stats.py transcript.txt --duration 2:10 --level B1 --segments 3
2. DECIDE   -> suitable / extract / pause between segments / gist-only task
3. TASKS    -> gist -> specific information / detail -> inference (references/listening-lesson-stages.md)
4. ORDER    -> questions follow the recording; short answers; space between answers
5. DECODE   -> 5-10 min bottom-up work on one section (references/decoding-activities.md)
6. RESPOND  -> speaking or writing using the content
7. KEY      -> answers with timestamps
```

No transcript? Ask for one, or transcribe the relevant extract first; tasks written without the exact words
often have answers that are not actually in the recording.

## Output

Stage table with plays and pair checks, task sheet (gist, detail, inference) with instructions, the decoding
activity on a chosen extract, the response task, and the answer key with timestamps.

## Scripts

```bash
python scripts/transcript_stats.py transcript.txt --duration 2:10 [--level B1] [--segments 3]
```
Duration in seconds or m:ss. "Name:" at the start of a line marks a speaker turn. Exit codes: 0 suitable for the
level, 1 too fast, too long or too many speakers, 2 read error or bad duration.

## Additional Resources

| File | Content |
|------|---------|
| [listening-lesson-stages.md](references/listening-lesson-stages.md) | Stages, plays by level, task types by sub-skill, question rules, speed bands, choosing recordings, answer keys |
| [decoding-activities.md](references/decoding-activities.md) | Connected speech features with examples, decoding activities, strategies, using transcripts |
