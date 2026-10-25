# Designing a Placement Test

A placement test has one job: put each learner in the class where they will learn best, quickly and cheaply. It
needs to separate adjacent levels well, not to measure everything.

## Blueprint

| Decision | Recommendation |
|----------|----------------|
| Levels to separate | Only the levels you actually run (e.g. A1, A2, B1, B2, C1) |
| Sections | Grammar and vocabulary in context (MCQ or gap-fill), reading, listening; plus a short speaking interview and/or writing sample for borderline and higher levels |
| Length | 40-60 MCQ items (30-40 minutes) + 5-minute interview; longer tests rarely place better |
| Items per level | 8-12 items targeted at each level, ordered from easy to hard (or a branching/adaptive design) |
| Item difficulty | Items at each level should be answered correctly by most learners at that level and few below it |
| Delivery | Online with automatic scoring for the written part; interview by trained teachers with a rubric |
| Security | Item bank with 2-3 parallel forms; rotate forms; do not use coursebook test items |

## Content by level (English example)

| Level | Grammar/vocabulary items test | Reading/listening texts |
|-------|-------------------------------|-------------------------|
| A1 | be, have got, present simple, there is, basic prepositions, numbers, family, days | Signs, short messages, form details |
| A2 | Past simple, going to, comparatives, countable/uncountable, should | Short emails, adverts, simple announcements |
| B1 | Present perfect, conditionals 1-2, passive, used to, reported speech | Short articles, voicemail messages, short conversations |
| B2 | Past perfect, third conditional, modals of deduction, phrasal verbs, collocation | Longer articles, interviews, opinions |
| C1 | Inversion, cleft sentences, advanced collocation, idiom, register | Academic or journalistic extracts, implied meaning |

## Item types

| Type | Placement use | Note |
|------|---------------|------|
| MCQ in a sentence or short dialogue | Fast, reliable | Three or four options; plausible distractors |
| Gap-fill in a text (open cloze) | Good discrimination at B1+ | Accept listed alternatives |
| Reading with MCQ | Tests real comprehension | Keep texts short (80-250 words) |
| Listening with MCQ | Needed: many learners read better than they listen | 30-60 second clips |
| Writing sample (60-150 words) | Distinguishes B1/B2/C1 | Rate with a short rubric |
| Speaking interview (5 min) | Essential for spoken courses and borderline cases | Warm-up, level probes, checks of the next level up |

## Speaking interview structure

1. Warm-up (A1-A2): name, where from, work or study.
2. Probe at the provisional level from the written test.
3. Push one level higher (a B2 question for a provisional B1): can the learner sustain it?
4. Wind down at a comfortable level.
Rate against a short level-referenced rubric (see the speaking-rubric-builder skill).

## Setting cut scores

| Method | How | When |
|--------|-----|------|
| Contrasting groups | Give the test to learners already well placed at each level; set the cut where the score distributions of adjacent levels cross | Existing classes available |
| Borderline group | Teachers identify learners on the border between two levels; the cut is their median score | Experienced teachers |
| Modified Angoff | Panel estimates, item by item, the probability that a just-qualified learner at the level answers correctly; sum = cut | New test before trial data |
| Empirical adjustment | After the first term, move cuts where many learners were moved up or down | Always, every year |

Treat scores within one standard error of measurement (SEM) of a cut as borderline. SEM = SD x sqrt(1 - reliability);
for a 50-item test with SD 8 and reliability 0.9, SEM is about 2.5 points.

## Validating placement

- Track how many learners change class in the first two weeks (target under 10%).
- Ask teachers in week two: is each learner in the right class?
- Run item analysis (`item_analysis.py`) after each intake of 30+ learners; replace weak items.
- Compare placement with end-of-course results.
