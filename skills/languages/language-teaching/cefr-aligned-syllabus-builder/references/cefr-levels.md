# The CEFR for Syllabus Design

The Common European Framework of Reference for Languages (Council of Europe 2001; Companion Volume 2020) describes
what learners **can do** with a language at six levels. It is language-neutral, action-oriented and not a
syllabus: it tells you outcomes, not what to teach in which order.

## Levels in brief (paraphrased from the global scale)

| Level | Name | A learner at this level can... |
|-------|------|--------------------------------|
| Pre-A1 | | Use isolated words and formulaic phrases for immediate needs (name, numbers, greetings) |
| A1 | Breakthrough | Understand and use familiar everyday expressions and very basic phrases; introduce themselves; ask and answer simple personal questions if the other person speaks slowly and helps |
| A2 | Waystage | Understand frequently used expressions in areas of immediate relevance (family, shopping, work); communicate in simple routine exchanges; describe background and immediate needs simply |
| B1 | Threshold | Understand the main points of clear standard input on familiar matters; deal with most travel situations; produce simple connected text; describe experiences, hopes, ambitions; give brief reasons |
| B2 | Vantage | Understand the main ideas of complex text, including technical discussion in their field; interact with fluency and spontaneity with native speakers without strain; produce clear detailed text and explain a viewpoint with pros and cons |
| C1 | Effective operational proficiency | Understand demanding longer texts and implicit meaning; express ideas fluently and spontaneously; use language flexibly for social, academic and professional purposes; produce well-structured detailed text on complex subjects |
| C2 | Mastery | Understand virtually everything heard or read; summarise and reconstruct arguments coherently; express themselves spontaneously, precisely and with fine shades of meaning |

"Plus" levels (A2+, B1+, B2+) mark a strong performance within a level and are useful for long courses.

## Modes of communication (Companion Volume 2020)

| Mode | Activities |
|------|------------|
| Reception | Listening, reading, audio-visual |
| Production | Speaking (sustained monologue, public announcements), writing (reports, essays, creative) |
| Interaction | Conversation, discussion, goal-oriented cooperation, transactions, information exchange, interviews, online interaction |
| Mediation | Mediating texts (relaying, explaining data, translating, summarising), mediating concepts (collaborating, leading group work), mediating communication (facilitating, acting as intermediary) |

Plan a syllabus with all four modes, not only the four skills: interaction and mediation are often missing.

## Competences

- **Linguistic**: range and control of vocabulary, grammar, phonology, orthography.
- **Sociolinguistic**: register, politeness, idiom, dialect awareness.
- **Pragmatic**: discourse (cohesion, coherence, turn-taking), functional (fluency, precision).
- **Plurilingual / pluricultural**: using all one's languages and cultural knowledge.

## Guided learning hours (approximate, Cambridge English)

| Level reached | Cumulative hours from beginner |
|---------------|--------------------------------|
| A2 | ~180-200 |
| B1 | ~350-400 |
| B2 | ~500-600 |
| C1 | ~700-800 |
| C2 | ~1,000-1,200 |

`scripts/cefr_hours.py` estimates hours between levels with an L1-distance adjustment. Hours are guides: levels
take longer at higher stages, and learners plateau around B1-B2 without exposure outside class.

## Building a syllabus from the CEFR

1. Fix the entry and exit level from placement data and the hours available.
2. Choose a syllabus type: topic/situation-based (general English), functional-notional, task-based, skills-
   based (EAP), or a multi-strand mix (most common).
3. Write can-do outcomes per unit (see the can-do-statement-writer skill).
4. Map language to outcomes: grammar from [core-inventory-by-level.md](core-inventory-by-level.md), lexis from
   topic and frequency lists, functions, pronunciation.
5. Sequence: simple to complex, frequent to rare, learner needs first; recycle each item in later units.
6. Balance modes (reception, production, interaction, mediation) across units.
7. Plan assessment: formative per unit, progress tests every 3-4 units, an exit test aligned to the exit level.
8. Check with `scripts/syllabus_check.py`.

## Syllabus unit template

| Field | Example (A2, unit 4) |
|-------|----------------------|
| Topic / situation | Holidays and travel |
| Can-do outcomes | I can talk about a past holiday; I can understand a simple travel blog |
| Grammar | Past simple regular/irregular; was/were |
| Vocabulary | Holiday activities, transport, adjectives for places |
| Functions | Telling a story, showing interest (Really? How was it?) |
| Pronunciation | -ed endings /t/ /d/ /ɪd/ |
| Skills / modes | Reading (blog), speaking (interaction), writing (postcard), mediation (summarise a friend's story) |
| Assessment | Speaking task with checklist; vocabulary quiz |
