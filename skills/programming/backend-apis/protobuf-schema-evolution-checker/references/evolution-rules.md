# Evolution Rules

| Change | Wire | JSON | Source | Do instead |
|--------|------|------|--------|-----------|
| Add field (new number) | Safe | Safe | Safe | |
| Remove field | Safe only if number and name reserved | Safe if reserved | Breaking | `reserved 3; reserved "total";` (mark `[deprecated = true]` first) |
| Rename field | Safe | Breaking | Breaking | Add new field, deprecate old, populate both during migration |
| Change field number | Breaking | Breaking | Safe-looking, corrupts data | Never |
| Reuse a number | Corrupts data | Breaking | | Never; reserve on removal |
| int32 <-> int64, uint32 <-> uint64, bool | Compatible (values truncate) | Mostly | Breaking | New field with the wider type |
| sint32 <-> int32 | Incompatible (ZigZag vs plain varint) | | | New field |
| string <-> bytes | Compatible if valid UTF-8 | Breaking (base64) | Breaking | New field |
| message <-> scalar | Breaking | Breaking | Breaking | New field |
| singular <-> repeated | Breaking for messages/strings; packed numerics partially compatible | Breaking | Breaking | New field |
| Move into/out of oneof | Unsafe (presence/clearing semantics) | | Breaking | New fields in a new oneof |
| Add `optional` (presence) | Safe | Safe | Source change | Usually fine; check generated API |
| Add enum value | Safe (unknown values preserved in proto3) | Readers may reject unknown strings | Safe | Ensure clients handle unknowns |
| Remove enum value | Old data decodes as unknown number | Breaking | Breaking | Reserve: `reserved 2; reserved "ORDER_STATUS_PAID";` |
| Rename enum value | Safe | Breaking | Breaking | Add alias with `option allow_alias = true;` during migration |
| Rename message | Safe on wire | Breaking for `Any` type URLs | Breaking | Keep name; add new message if needed |
| Change package | Breaking for gRPC (method paths include package) | | Breaking | New package version (`v2`) side by side |
| Remove RPC / change its types | Breaking | | Breaking | Deprecate, add new RPC |

## Defaults and unknown values

- proto3 readers see zero values for missing fields: design so zero means "unset/unspecified" (enum `_UNSPECIFIED = 0`).
- Unknown fields are preserved when re-serialising in most languages (proto3 since 3.5); middle services that copy
  messages don't drop new fields.
- Unknown enum values: open enums keep the number; generated code may expose `UNRECOGNIZED` (Java) or the raw int (Go).

## Deprecation

```proto
string total = 3 [deprecated = true];   // generated code warns; keep populating until consumers migrate
```
After every consumer has migrated, remove and reserve.
