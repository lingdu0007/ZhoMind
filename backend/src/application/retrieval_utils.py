from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable

_TOKEN_PATTERN = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_PATTERN.findall(text)]


def embed_text(text: str, dim: int = 64) -> list[float]:
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for idx in range(dim):
            vec[idx] += (digest[idx % len(digest)] / 255.0) - 0.5

    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def bm25_scores(query: str, docs: Iterable[dict], k1: float = 1.5, b: float = 0.75) -> list[tuple[dict, float]]:
    items = list(docs)
    if not items:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return [(item, 0.0) for item in items]

    doc_tokens = [tokenize(item.get("content", "")) for item in items]
    doc_lengths = [len(tokens) for tokens in doc_tokens]
    avg_dl = (sum(doc_lengths) / len(doc_lengths)) or 1.0

    df: Counter[str] = Counter()
    for tokens in doc_tokens:
        for token in set(tokens):
            df[token] += 1

    scored: list[tuple[dict, float]] = []
    n_docs = len(items)
    for item, tokens, dl in zip(items, doc_tokens, doc_lengths, strict=False):
        tf = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            freq = tf.get(token, 0)
            if freq == 0:
                continue
            idf = math.log((n_docs - df[token] + 0.5) / (df[token] + 0.5) + 1.0)
            denom = freq + k1 * (1 - b + b * dl / avg_dl)
            score += idf * (freq * (k1 + 1)) / (denom or 1.0)
        scored.append((item, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored
