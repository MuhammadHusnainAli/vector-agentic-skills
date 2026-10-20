"""Fixture: AI-engineering anti-patterns (review_idioms.py should flag them)."""
import asyncio
import datetime
import json
import logging
import time

import requests
from openai import OpenAI
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

OPENAI_API_KEY = "sk-proj-abc123def456ghi789jkl012mno345"
client = OpenAI(api_key=OPENAI_API_KEY)
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def call_llm(prompt):
    while True:
        try:
            resp = requests.post("https://api.example.com/v1/chat", json={"prompt": prompt})
            return resp.json()
        except Exception as e:
            print("retrying", e)
            time.sleep(2)


async def fetch_context(query):
    time.sleep(1)
    r = requests.get("https://search.example.com", params={"q": query})
    return r.text


async def embed_all(texts):
    vectors = []
    for t in texts:
        v = await asyncio.to_thread(embedder.encode, t)
        vectors.append(v)
    return vectors


def build_prompt(question, chunks):
    context = ""
    for c in chunks:
        context += c + "\n"
    prompt = "Answer using the context.\n" + context + "\nQuestion: " + question
    logger.info(f"prompt has {len(prompt)} chars")
    return prompt


def parse_tool_call(text):
    return eval(text)


def timestamp():
    return datetime.datetime.utcnow().isoformat()


def save(results, path):
    with open(path, "w") as fh:
        json.dump(results, fh)
