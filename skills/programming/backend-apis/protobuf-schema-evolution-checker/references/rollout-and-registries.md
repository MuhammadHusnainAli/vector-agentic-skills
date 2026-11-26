# Rollout and Registries

## Rollout order

| Change | Deploy first | Then |
|--------|--------------|------|
| Add a field the server will return | Server (clients ignore it) | Clients that use it |
| Add a field clients will send | Server that understands it | Clients |
| Add a new RPC | Server | Clients |
| Add an enum value the server emits | Clients that handle it (or confirm they treat unknowns safely) | Server |
| Remove a field | Clients stop reading/sending it | Server stops populating; reserve |
| Events: add a field | Consumers can ignore it, so producers first is fine | Consumers that use it |
| Events: start relying on a field | Producers populate it for all new events first; backfill or handle absence | Consumers |

Mobile clients live for years: assume old versions keep running; never remove fields they read without a long window.

## Events and stored data

- Wire compatibility must hold for as long as data is retained (Kafka retention, event store forever, cold storage).
- Never reuse numbers, even years later: reserved lists are permanent.
- Include a schema reference with stored payloads (registry ID or type URL) so readers pick the right descriptor.

## Schema registries

| Registry | Notes |
|----------|-------|
| Confluent Schema Registry | Protobuf support; compatibility modes BACKWARD, FORWARD, FULL (and _TRANSITIVE); serializers embed schema IDs |
| Buf Schema Registry | Module versioning, `buf breaking` against published versions, generated SDKs |
| Apicurio | Protobuf, Avro, JSON Schema; compatibility rules |

Choose BACKWARD (consumers on the new schema can read old data) as the minimum for events; FULL_TRANSITIVE when both
directions must hold across all versions.

## CI gates

```bash
buf lint
buf breaking --against '.git#branch=main'                 # module-wide
python scripts/proto_diff.py <(git show main:api/orders.proto) api/orders.proto
```
Choose the `buf breaking` category to match your contract: `WIRE` (binary only), `WIRE_JSON`, or `FILE`/`PACKAGE`
(source compatibility, strictest).

## Review checklist

- [ ] No PE codes from proto_diff (or an intentional new major package)
- [ ] Removed fields and enum values reserved by number and name
- [ ] New enum values: consumers tolerate unknowns
- [ ] Rollout order documented in the PR
- [ ] Registry compatibility mode passes
