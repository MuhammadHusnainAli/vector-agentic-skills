# Language teaching skill script cases. Syntax: see tests/run_tests.sh.

# ---- Lesson planning
t 'plan_scaffold: timed stage table' 0 '| 22-37 | Controlled practice |' \
  "$LT/language-lesson-plan-builder/scripts/plan_scaffold.py" "$FX/lt/lesson_good.json"
t 'plan_scaffold: unplanned minutes noted' 0 'Note: 10 min unplanned' \
  "$LT/language-lesson-plan-builder/scripts/plan_scaffold.py" "$FX/lt/lesson_weak.json"
STDIN='{"minutes":30,"stages":[{"name":"a","minutes":40}]}' t 'plan_scaffold: overrun exits 1' 1 'stages take 40 min but the lesson is 30 min' \
  "$LT/language-lesson-plan-builder/scripts/plan_scaffold.py" -
STDIN='{"stages":[]}' t 'plan_scaffold: empty stages exits 2' 2 'non-empty' \
  "$LT/language-lesson-plan-builder/scripts/plan_scaffold.py" -
t 'plan_check: sound plan passes' 0 'OK: aims, timing' \
  "$LT/language-lesson-plan-builder/scripts/plan_check.py" "$FX/lt/lesson_good.json"
t 'plan_check: teacher-centred aim' 1 "LP001 [high] main aim 'To teach the present perfect" \
  "$LT/language-lesson-plan-builder/scripts/plan_check.py" "$FX/lt/lesson_weak.json"
t 'plan_check: teacher-fronted time' 1 'LP005 [medium] T-Ss stages take 58%' \
  "$LT/language-lesson-plan-builder/scripts/plan_check.py" "$FX/lt/lesson_weak.json"
t 'plan_check: task without feedback' 1 "LP006 [medium] 'Gap-fill' is pair/group work" \
  "$LT/language-lesson-plan-builder/scripts/plan_check.py" "$FX/lt/lesson_weak.json"
t 'plan_check: no freer practice' 1 'LP007 [medium] language-focus lesson with no freer practice' \
  "$LT/language-lesson-plan-builder/scripts/plan_check.py" "$FX/lt/lesson_weak.json"
t 'ppp_timing: A2 60 min stages' 0 '| 12-24 | Clarification: meaning, form, pronunciation |' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_timing.py" --minutes 60 --level A2
t 'ppp_timing: phase totals' 0 'Presentation 24 min | Practice 13 min | Production 20 min' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_timing.py" --minutes 60 --level A2
t 'ppp_timing: json for plan_scaffold' 0 '"name": "Freer practice"' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_timing.py" --minutes 45 --level B2 --json
t 'ppp_timing: too short exits 2' 2 'need --minutes >= 20' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_timing.py" --minutes 10
t 'ppp_check: complete TLA passes' 0 'OK: meaning, form, pronunciation' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_check.py" "$FX/lt/tla_good.json"
t 'ppp_check: missing form and pronunciation' 1 "PP001 [high] 'be used to + -ing': no form, pronunciation" \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_check.py" "$FX/lt/tla_weak.json"
t 'ppp_check: CCQ repeats target language' 1 "PP003 [medium] 'Did Anna used to live in a village?' repeats" \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_check.py" "$FX/lt/tla_weak.json"
t 'ppp_check: do you understand' 1 "PP004 [medium] 'Do you understand?' does not check meaning" \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_check.py" "$FX/lt/tla_weak.json"
t 'ppp_check: controlled freer task' 1 'PP007 [medium] freer task' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_check.py" "$FX/lt/tla_weak.json"
STDIN='[1,2]' t 'ppp_check: non-object exits 2' 2 'JSON must be an object' \
  "$LT/ppp-lesson-structure-planner/scripts/ppp_check.py" -
t 'task_check: real task in full cycle' 0 'OK: a real task in a complete Willis cycle' \
  "$LT/task-based-language-lesson-designer/scripts/task_check.py" "$FX/lt/tbl_good.json"
t 'task_check: disguised grammar exercise' 1 "TB001 [high] instructions ask for 'using the going to'" \
  "$LT/task-based-language-lesson-designer/scripts/task_check.py" "$FX/lt/tbl_weak.json"
t 'task_check: no outcome' 1 'TB003 [high] no clear outcome' \
  "$LT/task-based-language-lesson-designer/scripts/task_check.py" "$FX/lt/tbl_weak.json"
t 'task_check: stage order' 1 'TB006 [medium] language focus is before the task' \
  "$LT/task-based-language-lesson-designer/scripts/task_check.py" "$FX/lt/tbl_weak.json"
t 'task_check: missing Willis stages' 1 'TB005 [medium] Willis stage(s) missing: planning, report' \
  "$LT/task-based-language-lesson-designer/scripts/task_check.py" "$FX/lt/tbl_weak.json"
t 'task_check: missing file exits 2' 2 'error:' \
  "$LT/task-based-language-lesson-designer/scripts/task_check.py" "$FX/lt/nope.json"
t 'activity_picker: filters by level, skill, time, size' 0 '8 of 38 activities match' \
  "$LT/communicative-activity-generator/scripts/activity_picker.py" --level B1 --skill speaking --minutes 15 --students 2
t 'activity_picker: focus and online' 0 '## Two truths and a lie' \
  "$LT/communicative-activity-generator/scripts/activity_picker.py" --level A2 --focus 'past simple' --online --prep low
t 'activity_picker: nothing fits exits 1' 1 'No activity matches' \
  "$LT/communicative-activity-generator/scripts/activity_picker.py" --level C2 --minutes 5
t 'activity_picker: bad level exits 2' 2 'level must be one of' \
  "$LT/communicative-activity-generator/scripts/activity_picker.py" --level D1
t 'activity_picker: missing bank exits 2' 2 'error:' \
  "$LT/communicative-activity-generator/scripts/activity_picker.py" --bank "$FX/lt/nope.md"
t 'warmer_picker: icebreakers for A2 class' 0 '8 match(es) in 34 warmers' \
  "$LT/warm-up-icebreaker-generator/scripts/warmer_picker.py" --purpose icebreaker --level A2 --students 14 --minutes 10
t 'warmer_picker: seeded review warmers online' 0 '## Categories  (review, energiser' \
  "$LT/warm-up-icebreaker-generator/scripts/warmer_picker.py" --purpose review --level B1 --online --seed 7 --exclude 'Alphabet race' --show 2
t 'warmer_picker: nothing fits exits 1' 1 'No warmer matches' \
  "$LT/warm-up-icebreaker-generator/scripts/warmer_picker.py" --purpose icebreaker --level A1 --minutes 3
t 'warmer_picker: bad level exits 2' 2 'level must be one of' \
  "$LT/warm-up-icebreaker-generator/scripts/warmer_picker.py" --level Z9
