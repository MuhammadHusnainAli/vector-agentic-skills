"""Fixture: idiomatic code that needs no comprehension refactor (never executed)."""
from collections import defaultdict
from itertools import batched, islice


def build_prompts(questions, template):
    return [template.format(q=q.strip()) for q in questions if q.strip()]


def batch_texts(texts, size=64):
    yield from batched(texts, size)


def top_hits(hits, k, min_score):
    return list(islice((h for h in hits if h.score >= min_score), k))


def group_by_doc(chunks):
    by_doc = defaultdict(list)
    for chunk in chunks:
        by_doc[chunk.doc_id].append(chunk)
    return dict(by_doc)


def write_jsonl(records, fh, dumps):
    for rec in records:
        fh.write(dumps(rec) + "\n")


def total_tokens(messages, count_tokens):
    return sum(count_tokens(m["content"]) for m in messages)


def retry_until_ok(calls):
    results = []
    for call in calls:
        try:
            results.append(call())
        except TimeoutError:
            results.append(None)
    return results
