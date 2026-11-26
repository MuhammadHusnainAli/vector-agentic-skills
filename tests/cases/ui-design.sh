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
