#!/usr/bin/env python3
"""Capacity plan for an HTTP API from a peak request rate: edge, regions, cells, instances, concurrency, database and bandwidth.

All rates are peak requests per second. The model, in order:
  edge      CDN/edge cache absorbs --cdn-hit of cacheable reads (GETs); the rest reach the origin
  regions   origin traffic split over --regions; with --survive-region-loss each region is sized for regions-1
  cells     each region is split into cells of at most --cell-rps (blast-radius limit)
  instances per region = origin_rps_region / (per_instance_rps x --target-util), +1 per cell for N+1
  in flight Little's law L = lambda x W, at mean latency and at p99 latency
  database  reads miss the app cache (1 - --app-cache-hit) x --db-reads-per-miss; writes x --db-writes-per-write
  bandwidth request and response bytes at the edge and at the origin

Per-instance throughput comes from a load test (--instance-rps) or from CPU cost (--cpu-ms x --cores).

Warnings (PLAN0xx) flag designs that break at scale: database load beyond one primary, utilisation targets with no
headroom, latency budgets the dependency chain can't meet, too many instances per cell, oversized payloads.

Usage:
    python capacity_plan.py --rps 1000000 --instance-rps 4000 --p50-ms 8 --p99-ms 45 --regions 3 --survive-region-loss
    python capacity_plan.py --rps 200000 --cpu-ms 2.5 --cores 8 --write-ratio 0.1 --json

Exit codes: 0 plan produced, 1 plan produced with warnings, 2 bad arguments.
"""

import argparse
import json
import math
import sys


def positive(v):
    f = float(v)
    if f <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return f


def fraction(v):
    f = float(v)
    if not 0 <= f < 1:
        raise argparse.ArgumentTypeError("must be in [0, 1)")
    return f


def fmt(n):
    for unit, size in (("M", 1e6), ("k", 1e3)):
        if n >= size:
            return f"{n / size:,.2f}{unit}"
    return f"{n:,.0f}" if n >= 10 else f"{n:,.2f}"


