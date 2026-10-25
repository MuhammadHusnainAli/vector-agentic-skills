---
name: five-whys-analysis-facilitator
description: "Facilitate and check 5 Why root cause analysis for quality problems, NCRs, CAPAs and 8D D4: factual problem statement without cause, why chains that stay on facts, branching when an answer has two causes, separate occurrence, escape (non-detection) and systemic legs, stopping at a controllable process or system cause rather than a person, the reverse 'therefore' test, and verifying causes by switching them on and off, reproducing them or with data. Checks a written 5 Why for causes in the problem statement, chains ending in blame or human error, too-short or too-long chains, circular answers, causes outside the organization's control, double causes and vague answers, and prints the therefore test for every leg. Includes worked examples from machining, assembly and office processes. Use when running a 5 Why session, reviewing a root cause before writing actions, or coaching a team whose CAPAs keep recurring."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Five Whys Analysis Facilitator

5 Why works when each answer is a checkable fact, the chain ends in a process or system you can change, and the
team asks not only why it happened but also why it was not caught. `scripts/whys_check.py` finds the usual logic
gaps and prints the reverse "therefore" test so the team can read the chain back.

## Trigger Conditions

Activate this skill when the user:
- Is running a 5 Why session for an NCR, complaint, CAPA or 8D D4
- Has a 5 Why that ends in "operator error" or "not trained"
- Wants a root cause reviewed before committing to actions
- Asks how to do 5 Why properly or when to stop

When there are many candidate causes, start with [quality-fishbone-diagram-builder](../quality-fishbone-diagram-builder/SKILL.md);
for the action plan, [capa-plan-writer](../capa-plan-writer/SKILL.md).

## Workflow

```
1. GEMBA     -> go to where it happened with parts, records and the people doing the work
2. PROBLEM   -> "Problem: <effect, where, how many, when>" - no cause
3. ASK       -> "Why:" lines; one fact per line; branch when an answer has two causes
4. LEGS      -> "## Occurrence", "## Escape" (why not detected), optional "## Systemic"
5. CHECK     -> python scripts/whys_check.py analysis.txt
6. THEREFORE -> read each chain bottom-up; every link must follow
7. VERIFY    -> switch the cause on/off, reproduce it, or confirm with data before acting
```

## Format

```
Problem: 40 of 200 VB-2210 parts had bore 12.021-12.030 mm (drawing max 12.018) in lot L2609-14
## Occurrence
Why: The boring insert wore beyond the size limit before the tool change
Why: Tool change interval is 400 parts but the new insert grade wears out at about 250 parts
Why: The interval was not re-validated when the insert grade changed in August
Why: Tooling grade changes are not covered by the change-control procedure QP-11
## Escape
Why: Only 1 in 50 parts gets an in-process bore check
...
```

## Checks (whys_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| WY001 | high | No problem statement, or it contains a cause |
| WY002 | high | Chain ends in blame / human error |
| WY003 | medium | Under 3 or over 7 whys |
| WY004 | medium | Answer repeats the previous one |
| WY005 | medium | Ends outside your control (customer, supplier, weather) |
| WY006 | medium | Two causes in one answer: branch |
| WY007 | low | Vague answer |
| WY008 | low | Only one leg: add escape |

Session rules, stopping criteria, verification methods and when to use another tool:
[facilitation-guide.md](references/facilitation-guide.md). Weak vs strong chains from machining, assembly and office
work, and common traps: [worked-examples.md](references/worked-examples.md).

## Output Format

Deliver:
1. **Problem statement** (effect only).
2. **Chains** per leg (occurrence, escape, systemic) with the evidence for each answer.
3. **Therefore test** result.
4. **Root causes** - the controllable cause at the end of each leg and how it was verified.
5. **Hand-off** - one action per root cause, ranked by strength (see capa-plan-writer).

## Scripts

```bash
python scripts/whys_check.py analysis.txt
cat analysis.txt | python scripts/whys_check.py -
```
Lines: `Problem: ...`, `Why: ...` (or `1.`, `Why 2:`), and `## <leg>` headings. Exit codes: 0 no high issues,
1 high issues, 2 unreadable file or no Why lines.

## Additional Resources

| File | Content |
|------|---------|
| [facilitation-guide.md](references/facilitation-guide.md) | Preparation, session rules, three legs, therefore test, verification, when 5 Why is not enough |
| [worked-examples.md](references/worked-examples.md) | Machining, assembly and office examples, weak vs strong, common traps |
