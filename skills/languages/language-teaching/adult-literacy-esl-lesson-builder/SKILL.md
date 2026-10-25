---
name: adult-literacy-esl-lesson-builder
description: "Build lessons for adult ESL learners who are developing literacy (LESLLA learners: pre-literate, non-literate, semi-literate, literate in a non-Roman script): learner profiles and sensitive initial assessment, principles (oral language first, known to new, systematic phonics with adult-relevant text, repetition, classroom skills, respect for experience), a lesson routine (oral warm-up, review, new grapheme, blending, segmenting, decodable text, writing, functional literacy, Language Experience Approach), a phonics sequence for adults, sight words, functional literacy targets (forms, signs, medicine labels) and portfolio assessment. Checks whether a reading text is decodable with the letter-sound patterns and sight words taught so far, catching untaught digraphs, listing non-decodable words with the untaught part, and suggesting the most useful next patterns. Use when teaching adults with low or no literacy, writing decodable adult texts, or planning a literacy-focused ESL course."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Adult Literacy ESL Lesson Builder

Adults learning to read in a new language need oral English first, systematic phonics, and texts that are both
decodable and adult. `scripts/decodable_check.py` shows whether a text can be read with what learners have been
taught.

## Trigger Conditions

Activate this skill when the user:
- Teaches adults who cannot read or write, or read only in another script
- Needs decodable texts or phonics lessons for adults (not children's materials)
- Plans functional literacy (forms, signs, medicine labels, timetables)
- Works with refugees or migrants with limited schooling

Settlement-focused planning: [refugee-language-support-planner](../refugee-language-support-planner/SKILL.md).
Adapting texts for literate learners: [reading-comprehension-text-adapter](../reading-comprehension-text-adapter/SKILL.md).

## Workflow

```
1. PROFILE   -> literacy profile, schooling, L1 script, oral English (references/literacy-learners.md)
2. SEQUENCE  -> where learners are in the phonics sequence (references/phonics-sequence.md)
3. LESSON    -> oral warm-up, review, new grapheme, blending, segmenting, text, writing, functional task
4. TEXT      -> write a short adult text; python scripts/decodable_check.py text.txt --taught ... --sight ...
5. REVISE    -> swap or pre-teach words the script lists until 90%+ readable
6. FUNCTION  -> one real-life literacy task per lesson
7. TRACK     -> checklist and portfolio
```

## Output

A lesson plan with timed stages, the grapheme and sight words of the lesson, the decodable text with its
`decodable_check.py` result, a dictation, a functional literacy task with the real-life material described, and
materials notes (large print, lined paper, letter tiles, pictures of real objects).

## Scripts

```bash
python scripts/decodable_check.py text.txt --taught s a t p i n m d ... [--sight the I to is] [--min 90]
python scripts/decodable_check.py text.txt --taught-file taught.txt --sight-file sight.txt
```
Exit codes: 0 at or above the readable target, 1 below, 2 read error or nothing taught.

## Additional Resources

| File | Content |
|------|---------|
| [literacy-learners.md](references/literacy-learners.md) | LESLLA learner profiles, principles, lesson routine, Language Experience Approach, functional literacy, assessment |
| [phonics-sequence.md](references/phonics-sequence.md) | Grapheme sets in teaching order with example words, sight words, teaching a grapheme, writing decodable adult texts |
