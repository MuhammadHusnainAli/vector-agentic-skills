"""Untyped LLM client wrapper: annotation_audit should report gaps and infer types."""
import json
import time


class ChatClient:
    def __init__(self, model, temperature=0.2, max_tokens=1024, stream=False):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream

    def with_model(self, model):
        self.model = model
        return self

    def build_messages(self, system, user, history=[]):
        return [{"role": "system", "content": system}, *history, {"role": "user", "content": user}]

    def format_prompt(self, question, context):
        return f"Context:\n{context}\n\nQuestion: {question}"

    def is_rate_limited(self, status_code):
        return status_code == 429

    def retry_delay(self, attempt, base=0.5):
        return base * 2 ** attempt

    def stream_tokens(self, text):
        for word in text.split():
            yield f"{word} "

    def to_json(self, payload):
        return json.dumps(payload)

    def first_tool_call(self, response):
        for call in response.get("tool_calls", []):
            if call["type"] == "function":
                return call["name"]


def chunk_text(text, size=512, overlap=64, separators=("\n\n", "\n", " ")):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


async def embed_batch(client, texts, model=None):
    started = time.perf_counter()
    vectors = await client.embed(texts, model=model)
    return vectors, time.perf_counter() - started


def fail_fast(reason):
    raise RuntimeError(reason)
