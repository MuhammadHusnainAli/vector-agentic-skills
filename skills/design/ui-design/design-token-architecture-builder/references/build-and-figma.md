# Build Pipeline, Figma Variables and Governance

## Style Dictionary v4

Style Dictionary v4 reads DTCG (`$value`, `$type`) natively. Keep references in the output so the CSS shows the
architecture and a theme only has to redefine semantic variables.

```js
// sd.config.mjs   (npx style-dictionary build --config sd.config.mjs)
const semantic = (t) => t.path[0] === "semantic";

export default {
  source: ["tokens/core/**/*.json", "tokens/semantic/light.json", "tokens/component/**/*.json"],
  platforms: {
    css: {
      transformGroup: "css",
      buildPath: "build/css/",
      files: [{ destination: "tokens.css", format: "css/variables",
                options: { outputReferences: true, selector: ":root" } }],
    },
    js: {
      transformGroup: "js",
      buildPath: "build/js/",
      files: [{ destination: "tokens.js", format: "javascript/es6" }],
    },
  },
};
```

Dark mode is a second config (or a loop over modes) with `tokens/semantic/dark.json`, the selector
`[data-theme="dark"]`, and a filter that outputs only semantic tokens (primitives and components don't change):

```js
files: [{ destination: "dark.css", format: "css/variables", filter: semantic,
          options: { outputReferences: true, selector: '[data-theme="dark"]' } }]
```

Output:
```css
:root {
  --core-color-blue-600: #2563eb;
  --semantic-color-action-primary-bg: var(--core-color-blue-600);
  --component-button-primary-bg: var(--semantic-color-action-primary-bg);
}
[data-theme="dark"] { --semantic-color-action-primary-bg: var(--core-color-blue-400); }
```
Also respect the system setting: `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { ... } }`.

Name transforms: decide whether tier prefixes appear in CSS (`--color-action-primary-bg` vs
`--semantic-color-action-primary-bg`). Shorter names are friendlier; keep the tier visible in docs either way.

## Figma variables

| Figma collection | Modes | Contains |
|------------------|-------|----------|
| Primitives | 1 (Value) | Colour ramps, spacing, radii as raw values; hidden from publishing so designers pick semantics |
| Semantic | Light, Dark (+ High contrast) | Aliases to primitives |
| Component (optional) | Light, Dark or Brand modes | Aliases to semantics |
| Density / Brand | Comfortable, Compact / Brand A, Brand B | Spacing or brand-specific aliases |

Settings that keep Figma and code aligned:
- Variable names use `/` groups that map to the token path (`color/action/primary/bg`).
- Code syntax (Web) set to the CSS custom property (`var(--color-action-primary-bg)`) so Dev Mode shows the real name.
- Scopes limit where variables appear (text colours only in text fill, spacing only in gap/padding).
- Sync through a plugin (Tokens Studio, or Figma's REST variables API) in one direction, with code as the source of truth
  or Figma as the source of truth, never both.

## Governance

| Change | Process |
|--------|---------|
| Add a primitive | Allowed when it fills a real gap in a ramp or scale; check it isn't a near-duplicate |
| Add a semantic role | Proposal with use cases; check an existing role can't serve; design and code review |
| Change a value | Visual regression check across products and modes; changelog entry |
| Rename | Keep the old name as an alias with `$deprecated: "Use color.text.subtle"`; remove in the next major |
| Remove | After the deprecation period; codemod or search report shows zero usage |

Version tokens with the design system (semver): renames and removals are breaking; new tokens are minor; value tweaks are
patch or minor depending on visual impact.
