# Criteria and Rubrics for L2 Writing

## Analytic criteria

| Criterion | Looks at | Common descriptor features |
|-----------|----------|----------------------------|
| Task achievement / content | All parts of the task addressed; relevant, developed ideas; position clear (essays); correct format and purpose | Covers all points; ideas supported with examples; reader fully informed |
| Organisation and coherence | Paragraphing, logical progression, cohesive devices, referencing | Clear paragraphs with topic sentences; range of linkers used accurately; pronouns refer clearly |
| Lexical range and accuracy | Range, precision, collocation, spelling, word formation | Topic-specific vocabulary; less common items; errors rare and do not impede |
| Grammatical range and accuracy | Range of structures, complex sentences, error frequency and impact, punctuation | Mix of simple and complex sentences; errors rare and minor |
| Register and communicative effect (optional) | Appropriate tone and formality for reader and purpose | Consistent formal or informal tone; conventions of the genre (greetings, sign-off) |

Many exam boards use four criteria like these; Cambridge English uses content, communicative achievement,
organisation and language. Pick names that match your task and keep them consistent across levels.

## Example: 0-5 analytic rubric for a B1 email (100-120 words)

| Band | Content | Organisation | Language |
|------|---------|--------------|----------|
| 5 | All three points covered and expanded; reader fully informed | Well organised; varied linkers; clear paragraphs | Range of everyday vocabulary and simple and some complex grammar; errors rare |
| 4 | All points covered; most expanded | Generally well organised; simple linkers used well | Everyday vocabulary used appropriately; simple grammar good control; errors do not impede |
| 3 | All points covered, some briefly; or one point missing but others expanded | Connected using basic linkers (and, but, because) | Everyday vocabulary, sometimes overused; simple grammar reasonable control; errors noticeable but meaning clear |
| 2 | Points partly covered; some irrelevance | Some linking but sentences often unconnected | Basic vocabulary; frequent errors sometimes obscure meaning |
| 1 | Little relevant content | Little organisation | Very basic language; errors often impede |
| 0 | Off-task or too little to assess | | |

## Genre-specific checks

| Genre | Content and format checks |
|-------|---------------------------|
| Informal email / letter | Greeting and sign-off, all prompt points, friendly tone, questions to the reader |
| Formal email / letter | Purpose stated early, formal greeting and closing, polite requests, no contractions |
| Opinion essay | Clear position, reasons with support, counter-argument at B2+, conclusion restating position |
| Discursive essay | Both sides, balanced, linking contrast, conclusion |
| Report | Title, headings, purpose, findings, recommendations, impersonal style |
| Review | Description, evaluation, recommendation, engaging style |
| Story | Clear sequence, narrative tenses, setting and characters, ending |

## Word counts by level (typical exam ranges)

| Level | Task | Words |
|-------|------|-------|
| A1 | Note, form, postcard | 25-35 |
| A2 | Short message, email, story | 35-100 |
| B1 | Email, article, story | 100-120 |
| B2 | Essay, article, review, letter | 140-190 |
| C1 | Essay, report, proposal | 220-260 |
| C2 | Essay, article, report | 240-320 |

## Scoring procedure

1. Read the whole text once for overall impression and task completion.
2. Score task/content first: if off-task, score 0 and stop (`writing_score.py --gate task`).
3. Score each remaining criterion with evidence noted (one or two examples).
4. Use `essay_profile.py` for length, paragraphing and linker data, not for the bands themselves.
5. Do not penalise one error in several criteria (a spelling error counts in lexis only).
6. Double-mark a sample; standardise with benchmark scripts before marking.

## Feedback from the rubric

Return the band per criterion with one strength and one target each. A "jagged" profile (one criterion far below
the others, flagged by `writing_score.py`) is the best target for the next piece of writing.
