---
name: pronunciation-feedback-for-teachers-tool
description: "Help teachers diagnose and give feedback on English learners' pronunciation with intelligibility as the goal: Lingua Franca Core priorities, likely difficulties by first language (Spanish, Portuguese, French, German, Italian, Arabic, Mandarin, Cantonese, Japanese, Korean, Vietnamese, Thai, Russian, Polish, Turkish, Hindi/Urdu, Persian, Indonesian) with priority, examples and teaching tips, merged for mixed-L1 classes, and a minimal-pairs bank for vowel, consonant, final-consonant and cluster contrasts with context sentences and seeded 1-or-2 listening drills with keys. Covers diagnosis from recordings, classroom techniques (model and drill, back-chaining, articulation, minimal pairs, stress marking, humming intonation, shadowing, recasts), written feedback on recordings and sensitivity about accent. Use when a teacher asks how to correct pronunciation, what problems their learners' L1 causes, or needs minimal pairs and pronunciation drills."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Pronunciation Feedback for Teachers Tool

Pronunciation feedback works when it targets what affects intelligibility for this learner, uses a technique that
lets the learner hear and feel the difference, and is followed by practice. `scripts/l1_issues.py` lists likely
difficulties by first language; `scripts/minimal_pairs.py` gives pairs and listening drills for a contrast.

## Trigger Conditions

Activate this skill when the user:
- Asks how to correct or give feedback on learners' pronunciation
- Wants to know which sounds are hard for speakers of a particular L1, or for a mixed class
- Needs minimal pairs, a discrimination drill or a pronunciation warmer
- Has learner recordings to give feedback on

Oral correction in general: [l2-error-correction-strategy-advisor](../l2-error-correction-strategy-advisor/SKILL.md).
Connected speech for listening: [listening-task-builder](../listening-task-builder/SKILL.md).

## Workflow

```
1. PREDICT   -> python scripts/l1_issues.py Arabic Spanish --priority high   (class L1s)
2. DIAGNOSE  -> record a passage + free speech; note sounds, clusters, stress, intonation
3. PRIORITISE-> 2-3 intelligibility priorities per learner (references/pronunciation-feedback-techniques.md)
4. PRACTISE  -> python scripts/minimal_pairs.py p-b --drill 8 --seed 1
5. FEEDBACK  -> technique matched to the problem; written feedback with timestamps for recordings
6. RECHECK   -> re-record the same text after practice; compare
```

Predictions are tendencies, not facts about a learner: always confirm by listening.

## Output Format

For a class: priority table (feature, which L1s, why it matters, activity). For a learner: strengths, 2-3
priorities with examples and timestamps, practice tasks (minimal pairs, drills, recording). For drills: the
pairs table, context sentence, listening drill with key, and production follow-up.

## Scripts

```bash
python scripts/l1_issues.py Spanish [Arabic ...] [--priority high|medium|low]
python scripts/l1_issues.py --list
```
Exit codes: 0 printed, 2 unknown L1 or no L1 given.

```bash
python scripts/minimal_pairs.py l-r|"/ɪ/-/iː/"|th-s ... [--drill 8] [--seed 1]
python scripts/minimal_pairs.py --list
```
Exit codes: 0 printed, 2 unknown contrast or none given.

## Additional Resources

| File | Content |
|------|---------|
| [l1-pronunciation-issues.md](references/l1-pronunciation-issues.md) | Typical difficulties for 18 L1s with priority, examples and teaching tips |
| [minimal-pairs.md](references/minimal-pairs.md) | Minimal pairs for 26 contrasts with aliases and context sentences; minimal-pair activities |
| [pronunciation-feedback-techniques.md](references/pronunciation-feedback-techniques.md) | Intelligibility priorities, diagnosis, classroom techniques, written feedback on recordings, sensitivity |
