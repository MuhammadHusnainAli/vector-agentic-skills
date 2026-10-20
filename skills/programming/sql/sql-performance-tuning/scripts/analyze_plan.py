#!/usr/bin/env python3
"""Find the bottlenecks in a PostgreSQL execution plan.

Feed it the JSON output of:
    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <your query>;

It reports the slowest plan nodes by their own time (excluding children), and
flags the usual culprits: sequential scans that throw most rows away, row
estimates that are far off (stale statistics), sorts and hashes spilling to
disk, nested loops with many iterations, lossy bitmap scans and heavy disk
reads. Each finding comes with a concrete next step. No dependencies.

Usage:
    psql -XqAt -c "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT ..." > plan.json
    python analyze_plan.py plan.json
    python analyze_plan.py plan.json --top 10 --json
"""

import argparse
import json
import sys


def load(text):
    data = json.loads(text)
    if isinstance(data, list):
        data = data[0]
    if "Plan" not in data:
        raise ValueError("expected EXPLAIN (FORMAT JSON) output with a top-level 'Plan' key")
    return data


def walk(node, depth=0, parent=None):
    yield node, depth, parent
    for child in node.get("Plans", []):
        yield from walk(child, depth + 1, node)


def label(node):
    parts = [node.get("Node Type", "?")]
    if node.get("Relation Name"):
        parts.append(f"on {node['Relation Name']}")
    if node.get("Index Name"):
        parts.append(f"using {node['Index Name']}")
    return " ".join(parts)


def self_time(node):
    loops = node.get("Actual Loops", 1) or 1
    total = node.get("Actual Total Time", 0) * loops
    children = sum(c.get("Actual Total Time", 0) * (c.get("Actual Loops", 1) or 1) for c in node.get("Plans", [])
                   if c.get("Parent Relationship") != "InitPlan")
    return max(total - children, 0.0)


def analyse(plan, top):
    root = plan["Plan"]
    if "Actual Total Time" not in root:
        raise ValueError("plan has no timing data; run EXPLAIN with ANALYZE")
    total = plan.get("Execution Time") or root["Actual Total Time"]
    nodes = list(walk(root))
    findings = []

    def add(sev, node, title, detail, fix):
        findings.append({"severity": sev, "node": label(node), "title": title, "detail": detail, "fix": fix})

    for node, _, _ in nodes:
        nt = node.get("Node Type", "")
        loops = node.get("Actual Loops", 1) or 1
        actual = node.get("Actual Rows", 0) * loops
        planned = node.get("Plan Rows", 0) * loops
        removed = node.get("Rows Removed by Filter", 0) * loops

        if nt == "Seq Scan" and removed > 10_000 and removed > 9 * max(actual, 1):
            add("high", node, "Sequential scan discards most rows",
                f"read {actual + removed:,} rows, kept {actual:,} ({actual / (actual + removed):.1%}); filter: {node.get('Filter', '?')}",
                "Create an index on the filtered column(s); for multi-column filters put equality columns first.")
        if planned and actual and (actual / planned > 10 or planned / actual > 10) and max(actual, planned) > 1000:
            ratio = actual / planned
            add("medium", node, "Row estimate is far off",
                f"planned {planned:,} rows, got {actual:,} ({ratio:.1f}x)",
                "Run ANALYZE on the table; for correlated columns use CREATE STATISTICS; raise default_statistics_target for skewed data.")
        if node.get("Sort Space Type") == "Disk":
            add("high", node, "Sort spilled to disk",
                f"{node.get('Sort Method', 'sort')} used {node.get('Sort Space Used', '?')} kB on disk; key: {', '.join(node.get('Sort Key', []))}",
                "Increase work_mem for this query (SET LOCAL work_mem), or add an index matching the ORDER BY to avoid the sort.")
        if nt == "Hash" and node.get("Hash Batches", 1) > 1:
            add("medium", node, "Hash table spilled into batches",
                f"{node['Hash Batches']} batches (original {node.get('Original Hash Batches', '?')}), peak memory {node.get('Peak Memory Usage', '?')} kB",
                "Increase work_mem or reduce the rows/columns feeding the hash join.")
        if nt == "Nested Loop":
            inner = node.get("Plans", [])[-1] if node.get("Plans") else None
            if inner and inner.get("Actual Loops", 1) > 1000:
                add("medium", node, "Nested loop with many inner iterations",
                    f"inner side ran {inner['Actual Loops']:,} times ({label(inner)})",
                    "Make sure the inner side uses an index on the join key; if both sides are large a hash join is usually better (check estimates).")
        if node.get("Lossy Heap Blocks", 0) > 0:
            add("low", node, "Lossy bitmap heap scan",
                f"{node['Lossy Heap Blocks']:,} lossy blocks forced rechecks",
                "Increase work_mem so the bitmap stays exact, or use a more selective index.")
        reads = node.get("Shared Read Blocks", 0)
        if reads > 10_000 and reads > 4 * node.get("Shared Hit Blocks", 0):
            add("low", node, "Most pages came from disk",
                f"{reads:,} blocks read vs {node.get('Shared Hit Blocks', 0):,} cache hits (~{reads * 8 / 1024:.0f} MB)",
                "Expect this to be faster when cached; otherwise reduce pages touched (covering index, narrower rows, partition pruning).")

    slow = sorted(((self_time(n), n) for n, _, _ in nodes), key=lambda x: -x[0])[:top]
    hotspots = [{"node": label(n), "self_ms": round(t, 2), "share": round(t / total, 4) if total else 0,
                 "rows": n.get("Actual Rows", 0) * (n.get("Actual Loops", 1) or 1), "loops": n.get("Actual Loops", 1)}
                for t, n in slow]
    order = {"high": 0, "medium": 1, "low": 2}
    return {
        "execution_ms": round(total, 2),
        "planning_ms": plan.get("Planning Time"),
        "hotspots": hotspots,
        "findings": sorted(findings, key=lambda f: order[f["severity"]]),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="EXPLAIN (ANALYZE, FORMAT JSON) output, or - for stdin")
    ap.add_argument("--top", type=int, default=5, help="number of hotspots to show (default 5)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()
    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    try:
        report = analyse(load(text), args.top)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
        return
    planning = f", planning {report['planning_ms']} ms" if report["planning_ms"] is not None else ""
    print(f"Execution {report['execution_ms']} ms{planning}\n\nHotspots (self time):")
    for h in report["hotspots"]:
        print(f"  {h['self_ms']:>10.2f} ms  {h['share']:>6.1%}  {h['node']}  (rows {h['rows']:,}, loops {h['loops']})")
    if not report["findings"]:
        print("\nNo common problems detected.")
    for i, f in enumerate(report["findings"], 1):
        print(f"\n{i}. [{f['severity'].upper()}] {f['title']} - {f['node']}\n   {f['detail']}\n   fix: {f['fix']}")


if __name__ == "__main__":
    main()
