#!/usr/bin/env python3
"""Smoke-test every helper script that ships inside a skill.

1. Every skills/*/*/*/scripts/*.py must run `--help` successfully.
2. Each script has at least one real case below: it runs against the
   fixtures in tests/fixtures and must exit with the expected code and print
   the expected text.

Usage:
    python scripts/test_skill_scripts.py          # run everything
    python scripts/test_skill_scripts.py -k sql   # only cases whose name contains "sql"

Scripts that need optional packages (sqlglot) are tested with and without them:
without the package they must fail cleanly with an install hint.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "tests" / "fixtures"
SQL = ROOT / "skills/programming/sql"
XL = ROOT / "skills/productivity/excel"
PY = ROOT / "skills/programming/python"
HAS_SQLGLOT = importlib.util.find_spec("sqlglot") is not None

# (name, script, args, expected exit code, text expected in stdout+stderr)
CASES = [
    ("plan_joins: bridge tables", SQL / "sql-query-writer/scripts/plan_joins.py",
     [FX / "schema.sql", "--tables", "customers", "products"], 0, "JOIN order_items AS oi"),
    ("plan_joins: no path", SQL / "sql-query-writer/scripts/plan_joins.py",
     [FX / "schema.sql", "--tables", "customers", "audit_log"], 1, "no foreign-key path"),
    ("check_sql: catches errors", SQL / "sql-syntax-checker/scripts/check_sql.py",
     [FX / "bad.sql"], 1, "Trailing comma before FROM"),
    ("check_sql: clean query", SQL / "sql-syntax-checker/scripts/check_sql.py",
     ["-"], 0, "Status: VALID", "SELECT id FROM users WHERE active = 1"),
    ("outline_query: execution order", SQL / "sql-query-explainer/scripts/outline_query.py",
     [FX / "query.sql"], 0, "LEFT OUTER JOIN: segments s USING (customer_id)"),
    ("find_antipatterns: slow query", SQL / "sql-optimizer/scripts/find_antipatterns.py",
     [FX / "slow.sql", "--strict"], 1, "NOT IN with a subquery"),
    ("analyze_plan: spills and scans", SQL / "sql-performance-tuning/scripts/analyze_plan.py",
     [FX / "plan.json"], 0, "Sort spilled to disk"),
    ("diagnose_error: postgres group by", SQL / "sql-debugger/scripts/diagnose_error.py",
     ['ERROR: column "o.total" must appear in the GROUP BY clause'], 0, "Dialect: PostgreSQL"),
    ("diagnose_error: oracle code", SQL / "sql-debugger/scripts/diagnose_error.py",
     ["ORA-00904: invalid identifier"], 0, "unknown-column"),
    ("sql_sandbox: running total", SQL / "sql-window-functions/scripts/sql_sandbox.py",
     ["--demo", "--query", "SELECT SUM(revenue) OVER (ORDER BY month, region ROWS UNBOUNDED PRECEDING) AS r "
      "FROM sales ORDER BY r DESC LIMIT 1"], 0, "11300"),
    ("analytics_sql: funnel runs in sqlite", SQL / "sql-analytics/scripts/analytics_sql.py",
     ["funnel", "--table", "events", "--user", "user_id", "--ts", "created_at", "--event-col", "event_name",
      "--steps", "signup", "activate", "purchase", "--dialect", "sqlite"], 0, "pct_of_previous"),
    ("date_ranges: literal mtd", SQL / "sql-reporting/scripts/date_ranges.py",
     ["mtd", "--literal", "--as-of", "2026-10-20"], 0, "created_at >= DATE '2026-10-01'"),
    ("profile_data: csv gate", SQL / "sql-data-quality/scripts/profile_data.py",
     ["csv", FX / "customers.csv", "--key", "id", "--fail-on", "duplicate_keys=0"], 1, "2 duplicate keys"),
    ("profile_data: sql mode", SQL / "sql-data-quality/scripts/profile_data.py",
     ["sql", "--table", "t", "--columns", "a", "--key", "a"], 0, "HAVING COUNT(*) > 1"),
    ("check_formula: unbalanced", XL / "excel-formulas/scripts/check_formula.py",
     ["=SUM(A1:A10"], 1, "unclosed '('"),
    ("check_compat: version", XL / "excel-advanced-formulas/scripts/check_compat.py",
     ["--target", "2019", "=XLOOKUP(A1,B:B,C:C)"], 1, "Excel 2021+"),
    ("inspect_workbook: structure", XL / "excel-fundamentals/scripts/inspect_workbook.py",
     [FX / "test.xlsx"], 0, "table Sales A1:D4"),
    ("review_idioms: ai pipeline risks", PY / "python-idiomatic-code-reviewer/scripts/review_idioms.py",
     [FX / "python/idiom_ai_pipeline.py", "--strict"], 1, "PY037 [high] time.sleep() in async def"),
    ("review_idioms: general idioms", PY / "python-idiomatic-code-reviewer/scripts/review_idioms.py",
     [FX / "python/idiom_general.py", "--strict"], 1, "PY001 [high] mutable default `[]` in add_doc()"),
    ("review_idioms: clean file", PY / "python-idiomatic-code-reviewer/scripts/review_idioms.py",
     [FX / "python/idiom_clean.py", "--strict"], 0, "No findings in 1 file(s)"),
    ("review_idioms: stdin secret", PY / "python-idiomatic-code-reviewer/scripts/review_idioms.py",
     ["-", "--strict", "--select", "PY036"], 1, "PY036 [high]", 'OPENAI_API_KEY = "sk-proj-abc123def456ghi789jkl012mno345"\n'),
    ("find_comprehension_candidates: walrus loop rewrite", PY / "python-comprehension-refactorer/scripts/find_comprehension_candidates.py",
     [FX / "python/compr_rag_pipeline.py", "--strict"], 1, "answers = [parsed for raw in raw_outputs if (parsed := parse(raw)) is not None]"),
    ("find_comprehension_candidates: counter loop", PY / "python-comprehension-refactorer/scripts/find_comprehension_candidates.py",
     [FX / "python/compr_rag_pipeline.py", "--strict"], 1, "counts = Counter(tokens)"),
    ("find_comprehension_candidates: clean file", PY / "python-comprehension-refactorer/scripts/find_comprehension_candidates.py",
     [FX / "python/compr_clean.py", "--strict"], 0, "no comprehension refactors suggested"),
    ("find_comprehension_candidates: side-effect comprehension on stdin", PY / "python-comprehension-refactorer/scripts/find_comprehension_candidates.py",
     ["-", "--strict"], 1, "side-effect-comprehension", "xs = [1]\n[print(x) for x in xs]\n"),
    ("annotation_audit: legacy typing rewrites", PY / "python-type-hints-annotator/scripts/annotation_audit.py",
     [FX / "python/hints_legacy_typing.py", "--strict"], 1, "fix: list[dict[str, Any]] | None"),
    ("annotation_audit: coverage gate fails", PY / "python-type-hints-annotator/scripts/annotation_audit.py",
     [FX / "python/hints_untyped_llm_client.py", "--min-coverage", "50"], 1, "Coverage gate: FAIL (overall 0.0%, minimum 50.0%)"),
    ("annotation_audit: infers return types", PY / "python-type-hints-annotator/scripts/annotation_audit.py",
     [FX / "python/hints_untyped_llm_client.py", "--strict"], 1, "return         -> Iterator[str]"),
    ("annotation_audit: clean 3.12 module", PY / "python-type-hints-annotator/scripts/annotation_audit.py",
     [FX / "python/hints_typed_clean.py", "--target-version", "3.12", "--strict", "--min-coverage", "100"], 0, "Coverage gate: PASS"),
    ("annotation_audit: stdin implicit optional", PY / "python-type-hints-annotator/scripts/annotation_audit.py",
     ["-", "--strict"], 1, "fix: stop: list[str] | None = None", "def f(stop: list[str] = None) -> None:\n    pass\n"),
    ("to_dataclass: class mode converts boilerplate", PY / "python-dataclass-converter/scripts/to_dataclass.py",
     ["class", FX / "python/dc_legacy_models.py", "--strict"], 1, "stop: list = field(default_factory=list, hash=False)"),
    ("to_dataclass: json mode nested + aliases", PY / "python-dataclass-converter/scripts/to_dataclass.py",
     ["json", FX / "python/dc_llm_response.json", "--name", "ChatCompletion"], 0, 'x_request_id: str = field(metadata={"json_key": "x-request-id"})'),
    ("to_dataclass: pydantic style", PY / "python-dataclass-converter/scripts/to_dataclass.py",
     ["json", FX / "python/dc_llm_response.json", "--style", "pydantic"], 0, 'latency_ms: float = Field(alias="latencyMs")'),
    ("to_dataclass: stdin mutable default", PY / "python-dataclass-converter/scripts/to_dataclass.py",
     ["class", "-", "--strict"], 1, "DC001", "class A:\n    def __init__(self, x, tags=[]):\n        self.x = x\n        self.tags = tags\n"),
    ("to_dataclass: bad json exits 2", PY / "python-dataclass-converter/scripts/to_dataclass.py",
     ["json", "-"], 2, "cannot parse", "{bad"),
    ("audit_exceptions: smells in llm client", PY / "python-exception-handling-designer/scripts/audit_exceptions.py",
     [FX / "python/exc_bad_handlers.py", "--strict"], 1, "EXC008 [high] cancellation-swallowed"),
    ("audit_exceptions: clean handlers", PY / "python-exception-handling-designer/scripts/audit_exceptions.py",
     [FX / "python/exc_good_handlers.py", "--strict"], 0, "No exception-handling issues found"),
    ("audit_exceptions: stdin swallow", PY / "python-exception-handling-designer/scripts/audit_exceptions.py",
     ["-", "--strict"], 1, "broad-except-swallow", "try:\n    x()\nexcept Exception:\n    pass\n"),
    ("scaffold_exceptions: json spec", PY / "python-exception-handling-designer/scripts/scaffold_exceptions.py",
     ["--spec", FX / "python/exc_errors_spec.json"], 0, "class RateLimitError(ProviderError):"),
    ("scaffold_exceptions: unknown parent", PY / "python-exception-handling-designer/scripts/scaffold_exceptions.py",
     ["--spec", "-"], 2, "unknown parent 'MissingParent'", '{"package": "kit", "errors": ["ChildError(MissingParent)"]}'),
    ("ctx_tool: leaky pipeline", PY / "python-context-manager-writer/scripts/ctx_tool.py",
     ["leaks", FX / "python/ctx_leaky_pipeline.py", "--strict"], 1, "cleanup after `yield` in `vector_transaction`"),
    ("ctx_tool: clean pipeline", PY / "python-context-manager-writer/scripts/ctx_tool.py",
     ["leaks", FX / "python/ctx_clean_pipeline.py", "--strict"], 0, "No resource-handling issues found"),
    ("ctx_tool: acquire without finally (stdin)", PY / "python-context-manager-writer/scripts/ctx_tool.py",
     ["leaks", "-", "--strict"], 1, "CTX002 acquire-without-finally",
     "import threading\nlock = threading.Lock()\ndef f(d):\n    lock.acquire()\n    d['k'] = 1\n    lock.release()\n"),
    ("ctx_tool: atomic-write recipe", PY / "python-context-manager-writer/scripts/ctx_tool.py",
     ["scaffold", "--recipe", "atomic-write"], 0, "os.replace(tmp_name, target)"),
    ("explain_concepts: beginner pitfalls", PY / "python-beginner-concept-tutor/scripts/explain_concepts.py",
     ["concepts", FX / "python/tutor_beginner.py", "--strict"], 1, "none-returning-method"),
    ("explain_concepts: above learner level", PY / "python-beginner-concept-tutor/scripts/explain_concepts.py",
     ["concepts", FX / "python/tutor_advanced.py", "--max-level", "2", "--strict"], 1, "walrus operator (:=) (L4"),
    ("explain_concepts: trace shows aliasing", PY / "python-beginner-concept-tutor/scripts/explain_concepts.py",
     ["trace", FX / "python/tutor_trace.py", "--strict"], 1, "(same object as prompt_parts)"),
    ("explain_concepts: trace syntax error", PY / "python-beginner-concept-tutor/scripts/explain_concepts.py",
     ["trace", FX / "python/tutor_syntax_error.py"], 2, "expected ':'"),
    ("explain_concepts: trace step limit", PY / "python-beginner-concept-tutor/scripts/explain_concepts.py",
     ["trace", "-", "--max-steps", "20", "--strict"], 1, "stopped after 20 steps", "n = 0\nwhile n < 3:\n    print(n)\n"),
]
if HAS_SQLGLOT:
    CASES += [("translate_sql: tsql to postgres", SQL / "sql-dialect-translator/scripts/translate_sql.py",
               ["-", "--from", "tsql", "--to", "postgres"], 0, "LIMIT 5", "SELECT TOP 5 name FROM users")]
else:
    CASES += [("translate_sql: missing sqlglot hint", SQL / "sql-dialect-translator/scripts/translate_sql.py",
               ["-", "--from", "tsql", "--to", "postgres"], 2, "pip install sqlglot", "SELECT 1")]


def run(script, args, stdin=None):
    p = subprocess.run([sys.executable, str(script), *map(str, args)], input=stdin, capture_output=True,
                       text=True, cwd=ROOT, timeout=60)
    return p.returncode, p.stdout + p.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", help="only run cases whose name contains this text")
    args = ap.parse_args()

    failures = 0
    scripts = sorted(ROOT.glob("skills/*/*/*/scripts/*.py"))
    covered = {c[1] for c in CASES}
    for s in scripts:
        if args.k and args.k not in str(s):
            continue
        code, out = run(s, ["--help"])
        ok = code == 0 and "usage" in out.lower()
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} --help {s.relative_to(ROOT)}")
        if s not in covered:
            failures += 1
            print(f"FAIL no test case for {s.relative_to(ROOT)}; add one to CASES")

    for name, script, argv, want_code, want_text, *stdin in CASES:
        if args.k and args.k not in name:
            continue
        code, out = run(script, argv, stdin[0] if stdin else None)
        ok = code == want_code and want_text in out
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        if not ok:
            print(f"     expected exit {want_code} and {want_text!r}; got exit {code}:\n"
                  + "\n".join("     | " + line for line in out.strip().splitlines()[:15]))

    print(f"\n{'All script tests passed.' if not failures else f'{failures} failure(s).'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