t 'group_learners: mixed groups span levels and L1s' 0 'Group 1: Eva (C1, Spanish), Chen (B1, Mandarin), Goro (B1, Japanese), Farid (A1, Arabic)' \
  "$LT/language-lesson-differentiation-planner/scripts/group_learners.py" "$FX/lt/class_levels.csv" --size 4
t 'group_learners: same-level groups' 0 'Group 4: Hana (A2, Japanese), Kemal (A2, Turkish), Farid (A1, Arabic)' \
  "$LT/language-lesson-differentiation-planner/scripts/group_learners.py" "$FX/lt/class_levels.csv" --size 3 --mode same
t 'group_learners: flags outliers' 0 'FLAG Farid (A1) is far from the class median: support' \
  "$LT/language-lesson-differentiation-planner/scripts/group_learners.py" "$FX/lt/class_levels.csv"
STDIN=$'name,level\nA,Q9\nB,B1\n' t 'group_learners: bad level exits 2' 2 'needs name and level columns' \
  "$LT/language-lesson-differentiation-planner/scripts/group_learners.py" /dev/stdin

# ---- Materials creation
t 'gap_fill: target words gapped with bank' 0 'Last summer I (1) ________ to Lisbon' \
  "$LT/esl-worksheet-generator/scripts/gap_fill.py" "$FX/lt/holiday.txt" --words went stayed bought saw 'used to' --distractors goed seen
t 'gap_fill: phrase in answer key' 0 '5. used to' \
  "$LT/esl-worksheet-generator/scripts/gap_fill.py" "$FX/lt/holiday.txt" --words went stayed bought saw 'used to'
t 'gap_fill: cloze with hints' 0 'small hotel (1) n______ the river' \
  "$LT/esl-worksheet-generator/scripts/gap_fill.py" "$FX/lt/holiday.txt" --every 7 --no-bank --hint
t 'gap_fill: missing word exits 1' 1 'not in the text: flew' \
  "$LT/esl-worksheet-generator/scripts/gap_fill.py" "$FX/lt/holiday.txt" --words flew
t 'gap_fill: nothing to gap exits 2' 2 'nothing to gap' \
  "$LT/esl-worksheet-generator/scripts/gap_fill.py" "$FX/lt/holiday.txt"
t 'matching: shuffled with key' 0 'Answer key: 1-c  2-e  3-a  4-b  5-d' \
  "$LT/esl-worksheet-generator/scripts/matching.py" "$FX/lt/phrasal_pairs.csv" --seed 2
t 'matching: markdown table' 0 '| 1 | give up | a |' \
  "$LT/esl-worksheet-generator/scripts/matching.py" "$FX/lt/phrasal_pairs.csv" --markdown
STDIN=$'a,b\n' t 'matching: too few pairs exits 2' 2 'need 3-26 pairs, got 1' \
  "$LT/esl-worksheet-generator/scripts/matching.py" -
t 'text_level: A2 text fits A2' 0 'Target A2: OK' \
  "$LT/reading-comprehension-text-adapter/scripts/text_level.py" "$FX/lt/holiday.txt" --target A2
t 'text_level: dense article above B1' 1 'Target B1: ADAPT - text is above target' \
  "$LT/reading-comprehension-text-adapter/scripts/text_level.py" "$FX/lt/article_b2.txt" --target B1
t 'text_level: long sentences listed' 1 'Sentences over 20 words for B1:' \
  "$LT/reading-comprehension-text-adapter/scripts/text_level.py" "$FX/lt/article_b2.txt" --target B1
t 'text_level: rare words with counts' 0 'Less frequent words: hives (2), urban' \
  "$LT/reading-comprehension-text-adapter/scripts/text_level.py" "$FX/lt/article_b2.txt"
STDIN='   ' t 'text_level: empty text exits 2' 2 'no sentences found' \
  "$LT/reading-comprehension-text-adapter/scripts/text_level.py" -
t 'question_mix: staged question set' 0 'Order: gist -> detail -> detail -> inference -> response' \
  "$LT/reading-comprehension-text-adapter/scripts/question_mix.py" "$FX/lt/questions_good.txt" --level B1
t 'question_mix: no gist task' 1 'RQ001 [high] no gist task' \
  "$LT/reading-comprehension-text-adapter/scripts/question_mix.py" "$FX/lt/questions_weak.txt"
t 'question_mix: guessable yes/no' 1 "RQ006 [low] Q3 'Is Lisbon a city?'" \
  "$LT/reading-comprehension-text-adapter/scripts/question_mix.py" "$FX/lt/questions_weak.txt"
STDIN=$'1. The writer went with her sister. (T/F)\n2. They stayed in a big hotel. (T/F)\n3. They saw a film. (T/F)\nWhat is the text mainly about?\n' \
  t 'question_mix: one-sided T/F key' 0 'RQ004 [medium] all true/false answers are T' \
  "$LT/reading-comprehension-text-adapter/scripts/question_mix.py" - --key T T T
t 'wordsearch: phrase placed without spaces' 0 'LOOKAFTER row 5 col 2 right' \
  "$LT/vocabulary-game-generator/scripts/wordsearch.py" --file "$FX/lt/house_words.txt" --seed 4
t 'wordsearch: word longer than grid exits 2' 2 "'EXTRAORDINARILY' is longer than the 8x8 grid" \
  "$LT/vocabulary-game-generator/scripts/wordsearch.py" --words extraordinarily --size 8
t 'wordsearch: no words exits 2' 2 'give --words or --file' \
  "$LT/vocabulary-game-generator/scripts/wordsearch.py"
t 'bingo_cards: free centre square' 0 '| bird  | FREE  | goat  |' \
  "$LT/vocabulary-game-generator/scripts/bingo_cards.py" --words cat dog bird fish horse cow sheep goat duck --cards 2 --size 3 --free --seed 2
t 'bingo_cards: caller list' 0 'Caller list: cow, goat, dog' \
  "$LT/vocabulary-game-generator/scripts/bingo_cards.py" --words cat dog bird fish horse cow sheep goat duck --cards 2 --size 3 --free --seed 2
t 'bingo_cards: too few words exits 2' 2 '4x4 cards need at least 16 different words, got 8' \
  "$LT/vocabulary-game-generator/scripts/bingo_cards.py" --file "$FX/lt/house_words.txt" --size 4
t 'vocab_extract: pre-teach shortlist with task words' 0 'Pre-teach (max 6): register (1x), stings (1x), scheme (4x)' \
  "$LT/authentic-material-lesson-adapter/scripts/vocab_extract.py" "$FX/lt/news_authentic.txt" --level B1 --task-words register stings cost
t 'vocab_extract: names and cultural references' 0 'Names / cultural references to check: City Council, New York, Los Angeles' \
  "$LT/authentic-material-lesson-adapter/scripts/vocab_extract.py" "$FX/lt/news_authentic.txt"
t 'vocab_extract: low coverage advice' 0 'grade the task (gist, scanning)' \
  "$LT/authentic-material-lesson-adapter/scripts/vocab_extract.py" "$FX/lt/news_authentic.txt"
