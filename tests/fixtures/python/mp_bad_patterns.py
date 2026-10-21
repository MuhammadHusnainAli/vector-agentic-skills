"""Fixture for pool_tool.py check: every MP rule fires at least once. Never run this file."""
import functools
import itertools
import json
import multiprocessing
import os
import threading
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager, Pool, Process, Queue

import torch
from transformers import AutoModel

multiprocessing.set_start_method("fork")                          # MP007 import time, MP008 fork + torch

TOKEN_COUNTS = {}                                                 # parent expects workers to fill this
_model = None


def load_model():
    global _model
    _model = AutoModel.from_pretrained("bert-base-uncased")


def count_tokens(doc):
    for tok in doc.split():
        TOKEN_COUNTS[tok] = TOKEN_COUNTS.get(tok, 0) + 1        # MP009 global mutation in worker


def embed(text):
    return _model(text)


def parse_with_vocab(vocab, path):
    return [vocab.get(w) for w in open(path).read().split()]


def add_tokens(shared, doc):
    for tok in doc.split():
        shared[tok] = shared.get(tok, 0) + 1                    # MP011 proxy in loop (via param)


def fan_out(paths):
    with Pool(4) as inner:                                      # MP018 nested pool in a Pool worker
        return inner.map(len, paths)


def producer(q, n):
    for i in range(n):
        q.put(i)


def report(q, item):
    q.put(item)


pool = Pool(8)                                                    # MP001 import time, MP003 never closed, MP021


class Indexer:
    def __init__(self):
        self.pool = Pool(4)

    def chunk(self, doc):
        return doc.split("\n\n")

    def run(self, docs):
        return self.pool.map(self.chunk, docs)                  # MP002 bound method


def main(paths, docs):
    vocab = json.load(open("vocab.json"))                       # heavy object
    heartbeat = threading.Thread(target=print, daemon=True)
    heartbeat.start()

    def local_clean(doc):
        return doc.strip()

    with Pool(8, initializer=load_model) as p:                  # MP013 model, no maxtasksperchild; MP017 thread
        cleaned = p.map(lambda d: d.lower(), docs)              # MP002 lambda; MP016 no Ctrl-C handling
        stripped = p.map(local_clean, docs)                     # MP002 nested function
        p.apply_async(embed, (docs[0],))                        # MP006 result dropped, no error_callback
        pending = [p.apply_async(embed, (d,)) for d in docs]
        it = p.imap(embed, docs)                                # MP005 imap without chunksize
        mixed = p.starmap(parse_with_vocab, [(vocab, x) for x in paths])   # MP010 vocab per task
        p.map(fan_out, [paths, paths])
    results = [r.get() for r in pending]                        # MP004 read after with exited
    for d in docs:
        p2 = Pool(2)                                            # MP020 pool in loop (and MP003)
        p2.apply(embed, (d,))                                   # MP019 apply() in a loop

    ex = ProcessPoolExecutor(4)                                 # MP003 executor never shut down
    ex.submit(embed, docs[0])                                   # MP006 future dropped
    vectors = list(ex.map(embed, docs))                         # MP005 executor.map chunksize=1
    for d in docs:
        print(ex.submit(embed, d).result())                     # MP019 serialized submit
        ex.submit(parse_with_vocab, vocab, d).result()          # MP010 + MP019
    q = Queue()
    ex.submit(report, q, "x")                                   # MP014 mp.Queue to executor (and MP006)

    mgr = Manager()
    shared = mgr.dict()
    for d in docs:
        shared[d] = len(d)                                      # MP011 proxy in loop
    with Pool(2) as p3:
        p3.starmap(add_tokens, [(shared, d) for d in docs])
        p3.map(count_tokens, docs)

    procs = [Process(target=producer, args=(q, 100_000)) for _ in range(4)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()                                             # MP012 join before drain
    total = [q.get() for _ in range(400_000)]

    pid = os.fork()                                             # MP015 os.fork (+ MP008)
    multiprocessing.set_start_method("spawn")                   # MP007 second call
    p4 = Process(target=functools.partial(lambda x: x, 1))      # MP002 partial of lambda (spawn)
    p4.start()
    p4.join()
    print(len(TOKEN_COUNTS), cleaned, stripped, it, mixed, results, vectors, total, pid,
          list(itertools.chain(docs)))


main(["a.pdf"], ["doc"])                                          # MP001 main() at import time
