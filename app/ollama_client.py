"""
Ollama runtime client (FR-11, NFR-1, NFR-2, NFR-3).

The ONLY network endpoint Verbatim ever touches is the Ollama HTTP API bound to
the local host. There is no telemetry and no third-party call. Every method
degrades gracefully (returns a clear status, never crashes) when the runtime is
unreachable, satisfying NFR-3.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import List, Optional, Tuple

import requests

# Local host only. Configurable for an internal GPU server, but never a 3rd party.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Generation can be slow on the first call (the model loads into memory) and on
# larger models / CPU-bound machines. Generous default; override as needed.
DEFAULT_TIMEOUT = float(os.environ.get("VERBATIM_OLLAMA_TIMEOUT", "300"))
# Ollama's default context window (often 4096) silently truncates a multi-document
# prompt, after which the model returns empty/garbage. A larger window lets the
# whole grounded prompt through. Raise for big matters; lower to save memory.
NUM_CTX = int(os.environ.get("VERBATIM_NUM_CTX", "8192"))


class OllamaUnavailable(RuntimeError):
    """Raised when a call to the local model runtime fails.

    `kind` distinguishes the failure mode so the caller can report it precisely:
      - "timeout"    : the model did not respond within the timeout
      - "connection" : the runtime could not be reached at all
      - "http"       : the runtime returned an error status
      - "error"      : any other request failure
    """

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.kind = kind


def _url(path: str) -> str:
    return f"{OLLAMA_HOST.rstrip('/')}{path}"


def is_available() -> bool:
    try:
        r = requests.get(_url("/api/tags"), timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


# Name fragments that identify an embedding-only model. These cannot generate
# text, so they must be kept out of the generation-model picker (FR-11) even
# though they are valid retrieval models (FR-3).
_EMBEDDING_TAGS = ("embed", "nomic", "mxbai", "bge", "minilm", "arctic")


def is_embedding_model(name: str) -> bool:
    n = (name or "").lower()
    return any(tag in n for tag in _EMBEDDING_TAGS)


def list_models() -> List[dict]:
    """Enumerate all models installed in the local Ollama runtime (FR-11)."""
    try:
        r = requests.get(_url("/api/tags"), timeout=5)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        raise OllamaUnavailable(str(exc))
    models = []
    for m in data.get("models", []):
        name = m.get("name")
        models.append(
            {
                "name": name,
                "size": m.get("size"),
                "family": (m.get("details") or {}).get("family"),
                "parameter_size": (m.get("details") or {}).get("parameter_size"),
                "quantization": (m.get("details") or {}).get("quantization_level"),
                "embedding": is_embedding_model(name),
            }
        )
    return models


def has_embeddings_model() -> Optional[str]:
    """Return the name of an installed embedding model, if any (for FR-3 dense)."""
    try:
        models = list_models()
    except OllamaUnavailable:
        return None
    for m in models:
        if m.get("embedding"):
            return m["name"]
    return None


# Embeddings are deterministic for a given (model, text), but the dense index is
# rebuilt on every fill — re-embedding every chunk each time made fills crawl
# once an embedding model was installed. Cache by (model, text) so each unique
# chunk is embedded at most once per process; the second fill on a matter is
# effectively free for retrieval.
_EMBED_CACHE: dict = {}
_EMBED_CACHE_MAX = 20000


def embed(model: str, texts: List[str]) -> List[List[float]]:
    """Return embeddings for texts via the local runtime, with an in-process cache."""
    vectors: List[List[float]] = []
    for t in texts:
        ck = (model, t)
        cached = _EMBED_CACHE.get(ck)
        if cached is not None:
            vectors.append(cached)
            continue
        try:
            r = requests.post(
                _url("/api/embeddings"),
                json={"model": model, "prompt": t},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            vec = r.json().get("embedding", [])
        except requests.RequestException as exc:
            raise OllamaUnavailable(str(exc))
        if len(_EMBED_CACHE) >= _EMBED_CACHE_MAX:
            _EMBED_CACHE.clear()  # simple bound; prototype-scale
        _EMBED_CACHE[ck] = vec
        vectors.append(vec)
    return vectors


def generate_json(
    model: str,
    system: str,
    prompt: str,
    temperature: float = 0.0,
) -> Tuple[dict, float, str]:
    """
    Run a deterministic (temperature 0, NFR-2) JSON-mode completion.

    Returns (parsed_json, elapsed_seconds, raw_text). Raises OllamaUnavailable if
    the runtime cannot be reached.
    """
    payload = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # runtime-enforced JSON mode (SRS §9.3)
        # Reasoning models (e.g. Qwen3) otherwise emit <think> blocks that wreck
        # JSON-mode output; ask the runtime to disable thinking where supported.
        "think": False,
        "options": {"temperature": temperature, "num_ctx": NUM_CTX},
    }
    start = time.perf_counter()
    try:
        r = requests.post(_url("/api/generate"), json=payload, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        body = r.json()
    except requests.Timeout:
        raise OllamaUnavailable(
            f"model '{model}' did not respond within {DEFAULT_TIMEOUT:.0f}s. "
            f"The model may be too large for this machine, or still loading on "
            f"its first call. Try a smaller model, or raise VERBATIM_OLLAMA_TIMEOUT.",
            kind="timeout",
        )
    except requests.ConnectionError:
        raise OllamaUnavailable(
            f"could not connect to the Ollama runtime at {OLLAMA_HOST}", kind="connection"
        )
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = r.text[:300]
        except Exception:
            pass
        raise OllamaUnavailable(
            f"the runtime returned an error for model '{model}': {exc}. {detail}".strip(),
            kind="http",
        )
    except requests.RequestException as exc:
        raise OllamaUnavailable(str(exc), kind="error")
    elapsed = time.perf_counter() - start

    raw = body.get("response", "").strip()
    # Strip any reasoning wrapper a thinking model may still emit.
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Smaller models occasionally wrap JSON in prose / code fences; salvage it.
        parsed = _salvage_json(cleaned)
    return parsed, elapsed, raw


def _salvage_json(raw: str) -> dict:
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(raw[first : last + 1])
        except json.JSONDecodeError:
            pass
    return {"fields": []}
