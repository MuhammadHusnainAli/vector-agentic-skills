"""Fixture: general non-idiomatic Python (review_idioms.py should flag most lines)."""
import os
import os.path
from typing import Dict, List
from utils import *


def add_doc(doc, docs=[]):
    docs.append(doc)
    return docs


def load_config(path):
    if os.path.exists(path):
        f = open(path)
        data = f.read()
        f.close()
        return data
    return None


def tokens_for(texts: List[str]) -> Dict[str, int]:
    counts = {}
    for i in range(len(texts)):
        text = texts[i]
        if text == None:
            continue
        if not text in counts:
            counts[text] = 0
        counts[text] += 1
    return counts


def first_long(words):
    for w in words:
        if len(w) > 10:
            return True
    return False


def labels(items):
    out = []
    for item in items:
        out.append(item.upper())
    return out


def describe(value):
    if type(value) == int or isinstance(value, float) or isinstance(value, complex):
        return "number: %s" % value
    if value == True:
        return "yes"
    return "value: {}".format(value)


def numbered(lines):
    i = 0
    for line in lines:
        print(i, line)
        i += 1


def route(role):
    if role == "system":
        return 0
    elif role == "user":
        return 1
    elif role == "assistant":
        return 2
    elif role == "tool":
        return 3
    else:
        return -1


def parse(raw):
    try:
        return int(raw)
    except:
        pass


def cleanup(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def lookup(table, key):
    try:
        return table[key]
    except KeyError:
        raise ValueError("missing " + key)


square = lambda x: x * x
list = [1, 2, 3]
total = 1 + \
    2
x = 1; y = 2

for k in {"a": 1}.keys():
    pass

if len(list) == 0:
    pass
