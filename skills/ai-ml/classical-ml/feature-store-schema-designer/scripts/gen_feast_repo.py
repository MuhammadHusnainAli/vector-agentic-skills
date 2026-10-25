#!/usr/bin/env python3
"""Generate a Feast feature repository (definitions + feature_store.yaml) from a feature spec.

Input: the JSON (or YAML with PyYAML) spec described in references/spec-format.md: entities,
sources (file | bigquery | snowflake | redshift), feature views (entities, source, ttl, online,
features with dtypes) and feature services. Output files:
  features.py           Entity / Source / FeatureView / FeatureService definitions (Feast >= 0.30 API)
  feature_store.yaml    a local provider config (SQLite online store, file offline store) to start from

Run `python lint_feature_spec.py spec.json` first; this generator refuses specs with lint errors
unless --force.

Usage:
    python gen_feast_repo.py --template > spec.json
    python gen_feast_repo.py spec.json --out feature_repo/
    python gen_feast_repo.py spec.json --stdout            # print features.py only

Exit codes: 0 generated, 1 spec has lint errors (without --force), 2 usage or read error.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint_feature_spec import lint, load, seconds  # noqa: E402

TEMPLATE = {
    "project": "churn_features",
    "entities": [{"name": "customer", "join_keys": ["customer_id"], "description": "A subscriber account"}],
    "sources": [
        {"name": "customer_daily_activity", "type": "file", "path": "data/customer_daily_activity.parquet",
         "timestamp_field": "event_ts", "created_timestamp_field": "created_ts", "cadence": "daily"},
        {"name": "customer_profile", "type": "file", "path": "data/customer_profile.parquet",
         "timestamp_field": "updated_ts", "cadence": "daily"},
    ],
    "feature_views": [
        {"name": "customer_activity", "entities": ["customer"], "source": "customer_daily_activity", "ttl": "2d",
         "online": True, "freshness_sla": "1d", "owner": "retention-ds@example.com",
         "description": "Rolling engagement aggregates, recomputed nightly",
         "features": [
             {"name": "logins_7d", "dtype": "int64", "description": "Logins in the 7 days before event_ts"},
             {"name": "logins_30d", "dtype": "int64", "description": "Logins in the 30 days before event_ts"},
             {"name": "spend_30d", "dtype": "float64", "description": "Spend in the 30 days before event_ts"},
             {"name": "days_since_last_login", "dtype": "float32", "description": "Days from last login to event_ts"},
         ]},
        {"name": "customer_profile", "entities": ["customer"], "source": "customer_profile", "ttl": "400d",
         "online": True, "freshness_sla": "1d", "owner": "retention-ds@example.com",
         "description": "Slowly changing account attributes",
         "features": [
             {"name": "plan", "dtype": "string", "description": "Current plan as of updated_ts"},
             {"name": "tenure_days", "dtype": "int64", "description": "Days since signup as of updated_ts"},
         ]},
    ],
    "feature_services": [{"name": "churn_model_v1", "description": "Features for the weekly churn model",
                          "features": ["customer_activity:*", "customer_profile:plan", "customer_profile:tenure_days"]}],
}

FEAST_TYPES = {"int32": "Int32", "int64": "Int64", "float32": "Float32", "float64": "Float64", "string": "String",
               "bool": "Bool", "bytes": "Bytes", "unix_timestamp": "UnixTimestamp", "array<int64>": "Array(Int64)",
               "array<float32>": "Array(Float32)", "array<float64>": "Array(Float64)", "array<string>": "Array(String)"}


def ident(name):
    return re.sub(r"\W", "_", name)


def timedelta_expr(v):
    s = seconds(v)
    if s is None:
        return "timedelta(0)"
    if s % 86400 == 0:
        return f"timedelta(days={int(s // 86400)})"
    if s % 3600 == 0:
        return f"timedelta(hours={int(s // 3600)})"
    return f"timedelta(seconds={int(s)})"


def source_code(s):
    var = f"{ident(s['name'])}_source"
    common = f'name="{s["name"]}", timestamp_field="{s["timestamp_field"]}"'
    if s.get("created_timestamp_field"):
        common += f', created_timestamp_column="{s["created_timestamp_field"]}"'
    kind = s.get("type", "file")
    if kind == "bigquery":
        return var, "BigQuerySource", f'{var} = BigQuerySource({common}, table="{s["table"]}")'
    if kind == "snowflake":
        db, schema, table = s["table"].split(".")
        return var, "SnowflakeSource", (f'{var} = SnowflakeSource({common}, database="{db}", schema="{schema}", '
                                        f'table="{table}")')
    if kind == "redshift":
        schema, table = s["table"].split(".")
        return var, "RedshiftSource", f'{var} = RedshiftSource({common}, schema="{schema}", table="{table}")'
    return var, "FileSource", f'{var} = FileSource({common}, path="{s["path"]}")'


def generate(spec):
    imports = {"Entity", "FeatureView", "Field", "FeatureService"}
    types = set()
    body = []
    for e in spec["entities"]:
        keys = ", ".join(f'"{k}"' for k in e["join_keys"])
        desc = json.dumps(e.get("description", ""))
        body.append(f'{ident(e["name"])} = Entity(name="{e["name"]}", join_keys=[{keys}], description={desc})')
    body.append("")
    src_vars = {}
    for s in spec["sources"]:
        var, cls, code = source_code(s)
        imports.add(cls)
        src_vars[s["name"]] = var
        body.append(code)
    body.append("")
    view_vars = {}
    for v in spec["feature_views"]:
        var = f"{ident(v['name'])}_fv"
        view_vars[v["name"]] = var
        fields = []
        for f in v["features"]:
            t = FEAST_TYPES[f["dtype"].lower()]
            types.update(re.findall(r"[A-Z]\w+", t))
            fields.append(f'        Field(name="{f["name"]}", dtype={t}, description={json.dumps(f.get("description", ""))}),')
        tags = {"owner": v.get("owner", ""), "freshness_sla": str(v.get("freshness_sla", ""))}
        body += [f"{var} = FeatureView(",
                 f'    name="{v["name"]}",',
                 f'    entities=[{", ".join(ident(e) for e in v["entities"])}],',
                 f"    ttl={timedelta_expr(v.get('ttl'))},",
                 "    schema=[", *fields, "    ],",
                 f"    online={bool(v.get('online', True))},",
                 f"    source={src_vars[v['source']]},",
                 f"    description={json.dumps(v.get('description', ''))},",
                 f"    tags={json.dumps(tags)},",
                 ")", ""]
    for svc in spec.get("feature_services", []):
        parts = {}
        for ref in svc["features"]:
            view, _, feat = ref.partition(":")
            parts.setdefault(view, [])
            if feat and feat != "*":
                parts[view].append(feat)
            else:
                parts[view] = None if parts[view] == [] else parts[view]
        refs = []
        for view, feats in parts.items():
            refs.append(view_vars[view] if not feats else f"{view_vars[view]}[{json.dumps(feats)}]")
        body.append(f'{ident(svc["name"])} = FeatureService(name="{svc["name"]}", features=[{", ".join(refs)}], '
                    f'description={json.dumps(svc.get("description", ""))})')
    head = [f'"""Feast definitions for project {spec.get("project", "features")!r}. Generated by gen_feast_repo.py."""',
            "from datetime import timedelta", "",
            f"from feast import {', '.join(sorted(imports))}",
            f"from feast.types import {', '.join(sorted(types))}", "", ""]
    return "\n".join(head + body).rstrip() + "\n"


def store_yaml(spec):
    return (f"project: {spec.get('project', 'features')}\nregistry: data/registry.db\nprovider: local\n"
            "online_store:\n    type: sqlite\n    path: data/online_store.db\noffline_store:\n    type: file\n"
            "entity_key_serialization_version: 3\n")


def main():
    ap = argparse.ArgumentParser(description="Generate a Feast feature repo from a spec.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--out", help="directory to write features.py and feature_store.yaml")
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--force", action="store_true", help="generate even with lint errors")
    a = ap.parse_args()
    if a.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if not a.spec or not (a.out or a.stdout):
        print("error: give a spec and --out DIR or --stdout (or --template)", file=sys.stderr)
        return 2
    try:
        spec = load(a.spec)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errors = [f for f in lint(spec) if f["severity"] == "error"]
    if errors and not a.force:
        for f in errors:
            print(f"{f['code']} {f['where']}: {f['message']}", file=sys.stderr)
        print(f"{len(errors)} lint error(s); fix them or pass --force", file=sys.stderr)
        return 1
    code = generate(spec)
    if a.stdout:
        sys.stdout.write(code)
        return 0
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "features.py"), "w", encoding="utf-8") as f:
        f.write(code)
    with open(os.path.join(a.out, "feature_store.yaml"), "w", encoding="utf-8") as f:
        f.write(store_yaml(spec))
    print(f"wrote {a.out}/features.py and {a.out}/feature_store.yaml ({len(spec['feature_views'])} views)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
