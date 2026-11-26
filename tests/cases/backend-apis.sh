# Backend and API skill script cases. Syntax: see tests/run_tests.sh.

# ---- REST API design
CP="$BE/rest-api-endpoint-designer/scripts/capacity_plan.py"
t 'capacity_plan: 1M rps cells and instances' 1 'Instances                    39 per cell, 117 per region, 351 total' \
  "$CP" --rps 1000000 --instance-rps 4000 --p50-ms 8 --p99-ms 45 --regions 3 --survive-region-loss
t 'capacity_plan: CDN offload' 1 'Served at the edge (CDN)     456.00k req/s (45.6%)' \
  "$CP" --rps 1000000 --instance-rps 4000 --regions 3 --survive-region-loss
t 'capacity_plan: Little law in flight' 1 '4.35k at mean latency, 24.48k at p99' \
  "$CP" --rps 1000000 --instance-rps 4000 --p50-ms 8 --p99-ms 45 --regions 3 --survive-region-loss
t 'capacity_plan: write shard warning' 1 'PLAN002 [warn] 50.00k DB writes/s exceeds one primary' \
  "$CP" --rps 1000000 --instance-rps 4000 --regions 3
t 'capacity_plan: no headroom warning' 1 'PLAN001 [warn] target utilisation 85%' \
  "$CP" --rps 100000 --instance-rps 4000 --target-util 0.85
t 'capacity_plan: small clean plan' 0 'Per-instance capacity        2.00k req/s' \
  "$CP" --rps 20000 --cpu-ms 2 --cores 4 --write-ratio 0.02
t 'capacity_plan: missing throughput source exits 2' 2 'one of the arguments --instance-rps --cpu-ms is required' "$CP" --rps 1000
OL="$BE/openapi-spec-writer/scripts/openapi_lint.py"
t 'openapi_lint: clean spec' 0 '0 error(s), 0 warning(s), 0 info' "$OL" "$FX/be/openapi_good.json"
t 'openapi_lint: yaml spec' 0 '0 error(s), 0 warning(s), 0 info' "$OL" "$FX/be/openapi_good.yaml"
t 'openapi_lint: duplicate operationId' 1 "OA003 [error] GET /users/{id}: operationId 'createUser' already used by POST /users" "$OL" "$FX/be/openapi_bad.json"
t 'openapi_lint: unresolved ref' 1 'OA004 [error] #/components/schemas/Missing: unresolved $ref' "$OL" "$FX/be/openapi_bad.json"
t 'openapi_lint: path param mismatch' 1 'OA005 [error] GET /users/{id}: path parameter(s) not declared: id' "$OL" "$FX/be/openapi_bad.json"
t 'openapi_lint: unbounded list' 1 "OA008 [warn] GET /users: unbounded list 'body'" "$OL" "$FX/be/openapi_bad.json"
t 'openapi_lint: unbounded input' 1 'OA009 [warn] POST /users: unbounded input: name, tags' "$OL" "$FX/be/openapi_bad.json"
t 'openapi_lint: idempotency key' 1 'OA011 [warn] POST /users: no Idempotency-Key header' "$OL" "$FX/be/openapi_bad.json"
t 'openapi_lint: missing file exits 2' 2 'error:' "$OL" "$FX/be/nope.json"
OD="$BE/rest-api-versioning-strategist/scripts/openapi_diff.py"
t 'openapi_diff: removed operation' 1 'BC001 [error] GET /orders/{orderId}: operation removed' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_breaking.json"
t 'openapi_diff: removed response property in list' 1 'BC003 [error] GET /orders 200.data[].status: response property removed' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_breaking.json"
t 'openapi_diff: type change' 1 'BC004 [error] POST /orders body.quantity: type changed integer -> string' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_breaking.json"
t 'openapi_diff: tightened constraint' 1 'BC008 [error] POST /orders body.sku: maxLength tightened 40 -> 20' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_breaking.json"
t 'openapi_diff: renamed operationId' 1 'BC009 [error] POST /orders: operationId createOrder -> placeOrder' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_breaking.json"
t 'openapi_diff: summary' 1 '8 breaking, 0 potentially breaking, 3 non-breaking change(s)' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_breaking.json"
t 'openapi_diff: compatible changes pass' 0 '0 breaking, 0 potentially breaking, 4 non-breaking change(s)' "$OD" "$FX/be/openapi_good.json" "$FX/be/openapi_v2_safe.json"
t 'openapi_diff: missing file exits 2' 2 'error:' "$OD" "$FX/be/openapi_good.json" "$FX/be/nope.json"
NL="$BE/rest-api-naming-reviewer/scripts/path_naming_lint.py"
t 'path_naming_lint: verb in path' 1 "NM001 [warn] /v1/createUser: verb 'create' in segment 'createUser'" "$NL" "$FX/be/routes_bad.txt"
t 'path_naming_lint: singular collection' 1 "NM004 [warn] /v1/user/{id}: singular collection 'user'" "$NL" "$FX/be/routes_bad.txt"
t 'path_naming_lint: parameter names differ' 1 "NM007 [warn] /orders/{...}: same resource uses parameter names ['id', 'orderId', 'order_id']" "$NL" "$FX/be/routes_bad.txt"
t 'path_naming_lint: deep nesting' 1 'NM006 [warn] /v1/users/{userId}/orders/{orderId}/items/{itemId}/notes: 3 nested resource levels' "$NL" "$FX/be/routes_bad.txt"
t 'path_naming_lint: mixed version prefixes' 1 "NM009 [warn] versions: version prefixes differ: ['api/vN', 'vN']" "$NL" "$FX/be/routes_bad.txt"
t 'path_naming_lint: action suffix and kebab pass' 0 '6 paths, dominant segment style kebab-case: 0 warning(s)' "$NL" "$FX/be/routes_good.txt"
t 'path_naming_lint: openapi input' 0 '2 paths' "$NL" "$FX/be/openapi_good.json"
t 'path_naming_lint: missing file exits 2' 2 'error:' "$NL" "$FX/be/nope.txt"