t 'vocab_extract: task word missing' 0 'Task words not found in the text: lottery' \
  "$LT/authentic-material-lesson-adapter/scripts/vocab_extract.py" "$FX/lt/news_authentic.txt" --task-words lottery
STDIN='123 456' t 'vocab_extract: empty text exits 2' 2 'empty text' \
  "$LT/authentic-material-lesson-adapter/scripts/vocab_extract.py" -
t 'transcript_stats: rate and speakers' 1 '91 words in 0:40: 136 wpm (moderate); speakers: 2 (Guest, Receptionist)' \
  "$LT/listening-task-builder/scripts/transcript_stats.py" "$FX/lt/hotel_dialogue.txt" --duration 0:40 --level A2 --segments 3
t 'transcript_stats: pause points' 1 '1. ~0:14 after' \
  "$LT/listening-task-builder/scripts/transcript_stats.py" "$FX/lt/hotel_dialogue.txt" --duration 0:40 --level A2 --segments 3
t 'transcript_stats: suits B1' 0 'OK for the level' \
  "$LT/listening-task-builder/scripts/transcript_stats.py" "$FX/lt/hotel_dialogue.txt" --duration 40 --level B1
t 'transcript_stats: too fast for A1' 1 'speech is 72 wpm faster than the A1 guide' \
  "$LT/listening-task-builder/scripts/transcript_stats.py" "$FX/lt/hotel_dialogue.txt" --duration 30 --level A1
t 'transcript_stats: bad duration exits 2' 2 "duration '1:75' must be seconds or m:ss" \
  "$LT/listening-task-builder/scripts/transcript_stats.py" "$FX/lt/hotel_dialogue.txt" --duration 1:75
t 'dialogue_check: natural A2 dialogue passes' 0 'OK: target language present' \
  "$LT/dialogue-for-classroom-writer/scripts/dialogue_check.py" "$FX/lt/hotel_dialogue.txt" --level A2 --target 'Can I see' 'What time'
t 'dialogue_check: target line numbers' 0 "target 'What time': line 4" \
  "$LT/dialogue-for-classroom-writer/scripts/dialogue_check.py" "$FX/lt/hotel_dialogue.txt" --level A2 --target 'Can I see' 'What time'
t 'dialogue_check: missing target' 1 "DC001 [high] target phrase 'How much' is not in the dialogue" \
  "$LT/dialogue-for-classroom-writer/scripts/dialogue_check.py" "$FX/lt/dialogue_stiff.txt" --level A2 --target 'How much'
t 'dialogue_check: unbalanced roles' 0 'DC003 [medium] Customer has 87% of the words' \
  "$LT/dialogue-for-classroom-writer/scripts/dialogue_check.py" "$FX/lt/dialogue_stiff.txt" --level A2
t 'dialogue_check: long turn' 0 'DC004 [medium] line 1: Customer speaks 44 words in one turn (max 18 at A2)' \
  "$LT/dialogue-for-classroom-writer/scripts/dialogue_check.py" "$FX/lt/dialogue_stiff.txt" --level A2
STDIN='Just one line with no speaker' t 'dialogue_check: no speakers' 1 'DC002 [high] needs at least two speakers' \
  "$LT/dialogue-for-classroom-writer/scripts/dialogue_check.py" -

# ---- Curriculum and syllabus
t 'syllabus_check: coverage count' 1 '6 units, A1-A2: 12/25 core grammar items covered' \
  "$LT/cefr-aligned-syllabus-builder/scripts/syllabus_check.py" "$FX/lt/syllabus_a2.csv" --level A2 --from A1
t 'syllabus_check: unit without can-do' 1 'SY001 [high] unit 5 has no can-do statement' \
  "$LT/cefr-aligned-syllabus-builder/scripts/syllabus_check.py" "$FX/lt/syllabus_a2.csv" --level A2
t 'syllabus_check: item above level' 1 "SY003 [medium] unit 6: 'Third conditional' is B2, above the A2 course" \
  "$LT/cefr-aligned-syllabus-builder/scripts/syllabus_check.py" "$FX/lt/syllabus_a2.csv" --level A2
t 'syllabus_check: core gap' 1 'SY002 [medium] A2 core item not covered: Should (advice)' \
  "$LT/cefr-aligned-syllabus-builder/scripts/syllabus_check.py" "$FX/lt/syllabus_a2.csv" --level A2
STDIN=$'unit,topic\n1,x\n' t 'syllabus_check: no grammar column exits 2' 2 'needs at least unit and grammar' \
  "$LT/cefr-aligned-syllabus-builder/scripts/syllabus_check.py" /dev/stdin --level A2
t 'cefr_hours: A2 to B2' 0 'A2 -> B2: about 360 guided hours (range 288-432)' \
  "$LT/cefr-aligned-syllabus-builder/scripts/cefr_hours.py" --from A2 --to B2 --hours-per-week 6
t 'cefr_hours: weekly hours needed' 0 'In 30 weeks: about 16.2 class hours per week' \
  "$LT/cefr-aligned-syllabus-builder/scripts/cefr_hours.py" --from B1 --to C1 --weeks 30 --distance far
t 'cefr_hours: backwards exits 2' 2 'must be above' \
  "$LT/cefr-aligned-syllabus-builder/scripts/cefr_hours.py" --from B2 --to A2
t 'sequence_check: contrast before its parts' 1 "SQ001 [high] 'present perfect vs past simple' (unit 2) comes before 'present perfect' (unit 4)" \
  "$LT/language-course-scope-sequence-planner/scripts/sequence_check.py" "$FX/lt/scope.csv"
t 'sequence_check: never recycled' 1 "SQ003 [medium] 'comparatives' (unit 5) is never recycled" \
  "$LT/language-course-scope-sequence-planner/scripts/sequence_check.py" "$FX/lt/scope.csv"
t 'sequence_check: teaching order' 1 'Teaching order: present simple -> past simple -> present perfect -> present perfect vs past simple' \
  "$LT/language-course-scope-sequence-planner/scripts/sequence_check.py" "$FX/lt/scope.csv"
STDIN=$'item,unit,requires,recycled_in\na,1,b,2\nb,2,a,3\n' t 'sequence_check: cycle' 1 'SQ002 [high] circular prerequisites: a -> b -> a' \
  "$LT/language-course-scope-sequence-planner/scripts/sequence_check.py" /dev/stdin
STDIN=$'item,unit\na,x\n' t 'sequence_check: bad unit exits 2' 2 'needs item and numeric unit' \
  "$LT/language-course-scope-sequence-planner/scripts/sequence_check.py" /dev/stdin
t 'pacing: lessons after holidays' 0 '42 lessons (3 lost to holidays); 2 review, 2 assessment, 38 for 8 units' \
  "$LT/language-course-scope-sequence-planner/scripts/pacing.py" --start 2026-09-07 --end 2026-12-18 --days mon wed fri --units 8 --holidays 2026-10-26:2026-10-30 2026-11-26 --review-every 3 --assessment 2
