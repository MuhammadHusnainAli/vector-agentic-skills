"""Fixture: an LLM client wrapper with every exception-handling smell audit_exceptions.py detects.

Not meant to run; only parsed by the auditor.
"""
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


class RateLimitError(ProviderError):
    pass


def load_prompt(path):
    try:
        with open(path) as fh:
            return fh.read()
    except:  # EXC001 bare except
        return ""


def embed_batch(client, texts):
    try:
        return client.embed(texts)
    except Exception:  # EXC003 swallowed
        pass


async def stream_tokens(client, prompt):
    try:
        async for tok in client.stream(prompt):
            yield tok
    except asyncio.CancelledError:  # EXC008 not re-raised
        logger.info("stream cancelled")


def call_model(client, messages):
    try:
        return client.chat(messages)
    except ProviderError as err:
        raise RuntimeError("model call failed")  # EXC004 no from
    except RateLimitError:  # EXC006 unreachable: subclass after base
        return None


def parse_tool_args(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("bad tool arguments: " + str(e))  # EXC013 stringified


def rerank(docs, top_k):
    assert top_k > 0  # EXC009 assert validating input
    if not docs:
        raise Exception("no documents")  # EXC005 generic
    return docs[:top_k]


def save_trace(trace, path):
    try:
        with open(path, "w") as fh:
            fh.write(trace)
    finally:
        return path  # EXC007 return in finally


def index_chunks(store, chunks):
    for chunk in chunks:
        try:
            store.upsert(chunk)
        except ConnectionError as e:
            logger.error(e)  # EXC010 loses traceback


def shutdown(worker):
    try:
        worker.join()
    except BaseException:  # EXC002 no re-raise
        worker.kill()


def tokenize(tokenizer, text):
    try:
        return tokenizer.encode(text)
    except ValueError:
        raise  # EXC012 useless


def pipeline(cfg, client, store, docs):
    try:  # EXC011 too large (12 statements)
        a = cfg["model"]
        b = cfg["temperature"]
        c = cfg["max_tokens"]
        d = [x.strip() for x in docs]
        e = client.embed(d)
        f = store.upsert(e)
        g = client.chat(a)
        h = g.text
        i = h.upper()
        j = len(i)
        k = j + 1
        return k
    except KeyError as missing:
        raise ValueError(f"missing config key {missing}") from missing


def parse_model_json(raw):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as err:  # EXC014 redundant tuple member
        raise ProviderError("invalid JSON from model") from err
