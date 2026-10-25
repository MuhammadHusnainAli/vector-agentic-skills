# Coaching Yourself on Feedback: Record, Code, Practise

## 1. Record

Record 10-15 minutes of a lesson stage where learners speak and errors are likely (controlled practice,
discussion feedback, a speaking task). Get learners' consent; audio is enough.

## 2. Transcribe the feedback moments

Only the exchanges around errors. Format for `feedback_coder.py`:

```
Ana: I go to the park with my sister *       <- learner turn with an error: end with " *"
T: Oh, you went to the park?                 <- the teacher's move
Ana: Yes, I went.                             <- uptake; no " *" = repaired
```

End a learner's response with " *" if it still contains the error or does not repair it (e.g. "Yes." after a
recast that the learner did not take up).

## 3. Code and count

`python scripts/feedback_coder.py transcript.txt --stage accuracy` reports each move, uptake and repair. Check
the automatic coding by eye: it uses wording patterns and will misclassify some turns.

| Question | Look at |
|----------|---------|
| Which move do I use most? | Move counts |
| Do learners repair after my feedback? | Repair per move |
| Do I leave errors untreated in accuracy work? | "none" count |
| Do I give the answer too fast? | Prompts followed immediately by the form |

## 4. Set one goal

Examples:
- "Turn half of my recasts into prompts in controlled practice."
- "After every prompt, wait three seconds."
- "Ask the learner to repeat the whole sentence after correction."

## 5. Practise the moves

Practise aloud with these errors; give one recast, one elicitation, one metalinguistic clue and one repetition for
each:

| Learner error | Target |
|---------------|--------|
| *I have seen him yesterday.* | I saw him yesterday. |
| *He can speaks French.* | He can speak French. |
| *I am agree.* | I agree. |
| *She is more taller than me.* | She is taller than me. |
| *I didn't went.* | I didn't go. |
| *Can you explain me?* | Can you explain it to me? |
| *I'm boring in this class.* | I'm bored. |
| *Where you live?* | Where do you live? |

## 6. Re-record and compare

Record a similar stage two weeks later; compare move counts and repair rates with the first recording. Share the
results with a peer or mentor if you have one.
