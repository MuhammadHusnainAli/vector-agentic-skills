# Validation and Errors

## When to validate

| Moment | What to check | Notes |
|--------|---------------|-------|
| Before typing | Nothing | Never show errors on untouched fields |
| While typing | Only positive feedback (password rule ticks, character counter) | Errors mid-word are hostile |
| On blur, after the user typed | Format errors (email shape, date validity) | Re-validate on input once an error is shown, so it clears as soon as it's fixed |
| On submit | Everything, including required fields | Show the error summary; move focus to it |
| Server-side | Uniqueness, business rules | Same message style; keep the user's input |

## Error message formula

`[What's wrong] + [how to fix it]`, in plain language, about the field, not the user.

| Bad | Good |
|-----|------|
| Invalid input | Enter an email address in the correct format, like name@example.com |
| Required field | Enter your postcode |
| Error 422 | Date of birth must be in the past |
| Password does not meet requirements | Password must be at least 12 characters |
| Invalid date | Date of birth must include a month |
| You entered the wrong code | The code is incorrect or has expired. Request a new code |

Rules:
- Start with the action verb ("Enter", "Select", "Choose") for missing answers.
- Use the label's words. Don't introduce new terms.
- No blame ("You failed to..."), no jokes, no "please" padding, no exclamation marks.
- Give the range or format when that's the problem ("Enter an amount between $1 and $10,000").

## Error summary (on submit)

```html
<div role="alert" tabindex="-1" class="error-summary" aria-labelledby="error-summary-title">
  <h2 id="error-summary-title">There is a problem</h2>
  <ul>
    <li><a href="#email">Enter an email address in the correct format, like name@example.com</a></li>
  </ul>
</div>
```
- Appears at the top of the form; receives focus on submit.
- Each item links to the field (and focuses it). Same wording as the inline message.
- Page title gets an "Error: " prefix so screen reader users know on load.

## Inline error markup

```html
<label for="email">Email address</label>
<p id="email-hint" class="hint">We'll send your receipt here</p>
<p id="email-error" class="error"><span class="visually-hidden">Error:</span> Enter an email address in the correct format</p>
<input id="email" type="email" autocomplete="email" aria-describedby="email-hint email-error" aria-invalid="true">
```
- Error text between label/hint and input, so it's read before typing.
- Error styling: border + icon + text. Never colour alone (WCAG 1.4.1).
- Keep the user's input; never clear a field because it has an error.

## Error prevention (WCAG 3.3.4)

For legal, financial or data-changing submissions, at least one of: reversible, checked with a chance to correct, or a
review-and-confirm step. Check-your-answers pages with "Change" links per answer work well.

## Success

- Confirm what happened and what happens next ("We've sent a confirmation to name@example.com. It may take 5 minutes.").
- Give a reference number for anything users might need to quote.
- Don't show a green tick for every valid field; it adds noise and implies the others are wrong.
