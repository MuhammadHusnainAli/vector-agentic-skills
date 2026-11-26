# Field Design

## Numbering

- Field numbers 1-15 encode the tag in 1 byte; 16-2047 in 2 bytes. Give 1-15 to fields present in most messages.
- Never change or reuse a number. After removing a field: `reserved 7; reserved "old_name";`.
- 19000-19999 are reserved by protobuf; max is 536,870,911.
- Leave gaps only if you have a reason; numbering order doesn't matter on the wire.

## Scalar choice

| Value | Type | Why |
|-------|------|-----|
| Counts, IDs that are numbers, usually positive | `int64` / `uint64` | Varint: small values are small |
| Often negative numbers | `sint64` | ZigZag encoding keeps small negatives small (int64 negatives take 10 bytes) |
| Hashes, random 64-bit values | `fixed64` | Always 8 bytes, cheaper than varint for large values |
| IDs that are strings (UUID, prefixed) | `string` | Opaque; JSON-friendly |
| Money | `int64 amount_minor` + `string currency_code`, or `google.type.Money` | Never floats |
| Timestamps | `google.protobuf.Timestamp` | Not int64 epochs with unclear units |
| Durations | `google.protobuf.Duration` | |
| Binary | `bytes` | |
| Arbitrary JSON | `google.protobuf.Struct` / `Value` | Last resort; loses typing |

JavaScript note: int64 values beyond 2^53 lose precision in JSON; the protobuf JSON mapping encodes int64 as strings.

## Presence

- proto3 scalars have no presence: `0`, `""` and `false` are indistinguishable from unset. Use `optional` (proto3 since
  3.15) when "not set" differs from zero, e.g. `optional int32 discount_percent`.
- Messages always have presence (`has_field`).
- Wrapper types (`google.protobuf.Int32Value`) are the older way; prefer `optional`.

## Enums

```proto
enum OrderStatus {
  ORDER_STATUS_UNSPECIFIED = 0;   // default when unset; never a real state
  ORDER_STATUS_PENDING = 1;
  ORDER_STATUS_PAID = 2;
}
```
Unknown values are preserved in proto3; clients must handle values they don't know.

## oneof and maps

- `oneof payment_method { CardDetails card = 7; BankDetails bank = 8; }` for mutually exclusive fields. Moving fields into
  or out of a oneof is a breaking change.
- `map<string, string> labels = 6;` for keyed collections; keys must be scalar (not float/bytes/messages); order is not
  preserved.

## Size and performance

- Keep messages small on hot paths; avoid embedding large lists (paginate) and huge `bytes` (use object storage URLs).
- gRPC's default max receive message size is 4 MB in most implementations; raising it is a smell.
- Repeated scalar numerics are packed by default in proto3.

## Streaming shapes

| Shape | Use |
|-------|-----|
| Unary | Most calls |
| Server streaming | Watch/subscribe, large result sets in chunks, progress |
| Client streaming | Uploads, telemetry batches |
| Bidirectional | Chat, interactive sessions, multiplexed commands |

Each stream message should be independently useful (chunk index, final flag); design resumption (resume token) for
long-lived streams.
