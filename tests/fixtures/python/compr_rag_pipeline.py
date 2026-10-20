"""Fixture: loops and comprehensions from a small RAG pipeline (never executed)."""
import logging

log = logging.getLogger(__name__)
TEMPLATE = "Answer using the context.\n\nQuestion: {q}"


def build_prompts(questions):
    prompts = []
    for q in questions:
        if q.strip():
            prompts.append(TEMPLATE.format(q=q.strip()))
    return prompts


def keep_relevant(hits, min_score):
    relevant = []
    for hit in hits:
        if hit.score < min_score:
            continue
        relevant.append(hit.text)
    return relevant


def embeddings_by_id(records):
    vectors: dict[str, list[float]] = {}
    for rec in records:
        vectors[rec["id"]] = rec["embedding"]
    return vectors


def flatten_tool_calls(responses):
    calls = []
    for resp in responses:
        for choice in resp.choices:
            calls.extend(choice.message.tool_calls or [])
    return calls


def unique_sources(chunks):
    sources = set()
    for c in chunks:
        sources.add(c.metadata["source"])
    return sources


def labels(scores, threshold):
    out = []
    for s in scores:
        if s >= threshold:
            out.append("relevant")
        else:
            out.append("irrelevant")
    return out


def parsed_answers(raw_outputs, parse):
    answers = []
    for raw in raw_outputs:
        parsed = parse(raw)
        if parsed is not None:
            answers.append(parsed)
    return answers


def token_counts(tokens):
    counts = {}
    for tok in tokens:
        counts[tok] = counts.get(tok, 0) + 1
    return counts


def group_by_doc(chunks):
    by_doc = {}
    for chunk in chunks:
        by_doc.setdefault(chunk.doc_id, []).append(chunk)
    return by_doc


def total_tokens(messages, count_tokens):
    total = sum([count_tokens(m["content"]) for m in messages])
    has_tool = any([m["role"] == "tool" for m in messages])
    longest = max(list(len(m["content"]) for m in messages))
    return total, has_tool, longest


def misc(docs, mapping, hits):
    copies = [d for d in docs]
    same = {k: v for k, v in mapping.items()}
    n_long = len([d for d in docs if len(d) > 1000])
    best = [h for h in hits if h.score > 0.9][0]
    ids = list(map(lambda h: h.id, hits))
    texts = list([d.strip() for d in docs])
    return copies, same, n_long, best, ids, texts


def log_everything(chunks):
    [log.info("chunk %s", c.id) for c in chunks]


def too_clever(corpora):
    return [tok.lower() for corpus in corpora for doc in corpus for sent in doc.sents for tok in sent if tok.is_alpha if not tok.is_stop if len(tok) > 2]


def loop_var_used_later(items):
    names = []
    for item in items:
        names.append(item.name)
    print("last item:", item)
    return names


def not_a_candidate(items):
    out = []
    for item in items:
        out.append(item)
        print(item)
    return out


def all_chunk_texts(docs, splitter):
    texts = []
    for doc in docs:
        texts.extend(splitter.split(doc.page_content))
    return texts


def route(scores):
    tiers = []
    for s in scores:
        if s > 0.8:
            tiers.append("high")
        elif s > 0.5:
            tiers.append("mid")
        else:
            tiers.append("low")
    return tiers


async def embed_stream(batches, client):
    vectors = []
    async for batch in batches:
        vectors.append(await client.embed(batch))
    return vectors


class PromptLibrary:
    names = ["qa", "summarise"]
    templates = {}
    for name in names:
        templates[name] = name.upper()


def count_with_guard(tokens):
    freq = {}
    for t in tokens:
        if t not in freq:
            freq[t] = 0
        freq[t] += 1
    return freq


def nested_too_deep(batches):
    return [[[t for t in s] for s in b] for b in batches]
