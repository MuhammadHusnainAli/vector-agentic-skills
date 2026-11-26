# Proto Style (Google AIP + Buf)

## Layout

```
proto/
  acme/orders/v1/orders.proto            package acme.orders.v1;
  acme/orders/v1/order_service.proto
  acme/common/money/v1/money.proto
buf.yaml  buf.gen.yaml
```
- Directory matches package; one version per directory; `v1alpha1`/`v1beta1` for unstable APIs.
- `option go_package`, `java_package`, `java_multiple_files = true`, `csharp_namespace` as needed (or managed mode in
  buf.gen.yaml).

## Naming

| Element | Style | Example |
|---------|-------|---------|
| Package | lower.dot.v1 | `acme.orders.v1` |
| Service | PascalCase + Service | `OrderService` |
| RPC | PascalCase VerbNoun | `GetOrder`, `ListOrders`, `CancelOrder` |
| Message | PascalCase | `Order`, `ListOrdersRequest` |
| Field | lower_snake_case | `create_time`, `line_items` |
| Enum | PascalCase | `OrderStatus` |
| Enum value | UPPER_SNAKE with enum prefix | `ORDER_STATUS_PAID` |

## Standard methods (AIP-131 to 135)

```proto
service OrderService {
  rpc GetOrder(GetOrderRequest) returns (Order);                      // AIP allows returning the resource
  rpc ListOrders(ListOrdersRequest) returns (ListOrdersResponse);
  rpc CreateOrder(CreateOrderRequest) returns (Order);
  rpc UpdateOrder(UpdateOrderRequest) returns (Order);
  rpc DeleteOrder(DeleteOrderRequest) returns (google.protobuf.Empty);
  rpc CancelOrder(CancelOrderRequest) returns (CancelOrderResponse);  // custom method (AIP-136)
}
message UpdateOrderRequest {
  Order order = 1;
  google.protobuf.FieldMask update_mask = 2;                         // partial updates
}
message ListOrdersRequest {
  string parent = 1;
  int32 page_size = 2;                                               // server caps it (e.g. 1000)
  string page_token = 3;                                             // opaque
  string filter = 4;                                                 // AIP-160 filter syntax
  string order_by = 5;
}
message ListOrdersResponse { repeated Order orders = 1; string next_page_token = 2; }
```
Buf's default lint expects `<Rpc>Request`/`<Rpc>Response` for every RPC; AIP allows returning the resource. Pick one
convention per organisation (Buf's is easier to evolve).

## Idempotency and requests

- `request_id` (UUID) field on create/mutating RPCs for idempotent retries (AIP-155).
- `validate_only` for dry runs; `etag` field for optimistic concurrency (AIP-154).

## Errors

- Use canonical status codes (`NOT_FOUND`, `INVALID_ARGUMENT`, `FAILED_PRECONDITION`, `ALREADY_EXISTS`,
  `RESOURCE_EXHAUSTED`, `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `PERMISSION_DENIED`, `UNAUTHENTICATED`).
- Rich details via `google.rpc.Status` details: `BadRequest` (field violations), `ErrorInfo` (reason, domain, metadata),
  `RetryInfo` (retry delay), `QuotaFailure`.

## Buf configuration

```yaml
# buf.yaml
version: v2
modules:
  - path: proto
lint:
  use: [STANDARD]
breaking:
  use: [FILE]
```
```yaml
# buf.gen.yaml
version: v2
managed:
  enabled: true
  override:
    - file_option: go_package_prefix
      value: github.com/acme/apis/gen/go
plugins:
  - remote: buf.build/protocolbuffers/go
    out: gen/go
    opt: paths=source_relative
  - remote: buf.build/grpc/go
    out: gen/go
    opt: paths=source_relative
```
CI: `buf lint`, `buf breaking --against '.git#branch=main'`, `buf generate`.
