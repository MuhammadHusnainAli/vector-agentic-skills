# Adapting Texts for a CEFR Level

## Text features by level (guide values)

| Level | Length (words) | Avg sentence | Vocabulary | Grammar | Text types |
|-------|----------------|--------------|------------|---------|------------|
| A1 | 50-150 | 6-8 | Very frequent, concrete | Present simple, can, there is | Notes, signs, simple descriptions, short messages |
| A2 | 100-250 | 8-11 | Frequent everyday | Past simple, going to, comparatives | Emails, short stories, ads, simple articles |
| B1 | 200-400 | 11-15 | Everyday + topic words glossed | Present perfect, conditionals 1-2, passive (simple) | Articles, blogs, stories, reviews |
| B2 | 350-650 | 15-20 | Wider, some idiom | Full tense range, reported speech, relative clauses | Opinion articles, reports, literature extracts |
| C1 | 500-900 | 18-25 | Abstract, academic, idiomatic | Complex subordination, nominalisation | Academic, journalism, essays |
| C2 | Any | Any | Any | Any | Unadapted texts of any genre |

Learners need to know about 95-98% of the running words to read comfortably without a dictionary; that is
why coverage matters more than "difficult words" one by one.

## Two approaches

| Approach | What it does | Keeps | Risk |
|----------|--------------|-------|------|
| Simplification | Shorter sentences, frequent words, simpler grammar | Readability | Loses cohesion, richness, authenticity |
| Elaboration | Keeps the original language, adds redundancy: paraphrases, definitions in brackets, explicit links | Language input | Text gets longer |

Research favours elaboration where possible: learners understand nearly as well and meet more natural language.
Combine both: simplify the hardest sentences, elaborate key words.

## Techniques

| Problem | Technique | Before -> after |
|---------|-----------|-----------------|
| Long sentence | Split at linkers; one idea per sentence | "Advocates argue..., although ecologists warn..." -> "Supporters say... But scientists warn..." |
| Rare word, not key | Replace with a frequent word | considerably -> a lot |
| Rare word, key to the topic | Keep and gloss (bracket, footnote, picture) or pre-teach | hive (a box where bees live) |
| Nominalisation | Turn back into verbs | the introduction of registration schemes -> cities introduced rules |
| Passive with no agent | Make active when the agent helps | Hives are inspected -> Officials inspect the hives |
| Idiom / phrasal verb | Literal paraphrase at lower levels | ran into trouble -> had problems |
| Pronoun with distant referent | Repeat the noun | it -> the plan |
| Implicit link | Add the linker | (no link) -> so, because, but |
| Cultural reference | Explain or replace | a Saturday-job at Woolworths -> a weekend job in a shop |
| Dense numbers | Round and reduce | 37.4% -> more than a third |

Keep: the main ideas, the order of events, the text type (an email stays an email), the target language you
want learners to notice, and the facts the tasks depend on.

## Process

1. Measure: `python scripts/text_level.py original.txt --target B1`.
2. Decide what must stay (ideas, target language, facts for tasks).
3. Cut what the tasks do not need (side points, examples beyond two).
4. Split long sentences; replace or gloss rare words (start with words that appear more than once).
5. Re-measure; repeat until the estimate is at the target and long sentences are few.
6. Read aloud: it must still sound natural.
7. Credit the source: "Adapted from ... (date)".

## Graded versions for mixed classes

Write the B1 version first, then derive A2 (shorter, more glosses) and B2 (more original wording). Keep the
same paragraph order and facts so all learners can do the same gist task and discuss together.
