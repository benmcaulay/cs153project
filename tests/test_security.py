"""
The security contract: authentication is on by default, roles gate the two
surfaces, derived artifacts are encrypted at rest, and the audit log is
tamper-evident. These mirror the anti-hallucination tests in spirit — the
controls are measured, not just asserted.
"""
from __future__ import annotations

import json
import os

import pytest

from app import audit, crypto, security, store
from app.models import FillResult


@pytest.fixture()
def isolated_data(tmp_path, monkeypatch):
    """Point every persistence path (users, runs, keys, audit) at tmp."""
    monkeypatch.setattr(store, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(store, "RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(security, "_SESSIONS", {})
    monkeypatch.setattr(security, "_THROTTLE", {})
    monkeypatch.delenv("VERBATIM_DATA_KEY", raising=False)
    monkeypatch.delenv("VERBATIM_ENCRYPT", raising=False)
    monkeypatch.delenv("VERBATIM_AUTH", raising=False)
    return tmp_path


# --------------------------------------------------------------------------- #
# Passwords, users, lockout
# --------------------------------------------------------------------------- #
def test_password_hash_roundtrip():
    rec = security.hash_password("correct horse battery")
    assert security.verify_password("correct horse battery", rec)
    assert not security.verify_password("wrong", rec)
    # per-user salt: same password, different digests
    assert security.hash_password("x" * 10) != security.hash_password("x" * 10)


def test_create_authenticate_and_roles(isolated_data):
    security.create_user("alice", "password123", security.ROLE_ATTORNEY)
    user = security.authenticate("alice", "password123")
    assert user is not None and user.role == "attorney" and not user.is_admin
    assert security.authenticate("alice", "nope") is None
    # users.json stores no plaintext password
    raw = (isolated_data / "users.json").read_text()
    assert "password123" not in raw


def test_user_validation(isolated_data):
    with pytest.raises(ValueError):
        security.create_user("alice", "short")  # < 8 chars
    with pytest.raises(ValueError):
        security.create_user("bad name!", "password123")
    with pytest.raises(ValueError):
        security.create_user("alice", "password123", role="superuser")
    security.create_user("alice", "password123")
    with pytest.raises(ValueError):
        security.create_user("alice", "password456")  # duplicate


def test_lockout_after_repeated_failures(isolated_data):
    security.create_user("alice", "password123")
    for _ in range(security.LOCKOUT_THRESHOLD):
        assert security.authenticate("alice", "wrong") is None
    # locked: even the right password is refused until the window passes
    assert security.authenticate("alice", "password123") is None


def test_disabled_user_cannot_login_and_loses_sessions(isolated_data):
    security.create_user("alice", "password123")
    user = security.authenticate("alice", "password123")
    token = security.create_session(user)
    assert security.get_session_user(token) is not None
    security.set_disabled("alice", True)
    assert security.authenticate("alice", "password123") is None
    assert security.get_session_user(token) is None  # sessions revoked


def test_session_lifecycle(isolated_data):
    security.create_user("alice", "password123")
    user = security.authenticate("alice", "password123")
    token = security.create_session(user)
    assert security.get_session_user(token).username == "alice"
    assert security.get_session_user("forged-token") is None
    security.destroy_session(token)
    assert security.get_session_user(token) is None


def test_bootstrap_admin_once(isolated_data, monkeypatch):
    monkeypatch.setenv("VERBATIM_ADMIN_PASSWORD", "bootstrapped1")
    assert security.bootstrap_admin() is None  # env-provided => nothing to print
    assert security.authenticate("admin", "bootstrapped1").is_admin
    assert security.bootstrap_admin() is None  # idempotent


# --------------------------------------------------------------------------- #
# Encryption at rest
# --------------------------------------------------------------------------- #
def _fake_result(run_id="r1"):
    return FillResult(
        run_id=run_id,
        timestamp="2026-01-01T00:00:00",
        matter_id="m",
        matter_name="Smith v. Johnson",
        template_id="t",
        template_name="Affidavit",
        model="test",
        fields=[],
        original_text="Plaintiff: {{name}}",
        filled_text="Plaintiff: PRIVILEGED-FACT",
        inference_seconds=0.0,
        blanks_total=1,
        blanks_filled=1,
        blanks_needs_review=0,
        retrieval_mode="lexical",
        status="ok",
    )


def test_run_records_encrypted_on_disk(isolated_data):
    store.save_run(_fake_result())
    raw = (isolated_data / "runs" / "r1.json").read_bytes()
    assert raw.startswith(crypto.MAGIC)
    assert b"PRIVILEGED-FACT" not in raw  # extracted facts unreadable on disk
    loaded = store.load_run("r1")
    assert loaded.filled_text == "Plaintiff: PRIVILEGED-FACT"
    assert store.list_runs()[0].run_id == "r1"


def test_legacy_plaintext_runs_still_load(isolated_data):
    os.makedirs(isolated_data / "runs", exist_ok=True)
    (isolated_data / "runs" / "r1.json").write_text(
        json.dumps(_fake_result().model_dump()), encoding="utf-8"
    )
    assert store.load_run("r1").matter_name == "Smith v. Johnson"
    # next save re-encrypts in place
    store.save_run(store.load_run("r1"))
    assert (isolated_data / "runs" / "r1.json").read_bytes().startswith(crypto.MAGIC)


def test_wrong_key_fails_closed(isolated_data, monkeypatch):
    store.save_run(_fake_result())
    from cryptography.fernet import Fernet

    monkeypatch.setenv("VERBATIM_DATA_KEY", Fernet.generate_key().decode())
    with pytest.raises(ValueError):
        store.load_run("r1")


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
def test_audit_chain_detects_tampering(isolated_data):
    audit.log("alice", "auth.login")
    audit.log("alice", "fill.run", resource="Smith × Affidavit × llama3.1:8b")
    audit.log("alice", "run.export", resource="r1")
    assert audit.verify() is None

    path = isolated_data / "audit.log"
    lines = path.read_text().splitlines()
    doctored = json.loads(lines[1])
    doctored["user"] = "mallory"
    lines[1] = json.dumps(doctored, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    assert audit.verify() == 2  # first broken record

    records = audit.read()
    assert records[0]["action"] == "run.export"  # newest first


# --------------------------------------------------------------------------- #
# End-to-end over the HTTP API (cookie auth + RBAC)
# --------------------------------------------------------------------------- #
def test_api_auth_and_rbac(isolated_data, monkeypatch):
    httpx = pytest.importorskip("httpx")  # noqa: F841 (TestClient dependency)
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("VERBATIM_ADMIN_PASSWORD", "adminpass1")
    with TestClient(app) as client:  # triggers startup bootstrap
        # unauthenticated: probe is 200, everything else is 401
        assert client.get("/api/auth/me").json()["authenticated"] is False
        assert client.get("/api/matters").status_code == 401
        assert client.get("/api/runs").status_code == 401

        # bad credentials
        assert (
            client.post("/api/auth/login", json={"username": "admin", "password": "no"}).status_code
            == 401
        )

        # admin: full access, can create an attorney
        assert (
            client.post(
                "/api/auth/login", json={"username": "admin", "password": "adminpass1"}
            ).status_code
            == 200
        )
        assert client.get("/api/runs").status_code == 200
        assert (
            client.post(
                "/api/auth/users",
                json={"username": "alice", "password": "password123", "role": "attorney"},
            ).status_code
            == 200
        )
        assert client.get("/api/audit").json()["intact"] is True
        client.post("/api/auth/logout")

        # attorney: workspace yes, developer console no
        client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
        assert client.get("/api/matters").status_code == 200
        assert client.get("/api/runs").status_code == 403
        assert client.get("/api/report").status_code == 403
        assert client.get("/api/auth/users").status_code == 403
