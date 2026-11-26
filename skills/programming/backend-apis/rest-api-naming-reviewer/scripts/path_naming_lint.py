#!/usr/bin/env python3
"""Review REST naming across a whole API: paths, path parameters, query parameters and property names.

Input: an OpenAPI 3.x file (JSON, or YAML with PyYAML), or a text file of routes, one per line ("GET /users/{id}").

Checks:
  NM001 warn  verb in a path segment (/getUsers, /users/delete, /createOrder); use methods or an action sub-resource
  NM002 warn  segment casing differs from the API's dominant style (kebab-case or snake_case)
  NM003 warn  uppercase letters in a path segment
  NM004 warn  singular collection followed by an id (/user/{id}) while the API uses plural collections
  NM005 warn  trailing slash or file extension (/users/, /users.json)
  NM006 warn  nesting deeper than --max-depth resource levels (/a/{}/b/{}/c/{}/d)
  NM007 warn  path parameters for the same resource named differently ({id}, {userId}, {user_id})
  NM008 warn  mixed casing styles in query parameters or schema property names
  NM009 warn  more than one version prefix style (/v1 and /api/v2)
  NM010 info  collection name that is not a noun-like plural (ends in -ing, -ed)

Usage:
    python path_naming_lint.py openapi.yaml
    python path_naming_lint.py routes.txt --max-depth 2 --json

Exit codes: 0 no warnings, 1 warnings, 2 unreadable input.
"""

import argparse
import collections
import json
import re
import sys

VERBS = {"get", "fetch", "list", "create", "add", "insert", "update", "edit", "modify", "delete", "remove", "set",
         "do", "make", "save", "retrieve", "find", "search", "post", "put", "patch", "change", "process", "handle"}
METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def style(word):
    if "-" in word and word.lower() == word:
        return "kebab-case"
    if "_" in word and word.lower() == word:
        return "snake_case"
    if re.search(r"[a-z][A-Z]", word) and word[0].islower():
        return "camelCase"
    if re.search(r"[a-z][A-Z]", word) and word[0].isupper():
        return "PascalCase"
    return None          # single lowercase word: compatible with any style


def load(path):
    text = open(path, encoding="utf-8").read()
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = None
        if re.search(r"^\s*(openapi|swagger)\s*:", text, re.M):
            try:
                import yaml
            except ImportError:
                raise ValueError("YAML spec needs PyYAML (pip install pyyaml)")
            doc = yaml.safe_load(text)
    if isinstance(doc, dict) and "paths" in doc:
        routes, queries, props = [], [], []
        for p, item in doc["paths"].items():
            for m in METHODS:
                if isinstance(item, dict) and isinstance(item.get(m), dict):
                    routes.append((m.upper(), p))
                    for prm in (item.get("parameters") or []) + (item[m].get("parameters") or []):
                        if isinstance(prm, dict) and prm.get("in") == "query":
                            queries.append(prm.get("name", ""))
        def walk(node):
            if isinstance(node, dict):
                for k, v in (node.get("properties") or {}).items():
                    props.append(k)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(doc.get("components") or {})
        return routes, queries, props
    routes = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        routes.append((parts[0].upper(), parts[1]) if len(parts) > 1 else ("ANY", parts[0]))
    if not routes:
        raise ValueError("no routes found")
    return routes, [], []


def lint(routes, queries, props, max_depth):
    found = []
    add = lambda code, sev, where, msg: found.append({"code": code, "severity": sev, "where": where, "message": msg})
    paths = sorted({p for _, p in routes})
    segs = [s for p in paths for s in p.strip("/").split("/") if s and not s.startswith("{")]
    styles = collections.Counter(st for s in segs if (st := style(s.split(":")[0])) in ("kebab-case", "snake_case"))
    dominant = styles.most_common(1)[0][0] if styles else "kebab-case"   # camel/Pascal are reported as NM003
    collections_ = [s for p in paths for s, n in zip(p.strip("/").split("/"), p.strip("/").split("/")[1:] + [""]) if n.startswith("{")]
    plural = sum(c.endswith("s") for c in collections_) >= len(collections_) / 2 if collections_ else True
    version_styles, param_names = set(), collections.defaultdict(set)
    for p in paths:
        parts = [s for s in p.split("/") if s]
        if p.endswith("/") and p != "/":
            add("NM005", "warn", p, "trailing slash")
        if parts and re.search(r"\.(json|xml|html)$", parts[-1]):
            add("NM005", "warn", p, "file extension in path; use Accept headers")
        depth = sum(1 for s in parts if s.startswith("{"))
        if depth > max_depth:
            add("NM006", "warn", p, f"{depth} nested resource levels; flatten with top-level resources and filters")
        for i, s in enumerate(parts):
            if re.fullmatch(r"v\d+", s):
                version_styles.add("/".join(parts[:i + 1]))
                continue
            if s.startswith("{"):
                prev = parts[i - 1] if i else ""
                param_names[prev.rstrip("s")].add(re.match(r"\{([^}]+)\}", s).group(1))
                continue
            base = s.split(":")[0]
            words = [w.lower() for w in re.split(r"[-_]|(?<=[a-z])(?=[A-Z])", base) if w]
            if words and words[0] in VERBS and ":" not in s:
                add("NM001", "warn", p, f"verb '{words[0]}' in segment '{s}'; use the HTTP method or an action sub-resource (POST /orders/{{id}}:cancel)")
            st = style(base)
            if any(c.isupper() for c in base):
                add("NM003", "warn", p, f"uppercase in segment '{s}'")
            if st in ("kebab-case", "snake_case") and st != dominant:
                add("NM002", "warn", p, f"segment '{s}' is {st}; the API mostly uses {dominant}")
            nxt = parts[i + 1] if i + 1 < len(parts) else ""
            if nxt.startswith("{") and plural and not base.endswith("s") and base not in ("me", "self"):
                add("NM004", "warn", p, f"singular collection '{s}'; use '{s}s' like other collections")
            if re.search(r"(ing|ed)$", base) and nxt.startswith("{"):
                add("NM010", "info", p, f"collection '{s}' is not a noun")
    for resource, names in param_names.items():
        if len(names) > 1:
            add("NM007", "warn", f"/{resource}s/{{...}}", f"same resource uses parameter names {sorted(names)}; pick one")
    prefixes = {re.sub(r"v\d+$", "vN", v) for v in version_styles}
    if len(prefixes) > 1:
        add("NM009", "warn", "versions", f"version prefixes differ: {sorted(prefixes)}")
    for label, names in (("query parameters", queries), ("properties", props)):
        st = collections.Counter(s for n in names if (s := style(n)))
        if len(st) > 1:
            add("NM008", "warn", label, "mixed casing: " + ", ".join(f"{k} x{v}" for k, v in st.most_common()))
    return found, dominant


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", help="OpenAPI file or routes text file")
    ap.add_argument("--max-depth", type=int, default=2, help="max nested resource levels (default 2)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        routes, queries, props = load(a.input)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    found, dominant = lint(routes, queries, props, a.max_depth)
    found.sort(key=lambda f: (f["severity"] != "warn", f["code"], f["where"]))
    if a.json:
        print(json.dumps({"dominant_style": dominant, "findings": found}, indent=2))
    else:
        for f in found:
            print(f"{f['code']} [{f['severity']}] {f['where']}: {f['message']}")
        w = sum(f["severity"] == "warn" for f in found)
        print(f"\n{len({p for _, p in routes})} paths, dominant segment style {dominant}: {w} warning(s), {len(found) - w} info")
    return 1 if any(f["severity"] == "warn" for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
