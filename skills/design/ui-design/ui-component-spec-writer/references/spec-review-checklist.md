# Spec Review Checklist

Apply each check to the spec. Report findings as `CODE [severity] what is wrong -> what to do`, high first. A spec with
any high finding is not ready for handoff.

| Code | Severity | Check | How to spot it | Fix to suggest |
|------|----------|-------|----------------|----------------|
| CS001 | high | Core sections present | No heading for anatomy, states, keyboard, accessibility, content or tokens | Add the section from spec-template.md |
| CS002 | high | Focus state defined | Interactive component, but "focus" appears nowhere | Define focus-visible per variant; indicator 3:1 vs adjacent colours (WCAG 2.4.7, 1.4.11) |
| CS003 | high | Keyboard model | No key -> action table (Tab, Enter, Space, arrows, Escape) | Copy the pattern's table from apg-patterns.md and adapt it |
| CS004 | high | Semantics match the job | A "dropdown" of actions specified as a select, tabs used as page navigation, a switch that waits for Save | Re-map to the right APG pattern |
| CS005 | medium | Hover-only behaviour | "Appears on hover", "hover to reveal" with no focus or touch equivalent | Show on focus too; on touch, make it always visible or move it to a menu |
| CS006 | medium | Long-text rule | No max length, wrap, truncation or line-clamp per text slot | Add a content table; test the longest real string +40% |
| CS007 | medium | Raw values | Hex colours or px numbers in prose instead of token names | Replace with semantic tokens; propose new tokens if missing |
| CS008 | medium | Edge cases | No empty, error, loading, long text, RTL or zoom cases | Walk edge-case-catalogue.md |
| CS009 | medium | Disabled with no reason | Disabled state but nothing says how users learn why | Prefer enabled + validation; else aria-disabled + helper text |
| CS010 | medium | Target size | Any size under 24x24 CSS px, or touch product under 44pt / 48dp | Increase height or hit area (padding / pseudo-element) |
| CS011 | medium | Matrix explosion | Variants x states over about 60 cells | Split into two components or drop variants |
| CS012 | medium | Focus movement | Opens or removes content but does not say where focus goes | Define focus on open, close and delete |
| CS013 | low | Usage guidance | No "when to use / when not to use" | Add both, naming the alternative component |
| CS014 | low | Placeholders | TODO, TBD, ???, lorem ipsum | Resolve or move to Open questions with an owner |

## Summary line

End the review with: `N findings: H high, M medium, L low. Ready for handoff: yes/no.`
