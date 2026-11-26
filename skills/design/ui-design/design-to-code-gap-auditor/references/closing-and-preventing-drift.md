# Closing and Preventing Drift

## Fix order

1. **Exact matches (TD001):** mechanical replacements; codemod or search-and-replace per value; low risk, high count.
2. **Near-misses (TD002):** confirm with design in bulk (a table of value -> token), then replace. Usually unintended.
3. **Missing tokens:** off-palette values used many times become new semantic tokens (through governance).
4. **Off-palette one-offs (TD003):** map to the nearest role or fix the design; each is a small design decision.
5. **Component parity:** rename to align, build missing variants, remove dead ones.
6. **States:** add missing states with stories.

Prioritise by visibility: customer-facing, high-traffic screens and shared components first.

## Codemods

- CSS/SCSS: replace exact hex values with `var(--token)` using the replacement table from `token_drift.mjs --json`.
- CSS-in-JS / inline styles: replace string literals with the theme object (`theme.color.text.subtle`).
- Run per package, reviewed by the owning team, with visual regression tests.

## Guardrails

| Guardrail | Example |
|-----------|---------|
| Stylelint | `color-no-hex: true`, `color-named: "never"`, `function-disallowed-list: ["rgb", "rgba", "hsl", "hsla"]` (allow in the tokens file only) |
| ESLint | Forbid colour literals in style objects (custom rule or plugin); `no-restricted-imports` for legacy components |
| Tailwind | Theme colours replaced by tokens (not extended); arbitrary colour values blocked in review |
| CI | `node token_drift.mjs tokens.json src --ignore tokens.css` fails on new warnings (compare with a baseline count) |
| Figma | Variables required for colours (library); detach and local-style reports |
| Code Connect | Every library component mapped |
| PR review checklist | Tokens used, states covered, story added, design reviewed |

## Tracking

Monthly or per release:
- Token share (colours via tokens) and raw colour count
- Off-palette distinct values
- Parity gaps open/closed
- Missing states

Show the trend, not just the snapshot. Celebrate the teams that close gaps.
