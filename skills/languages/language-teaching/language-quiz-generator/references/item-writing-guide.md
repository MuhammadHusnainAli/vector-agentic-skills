# Writing Quiz Items for Language Classes

## Match the item to the purpose

| Purpose | Best item types |
|---------|-----------------|
| Check a grammar form | Gap-fill with verb in brackets, MCQ in context, transformation |
| Check meaning or use | MCQ with context, choose the best response, T/F about meaning |
| Check vocabulary | Gap-fill in a sentence, matching to definitions, odd one out, collocation MCQ |
| Check reading/listening | MCQ or T/F on a text; short-answer |
| Quick review (exit ticket, warmer) | 3-5 items mixed |

## Multiple-choice items

1. Test one point; the stem gives enough context that only one option is correct.
2. 3-4 options; 3 well-made options work as well as 4.
3. Distractors come from real learner errors (*goed*, *I am agree*, *more better*) or plausible confusions.
4. Options are grammatically consistent with the stem and similar in length and style.
5. No "all of the above" / "none of the above"; no options that overlap.
6. Put repeated words in the stem, not in every option.
7. Avoid negative stems; if needed, write NOT in capitals.
8. Vary the position of the key (shuffled by `quiz_build.py`).
9. Check for "two right answers" in some varieties of English (*have got* / *have*; *at the weekend* / *on the
   weekend*) and say which variety the quiz uses.

| Flawed | Problem | Better |
|--------|---------|--------|
| I ___ to Paris. A) went B) have been C) go D) was going | Several answers correct without context | I ___ to Paris last summer. A) go B) went C) have gone D) was going |
| She is ___ . A) happy B) happily C) happiness D) the happiest girl in the class who always smiles | Key position fine but D is long and odd | All options single words |
| Which is not a fruit? | Negative, unmarked | Which is NOT a fruit? (or ask "Which is a vegetable?") |

## Gap-fill items

- One gap per sentence for grammar; the sentence context must fix the answer (time markers, clues).
- Give the base form in brackets when testing form: *She ___ (live) here since 2010.*
- List all acceptable answers in the key (*has lived / 's lived*).
- Avoid gaps where any word fits (*I ___ coffee* - like, drink, want, hate...).

## True/false items

- Statements clearly true or false; no "sometimes"; avoid absolutes like "always/never" as cues.
- About half true and half false.
- For reading, paraphrase the text instead of copying it.

## Quiz composition

| Element | Guide |
|---------|-------|
| Length | 8-15 items for a class quiz; 3-5 for an exit ticket |
| Balance | Spread items across the points taught; `quiz_build.py` samples topics evenly |
| Order | Easy to hard, or by section (grammar, vocabulary, reading) |
| Instructions | One per section, with an example |
| Answer key | Answers with short explanations that teach |
| Versions | Different seeds for parallel versions (`--seed`) |

## After the quiz

- Look at items most of the class got wrong: was it the teaching or the item?
- Re-teach the point; reuse a different item on it later.
- Keep a bank and tag items by topic and level so quizzes can be rebuilt quickly.