t 'pacing: unit after half-term' 0 '| Unit 5 | 5 | 2026-11-02 | 2026-11-11 |' \
  "$LT/language-course-scope-sequence-planner/scripts/pacing.py" --start 2026-09-07 --end 2026-12-18 --days mon wed fri --units 8 --holidays 2026-10-26:2026-10-30 2026-11-26 --review-every 3 --assessment 2
t 'pacing: too few lessons exits 1' 1 'only 2 teaching lessons for 5 units' \
  "$LT/language-course-scope-sequence-planner/scripts/pacing.py" --start 2026-09-07 --end 2026-09-20 --days mon --units 5
t 'pacing: bad holiday date exits 2' 2 'error:' \
  "$LT/language-course-scope-sequence-planner/scripts/pacing.py" --start 2026-09-07 --end 2026-12-18 --days mon --units 2 --holidays 2026-13-01
t 'cando_lint: good set passes' 0 'OK: all statements are observable' \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" "$FX/lt/cando_good.txt"
t 'cando_lint: mediation detected' 0 '[4] (mediation) I can explain the main idea' \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" "$FX/lt/cando_good.txt"
t 'cando_lint: teacher-centred' 1 "CD001 [high] [1] start with 'I can'" \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" "$FX/lt/cando_weak.txt"
t 'cando_lint: knowledge not use' 1 "CD002 [high] [2] 'understand the passive' is knowledge" \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" "$FX/lt/cando_weak.txt"
t 'cando_lint: two skills' 1 'CD004 [medium] [4] two activities in one statement' \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" "$FX/lt/cando_weak.txt"
t 'cando_lint: grammar as outcome' 1 'CD007 [low] [5] names a grammar item' \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" "$FX/lt/cando_weak.txt"
STDIN=$'# only a comment\n' t 'cando_lint: no statements exits 2' 2 'no statements' \
  "$LT/can-do-statement-writer/scripts/cando_lint.py" -
t 'level_map: ACTFL abbreviation' 0 'ACTFL Intermediate High (IH)  ~  CEFR B1  ~  ILR 1+' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/level_map.py" ih
t 'level_map: from CEFR' 0 'ACTFL Advanced High (AH)  ~  CEFR B2  ~  ILR 2+' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/level_map.py" --cefr B2
t 'level_map: table' 0 '| Superior | C1 | 3 | Extended discourse |' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/level_map.py" --table
t 'level_map: unknown exits 2' 2 'unknown level' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/level_map.py" --ilr 5
t 'mode_coverage: matrix' 1 '| City | - | x | x | - |' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/mode_coverage.py" "$FX/lt/actfl_units.csv"
t 'mode_coverage: skit is not interpersonal' 1 "AC003 [medium] unit Food: interpersonal task 'Perform a memorized restaurant skit'" \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/mode_coverage.py" "$FX/lt/actfl_units.csv"
t 'mode_coverage: translation task' 1 "AC004 [low] unit Food: interpretive task 'Translate a menu'" \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/mode_coverage.py" "$FX/lt/actfl_units.csv"
t 'mode_coverage: no assessment' 1 'AC001 [high] unit City: no performance assessment' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/mode_coverage.py" "$FX/lt/actfl_units.csv"
STDIN=$'unit,reading\n1,x\n' t 'mode_coverage: wrong columns exits 2' 2 'needs unit, interpretive' \
  "$LT/actfl-proficiency-curriculum-mapper/scripts/mode_coverage.py" /dev/stdin
t 'program_metrics: course table' 1 '| General A2 | 12 | 83% | 90% | 1 | 89% | 4.5 |' \
  "$LT/language-program-review-writer/scripts/program_metrics.py" "$FX/lt/program_students.csv"
t 'program_metrics: low retention' 1 'PM001 [high] Evening B1: retention 62% (3 withdrew) is below 75%' \
  "$LT/language-program-review-writer/scripts/program_metrics.py" "$FX/lt/program_students.csv"
t 'program_metrics: zero gain' 1 'PM003 [medium] Evening B1: median level gain of completers is 0' \
  "$LT/language-program-review-writer/scripts/program_metrics.py" "$FX/lt/program_students.csv"
t 'program_metrics: custom threshold' 0 'PM002 [medium] Evening B1: pass rate 60%' \
  "$LT/language-program-review-writer/scripts/program_metrics.py" "$FX/lt/program_students.csv" --retention 50
STDIN=$'name,level\nA,B1\n' t 'program_metrics: wrong columns exits 2' 2 'needs student, course and status' \
  "$LT/language-program-review-writer/scripts/program_metrics.py" /dev/stdin

# ---- Assessment
t 'item_analysis: item table and reliability' 1 '30 students, 8 items, mean 5.2, KR-20 reliability 0.44' \
  "$LT/language-placement-test-builder/scripts/item_analysis.py" "$FX/lt/placement_responses.csv"
t 'item_analysis: miskeyed item' 1 'IA001 [high] Q6: discrimination -0.88' \
  "$LT/language-placement-test-builder/scripts/item_analysis.py" "$FX/lt/placement_responses.csv"
t 'item_analysis: mis-levelled item' 1 'IA005 [low] Q7 (B2) facility 0.90 is above the B1 mean 0.48' \
  "$LT/language-placement-test-builder/scripts/item_analysis.py" "$FX/lt/placement_responses.csv"
STDIN=$'student,Q1\nS1,A\n' t 'item_analysis: no key exits 2' 2 'need a header row, a KEY row' \
  "$LT/language-placement-test-builder/scripts/item_analysis.py" /dev/stdin
t 'placement_cutoffs: borderline interview' 0 '| Chen | 27 | A2 | borderline A2/B1: interview |' \
  "$LT/language-placement-test-builder/scripts/placement_cutoffs.py" "$FX/lt/placement_scores.csv" --cuts A1:0 A2:15 B1:28 B2:40 C1:50
t 'placement_cutoffs: summary' 0 'Placed: A1 2, A2 2, B1 1, B2 1, C1 1; 4 borderline to interview' \
  "$LT/language-placement-test-builder/scripts/placement_cutoffs.py" "$FX/lt/placement_scores.csv" --cuts A1:0 A2:15 B1:28 B2:40 C1:50
t 'placement_cutoffs: bad cuts exit 2' 2 'error:' \
  "$LT/language-placement-test-builder/scripts/placement_cutoffs.py" "$FX/lt/placement_scores.csv" --cuts A1:x
t 'rubric_check: missing band' 1 'SR001 [high] Pronunciation: no descriptor for band 4' \
  "$LT/speaking-rubric-builder/scripts/rubric_check.py" "$FX/lt/speaking_rubric_weak.csv"
t 'rubric_check: indistinct bands' 1 'SR002 [medium] Fluency: bands 3 and 4 are nearly identical' \
  "$LT/speaking-rubric-builder/scripts/rubric_check.py" "$FX/lt/speaking_rubric_weak.csv"
