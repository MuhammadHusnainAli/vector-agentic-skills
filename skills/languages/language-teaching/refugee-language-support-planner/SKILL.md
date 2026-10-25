---
name: refugee-language-support-planner
description: "Plan language support for refugees, asylum seekers and other new arrivals: intake with interpreters and literacy checks, pathways (foundation literacy, script transition for learners literate in non-Roman scripts, settlement ESOL, work and study), a settlement syllabus prioritising personal information, emergencies, health, housing, transport, money, children's schools, work, rights and community with can-do statements, flexible delivery (rolling enrolment, childcare, real local materials, volunteers) and links to literacy, employability and support services. Applies trauma-informed principles (safety, trust, choice, collaboration, empowerment, cultural humility), topic care, classroom practice, signs of distress and referral, and teacher wellbeing. Assigns each learner a pathway from intake data and groups learners into classes by pathway and availability, with childcare and goal summaries. Use when designing or running English classes for refugees or migrants, or organising intake and class grouping."
metadata:
  category: languages
  subcategory: language-teaching
  version: "1.0.0"
---

# Refugee Language Support Planner

Language support for new arrivals works when it starts from what people need now (health, housing, school,
safety), fits their literacy and lives, and is delivered in a safe, predictable way.
`scripts/learner_pathways.py` turns intake data into pathways and class groups.

## Trigger Conditions

Activate this skill when the user:
- Sets up or runs English (or other host-language) classes for refugees or migrants
- Organises intake, assessment and class grouping for new arrivals
- Asks what to teach first, or how to teach sensitively
- Trains volunteers to support refugee learners

Literacy: [adult-literacy-esl-lesson-builder](../adult-literacy-esl-lesson-builder/SKILL.md). Work English:
[esp-english-course-designer](../esp-english-course-designer/SKILL.md). Outcomes:
[can-do-statement-writer](../can-do-statement-writer/SKILL.md).

## Workflow

```
1. INTAKE    -> interpreter or L1 helper; oral interview; literacy check; goals; availability; childcare
2. PATHWAYS  -> python scripts/learner_pathways.py intake.csv
3. PRIORITY  -> settlement topics in the order learners need them (references/settlement-language-syllabus.md)
4. DELIVERY  -> rolling units, timing, childcare, real materials, visits, volunteers
5. PRACTICE  -> trauma-informed routines and topic care (references/trauma-informed-practice.md)
6. LINK      -> literacy, employability, EAP, support services
7. REVIEW    -> can-do checklists and portfolios; move learners between pathways as they progress
```

Keep intake records to learning information. Do not ask about or record asylum claims, trauma or journeys; if
learners share such information, follow the organisation's confidentiality and safeguarding procedures.

## Output Format

Programme plan: pathways with hours and class sizes, class groups from the script, the priority syllabus with
can-dos for the first term, delivery arrangements, a sample lesson (for example "making a doctor's appointment"),
and the safeguarding and referral contacts the teacher should have.

## Scripts

```bash
python scripts/learner_pathways.py intake.csv [--max-class 12]
```
Columns: name, english, l1_literacy, l1_script, schooling_years, goal, availability, childcare (name and english
required). Exit codes: 0 printed, 2 read error or missing columns.

## Additional Resources

| File | Content |
|------|---------|
| [settlement-language-syllabus.md](references/settlement-language-syllabus.md) | Priority topics with can-dos, intake and delivery, linking to other provision |
| [trauma-informed-practice.md](references/trauma-informed-practice.md) | Principles, topic care, classroom practice, signs of distress and referral, teacher wellbeing |
