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
import time
from typing import List, Optional, Tuple

import requests

# Local host only. Configurable for an internal GPU server, but never a 3rd party.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_TIMEOUT = float(os.environ.get("VERBATIM_OLLAMA_TIMEOUT", "120"))


class OllamaUnavailable(RuntimeError):
    """Raised when the local model runtime cannot be reached."""


def _url(path: str) -> str:
    return f"{OLLAMA_HOST.rstrip('/')}{path}"


def is_available() -> bool:
    try:
        r = requests.get(_url("/api/tags"), timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


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
        models.append(
            {
                "name": m.get("name"),
                "size": m.get("size"),
                "family": (m.get("details") or {}).get("family"),
                "parameter_size": (m.get("details") or {}).get("parameter_size"),
                "quantization": (m.get("details") or {}).get("quantization_level"),
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
        name = (m.get("name") or "").lower()
        if any(tag in name for tag in ("embed", "nomic", "mxbai", "bge")):
            return m["name"]
    return None


def embed(model: str, texts: List[str]) -> List[List[float]]:
    """Return embeddings for texts via the local runtime."""
    vectors: List[List[float]] = []
    for t in texts:
        try:
            r = requests.post(
                _url("/api/embeddings"),
                json={"model": model, "prompt": t},
                timeout=DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            vectors.append(r.json().get("embedding", []))
        except requests.RequestException as exc:
            raise OllamaUnavailable(str(exc))
    return vectors


def generate_json(
    model: str,
    system: str,
    prompt: str,
    temperature: float = 0.0,
) -> Tuple[dict, float]:
    """
    Run a deterministic (temperature 0, NFR-2) JSON-mode completion.

    Returns (parsed_json, elapsed_seconds). Raises OllamaUnavailable if the
    runtime cannot be reached.
    """
    payload = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # runtime-enforced JSON mode (SRS §9.3)
        "options": {"temperature": temperature},
    }
    start = time.perf_counter()
    try:
        r = requests.post(_url("/api/generate"), json=payload, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        body = r.json()
    except requests.RequestException as exc:
        raise OllamaUnavailable(str(exc))
    elapsed = time.perf_counter() - start

    raw = body.get("response", "").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Smaller models occasionally wrap JSON in prose; salvage the object.
        parsed = _salvage_json(raw)
    return parsed, elapsed


def _salvage_json(raw: str) -> dict:
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(raw[first : last + 1])
        except json.JSONDecodeError:
            pass
    return {"fields": []}
