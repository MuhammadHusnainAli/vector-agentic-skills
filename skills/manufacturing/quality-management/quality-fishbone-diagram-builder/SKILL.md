---
name: quality-fishbone-diagram-builder
description: "Build and use Ishikawa (fishbone, cause-and-effect) diagrams for quality problems: 6M bones (Man, Machine, Method, Material, Measurement, Environment) plus 8M, service (4S/8P) and IT variants, prompt questions to fill empty bones, causes written as conditions rather than solutions or blame, sub-causes, status marking (untested, likely, verified, ruled out) and a verification plan that turns candidate causes into a proven root cause. Generates a text or Mermaid fishbone from a CSV cause list, normalises category names, and flags empty bones, solution-shaped causes, blame, duplicates and diagrams with no candidate selected. Use when brainstorming causes for an NCR, complaint, CAPA or 8D D4, facilitating a root cause workshop, or documenting an investigation."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Quality Fishbone Diagram Builder

A fishbone organises everything that could cause an effect so the team does not jump to its favourite theory. It
is a map of hypotheses: its value comes from filling every bone, ruling causes out with data, and testing the
likely ones. `scripts/fishbone.py` draws the diagram from a CSV, checks it and lists what to verify next.

## Trigger Conditions

Activate this skill when the user:
- Needs to brainstorm possible causes of a defect, complaint or process problem
- Is facilitating a root cause workshop or 8D D4
- Wants a fishbone diagram (text or Mermaid) for a report
- Has a fishbone full of solutions or blame and no clear next step

After narrowing down: [five-whys-analysis-facilitator](../five-whys-analysis-facilitator/SKILL.md) for the chain to the
system cause; [design-of-experiments-planner](../design-of-experiments-planner/SKILL.md) for interacting factors.

## Workflow

```
1. HEAD      -> specific, factual effect (what, where, how many)
2. BRAINSTORM-> silent notes, place on bones, use 6m-prompts.md for empty bones
3. CLEAN     -> conditions, not solutions or blame; remove duplicates
4. DRAW      -> python scripts/fishbone.py causes.csv --problem "<effect>"
5. NARROW    -> rule out with existing data; multi-vote the likely causes
6. TEST      -> verification plan per likely cause; update status to verified / ruled-out
7. HAND OFF  -> verified cause -> 5 Why to system cause -> CAPA actions
```

## CSV Format

```
category,cause,subcause,status,evidence
Method,Open trays with no dividers on line 2,,verified,Transport trial 14/40 scratched without dividers
Measurement,Inspection light below 1000 lux at packing,,untested,
```
Status: untested, likely, verified, ruled-out. Category aliases map to the 6M (people -> Man, equipment -> Machine,
procedure -> Method, supplier -> Material, gauge -> Measurement, surroundings -> Environment); other names become
extra bones.

## Checks (fishbone.py)

| Code | Severity | Problem |
|------|----------|---------|
| FB001 | medium | Empty 6M bone |
| FB002 | medium | Cause written as a solution |
| FB003 | medium | Cause blames a person |
| FB004 | low | Same cause on several bones |
| FB005 | low | Nothing marked likely or verified |

```
Method
  [V] Open trays with no dividers on line 2
  [L] Visual inspection before packing not after
FB002 [medium] Method: 'Need a vision system' is a solution; write the condition it would fix
```

Prompt questions per bone and variants for 8M, services and IT: [6m-prompts.md](references/6m-prompts.md).
Session plan, verification plan and next tools: [from-fishbone-to-root-cause.md](references/from-fishbone-to-root-cause.md).

## Output Format

Deliver:
1. **Effect statement** at the head.
2. **Diagram** - text tree or Mermaid (`--format mermaid`), with status marks.
3. **Ruled-out causes** with the data that ruled them out.
4. **Verification plan** for likely causes (test, expected result, owner, due).
5. **Verified root cause(s)** and the hand-off to 5 Why / CAPA.

## Scripts

```bash
python scripts/fishbone.py causes.csv --problem "Scratches on HS-110 face A"
python scripts/fishbone.py causes.csv --problem "..." --format mermaid > fishbone.mmd
```
In Mermaid mode findings go to stderr so the diagram can be piped. Exit codes: 0 no medium findings, 1 medium
findings, 2 read error or missing columns.

## Additional Resources

| File | Content |
|------|---------|
| [6m-prompts.md](references/6m-prompts.md) | Prompt questions per bone; 8M, service and IT variants |
| [from-fishbone-to-root-cause.md](references/from-fishbone-to-root-cause.md) | Session steps, voting, verification plan, next tools |
