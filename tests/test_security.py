"""
Security hardening tests (NFR-4 encryption at rest, NFR-5 API auth).

The contract under test:
  - With no VERBATIM_API_TOKEN, the API behaves exactly as before (open on a
    trusted local host) — the one-command demo must not regress.
  - With a token set, every /api/* endpoint except /api/health requires
    `Authorization: Bearer <token>`; wrong/missing tokens get 401.
  - With VERBATIM_DATA_KEY set, run records and config are unreadable as
    plaintext on disk but round-trip transparently; plaintext records written
    before the key existed remain readable (non-destructive migration).
"""
from __future__ import annotations

import importlib
import json
import os

import pytest
from fastapi.testclient import TestClient

from app import security


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """A TestClient with an isolated data dir; token configurable per-test."""
    monkeypatch.setenv("VERBATIM_DATA_DIR", str(tmp_path))
    import app.store as store

    importlib.reload(store)
    from app.main import app as fastapi_app

    return TestClient(fastapi_app)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def test_open_by_default(client, monkeypatch):
    monkeypatch.delenv("VERBATIM_API_TOKEN", raising=False)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/templates").status_code == 200


def test_token_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("VERBATIM_API_TOKEN", "s3cret")
    r = client.get("/api/templates")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == "Bearer"


def test_wrong_token_rejected(client, monkeypatch):
    monkeypatch.setenv("VERBATIM_API_TOKEN", "s3cret")
    r = client.get("/api/templates", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_correct_token_accepted(client, monkeypatch):
    monkeypatch.setenv("VERBATIM_API_TOKEN", "s3cret")
    r = client.get("/api/templates", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200


def test_health_stays_open_with_auth(client, monkeypatch):
    monkeypatch.setenv("VERBATIM_API_TOKEN", "s3cret")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["auth_required"] is True


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


# --------------------------------------------------------------------------- #
# Encryption at rest
# --------------------------------------------------------------------------- #
def _sample_result():
    from app.models import FillResult

    return FillResult(
        run_id="testrun123",
        timestamp="2026-01-01T00:00:00",
        matter_id="m1",
        matter_name="Doe v Roe",
        template_id="t1",
        template_name="Demand Letter",
        model="test",
        fields=[],
        original_text="Dear {{name}},",
        filled_text="Dear Jane Doe,",
        inference_seconds=0.0,
        blanks_total=1,
        blanks_filled=1,
        blanks_needs_review=0,
        retrieval_mode="lexical",
        status="ok",
    )


def test_run_record_encrypted_on_disk(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("VERBATIM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VERBATIM_DATA_KEY", key)
    import app.store as store

    importlib.reload(store)
    store.save_run(_sample_result())

    raw = open(os.path.join(str(tmp_path), "runs", "testrun123.json"), "rb").read()
    assert raw.startswith(security.FERNET_PREFIX)          # ciphertext on disk
    assert b"Jane Doe" not in raw                          # no plaintext leakage

    loaded = store.load_run("testrun123")                  # transparent decrypt
    assert loaded is not None and loaded.filled_text == "Dear Jane Doe,"


def test_legacy_plaintext_still_readable_with_key(monkeypatch, tmp_path):
    """Enabling encryption must not strand records written before the key."""
    monkeypatch.setenv("VERBATIM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VERBATIM_DATA_KEY", raising=False)
    import app.store as store

    importlib.reload(store)
    store.save_run(_sample_result())                       # plaintext write

    from cryptography.fernet import Fernet

    monkeypatch.setenv("VERBATIM_DATA_KEY", Fernet.generate_key().decode())
    importlib.reload(store)
    loaded = store.load_run("testrun123")
    assert loaded is not None and loaded.matter_name == "Doe v Roe"


def test_wrong_key_fails_loudly(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("VERBATIM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VERBATIM_DATA_KEY", Fernet.generate_key().decode())
    import app.store as store

    importlib.reload(store)
    store.save_run(_sample_result())

    monkeypatch.setenv("VERBATIM_DATA_KEY", Fernet.generate_key().decode())
    with pytest.raises(RuntimeError):
        store.load_run("testrun123")
