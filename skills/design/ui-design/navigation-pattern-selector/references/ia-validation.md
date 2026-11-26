# IA Shape and Validation

## Depth vs breadth

- Broad and shallow beats narrow and deep for findability, as long as each level is well grouped and labelled.
- The "7 plus or minus 2" rule is about short-term memory, not menus. Visible lists can be long if they are scannable
  and grouped. Hidden levels are the expensive part.
- Each extra level is another decision where users can go wrong. More than 3-4 levels needs search and breadcrumbs.

## Labels

| Problem | Example | Better |
|---------|---------|--------|
| Vague | Resources, Solutions, More, Explore | Name the content: Guides, Pricing, Templates |
| Internal names | "Nexus", team names, product codenames | What users call it (from search logs, support tickets) |
| Overlapping | Reports / Analytics / Insights | Merge, or make the difference obvious |
| Nouns vs verbs mixed | Projects, Create, Billing | Destinations are nouns; actions are buttons |
| Too long | "Manage your account settings and preferences" | Settings |

Sources for user language: site search queries, support tickets, sales call notes, competitor labels, open card sorts.

## Card sorting (generate the structure)
- Open sort: participants group and name cards; shows mental models and vocabulary. About 15-30 participants
  for stable patterns in remote unmoderated sorts.
- Closed sort: participants put cards into given categories; tests a proposed grouping.
- Use 30-60 cards that represent real content; analyse with a similarity matrix and dendrogram.

## Tree testing (evaluate the structure, without visual design)
- Text-only tree of the IA; participants find where they'd look for X.
- Write 8-10 tasks from real top tasks, phrased without the label words ("You want to change the card you pay with",
  not "Find Billing").
- Measure per task: success rate, directness (no backtracking), time, and first click. Compare against the current IA
  as a baseline.
- Fix tasks with low success first; look at where wrong paths went to find mislabelled or misgrouped nodes.

## First-click testing (evaluate the design)
- Show the designed screen; ask where they'd click first for a task. A correct first click strongly predicts task
  success.

## Wayfinding checklist
- Where am I? Page title, selected nav item, breadcrumbs.
- Where can I go? Visible primary destinations; related links in context.
- How do I get back? Predictable back/up; breadcrumb parent; state preserved.
- Where did I come from? Deep links land with context, not on an orphan page.
- What's here? Section landing pages that summarise, not just a list of child links.
