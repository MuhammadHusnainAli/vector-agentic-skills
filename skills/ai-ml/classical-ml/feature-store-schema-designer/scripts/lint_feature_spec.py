#!/usr/bin/env python3
"""Lint a feature-store design spec (JSON, or YAML when PyYAML is installed) before generating code.

The spec describes entities, sources, feature views, features and feature services (see
references/spec-format.md; print an example with gen_feast_repo.py --template). Rules:

  FS001 error    entity without join_keys / feature view referencing an unknown entity or source
  FS002 error    source without timestamp_field (point-in-time joins impossible)
  FS003 error    duplicate feature name inside a view, or duplicate view / entity / source names
  FS004 error    feature without dtype, or a dtype outside the supported set
  FS005 error    feature service references an unknown view or feature
  FS006 warning  ttl missing, or shorter than the source's update cadence (online lookups return nothing)
  FS007 warning  online view without freshness_sla, or freshness_sla looser than ttl
  FS008 warning  names not snake_case, or windowed aggregates without a window suffix (_7d, _24h)
  FS009 warning  feature or view without description / owner
  FS010 warning  likely PII (email, phone, name, address, ssn, dob, ip) without pii: true
  FS011 info     view with more than 50 features (split by source cadence or entity)
  FS012 warning  label-like feature name (churned, is_fraud, target, label, outcome) inside a feature view

Usage:
    python lint_feature_spec.py features.json
    python lint_feature_spec.py features.yaml --json

Exit codes: 0 no errors, 1 errors, 2 read error.
"""

import argparse
import json
import re
import sys

DTYPES = {"int32", "int64", "float32", "float64", "string", "bool", "bytes", "unix_timestamp",
          "array<int64>", "array<float32>", "array<float64>", "array<string>"}
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
CADENCE = {"realtime": 1, "streaming": 1, "minutely": 60, "hourly": 3600, "daily": 86400, "weekly": 604800,
           "monthly": 2_678_400}
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
AGG = re.compile(r"(count|sum|mean|avg|max|min|std|n_|nuniq|distinct|total)", re.I)
WINDOW = re.compile(r"_(\d+)(m|h|d|w|min|hr|days?|weeks?)$|_(lifetime|all_time|prior)$", re.I)
PII = re.compile(r"(email|phone|first_name|last_name|full_name|address|ssn|social_security|dob|birth|passport|"
                 r"ip_address|^ip$|_ip$|card_number|iban)", re.I)
LABELY = re.compile(r"^(churned|is_fraud|fraud|target|label|outcome|y|defaulted|converted)$", re.I)


def seconds(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smhdw])\s*", str(v))
    return float(m.group(1)) * UNITS[m.group(2)] if m else None


def load(path):
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            raise ValueError("YAML spec needs PyYAML (pip install pyyaml), or convert it to JSON")
        return yaml.safe_load(text)
    return json.loads(text)


def lint(spec):
    out = []

    def add(code, sev, where, msg):
        out.append({"code": code, "severity": sev, "where": where, "message": msg})

    ents = {}
    for e in spec.get("entities", []):
        n = e.get("name", "?")
        if n in ents:
            add("FS003", "error", f"entity {n}", "duplicate entity name")
        ents[n] = e
        if not e.get("join_keys"):
            add("FS001", "error", f"entity {n}", "no join_keys")
    srcs = {}
    for s in spec.get("sources", []):
        n = s.get("name", "?")
        if n in srcs:
            add("FS003", "error", f"source {n}", "duplicate source name")
        srcs[n] = s
        if not s.get("timestamp_field"):
            add("FS002", "error", f"source {n}", "no timestamp_field: point-in-time joins and TTL cannot work")
    views = {}
    all_feats = {}
    for v in spec.get("feature_views", []):
        n = v.get("name", "?")
        where = f"view {n}"
        if n in views:
            add("FS003", "error", where, "duplicate feature view name")
        views[n] = v
        for en in v.get("entities", []):
            if en not in ents:
                add("FS001", "error", where, f"unknown entity {en!r}")
        src = srcs.get(v.get("source"))
        if not src:
            add("FS001", "error", where, f"unknown source {v.get('source')!r}")
        if not SNAKE.match(n):
            add("FS008", "warning", where, "view name is not snake_case")
        if not v.get("owner"):
            add("FS009", "warning", where, "no owner")
        if not v.get("description"):
            add("FS009", "warning", where, "no description")
        ttl = seconds(v.get("ttl"))
        if ttl is None:
            add("FS006", "warning", where, "no ttl: stale rows are served forever (or nothing, depending on the store)")
        elif src and CADENCE.get(str(src.get("cadence", "")).lower()) and ttl < CADENCE[src["cadence"].lower()]:
            add("FS006", "warning", where, f"ttl {v['ttl']} is shorter than the source cadence {src['cadence']!r}: "
                "online reads go empty between refreshes")
        if v.get("online"):
            sla = seconds(v.get("freshness_sla"))
            if sla is None:
                add("FS007", "warning", where, "online view without freshness_sla")
            elif ttl is not None and sla > ttl:
                add("FS007", "warning", where, f"freshness_sla {v['freshness_sla']} is looser than ttl {v['ttl']}")
        feats = v.get("features", [])
        if len(feats) > 50:
            add("FS011", "info", where, f"{len(feats)} features: consider splitting by source cadence or entity")
        names = set()
        for f in feats:
            fn = f.get("name", "?")
            fw = f"{n}:{fn}"
            if fn in names:
                add("FS003", "error", fw, "duplicate feature name in view")
            names.add(fn)
            all_feats[fw] = f
            dt = str(f.get("dtype", "")).lower()
            if not dt:
                add("FS004", "error", fw, "no dtype")
            elif dt not in DTYPES:
                add("FS004", "error", fw, f"dtype {dt!r} not in {sorted(DTYPES)}")
            if not SNAKE.match(fn):
                add("FS008", "warning", fw, "feature name is not snake_case")
            elif AGG.search(fn) and not WINDOW.search(fn) and not f.get("window"):
                add("FS008", "warning", fw, "aggregate without a window suffix (_7d, _24h, _lifetime) or window field")
            if not f.get("description"):
                add("FS009", "warning", fw, "no description")
            if PII.search(fn) and not f.get("pii"):
                add("FS010", "warning", fw, "looks like PII: set pii: true and restrict access, or drop it")
            if LABELY.match(fn):
                add("FS012", "warning", fw, "label-like name inside a feature view: labels belong in the training "
                    "spine, not in served features")
    for svc in spec.get("feature_services", []):
        sn = svc.get("name", "?")
        for ref in svc.get("features", []):
            view, _, feat = ref.partition(":")
            if view not in views:
                add("FS005", "error", f"service {sn}", f"unknown view {view!r}")
            elif feat and feat != "*" and f"{view}:{feat}" not in all_feats:
                add("FS005", "error", f"service {sn}", f"unknown feature {ref!r}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Lint a feature store spec.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="JSON/YAML spec or - for stdin (JSON)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        spec = load(a.spec)
        if not isinstance(spec, dict):
            raise ValueError("spec must be a mapping")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = lint(spec)
    errors = sum(f["severity"] == "error" for f in findings)
    if a.json:
        print(json.dumps({"errors": errors, "findings": findings}, indent=2))
    else:
        for f in findings:
            print(f"{f['code']} [{f['severity']}] {f['where']}: {f['message']}")
        nv = len(spec.get("feature_views", []))
        nf = sum(len(v.get("features", [])) for v in spec.get("feature_views", []))
        print(f"\n{nv} view(s), {nf} feature(s): {len(findings)} finding(s), {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
