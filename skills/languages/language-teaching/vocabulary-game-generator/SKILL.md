---
name: vocabulary-game-generator
description: "Generate vocabulary games for language classes from a word list: printable word searches (easy, medium and hard directions, solution grid and positions), unique bingo cards with free squares and a shuffled caller list, and 20 classroom games (back to the board, taboo, pelmanism, dominoes, word-formation races, sentence auction, running dictation of definitions, info-gap crosswords and more) with the language each practises. Covers making games learning-rich (recall over recognition, production, recycling), spacing encounters across lessons, and choosing and grouping words. Use when a teacher wants a vocabulary game, review activity, bingo, word search or fun way to recycle a word list."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Vocabulary Game Generator

Games pay off when learners retrieve and use words, and when the same words come back across lessons.
`scripts/wordsearch.py` builds a word search with a solution; `scripts/bingo_cards.py` builds unique bingo cards
and a caller list. [game-bank.md](references/game-bank.md) has 20 games and a recycling plan.

## Trigger Conditions

Activate this skill when the user:
- Wants a vocabulary game, bingo, word search or review activity
- Has a word list from a unit and wants ways to recycle it
- Needs a fast-finisher or end-of-lesson activity
- Asks how to make vocabulary stick

Speaking activities: [communicative-activity-generator](../communicative-activity-generator/SKILL.md). Warmers:
[warm-up-icebreaker-generator](../warm-up-icebreaker-generator/SKILL.md). Young learners:
[young-learner-esl-activity-generator](../young-learner-esl-activity-generator/SKILL.md).

## Workflow

```
1. WORDS    -> the list (8-12 new items at lower levels), grouped by topic or word family
2. CHOOSE   -> recognition game or recall game (references/game-bank.md); mix both across the week
3. BUILD    -> python scripts/bingo_cards.py --file words.txt --cards 24 --size 4
               python scripts/wordsearch.py --file words.txt --level medium
4. CALLER   -> write definitions, gapped sentences or picture prompts for each word (not just the word)
5. PRODUCE  -> add a production step: sentence, collocation, spelling
6. RECYCLE  -> schedule the words again next lesson, next week, next month
```

## Output

Give the game materials ready to print, teacher instructions (3-5 steps), the caller prompts written out for
bingo, the production follow-up and a note on when to recycle the words. For bingo, prefer more words than
squares so that cards differ and winners come one at a time.

## Scripts

```bash
python scripts/wordsearch.py --file words.txt [--words ...] [--size 12] [--level easy|medium|hard] [--seed 1]
```
Exit codes: 0 printed, 1 a word could not be placed, 2 no words or a word longer than the grid.

```bash
python scripts/bingo_cards.py --file words.txt [--words ...] [--cards 20] [--size 3|4|5] [--free] [--seed 1]
```
Exit codes: 0 printed, 2 too few words or read error.

## Additional Resources

| File | Content |
|------|---------|
| [game-bank.md](references/game-bank.md) | 20 vocabulary games with what they practise, levels, grouping and procedure; learning-rich games; encounters and recycling; choosing words |
