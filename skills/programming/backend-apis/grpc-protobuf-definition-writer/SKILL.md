---
name: grpc-protobuf-definition-writer
description: "Write Protocol Buffers definitions for gRPC services that are idiomatic, efficient on the wire and safe to evolve: proto3 (and editions) syntax, versioned packages, file layout, resource-oriented services following Google API Improvement Proposals (Get, List, Create, Update with field masks, Delete, custom methods), dedicated request/response messages, pagination with page_size/page_token, field numbering (1-15 for hot fields, reserved numbers and names after removals), scalar type choice (int64 vs sint64 vs fixed64), well-known types (Timestamp, Duration, FieldMask, Struct), money and enums with UNSPECIFIED zero values, oneof, maps and optional presence, streaming RPC shapes, rich errors (google.rpc.Status details), and Buf tooling. Ships proto_lint.py (with a stdlib .proto parser) that reports field-number misuse, bad enum zero values, required fields, unversioned packages, naming, shared messages and unpaginated List RPCs. Use when writing or reviewing .proto files."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# gRPC Protobuf Definition Writer

A `.proto` file is a contract compiled into every client. Mistakes made on day one, like a shared request message, an
enum without an UNSPECIFIED zero, a reused field number, or a List RPC with no pagination, are permanent or expensive to
undo. Protobuf gives you a compact, fast wire format and safe evolution, but only if the definitions follow its rules.
This skill writes protos in the Google AIP / Buf style and lints them with `scripts/proto_lint.py`.

## Trigger Conditions

Activate this skill when the user:
- Writes or reviews `.proto` files or gRPC service definitions
- Designs a resource-oriented gRPC API (Get/List/Create/Update/Delete)
- Chooses field types, numbering, enums, oneofs or well-known types
- Sets up Buf linting and code generation

Server code: `grpc-service-scaffolder`. Evolution and breaking changes: `protobuf-schema-evolution-checker`.

## Workflow

```
1. LAYOUT    -> package acme.<domain>.v1, one service per file, go_package/java_package options (references/proto-style.md)
2. RESOURCES -> resource messages with name/id, standard methods per AIP; custom methods for actions
3. MESSAGES  -> <Rpc>Request / <Rpc>Response for every RPC; FieldMask for updates; page_size/page_token for lists
4. FIELDS    -> types and numbers deliberately (references/field-design.md); 1-15 for frequent fields
5. ENUMS     -> <ENUM>_UNSPECIFIED = 0, values prefixed with the enum name
6. LINT      -> python scripts/proto_lint.py api/**/*.proto (then buf lint + buf breaking in CI)
7. GENERATE  -> buf generate for each language; publish to a schema registry (Buf Schema Registry or internal)
```

## Lint Codes (proto_lint.py)

| Code | Severity | Problem |
|------|----------|---------|
| PL001 | error | Duplicate field number, number in 19000-19999, or reused reserved number/name |
| PL002 | error | Enum without zero first value, or zero not `<ENUM>_UNSPECIFIED` |
| PL003 | error | proto2 `required` field |
| PL004 | warn | Package missing or unversioned |
| PL005 | warn | Naming conventions broken |
| PL006 | warn | RPC uses shared, non-dedicated or `google.protobuf.Empty` messages |
| PL007 | warn | Service name not ending in `Service` |
| PL008 | warn | List RPC without page_size/page_token/next_page_token |
| PL009 | warn | Syntax missing or proto2 |
| PL010 | info | Missing go_package/java_package options |

AIP-135 permits `google.protobuf.Empty` as the response of standard Delete methods; Buf's default lint does not. Pick one
rule for your organisation and document it.

## Scripts

```bash
python scripts/proto_lint.py api/acme/orders/v1/orders.proto [more.proto] [--json]
```
`scripts/_proto.py` is a small standard-library parser (messages, nested types, oneofs, maps, enums, reserved ranges, services,
streaming RPCs). It complements, not replaces, `protoc`/`buf` compilation.
Exit codes: 0 clean, 1 errors or warnings, 2 unreadable input.

## Output

`.proto` files with comments on every service, RPC, message and field; lint results; `buf.yaml`/`buf.gen.yaml`.

## Additional Resources

| File | Content |
|------|---------|
| [proto-style.md](references/proto-style.md) | File layout, packages, naming, AIP standard and custom methods, pagination, field masks, errors, Buf config |
| [field-design.md](references/field-design.md) | Scalar choice and wire costs, numbering, well-known types, money, enums, oneof, maps, presence, streaming shapes |
