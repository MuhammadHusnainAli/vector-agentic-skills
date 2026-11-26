# UI design skill script cases. Syntax: see tests/run_tests.sh.

# ---- Design systems
TL="$UI/design-token-architecture-builder/scripts/token_lint.mjs"
t 'token_lint: clean three-tier set' 0 '0 error(s), 0 warning(s)' \
  "$TL" "$FX/ui/tokens_core.json" "$FX/ui/tokens_light.json" "$FX/ui/tokens_components.json"
t 'token_lint: mode parity' 0 'TK010 [warn] semantic.color.text.default: missing in mode file(s)' \
  "$TL" "$FX/ui/tokens_core.json" "$FX/ui/tokens_light.json" --modes "$FX/ui/tokens_light.json" "$FX/ui/tokens_dark.json"
t 'token_lint: --strict fails on warnings' 1 '1 warning(s)' \
  "$TL" "$FX/ui/tokens_core.json" "$FX/ui/tokens_light.json" --modes "$FX/ui/tokens_light.json" "$FX/ui/tokens_dark.json" --strict
t 'token_lint: broken alias' 1 'TK001 [error] component.alert.border: alias {semantic.missing} not found' "$TL" "$FX/ui/tokens_bad.json"
t 'token_lint: cycle reported once' 1 'TK002 [error] semantic.loop-a: cycle: semantic.loop-a -> semantic.loop-b -> semantic.loop-a' "$TL" "$FX/ui/tokens_bad.json"
t 'token_lint: invalid colour' 1 'TK004 [error] core.color.red: invalid color value "#GG0000"' "$TL" "$FX/ui/tokens_bad.json"
t 'token_lint: tier skip' 1 'TK006 [warn] component.alert.bg: references primitive' "$TL" "$FX/ui/tokens_bad.json"
t 'token_lint: type mismatch' 1 'TK005 [warn] semantic.gap: is dimension but resolves to a color' "$TL" "$FX/ui/tokens_bad.json"
t 'token_lint: unknown tier exits 2' 2 "unknown tier 'foo'" "$TL" "$FX/ui/tokens_core.json" --tiers foo=bar
t 'token_lint: missing file exits 2' 2 'error:' "$TL" "$FX/ui/nope.json"
IS="$UI/component-library-inventory-auditor/scripts/inventory_scan.mjs"
t 'inventory_scan: near-duplicate button family' 1 'IN001 [warn] button: near-duplicates: Btn (1 uses), Button (1 uses), PrimaryButton (1 uses)' "$IS" "$FX/ui/app_src"
t 'inventory_scan: local Modal shadows DS Dialog' 1 'IN002 [warn] Modal: local Modal in components/Modal.tsx duplicates design-system Dialog' "$IS" "$FX/ui/app_src" --ds @acme/ui
t 'inventory_scan: stories do not count as usage' 1 'IN003 [info] OldBanner: defined in components/OldBanner.tsx but never used' "$IS" "$FX/ui/app_src"
t 'inventory_scan: hard-coded colour hotspot' 1 'IN004 [warn] components/Card.tsx: 6 hard-coded colours' "$IS" "$FX/ui/app_src"
t 'inventory_scan: vue kebab usage counted' 1 '| UserAvatar | components/user-avatar.vue | 1 | 1 | user-avatar |' "$IS" "$FX/ui/app_src"
t 'inventory_scan: csv output' 1 '"Card","components/Card.tsx","2","1","card",""' "$IS" "$FX/ui/app_src" --csv
t 'inventory_scan: missing dir exits 2' 2 'error:' "$IS" "$FX/ui/nope"
AS="$UI/design-system-adoption-tracker/scripts/adoption_scan.mjs"
t 'adoption_scan: per-app adoption' 0 '| apps/web | 80% | - | 4 | 1 | 0 | 0 | 75% | 1 | ^3.1.0 |' "$AS" "$FX/ui/monorepo" --ds @acme/ui --depth 2
t 'adoption_scan: below target fails' 1 'AD001 [warn] apps/admin: adoption 14.3% is below the 50% target' "$AS" "$FX/ui/monorepo" --ds @acme/ui --depth 2 --min 50
t 'adoption_scan: version lag' 0 'AD003 [warn] apps/admin: on @acme/ui ^2.4.0, latest major is 3' "$AS" "$FX/ui/monorepo" --ds @acme/ui --depth 2 --latest 3.2.0
t 'adoption_scan: raw html list' 0 'AD002 [info] apps/admin: raw HTML the design system replaces: <button> x1, <input> x1, <table> x1' "$AS" "$FX/ui/monorepo" --ds @acme/ui --depth 2
t 'adoption_scan: change since baseline' 0 '| apps/web | 80% | +10 pts |' "$AS" "$FX/ui/monorepo" --ds @acme/ui --depth 2 --baseline "$FX/ui/adoption_baseline.json"
t 'adoption_scan: csv history row' 0 ',apps/admin,14.3,1,2,1,3,0,2,^2.4.0' "$AS" "$FX/ui/monorepo" --ds @acme/ui --depth 2 --csv
t 'adoption_scan: --ds required' 2 'name the design-system package with --ds' "$AS" "$FX/ui/monorepo"

