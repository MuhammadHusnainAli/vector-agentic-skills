---
name: authentic-material-lesson-adapter
description: "Turn authentic material (news articles, podcasts, videos, songs, menus, timetables, adverts, social media posts, forms, infographics) into language lessons by grading the task rather than the text. Selects texts for interest, relevance, exploitability, coverage, cultural load and rights; finds the 4-6 words to pre-teach, words to gloss on the page and words learners can ignore, plus names and cultural references to explain, with reading time by level; and builds a lesson shape (lead-in, pre-teach, gist or scanning, graded detail task, language focus on chunks and register, response) with task ideas per material type and level from A1 to C1. Covers copyright, fair dealing and fair use, Creative Commons and attribution. Use when a teacher wants to use a real-world text, video or song in class, or asks how to make authentic material work at a low level."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Authentic Material Lesson Adapter

Authentic texts motivate learners and show real language; they work at any level when the task is graded to the
learners, not the text to the task. `scripts/vocab_extract.py` shows what to pre-teach, gloss or ignore, and
whether the text can support detail tasks.

## Trigger Conditions

Activate this skill when the user:
- Wants a lesson from a real article, video, podcast, song, menu, ad or post
- Asks how to use authentic material with low-level learners
- Needs to choose what vocabulary to pre-teach from a real text
- Asks whether they may copy or share a text, video or song in class

To rewrite a text for a level instead: [reading-comprehension-text-adapter](../reading-comprehension-text-adapter/SKILL.md).
Audio and video tasks: [listening-task-builder](../listening-task-builder/SKILL.md).

## Workflow

```
1. SELECT   -> interest, relevance, exploitability, length, cultural load, sensitivity, rights
2. ANALYSE  -> python scripts/vocab_extract.py text.txt --level B1 --task-words ...
3. TASK     -> grade the task to the level (references/exploiting-authentic-texts.md)
4. SHAPE    -> lead-in -> pre-teach (max 6) -> gist/scan -> detail -> language focus -> response
5. SUPPORT  -> gloss on the page; explain cultural references in the lead-in
6. CREDIT   -> source, date, licence; cut to the useful part (references/copyright-and-sources.md)
```

If coverage is under about 85%, keep to gist and scanning tasks, cut to a shorter extract, or adapt the text.

## Output

| Part | Content |
|------|---------|
| Text choice | Why it suits the class; the extract to use; source and licence |
| Vocabulary | Pre-teach items with how to teach them; glosses; words to ignore |
| Background | Names and cultural references with one-line explanations |
| Tasks | Graded gist/scan task, detail task, language focus, response, with answer key |
| Plan | Stage table with timings |

## Scripts

```bash
python scripts/vocab_extract.py text.txt [--level B1] [--task-words word ...] [--max 6]
```
Ranks less frequent words by repetition, appearance in the title or first sentence, and task relevance; groups
word forms. Exit codes: 0 printed, 2 read error or empty text.

## Additional Resources

| File | Content |
|------|---------|
| [exploiting-authentic-texts.md](references/exploiting-authentic-texts.md) | Grade the task not the text, selection criteria, task ideas for ten material types, lesson shape, building tolerance of not understanding |
| [copyright-and-sources.md](references/copyright-and-sources.md) | Teaching exceptions in the UK, US, EU, Canada and Australia; Creative Commons; safer sources; attribution; practical rules |
| [high-frequency-words.txt](references/high-frequency-words.txt) | About 1,000 high-frequency English base forms used by `vocab_extract.py` |
