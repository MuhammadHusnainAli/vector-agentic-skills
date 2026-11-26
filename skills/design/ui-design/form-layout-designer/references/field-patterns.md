# Field Patterns

## Quick table

| Field | type | inputmode | autocomplete | Width | Notes |
|-------|------|-----------|--------------|-------|-------|
| Full name | text | - | name | 20-30ch | One field works globally; split only if a system needs given/family |
| Given / family name | text | - | given-name / family-name | 20ch | Label "First name" fails for name-order cultures; prefer "Given name" when global |
| Email | email | - | email | 30ch | `spellcheck="false"`, `autocapitalize="none"`; suggest corrections for common domain typos |
| Phone | tel | - | tel | 20ch | One field; accept spaces, dashes, +; store in E.164; country code via autocomplete or a selector |
| Street address | text | - | address-line1 / address-line2 | full | Or one `textarea` with street-address |
| City | text | - | address-level2 | 20ch | |
| State / region | text or select | - | address-level1 | 20ch | Only for countries that use it |
| Postcode / ZIP | text | text (or numeric for US-only ZIP) | postal-code | 10ch | Never `type=number` (leading zeros, letters) |
| Country | select / combobox | - | country | 20ch | Default from locale; type-ahead |
| Date of birth | text x3 or 1 | numeric | bday-day / bday-month / bday-year | 2/2/4ch | Memorable dates: three fields, not a picker |
| Appointment date | date picker | - | off | - | Near-future dates benefit from a calendar |
| New password | password | - | new-password | 30ch | Show rules up front, show-password toggle, allow paste and managers |
| Current password | password | - | current-password | 30ch | |
| One-time code | text | numeric | one-time-code | 8ch | One field, not 6 boxes; allows paste and SMS autofill |
| Card number | text | numeric | cc-number | 22ch | Never `type=number`; format with spaces as typed; detect brand |
| Expiry | text | numeric | cc-exp | 7ch | "MM / YY", one field |
| Security code | text | numeric | cc-csc | 5ch | Hint where to find it |
| Name on card | text | - | cc-name | 30ch | |
| Amount | text | decimal | transaction-amount | 12ch | Currency symbol as a prefix outside the input |
| Quantity | number or stepper | numeric | off | 6ch | `type=number` is fine for true quantities |
| Search | search | - | off | full | Submit on Enter; clear button |
| URL | url | - | url | full | |

Never use `type=number` for identifiers (card numbers, codes, postcodes, account numbers): it strips leading zeros, adds
spinners, and changes value on scroll.

## autocomplete tokens (HTML standard)

Names: `name`, `honorific-prefix`, `given-name`, `additional-name`, `family-name`, `honorific-suffix`, `nickname`.
Account: `username`, `new-password`, `current-password`, `one-time-code`, `webauthn` (with username).
Organisation: `organization-title`, `organization`.
Address: `street-address`, `address-line1`, `address-line2`, `address-line3`, `address-level4` to `address-level1`,
`country`, `country-name`, `postal-code`.
Payment: `cc-name`, `cc-given-name`, `cc-additional-name`, `cc-family-name`, `cc-number`, `cc-exp`, `cc-exp-month`,
`cc-exp-year`, `cc-csc`, `cc-type`, `transaction-currency`, `transaction-amount`.
Personal: `language`, `bday`, `bday-day`, `bday-month`, `bday-year`, `sex`, `url`, `photo`, `impp`.
Contact: `email`, `tel`, `tel-country-code`, `tel-national`, `tel-area-code`, `tel-local`, `tel-extension`.
Prefixes: `shipping` / `billing` (e.g. `shipping postal-code`), `section-*` for repeated groups.

`autocomplete="off"` is ignored by most browsers for login fields; don't fight password managers.

## Choice fields

| Options | Use |
|---------|-----|
| 2, mutually exclusive, both explicit | Radio buttons (not a switch, not a checkbox) |
| 1 on/off consent or setting saved with the form | Single checkbox |
| On/off that applies immediately | Switch |
| 2-6 options | Radio buttons, all visible |
| 7-15 options | Select (or radios if comparison matters) |
| Many options, known to the user (country) | Combobox with type-ahead |
| Many options, multi-select | Checkbox list with search, or a multi-select combobox with chips |

Order options logically (frequency, magnitude, alphabetical). Include "None", "Other" or "Prefer not to say" where real.

## Passwords

- Show all rules before typing; tick them off as met.
- Minimum length matters more than composition rules (NIST SP 800-63B: at least 8, allow at least 64, no forced composition).
- Show-password toggle (a button with `aria-pressed`, label stays "Show password").
- Allow paste and password managers (blocking paste fails WCAG 3.3.8).
- Confirm-password fields are unnecessary with a show toggle.