# ---- Visual UI polish
SA="$UI/ui-spacing-scale-consistency-checker/scripts/spacing_audit.mjs"
t 'spacing_audit: off-scale value with locations' 1 'SP001 [warn] 10px used 2x is off scale -> 8 or 12px' "$SA" "$FX/ui/spacing"
t 'spacing_audit: rem and tailwind arbitrary converted' 1 '| 17.6px | 1 | no -> 16 |' "$SA" "$FX/ui/spacing"
t 'spacing_audit: on-scale share' 1 '17 raw spacing values in 3 files: 58.8% on scale' "$SA" "$FX/ui/spacing"
t 'spacing_audit: clean file passes' 0 '100% on scale, 0 off-scale value(s)' "$SA" "$FX/ui/spacing/clean.css"
t 'spacing_audit: --base 2 accepts even values' 1 '88.2% on scale, 2 off-scale value(s)' "$SA" "$FX/ui/spacing" --base 2
t 'spacing_audit: --min threshold passes' 0 '58.8% on scale' "$SA" "$FX/ui/spacing" --min 50
t 'spacing_audit: bad scale exits 2' 2 '--scale must be' "$SA" "$FX/ui/spacing" --scale 4,x
GC="$UI/icon-pixel-grid-aligner/scripts/svg_grid_check.mjs"
t 'svg_grid_check: 1px stroke on whole pixels blurs' 1 'IG002 [warn] 5 off-grid edge(s): x=4 -> 4.5, x=20 -> 20.5' "$GC" "$FX/ui/icons/blurry.svg"
t 'svg_grid_check: fills on half pixels' 1 'x=20.5 -> 21, y=5.5 -> 6, x=3.5 -> 4' "$GC" "$FX/ui/icons/filled.svg"
t 'svg_grid_check: transform flagged' 1 'IG004 [warn] transform attribute found' "$GC" "$FX/ui/icons/filled.svg"
t 'svg_grid_check: fractional stroke and viewBox' 1 'IG003 [warn] fractional stroke width 1.5' "$GC" "$FX/ui/icons/wide.svg"
t 'svg_grid_check: set mixes caps' 1 'SET IG007 [warn] mixed stroke caps: butt (1), round (2), square (1)' "$GC" "$FX/ui/icons"
t 'svg_grid_check: clean icons pass' 0 '2 icon(s), 0 warning(s)' "$GC" "$FX/ui/icons/menu.svg" "$FX/ui/icons/check.svg" --stroke 2 --padding 2
t 'svg_grid_check: invalid path exits 2' 2 'path data must start with M' "$GC" "$FX/ui/icon_bad_path.svg"