t 'rubric_check: evaluative only' 1 "SR003 [medium] Grammar band 2 'Good grammar'" \
  "$LT/speaking-rubric-builder/scripts/rubric_check.py" "$FX/lt/speaking_rubric_weak.csv"
t 'rubric_check: native benchmark' 1 'SR004 [medium] Grammar band 4: replace the native-speaker benchmark' \
  "$LT/speaking-rubric-builder/scripts/rubric_check.py" "$FX/lt/speaking_rubric_weak.csv"
STDIN=$'criterion,band\nx,1\n' t 'rubric_check: bad csv exits 2' 2 'needs criterion, band' \
  "$LT/speaking-rubric-builder/scripts/rubric_check.py" /dev/stdin
t 'rater_agreement: summary' 0 'Exact agreement 70%, adjacent 20%, within one band 90%' \
  "$LT/speaking-rubric-builder/scripts/rater_agreement.py" "$FX/lt/rater_scores.csv"
t 'rater_agreement: kappa and third rating' 0 'RA004 [low] S6: 2 vs 4; needs a third rating' \
  "$LT/speaking-rubric-builder/scripts/rater_agreement.py" "$FX/lt/rater_scores.csv"
STDIN=$'student,rater_a,rater_b\nA,1,4\nB,4,1\nC,2,2\n' t 'rater_agreement: poor agreement' 1 'RA001 [high] only 33% within one band' \
  "$LT/speaking-rubric-builder/scripts/rater_agreement.py" /dev/stdin
t 'essay_profile: linkers counted' 1 'Linkers (5 different): and x8, because x3, but x2' \
  "$LT/writing-rubric-for-l2-builder/scripts/essay_profile.py" "$FX/lt/essay_b1.txt" --min 140 --max 190 --formal
t 'essay_profile: under length' 1 'WP001 [high] 124 words is under the minimum of 140' \
  "$LT/writing-rubric-for-l2-builder/scripts/essay_profile.py" "$FX/lt/essay_b1.txt" --min 140 --max 190
t 'essay_profile: informal in formal task' 1 'WP005 [low] informal for the task: a lot of, don'"'"'t, gonna' \
  "$LT/writing-rubric-for-l2-builder/scripts/essay_profile.py" "$FX/lt/essay_b1.txt" --min 140 --formal
t 'essay_profile: within limits' 0 'Words: 124 (task 100-130)' \
  "$LT/writing-rubric-for-l2-builder/scripts/essay_profile.py" "$FX/lt/essay_b1.txt" --min 100 --max 130
t 'writing_score: weighted total and level' 0 '| Ana | 4 | 4 | 3 | 3 | 72 | B1 |  |' \
  "$LT/writing-rubric-for-l2-builder/scripts/writing_score.py" "$FX/lt/writing_scores.csv" --cuts A2:40 B1:60 B2:80 --weights task:2
t 'writing_score: off-task gate' 0 '| Chen | 0 | 3 | 3 | 3 | 0 | below | off-task' \
  "$LT/writing-rubric-for-l2-builder/scripts/writing_score.py" "$FX/lt/writing_scores.csv" --cuts A2:40 B1:60 B2:80
t 'writing_score: unknown weight exits 2' 2 'unknown criterion in --weights: style' \
  "$LT/writing-rubric-for-l2-builder/scripts/writing_score.py" "$FX/lt/writing_scores.csv" --weights style:2
t 'writing_score: out of range exits 2' 2 'outside 0-3' \
  "$LT/writing-rubric-for-l2-builder/scripts/writing_score.py" "$FX/lt/writing_scores.csv" --max-band 3
t 'quiz_build: shuffled quiz with key' 0 '1. D) have lived - "Since 2019"' \
  "$LT/language-quiz-generator/scripts/quiz_build.py" "$FX/lt/quiz_bank.txt" --n 4 --seed 2
t 'quiz_build: gap answer in key' 0 "didn't see | did not see" \
  "$LT/language-quiz-generator/scripts/quiz_build.py" "$FX/lt/quiz_bank.txt" --topic 'past simple' --n 2
t 'quiz_build: too few items exits 1' 1 'only 2 matching items for --n 5' \
  "$LT/language-quiz-generator/scripts/quiz_build.py" "$FX/lt/quiz_bank.txt" --level B1 --n 5
t 'quiz_build: no match exits 1' 1 'No items match' \
  "$LT/language-quiz-generator/scripts/quiz_build.py" "$FX/lt/quiz_bank.txt" --level C2
t 'quiz_check: clean bank' 0 'By topic: past simple 2, present perfect 2' \
  "$LT/language-quiz-generator/scripts/quiz_check.py" "$FX/lt/quiz_bank.txt"
t 'quiz_check: two keys' 1 'QC001 [high] item 1 (articles): 2 options marked correct' \
  "$LT/language-quiz-generator/scripts/quiz_check.py" "$FX/lt/quiz_bank_bad.txt"
t 'quiz_check: invalid tf answer' 1 'QC002 [high] item 4 (present perfect): missing or invalid ANS' \
  "$LT/language-quiz-generator/scripts/quiz_check.py" "$FX/lt/quiz_bank_bad.txt"
t 'quiz_check: long key cue' 1 'QC005 [medium] item 2 (modals): correct option is much longer' \
  "$LT/language-quiz-generator/scripts/quiz_check.py" "$FX/lt/quiz_bank_bad.txt"
t 'quiz_check: empty bank exits 2' 2 'no items found' \
  "$LT/language-quiz-generator/scripts/quiz_check.py" "$FX/lt/holiday.txt"
t 'exit_ticket_tally: reteach decision' 0 '| ed pronunciation | 40% | RETEACH | whole class |' \
  "$LT/formative-assessment-for-language-planner/scripts/exit_ticket_tally.py" "$FX/lt/exit_ticket.csv"
t 'exit_ticket_tally: small group' 0 '| ask about weekend | 80% | GROUP | Eva, Farid |' \
  "$LT/formative-assessment-for-language-planner/scripts/exit_ticket_tally.py" "$FX/lt/exit_ticket.csv"
t 'exit_ticket_tally: extension list' 0 'Met everything: Ana, Dina, Goro, Ivan' \
  "$LT/formative-assessment-for-language-planner/scripts/exit_ticket_tally.py" "$FX/lt/exit_ticket.csv"
STDIN=$'student,a\nX,maybe\n' t 'exit_ticket_tally: bad value exits 2' 2 'needs student + objective columns' \
  "$LT/formative-assessment-for-language-planner/scripts/exit_ticket_tally.py" /dev/stdin

# ---- Feedback and correction
t 'error_log: categories' 0 'By category: grammar 7, vocabulary 1, pronunciation 1' \
  "$LT/l2-error-correction-strategy-advisor/scripts/error_log.py" "$FX/lt/error_log.csv"
