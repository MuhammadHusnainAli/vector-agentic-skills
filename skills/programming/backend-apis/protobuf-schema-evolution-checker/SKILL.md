---
name: protobuf-schema-evolution-checker
description: "Evolve Protocol Buffers schemas without breaking deployed clients, stored data or event consumers: the three compatibility levels (wire, JSON, generated source), rules for removing fields (reserve numbers and names), renames, type changes within wire-compatible groups, presence and cardinality, oneof moves, enum evolution with unknown values, RPC and service changes, package moves, rollout order for producers and consumers, schema registries for Kafka and long-lived data, and CI gates with buf breaking. Ships proto_diff.py (with a stdlib .proto parser) that compares two versions and reports breaking changes (unreserved removals, number reuse, incompatible types, cardinality and oneof changes, removed messages, enums, enum values, RPCs, services), risky changes (renames, compatible-group type changes, presence changes) and safe additions. Use when changing .proto files, reviewing schema pull requests or setting up compatibility checks for gRPC or protobuf events."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# Protobuf Schema Evolution Checker

Protobuf is designed for evolution: old readers skip unknown fields and new readers see defaults for missing ones. It only
works if you follow its rules. Reusing a field number silently corrupts data. Old events stored in Kafka or a database get
decoded into the wrong field, and nobody notices until finance does. This skill classifies every change with
`scripts/proto_diff.py`, explains the safe alternative, and plans rollout order across producers and consumers.

## Trigger Conditions

Activate this skill when the user:
- Changes a `.proto` used by deployed services, mobile apps, events or stored data
- Reviews a schema pull request
- Sets up `buf breaking` or a schema registry compatibility mode
- Asks whether a rename, type change or removal is safe

Proto authoring: `grpc-protobuf-definition-writer`. REST/OpenAPI equivalent: `rest-api-versioning-strategist`. Kafka:
`kafka-producer-consumer-writer`.

## Compatibility Levels

| Level | Who cares | Breaks on |
|-------|-----------|-----------|
| Wire (binary) | Every reader of encoded bytes: services, events, stored blobs | Number reuse, incompatible type change, cardinality change |
| JSON | REST transcoding, logs, JSON-encoded events | Field or enum value rename |
| Source (generated code) | Code compiled against the stubs | Renames, removals, type changes, oneof moves |

Long-lived data (events, stored messages) needs wire compatibility forever. Internal services updated together may accept
source breaks with coordinated releases.

## Diff Codes (proto_diff.py)

| Code | Severity | Change |
|------|----------|--------|
| PE001 | error | Field removed without reserving number and name |
| PE002 | error | Field number reused or changed |
| PE003 | error | Incompatible type change |
| PE004 | error | Repeated/singular or map change |
| PE005 | error | Field moved into or out of a oneof |
| PE006 | error | Message or enum removed |
| PE007 | error | Enum value removed or renumbered |
| PE008 | error | RPC removed, signature or streaming changed |
| PE009 | error | Service removed or package changed |
| PW001-PW003 | warn | Rename; compatible-group type change; presence change |
| PI001-PI002 | info | Additions; removal with reservation |

## Scripts

```bash
python scripts/proto_diff.py old/orders.proto new/orders.proto [--json]
```
Uses `scripts/_proto.py`, a standard-library parser. Run it per file; for whole modules use `buf breaking` in CI as well.
Exit codes: 0 no breaking changes, 1 breaking, 2 unreadable files.

## Output

Change classification with the safe alternative for each breaking change, the rollout order, and CI configuration.

## Additional Resources

| File | Content |
|------|---------|
| [evolution-rules.md](references/evolution-rules.md) | Safe and unsafe changes with alternatives, enums and unknown values, presence, oneof, defaults |
| [rollout-and-registries.md](references/rollout-and-registries.md) | Producer/consumer rollout order, events and stored data, schema registries, buf breaking, deprecation |