def plan(a):
    warn = []
    per_inst = a.instance_rps or (a.cores * 1000.0 / a.cpu_ms)
    reads, writes = a.rps * (1 - a.write_ratio), a.rps * a.write_ratio
    cacheable = reads * a.cacheable
    edge_served = cacheable * a.cdn_hit
    origin = a.rps - edge_served
    live_regions = a.regions - 1 if a.survive_region_loss and a.regions > 1 else a.regions
    region_rps = origin / live_regions
    cells = max(1, math.ceil(region_rps / a.cell_rps))
    cell_rps = region_rps / cells
    inst_per_cell = math.ceil(cell_rps / (per_inst * a.target_util)) + 1        # +1: survive losing one instance
    inst_region = inst_per_cell * cells
    mean_s = (a.mean_ms or a.p50_ms) / 1000.0
    inflight_mean, inflight_p99 = origin * mean_s, origin * a.p99_ms / 1000.0
    origin_reads = reads - edge_served
    db_reads = origin_reads * (1 - a.app_cache_hit) * a.db_reads_per_miss
    db_writes = writes * a.db_writes_per_write
    edge_in = a.rps * a.req_kb * 8 / 1e6                   # Gbit/s (kB -> kbit -> Gbit)
    edge_out = a.rps * a.resp_kb * 8 / 1e6
    origin_out = origin * a.resp_kb * 8 / 1e6

    if a.target_util > 0.75:
        warn.append(("PLAN001", f"target utilisation {a.target_util:.0%} leaves no headroom for spikes, GC and failover; use 0.5-0.7"))
    if db_writes > a.db_write_limit:
        warn.append(("PLAN002", f"{fmt(db_writes)} DB writes/s exceeds one primary (~{fmt(a.db_write_limit)}/s): shard by a key, batch, or queue writes"))
    if db_reads > a.db_read_limit:
        warn.append(("PLAN003", f"{fmt(db_reads)} DB reads/s exceeds ~{fmt(a.db_read_limit)}/s per primary+replicas set: raise cache hit rate, add replicas or shard"))
    if a.p99_ms > a.budget_ms:
        warn.append(("PLAN004", f"service p99 {a.p99_ms:g} ms exceeds the {a.budget_ms:g} ms budget before network and edge time"))
    if inst_per_cell > a.max_cell_instances:
        warn.append(("PLAN005", f"{inst_per_cell} instances per cell: lower --cell-rps or raise per-instance throughput"))
    if a.resp_kb > 100:
        warn.append(("PLAN006", f"{a.resp_kb:g} kB responses: {edge_out:,.0f} Gbit/s at the edge; paginate, compress, use sparse fieldsets"))
    if a.cdn_hit and a.cacheable == 0:
        warn.append(("PLAN007", "CDN hit rate given but --cacheable is 0: nothing is cacheable at the edge"))
    if a.instance_rps is None and a.cpu_ms < 0.2:
        warn.append(("PLAN008", f"{a.cpu_ms} ms CPU per request is optimistic for real handlers; measure with a load test"))

    rows = [
        ("Peak traffic", f"{fmt(a.rps)} req/s ({fmt(reads)} reads, {fmt(writes)} writes)"),
        ("Served at the edge (CDN)", f"{fmt(edge_served)} req/s ({edge_served / a.rps:.1%})"),
        ("Origin traffic", f"{fmt(origin)} req/s"),
        ("Regions", f"{a.regions} ({'sized for loss of one: ' if live_regions < a.regions else ''}{fmt(region_rps)} req/s each)"),
        ("Cells per region", f"{cells} x {fmt(cell_rps)} req/s"),
        ("Per-instance capacity", f"{fmt(per_inst)} req/s at 100%, {fmt(per_inst * a.target_util)} at {a.target_util:.0%} target"),
        ("Instances", f"{inst_per_cell} per cell, {inst_region} per region, {inst_region * a.regions} total"),
        ("Requests in flight (origin)", f"{fmt(inflight_mean)} at mean latency, {fmt(inflight_p99)} at p99"),
        ("DB reads after caches", f"{fmt(db_reads)} /s"),
        ("DB writes", f"{fmt(db_writes)} /s"),
        ("Bandwidth at edge", f"{edge_in:,.1f} Gbit/s in, {edge_out:,.1f} Gbit/s out"),
        ("Bandwidth at origin (out)", f"{origin_out:,.1f} Gbit/s"),
    ]
    data = {"per_instance_rps": per_inst, "origin_rps": origin, "region_rps": region_rps, "cells_per_region": cells,
            "instances_per_cell": inst_per_cell, "instances_total": inst_region * a.regions,
            "inflight_mean": inflight_mean, "inflight_p99": inflight_p99, "db_reads": db_reads, "db_writes": db_writes,
            "edge_gbps_in": edge_in, "edge_gbps_out": edge_out, "origin_gbps_out": origin_out}
    return rows, warn, data


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rps", type=positive, required=True, help="peak requests per second")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--instance-rps", type=positive, help="measured max req/s of one instance (load test)")
    src.add_argument("--cpu-ms", type=positive, help="CPU milliseconds per request (use with --cores)")
    ap.add_argument("--cores", type=positive, default=4, help="cores per instance with --cpu-ms (default 4)")
    ap.add_argument("--p50-ms", type=positive, default=10, help="service median latency (default 10)")
    ap.add_argument("--mean-ms", type=positive, help="service mean latency (default: p50)")
    ap.add_argument("--p99-ms", type=positive, default=50, help="service p99 latency (default 50)")
    ap.add_argument("--budget-ms", type=positive, default=100, help="end-to-end p99 budget (default 100)")
    ap.add_argument("--write-ratio", type=fraction, default=0.05, help="share of requests that write (default 0.05)")
    ap.add_argument("--cacheable", type=float, default=0.6, help="share of reads cacheable at the edge (default 0.6)")
    ap.add_argument("--cdn-hit", type=fraction, default=0.8, help="edge hit rate for cacheable reads (default 0.8)")
    ap.add_argument("--app-cache-hit", type=fraction, default=0.9, help="app cache (Redis) hit rate for origin reads (default 0.9)")
    ap.add_argument("--db-reads-per-miss", type=positive, default=1.5, help="DB queries per cache miss (default 1.5)")
    ap.add_argument("--db-writes-per-write", type=positive, default=1.0, help="DB writes per write request (default 1)")
    ap.add_argument("--db-write-limit", type=positive, default=30000, help="sustainable writes/s per primary (default 30k)")
    ap.add_argument("--db-read-limit", type=positive, default=200000, help="sustainable reads/s per replica set (default 200k)")
    ap.add_argument("--regions", type=int, default=3, help="active regions (default 3)")
    ap.add_argument("--survive-region-loss", action="store_true", help="size each region to carry traffic if one fails")
    ap.add_argument("--cell-rps", type=positive, default=100000, help="max req/s per cell (default 100k)")
    ap.add_argument("--max-cell-instances", type=int, default=200, help="warn above this many instances per cell")
    ap.add_argument("--target-util", type=float, default=0.6, help="planned CPU utilisation at peak (default 0.6)")
    ap.add_argument("--req-kb", type=positive, default=1.0, help="average request size in kB (default 1)")
    ap.add_argument("--resp-kb", type=positive, default=4.0, help="average response size in kB (default 4)")
    ap.add_argument("--json", action="store_true", help="print JSON")
    a = ap.parse_args()
    if a.regions < 1 or not 0 < a.target_util <= 1 or not 0 <= a.cacheable <= 1:
        print("error: --regions >= 1, --target-util in (0, 1], --cacheable in [0, 1]", file=sys.stderr)
        return 2
    rows, warn, data = plan(a)
    if a.json:
        print(json.dumps({**data, "warnings": [{"code": c, "message": m} for c, m in warn]}, indent=2))
    else:
        width = max(len(k) for k, _ in rows)
        for k, v in rows:
            print(f"{k:<{width}}  {v}")
        if warn:
            print()
        for code, msg in warn:
            print(f"{code} [warn] {msg}")
    return 1 if warn else 0


if __name__ == "__main__":
    sys.exit(main())