t 'error_log: persistent pattern' 0 "Ana: '3rd person -s' (grammar), on 3 dates" \
  "$LT/l2-error-correction-strategy-advisor/scripts/error_log.py" "$FX/lt/error_log.csv"
t 'error_log: strategy for category' 0 'word order: elicitation with finger technique' \
  "$LT/l2-error-correction-strategy-advisor/scripts/error_log.py" "$FX/lt/error_log.csv"
t 'error_log: one student' 0 '3 errors logged for ben' \
  "$LT/l2-error-correction-strategy-advisor/scripts/error_log.py" "$FX/lt/error_log.csv" --student ben
t 'error_log: unknown student exits 2' 2 'no errors logged for Zed' \
  "$LT/l2-error-correction-strategy-advisor/scripts/error_log.py" "$FX/lt/error_log.csv" --student Zed
t 'correction_codes: counts by code' 1 '| Sp | spelling | 2 |' \
  "$LT/student-writing-feedback-generator/scripts/correction_codes.py" "$FX/lt/coded_text.txt"
t 'correction_codes: learner summary' 1 'Ana, your main areas to work on are tense (2)' \
  "$LT/student-writing-feedback-generator/scripts/correction_codes.py" "$FX/lt/coded_text.txt" --name Ana
t 'correction_codes: dense marking note' 1 'Note: dense marking' \
  "$LT/student-writing-feedback-generator/scripts/correction_codes.py" "$FX/lt/coded_text.txt"
t 'correction_codes: unknown code' 1 'Unknown codes: zz' \
  "$LT/student-writing-feedback-generator/scripts/correction_codes.py" "$FX/lt/coded_text.txt"
STDIN='I goed[T] to school[Art].' t 'correction_codes: clean redraft' 0 'I goed to school.' \
  "$LT/student-writing-feedback-generator/scripts/correction_codes.py" - --clean
STDIN='No codes here.' t 'correction_codes: no codes exits 2' 2 'no [codes] found' \
  "$LT/student-writing-feedback-generator/scripts/correction_codes.py" -
t 'l1_issues: shared feature merged' 0 '[high] vowels  (Spanish, Arabic)' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/l1_issues.py" Arabic Spanish --priority high
t 'l1_issues: tip printed' 0 'Tip: Paper strip test' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/l1_issues.py" arabic
t 'l1_issues: list' 0 'L1s: Arabic, Cantonese' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/l1_issues.py" --list
t 'l1_issues: unknown L1 exits 2' 2 'not in the table: klingon' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/l1_issues.py" Klingon
t 'minimal_pairs: alias lookup' 0 '| collect | correct |' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/minimal_pairs.py" l-r
t 'minimal_pairs: seeded drill key' 0 'Key: 1-1 2-1 3-1 4-2 5-1 6-1' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/minimal_pairs.py" l-r --drill 6 --seed 2
t 'minimal_pairs: IPA lookup' 0 '| ship | sheep |' \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/minimal_pairs.py" '/ɪ/-/iː/'
t 'minimal_pairs: unknown exits 2' 2 "unknown contrast 'zz'" \
  "$LT/pronunciation-feedback-for-teachers-tool/scripts/minimal_pairs.py" zz
t 'feedback_coder: move table' 0 '| recast | 2 | 2 | 0 |' \
  "$LT/recast-and-prompt-technique-coach/scripts/feedback_coder.py" "$FX/lt/feedback_transcript.txt"
t 'feedback_coder: explicit correction' 0 'T: Not am agree - I agree.  -> explicit | repair' \
  "$LT/recast-and-prompt-technique-coach/scripts/feedback_coder.py" "$FX/lt/feedback_transcript.txt"
t 'feedback_coder: elicitation' 0 'T: My brother...?  -> elicitation | repair' \
  "$LT/recast-and-prompt-technique-coach/scripts/feedback_coder.py" "$FX/lt/feedback_transcript.txt"
STDIN=$'S: He go *\nT: He went.\nS: Yes *\nS: She go *\nT: She went.\nS: Ok *\n' t 'feedback_coder: recast overuse' 0 'CF001 [medium] 100% of feedback is recasts' \
  "$LT/recast-and-prompt-technique-coach/scripts/feedback_coder.py" -
STDIN=$'T: Hello\nS: Hi\n' t 'feedback_coder: nothing marked exits 2' 2 'no learner error turns' \
  "$LT/recast-and-prompt-technique-coach/scripts/feedback_coder.py" -
t 'progress_summary: change by skill' 0 '| speaking | 2026-T2 | 70 | +12 |' \
  "$LT/student-progress-report-writer/scripts/progress_summary.py" "$FX/lt/progress_scores.csv"
t 'progress_summary: evidence sentence' 0 'Evidence: Ana is strongest in reading (78); most progress in speaking (+12); next focus: writing (60).' \
  "$LT/student-progress-report-writer/scripts/progress_summary.py" "$FX/lt/progress_scores.csv" --student Ana
t 'progress_summary: drop flagged' 0 'Check: speaking fell 8 points' \
  "$LT/student-progress-report-writer/scripts/progress_summary.py" "$FX/lt/progress_scores.csv" --student Ben
t 'progress_summary: unknown student exits 2' 2 'no scores for Zed' \
  "$LT/student-progress-report-writer/scripts/progress_summary.py" "$FX/lt/progress_scores.csv" --student Zed
t 'comment_check: pasted name' 1 'RC001 [high] Chen Wei: mentions Ana - wrong name pasted?' \
  "$LT/student-progress-report-writer/scripts/comment_check.py" "$FX/lt/report_comments.md"
t 'comment_check: vague praise' 1 "RC003 [medium] Ben Okafor: 'good student' with no skill or example" \
  "$LT/student-progress-report-writer/scripts/comment_check.py" "$FX/lt/report_comments.md"
t 'comment_check: jargon' 1 'RC005 [low] Chen Wei: jargon A2, CCQs, TL' \
  "$LT/student-progress-report-writer/scripts/comment_check.py" "$FX/lt/report_comments.md"
t 'comment_check: no sections exits 2' 2 "no '## Name' sections" \
  "$LT/student-progress-report-writer/scripts/comment_check.py" "$FX/lt/holiday.txt"

# ---- Teacher development
t 'celta quiz: list domains' 0 'Phonology   6 questions' \
  "$LT/tefl-celta-prep-tutor/scripts/quiz.py" --list
t 'celta quiz: key with explanation' 0 'Answer: C - pho-TO-gra-phy' \
  "$LT/tefl-celta-prep-tutor/scripts/quiz.py" --n 3 --seed 3 --key
t 'celta quiz: grading below pass' 1 'Score: 2/4 = 50% (below at 70%)' \
  "$LT/tefl-celta-prep-tutor/scripts/quiz.py" --n 4 --seed 5 --answers AAAA
t 'celta quiz: weak domains' 1 'Review next: Planning, Skills' \
  "$LT/tefl-celta-prep-tutor/scripts/quiz.py" --n 4 --seed 5 --answers AAAA
