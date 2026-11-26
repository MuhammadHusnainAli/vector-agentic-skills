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