# ---- GraphQL and gRPC
GL="$BE/graphql-schema-designer/scripts/graphql_schema_lint.py"
t 'graphql_schema_lint: unbounded list' 1 'GQ001 [warn] Query.users: unbounded list [User]' "$GL" "$FX/be/schema_bad.graphql"
t 'graphql_schema_lint: mutation input and payload' 1 'GQ003 [warn] Mutation.createOrder: mutations should take one argument: input: XInput!' "$GL" "$FX/be/schema_bad.graphql"
t 'graphql_schema_lint: id typed string' 1 'GQ004 [warn] User.id: identifier typed String; use ID' "$GL" "$FX/be/schema_bad.graphql"
t 'graphql_schema_lint: enum value casing' 1 'GQ005 [warn] orderStatus.pending: enum values should be UPPER_SNAKE_CASE' "$GL" "$FX/be/schema_bad.graphql"
t 'graphql_schema_lint: rpc-style query' 1 'GQ006 [warn] Query.getUser: RPC-style name' "$GL" "$FX/be/schema_bad.graphql"
t 'graphql_schema_lint: relay schema passes' 0 '13 type(s): 0 warning(s), 0 info' "$GL" "$FX/be/schema_good.graphql"
t 'graphql_schema_lint: missing file exits 2' 2 'error:' "$GL" "$FX/be/nope.graphql"
PLT="$BE/grpc-protobuf-definition-writer/scripts/proto_lint.py"
t 'proto_lint: idiomatic proto passes' 0 '0 error(s), 0 warning(s), 0 info' "$PLT" "$FX/be/orders_good.proto"
t 'proto_lint: duplicate field number' 1 'PL001 [error] orders_bad.proto:14: Order.status reuses field number 2 (also totalAmount)' "$PLT" "$FX/be/orders_bad.proto"
t 'proto_lint: reserved range' 1 'Order.trace uses number 19001 in the reserved 19000-19999 range' "$PLT" "$FX/be/orders_bad.proto"
t 'proto_lint: enum zero value' 1 'PL002 [error] orders_bad.proto:20: enum Status must start with a zero value' "$PLT" "$FX/be/orders_bad.proto"
t 'proto_lint: dedicated request message' 1 'getOrder request is OrderId; use GetOrderRequest' "$PLT" "$FX/be/orders_bad.proto"
t 'proto_lint: list pagination' 1 'PL008 [warn] orders_bad.proto:4: ListOrders needs page_size + page_token' "$PLT" "$FX/be/orders_bad.proto"
t 'proto_lint: missing file exits 2' 2 'error:' "$PLT" "$FX/be/nope.proto"
PD2="$BE/protobuf-schema-evolution-checker/scripts/proto_diff.py"
t 'proto_diff: unreserved removal' 1 'PE001 [error] Order.total_minor (3): removed without' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_breaking.proto"
t 'proto_diff: incompatible type' 1 'PE003 [error] Order.currency_code (4): type string -> int64' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_breaking.proto"
t 'proto_diff: oneof move' 1 'PE005 [error] Order.card_id (7): oneof membership changed (payment -> none)' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_breaking.proto"
t 'proto_diff: rename is risky' 1 'PW001 [warn] Order.id (1): renamed to order_id' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_breaking.proto"
t 'proto_diff: rpc signature' 1 'PE008 [error] OrderService.GetOrder: request/response changed' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_breaking.proto"
t 'proto_diff: summary' 1 '6 breaking, 1 risky, 2 safe change(s)' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_breaking.proto"
t 'proto_diff: reserved removal and additions are safe' 0 'PI002 [info] Order.total_minor (3): removed and reserved' "$PD2" "$FX/be/orders_good.proto" "$FX/be/orders_v2_safe.proto"
t 'proto_diff: missing file exits 2' 2 'error:' "$PD2" "$FX/be/orders_good.proto" "$FX/be/nope.proto"

# ---- Authentication and authorization
JI="$BE/jwt-auth-flow-implementer/scripts/jwt_inspect.py"
t 'jwt_inspect: valid hmac token' 0 'size: 251 bytes; signature: verified' "$JI" "$FX/be/jwt_good.txt" --secret s3cret-key-0123456789 --audience orders-api --now 1767226000
t 'jwt_inspect: wrong secret' 1 'JW004 [error] HS256 signature does not verify' "$JI" "$FX/be/jwt_good.txt" --secret wrong --now 1767226000
t 'jwt_inspect: expired token' 1 'JW003 [error] expired at 2026-01-01 00:15:00 UTC' "$JI" "$FX/be/jwt_good.txt" --now 1767300000
t 'jwt_inspect: alg none' 1 "JW001 [error] alg is 'none'" "$JI" "$FX/be/jwt_bad.txt" --now 1767226000
t 'jwt_inspect: sensitive claim' 1 "JW009 [warn] claim 'password' looks sensitive" "$JI" "$FX/be/jwt_bad.txt" --now 1767226000
t 'jwt_inspect: long lifetime and size' 1 'JW011 [warn] token is 3035 bytes' "$JI" "$FX/be/jwt_long.txt" --now 1767226000
t 'jwt_inspect: missing kid' 1 'JW008 [warn] asymmetric alg without kid' "$JI" "$FX/be/jwt_long.txt" --now 1767226000
t 'jwt_inspect: not a jwt exits 2' 2 'not a JWT' "$JI" abc.def