t 'celta quiz: wrong answer count exits 2' 2 'give 4 answers' \
  "$LT/tefl-celta-prep-tutor/scripts/quiz.py" --n 4 --seed 5 --answers AA
t 'celta quiz: unknown domain exits 2' 2 'no questions for domain' \
  "$LT/tefl-celta-prep-tutor/scripts/quiz.py" --domain Cooking
t 'word_count: section under limit' 1 '| Introduction | 38 | 40-60 | UNDER |' \
  "$LT/delta-assignment-planner/scripts/word_count.py" "$FX/lt/delta_essay.md" --limit 'Introduction=40-60' --total 100-200
t 'word_count: references excluded' 0 '| References | 56 | - | excluded |' \
  "$LT/delta-assignment-planner/scripts/word_count.py" "$FX/lt/delta_essay.md"
t 'word_count: tables and quotes excluded' 0 'Counted total: 75' \
  "$LT/delta-assignment-planner/scripts/word_count.py" "$FX/lt/delta_essay.md" --no-tables --no-quotes
t 'word_count: bad limit exits 2' 2 'limits look like' \
  "$LT/delta-assignment-planner/scripts/word_count.py" "$FX/lt/delta_essay.md" --limit 'Intro=abc'
t 'citation_check: missing reference' 1 'CI001 [high] Coe (2001) cited but not in the reference list' \
  "$LT/delta-assignment-planner/scripts/citation_check.py" "$FX/lt/delta_essay.md"
t 'citation_check: uncited reference' 1 'CI002 [medium] Harmer is in the reference list but never cited' \
  "$LT/delta-assignment-planner/scripts/citation_check.py" "$FX/lt/delta_essay.md"
t 'citation_check: year mismatch' 1 'CI003 [medium] Swan: cited as 2016, listed as 2001, 2005' \
  "$LT/delta-assignment-planner/scripts/citation_check.py" "$FX/lt/delta_essay.md"
t 'citation_check: quote without page' 1 'CI004 [low] Thornbury (2006): direct quotation without a page number' \
  "$LT/delta-assignment-planner/scripts/citation_check.py" "$FX/lt/delta_essay.md"
t 'citation_check: no reference list exits 2' 2 'no ' \
  "$LT/delta-assignment-planner/scripts/citation_check.py" "$FX/lt/holiday.txt"
t 'observation_form: evaluative with ratings' 0 '| Instructions are clear | Short, graded language; demonstration; ICQs; materials given after instructions |  |  |' \
  "$LT/language-teacher-observation-form-builder/scripts/observation_form.py" --areas classroom 'error correction' --teacher 'J. Doe'
t 'observation_form: developmental questions' 0 '2. What evidence shows learners achieved the aim?' \
  "$LT/language-teacher-observation-form-builder/scripts/observation_form.py" --areas clarification --developmental
t 'observation_form: unknown area exits 2' 2 "no area matches 'cooking'" \
  "$LT/language-teacher-observation-form-builder/scripts/observation_form.py" --areas cooking
t 'observation_trends: support flag' 0 '| Classroom management | 2 -> 2 -> 2 | 2 | support |' \
  "$LT/language-teacher-observation-form-builder/scripts/observation_trends.py" "$FX/lt/observations.csv"
t 'observation_trends: share strength' 0 '| Rapport | 4 -> 4 | 4 | share |' \
  "$LT/language-teacher-observation-form-builder/scripts/observation_trends.py" "$FX/lt/observations.csv" --teacher 'J. Doe'
STDIN=$'teacher,date,area,rating\nX,2026-01-01,Rapport,7\n' t 'observation_trends: bad rating exits 2' 2 'rating 7 outside 1-4' \
  "$LT/language-teacher-observation-form-builder/scripts/observation_trends.py" /dev/stdin
t 'instruction_check: too long' 1 'IC001 [medium] 63 words of instructions; aim for under 40 at A2' \
  "$LT/classroom-management-for-esl-coach/scripts/instruction_check.py" "$FX/lt/instructions_weak.txt" --level A2
t 'instruction_check: useless ICQ' 1 "IC003 [medium] 'Do you understand?' checks nothing" \
  "$LT/classroom-management-for-esl-coach/scripts/instruction_check.py" "$FX/lt/instructions_weak.txt" --level A2
t 'instruction_check: filler' 1 'IC006 [low] filler: basically, kind of' \
  "$LT/classroom-management-for-esl-coach/scripts/instruction_check.py" "$FX/lt/instructions_weak.txt" --level A2
t 'instruction_check: good instructions' 0 'OK: short, demonstrated and checked' \
  "$LT/classroom-management-for-esl-coach/scripts/instruction_check.py" "$FX/lt/instructions_good.txt" --level A2
t 'seating_plan: front and keep apart' 0 'Table 1: Farid (front), Hana' \
  "$LT/classroom-management-for-esl-coach/scripts/seating_plan.py" "$FX/lt/seating.csv" --size 2
STDIN=$'name,level,l1,keep_apart\nA,B1,x,B\nB,B1,y,A\n' t 'seating_plan: impossible constraint exits 1' 1 'Could not keep apart: A' \
  "$LT/classroom-management-for-esl-coach/scripts/seating_plan.py" /dev/stdin --size 2
STDIN=$'first,last\nA,B\n' t 'seating_plan: missing columns exits 2' 2 'needs name and level' \
  "$LT/classroom-management-for-esl-coach/scripts/seating_plan.py" /dev/stdin
t 'setup_check: low upload' 1 'OS001 [high] upload 1.2 Mbps' \
  "$LT/online-language-teaching-setup-advisor/scripts/setup_check.py" "$FX/lt/online_setup_weak.json"
t 'setup_check: safeguarding for teens' 1 'OS002 [high] teens: agree a safeguarding policy' \
  "$LT/online-language-teaching-setup-advisor/scripts/setup_check.py" "$FX/lt/online_setup_weak.json"
t 'setup_check: no breakout rooms' 1 'OS004 [medium] 12 learners and no breakout rooms' \
  "$LT/online-language-teaching-setup-advisor/scripts/setup_check.py" "$FX/lt/online_setup_weak.json"
t 'setup_check: good setup' 0 'OK: connection, audio, platform and policies fit the class' \
  "$LT/online-language-teaching-setup-advisor/scripts/setup_check.py" "$FX/lt/online_setup_good.json"
STDIN='{"upload_mbps": "fast"}' t 'setup_check: bad value exits 2' 2 'error:' \
  "$LT/online-language-teaching-setup-advisor/scripts/setup_check.py" -
t 'cv_check: no qualification' 1 'CV001 [high] no teaching qualification found' \
  "$LT/language-teacher-cv-writer/scripts/cv_check.py" "$FX/lt/cv_weak.md"
t 'cv_check: duty phrases' 1 'CV004 [medium] duty phrases (duties included, responsible for)' \
  "$LT/language-teacher-cv-writer/scripts/cv_check.py" "$FX/lt/cv_weak.md"
