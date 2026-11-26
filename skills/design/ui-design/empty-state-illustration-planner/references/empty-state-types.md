# Empty State Types

## First use (new product, feature or space)

- **When:** a new account, workspace, project, or a feature never used.
- **Goal:** explain the value in one sentence and get the first meaningful action done.
- **Structure:** headline naming the value, one sentence, primary action, secondary (template, import, learn more).
- **Helpers:** templates, sample data clearly marked as sample (with "Remove sample data"), import from another tool,
  invite teammates when the product is collaborative.
- **Example:** "Track every customer conversation" / "Connect your inbox and conversations appear here automatically." /
  [Connect inbox] · Import from CSV
- **Pitfall:** a tour of every feature instead of one first step.

## No data yet (waiting on activity)

- **When:** the setup is done but nothing has happened (no orders, no analytics events).
- **Goal:** reassure that it's working and say when data will appear; offer a way to make it happen (test event,
  share link).
- **Example:** "No orders yet" / "Orders appear here as soon as a customer checks out." / [Share your store link]

## User cleared (completed everything)

- **When:** inbox zero, all tasks done, notifications read.
- **Goal:** confirm success, then get out of the way.
- **Example:** "You're all caught up" / "New messages will appear here."
- **Pitfall:** pushing an action when the user is done.

## No results (search or filter)

- **When:** a query or filter combination returns nothing, while data exists.
- **Goal:** help adjust the query; make clear the data still exists.
- **Structure:** echo the query and active filters; suggestions (check spelling, fewer words, broader date range);
  [Clear filters]; related results or "Did you mean".
- **Example:** "No results for 'invioce'" / "Check the spelling or try different keywords." / Did you mean "invoice"?
- **Pitfall:** the same screen as no data, so users think their data is gone.

## Error or failed to load

- **When:** the request failed, timed out, or data is unavailable.
- **Goal:** say what failed, whether data is safe, and what to do.
- **Structure:** plain statement, cause if known, [Try again], status page or support link, error reference for support.
- **Example:** "Couldn't load invoices" / "Your invoices are safe. Check your connection and try again." / [Try again]
- **Pitfall:** "No invoices" shown because the request failed. Never render the empty state for an error.

## Offline

- **When:** no connection.
- **Goal:** show what's available offline and what will sync later.
- **Example:** "You're offline" / "You can keep editing. Changes sync when you're back online."

## No permission

- **When:** the user lacks access to content or a feature.
- **Goal:** say who can grant it, with a way to request access.
- **Example:** "You don't have access to Billing" / "Ask a workspace admin (Dana Lee) to give you access." / [Request access]
- **Pitfall:** hiding the reason, so users think it's a bug.

## Locked by plan

- **When:** feature not included in the user's plan.
- **Goal:** show the value, the plan that includes it, and who can upgrade (often not the viewer).
- **Pitfall:** aggressive upsell on every empty slot; respect users who can't buy.

## Containers and sizes

| Container | What fits |
|-----------|-----------|
| Full page | Illustration (medium/large), headline, body, primary + secondary action |
| Panel / card | Small illustration or icon, headline, one line, one action |
| Table body | One line in the table area with an action; keep column headers visible for context |
| Widget / chart | One line ("No data for this period") + adjust range link |
| Dropdown / combobox | "No matches for 'xyz'" + create option if allowed |
