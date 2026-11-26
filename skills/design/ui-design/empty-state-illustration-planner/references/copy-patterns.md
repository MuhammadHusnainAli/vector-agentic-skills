# Empty State Copy Patterns

## Formulas

| Part | Formula | Length |
|------|---------|--------|
| Headline | State the situation or the value, plainly | 2-6 words |
| Body | Why it's empty and what happens next, or how to fix it | 1 sentence, at most 2 |
| Primary action | Verb + object of the most likely next step | 1-3 words |
| Secondary | Alternative path or learn more | Link |

## By type

| Type | Headline | Body | Action |
|------|----------|------|--------|
| First use | "Create your first project" / value statement | What a project holds, one sentence | Create project |
| No data yet | "No orders yet" | When and how data appears | Share store link / Send test order |
| Cleared | "You're all caught up" | Where new items will appear | (none) |
| No results | "No results for 'query'" | Suggest a fix | Clear filters |
| Error | "Couldn't load invoices" | Data is safe + what to try | Try again |
| Offline | "You're offline" | What still works | (none) / Retry |
| Permission | "You don't have access to X" | Who can grant it | Request access |
| Locked | "Reports are on the Pro plan" | The value in one sentence | See plans / Ask an admin |

## Tone

- Friendly is fine for first use and cleared states. Neutral and specific for errors and permissions: nobody wants a joke
  when their data didn't load.
- No blame ("You haven't created anything"), no guilt ("Don't miss out").
- No jargon or internal names ("No entities", "Null dataset", "0 records returned").
- Second person, present tense, sentence case.

## Before and after

| Before | After |
|--------|-------|
| No data | No orders yet. Orders appear here as soon as a customer checks out. [Share store link] |
| Oops! Something went wrong 🙈 | Couldn't load your files. Your files are safe; try again in a moment. [Try again] |
| No results found | No results for "q3 report" with the filter "Owner: me". [Clear filters] |
| You have no permissions. | You don't have access to Billing. Ask a workspace admin to add you. [Request access] |
| Nothing here yet! Start by clicking the button below to create your very first awesome project! | Create your first project. Projects keep your tasks, files and discussions in one place. [Create project] |

## Localization

- Keep strings out of images.
- Allow +40% length; headlines may wrap to two lines.
- Quote the user's query with locale-appropriate quotation marks.