t 'cv_check: regional personal details' 1 'CV007 [low] UK recruiters usually do not expect: date of birth, marital status' \
  "$LT/language-teacher-cv-writer/scripts/cv_check.py" "$FX/lt/cv_weak.md" --region uk
t 'cv_check: strong CV' 0 'qualifications found: CELTA' \
  "$LT/language-teacher-cv-writer/scripts/cv_check.py" "$FX/lt/cv_good.md" --region uk
t 'cv_check: missing file exits 2' 2 'error:' \
  "$LT/language-teacher-cv-writer/scripts/cv_check.py" "$FX/lt/nope.md"

# ---- Specialized language teaching
t 'needs_analysis: ranked core tasks' 0 '| 1 | Handover reports to colleagues | 5.0 | 5.0 | 4.0 | 100 | core | 6 |' \
  "$LT/esp-english-course-designer/scripts/needs_analysis.py" "$FX/lt/esp_survey.csv"
t 'needs_analysis: disagreement flagged' 0 'Respondents disagree on importance (interview to find out why): Writing incident reports' \
  "$LT/esp-english-course-designer/scripts/needs_analysis.py" "$FX/lt/esp_survey.csv"
t 'needs_analysis: by role' 0 'Top tasks for nurse: Handover reports to colleagues (100); Explaining procedures to patients (100); Writing incident reports (40)' \
  "$LT/esp-english-course-designer/scripts/needs_analysis.py" "$FX/lt/esp_survey.csv" --by-role
STDIN=$'respondent,task,frequency,importance,difficulty\nR1,x,9,1,1\n' t 'needs_analysis: out of range exits 2' 2 'outside 1-5' \
  "$LT/esp-english-course-designer/scripts/needs_analysis.py" /dev/stdin
t 'academic_style_check: informal alternatives' 1 "AS002 [medium] 'look into' -> investigate / examine" \
  "$LT/academic-english-eap-course-planner/scripts/academic_style_check.py" "$FX/lt/eap_essay.txt"
t 'academic_style_check: unhedged claims' 1 'AS003 [medium] absolute claims (always, obvious) and no hedging' \
  "$LT/academic-english-eap-course-planner/scripts/academic_style_check.py" "$FX/lt/eap_essay.txt"
STDIN='Research suggests that social media use may reduce study time for some students (Smith, 2021). However, the effect appears to depend on the type of use.' \
  t 'academic_style_check: academic text passes' 0 'OK: formal, hedged and referenced' \
  "$LT/academic-english-eap-course-planner/scripts/academic_style_check.py" -
t 'ielts_gap: IELTS rounding and priority skills' 0 'Priority skills: W (+1), S (+0.5)' \
  "$LT/academic-english-eap-course-planner/scripts/ielts_gap.py" --skills L6 R6.5 W5 S5.5 --target 6.5 --min-skill 6 --weeks 10 --hours-per-week 20
t 'ielts_gap: overall from skills' 0 'Current overall 6.0 (B2) -> target 6.5 (B2)' \
  "$LT/academic-english-eap-course-planner/scripts/ielts_gap.py" --skills L6 R6.5 W5 S5.5 --target 6.5
t 'ielts_gap: not enough time exits 1' 1 'not enough; consider a longer course' \
  "$LT/academic-english-eap-course-planner/scripts/ielts_gap.py" --current 5.0 --target 6.5 --hours-per-week 15 --weeks 8
t 'ielts_gap: bad skill score exits 2' 2 "skill score 'S6.25' should look like W5.5" \
  "$LT/academic-english-eap-course-planner/scripts/ielts_gap.py" --skills L6 R6.5 W6 S6.25 --target 6
t 'yl_lesson_timer: opens with routines' 0 '| 0-3 | Hello song | stir |' \
  "$LT/young-learner-esl-activity-generator/scripts/yl_lesson_timer.py" --age 6 --minutes 45 --seed 2
t 'yl_lesson_timer: attention span' 0 'Age 6: attention span about 8 min per activity' \
  "$LT/young-learner-esl-activity-generator/scripts/yl_lesson_timer.py" --age 6 --minutes 45 --seed 2
t 'yl_lesson_timer: closes with goodbye' 0 '| 42-45 | Goodbye song | stir |' \
  "$LT/young-learner-esl-activity-generator/scripts/yl_lesson_timer.py" --age 6 --minutes 45 --seed 2
t 'yl_lesson_timer: bad age exits 2' 2 '--age 3-12' \
  "$LT/young-learner-esl-activity-generator/scripts/yl_lesson_timer.py" --age 2 --minutes 45
t 'decodable_check: untaught digraph' 1 "shop x2  ['sh']" \
  "$LT/adult-literacy-esl-lesson-builder/scripts/decodable_check.py" "$FX/lt/decodable_text.txt" --taught s a t p i n m d g o c k ck e u r h b f l --sight the is to a
t 'decodable_check: next pattern' 1 'Most useful next patterns: sh (3)' \
  "$LT/adult-literacy-esl-lesson-builder/scripts/decodable_check.py" "$FX/lt/decodable_text.txt" --taught s a t p i n m d g o c k ck e u r h b f l --sight the is to a
t 'decodable_check: fully decodable' 0 '24 words: 100% readable' \
  "$LT/adult-literacy-esl-lesson-builder/scripts/decodable_check.py" "$FX/lt/decodable_text.txt" --taught s a t p i n m d g o c k ck e u r h b f l sh --sight the is to a
t 'decodable_check: nothing taught exits 2' 2 'give the taught graphemes' \
  "$LT/adult-literacy-esl-lesson-builder/scripts/decodable_check.py" "$FX/lt/decodable_text.txt"
t 'learner_pathways: foundation literacy' 0 '| Amina | pre-A1 | none | 0 | Foundation literacy | health |' \
  "$LT/refugee-language-support-planner/scripts/learner_pathways.py" "$FX/lt/refugee_intake.csv"
t 'learner_pathways: script transition' 0 '| Yonas | A1 | fluent | 12 | Script transition | work |' \
  "$LT/refugee-language-support-planner/scripts/learner_pathways.py" "$FX/lt/refugee_intake.csv"
t 'learner_pathways: class grouping' 0 'Foundation literacy (mornings), 2 learners: Amina, Khadija' \
  "$LT/refugee-language-support-planner/scripts/learner_pathways.py" "$FX/lt/refugee_intake.csv"
t 'learner_pathways: childcare summary' 0 'Childcare needed by 3 learner(s)' \
  "$LT/refugee-language-support-planner/scripts/learner_pathways.py" "$FX/lt/refugee_intake.csv"
STDIN=$'learner,level\nA,A1\n' t 'learner_pathways: missing columns exits 2' 2 'needs at least name and english' \
  "$LT/refugee-language-support-planner/scripts/learner_pathways.py" /dev/stdin
