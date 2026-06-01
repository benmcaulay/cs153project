"""
Retrieval (FR-3).

Dense (embedding-based) retrieval is used when an embedding model is installed
in the local runtime; otherwise the system transparently falls back to lexical
(TF-IDF) retrieval, with no change to the user experience. The lexical path is
pure-Python (no heavy ML dependency) so the prototype runs with only a chat
model installed (NFR-3).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

from .ingest import Chunk
from . import ollama_client

_WORD = re.compile(r"[A-Za-z0-9$#./-]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(text)]


@dataclass
class Retrieved:
    document: str
    text: str
    score: float


# --------------------------------------------------------------------------- #
# Lexical TF-IDF retrieval (fallback / default)
# --------------------------------------------------------------------------- #
class _TfidfIndex:
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.docs_tokens = [_tokenize(c.text) for c in chunks]
        self.df: Counter = Counter()
        for toks in self.docs_tokens:
            for term in set(toks):
                self.df[term] += 1
        self.n = max(len(chunks), 1)
        self.vectors = [self._vec(toks) for toks in self.docs_tokens]

    def _idf(self, term: str) -> float:
        return math.log((self.n + 1) / (self.df.get(term, 0) + 1)) + 1.0

    def _vec(self, tokens: List[str]) -> dict:
        tf = Counter(tokens)
        if not tf:
            return {}
        length = len(tokens)
        return {term: (count / length) * self._idf(term) for term, count in tf.items()}

    @staticmethod
    def _cosine(a: dict, b: dict) -> float:
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        num = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0 or nb == 0:
            return 0.0
        return num / (na * nb)

    def query(self, text: str, k: int) -> List[Retrieved]:
        q = self._vec(_tokenize(text))
        scored = [
            Retrieved(self.chunks[i].document, self.chunks[i].text, self._cosine(q, self.vectors[i]))
            for i in range(len(self.chunks))
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


# --------------------------------------------------------------------------- #
# Dense retrieval (when an embedding model is installed)
# --------------------------------------------------------------------------- #
class _DenseIndex:
    def __init__(self, chunks: List[Chunk], model: str):
        self.chunks = chunks
        self.model = model
        self.vectors = ollama_client.embed(model, [c.text for c in chunks])

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        num = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return num / (na * nb)

    def query(self, text: str, k: int) -> List[Retrieved]:
        qv = ollama_client.embed(self.model, [text])[0]
        scored = [
            Retrieved(self.chunks[i].document, self.chunks[i].text, self._cosine(qv, self.vectors[i]))
            for i in range(len(self.chunks))
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


class Retriever:
    """Builds the best available index and reports which mode it used."""

    def __init__(self, chunks: List[Chunk], embed_model: Optional[str] = None):
        self.mode = "lexical"
        self._index = None
        if embed_model:
            try:
                self._index = _DenseIndex(chunks, embed_model)
                self.mode = "dense"
            except ollama_client.OllamaUnavailable:
                self._index = None
        if self._index is None:
            self._index = _TfidfIndex(chunks)
            self.mode = "lexical"

    def retrieve(self, query: str, k: int = 6) -> List[Retrieved]:
        results = self._index.query(query, k)
        return [r for r in results if r.score > 0]


def auto_retriever(chunks: List[Chunk]) -> Retriever:
    """Pick dense retrieval if an embedding model exists, else lexical (FR-3)."""
    embed_model = ollama_client.has_embeddings_model()
    return Retriever(chunks, embed_model=embed_model)
