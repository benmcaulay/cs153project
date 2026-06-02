"""
The dense retrieval index is rebuilt every fill; without caching it re-embeds
every chunk each time, which made fills crawl once an embedding model was
installed. These tests pin the (model, text) cache and the embedding-model
classification used to keep embedders out of the generation picker.
"""
from __future__ import annotations

from app import ollama_client


class _FakeResp:
    def __init__(self, vec):
        self._vec = vec

    def raise_for_status(self):
        pass

    def json(self):
        return {"embedding": self._vec}


def test_embed_is_cached_per_model_and_text(monkeypatch):
    ollama_client._EMBED_CACHE.clear()
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        return _FakeResp([float(len(json["prompt"]))])

    monkeypatch.setattr(ollama_client.requests, "post", fake_post)

    first = ollama_client.embed("nomic-embed-text", ["alpha", "beta"])
    assert calls["n"] == 2
    # Re-embedding the same texts hits the cache — no new HTTP calls.
    second = ollama_client.embed("nomic-embed-text", ["alpha", "beta"])
    assert calls["n"] == 2
    assert first == second
    # A different model is a distinct cache key.
    ollama_client.embed("mxbai-embed-large", ["alpha"])
    assert calls["n"] == 3


def test_embedding_model_classification():
    assert ollama_client.is_embedding_model("nomic-embed-text:latest")
    assert ollama_client.is_embedding_model("mxbai-embed-large")
    assert ollama_client.is_embedding_model("all-minilm")
    assert not ollama_client.is_embedding_model("qwen3.6:latest")
    assert not ollama_client.is_embedding_model("gemma4:latest")
