"""
Authentication and role-based access control.

Verbatim handles privileged case material, so access to the API is
authenticated by default. Design constraints, matching the rest of the app:
local-only, no third-party services, stdlib crypto for passwords.

  - Users live in data/users.json: scrypt-hashed passwords (hashlib.scrypt,
    per-user random salt), a role, and a disabled flag. No plaintext secrets.
  - Roles: "attorney" (workspace + library) and "admin" (everything, including
    the Developer Console and user management). admin ⊇ attorney.
  - Sessions are opaque random tokens in an HttpOnly SameSite=Lax cookie,
    held server-side in memory with a sliding 12-hour expiry. Restarting the
    server logs everyone out — acceptable for a single-host deployment.
  - Brute-force throttle: 5 consecutive failures locks a username for 60 s.
  - First run bootstraps an "admin" account. The password comes from
    VERBATIM_ADMIN_PASSWORD or is generated and printed once to the console.
  - VERBATIM_AUTH=0 disables authentication entirely (local demos, tests);
    every request then acts as a built-in admin.

User management CLI (also available to admins over the API):
    python -m app.security adduser <name> [--role attorney|admin]
    python -m app.security passwd  <name>
    python -m app.security disable <name>
    python -m app.security list
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

ROLE_ATTORNEY = "attorney"
ROLE_ADMIN = "admin"
ROLES = (ROLE_ATTORNEY, ROLE_ADMIN)

SESSION_COOKIE = "verbatim_session"
SESSION_TTL_SECONDS = 12 * 3600
LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 60

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1

# token -> {"username", "role", "expires"}
_SESSIONS: Dict[str, dict] = {}
# username -> {"failures", "locked_until"}
_THROTTLE: Dict[str, dict] = {}


def auth_enabled() -> bool:
    return os.environ.get("VERBATIM_AUTH", "1") != "0"


@dataclass
class User:
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


# --------------------------------------------------------------------------- #
# Password hashing (stdlib scrypt)
# --------------------------------------------------------------------------- #
def hash_password(password: str, salt: Optional[bytes] = None) -> dict:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return {"salt": salt.hex(), "hash": digest.hex()}


def verify_password(password: str, record: dict) -> bool:
    try:
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["hash"])
    except (KeyError, ValueError):
        return False
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return hmac.compare_digest(digest, expected)


# --------------------------------------------------------------------------- #
# User store (data/users.json)
# --------------------------------------------------------------------------- #
def _users_path() -> str:
    from .store import DATA_DIR

    return os.path.join(DATA_DIR, "users.json")


def _load_users() -> dict:
    path = _users_path()
    if not os.path.exists(path):
        return {"users": []}
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return {"users": []}


def _save_users(data: dict) -> None:
    path = _users_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _find(data: dict, username: str) -> Optional[dict]:
    for u in data["users"]:
        if u["username"] == username:
            return u
    return None


def list_users() -> List[dict]:
    return [
        {
            "username": u["username"],
            "role": u["role"],
            "disabled": u.get("disabled", False),
            "created_at": u.get("created_at"),
        }
        for u in _load_users()["users"]
    ]


def create_user(username: str, password: str, role: str = ROLE_ATTORNEY) -> dict:
    username = username.strip()
    if not username or not username.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise ValueError("Username must be alphanumeric (plus -_.)")
    if role not in ROLES:
        raise ValueError(f"Role must be one of {ROLES}")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    data = _load_users()
    if _find(data, username) is not None:
        raise ValueError(f"User {username!r} already exists")
    record = {
        "username": username,
        "role": role,
        "disabled": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **hash_password(password),
    }
    data["users"].append(record)
    _save_users(data)
    return {"username": username, "role": role, "disabled": False}


def set_password(username: str, password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    data = _load_users()
    user = _find(data, username)
    if user is None:
        raise ValueError(f"No such user {username!r}")
    user.update(hash_password(password))
    _save_users(data)


def set_disabled(username: str, disabled: bool) -> None:
    data = _load_users()
    user = _find(data, username)
    if user is None:
        raise ValueError(f"No such user {username!r}")
    user["disabled"] = disabled
    _save_users(data)
    if disabled:
        revoke_user_sessions(username)


def bootstrap_admin() -> Optional[str]:
    """Ensure at least one account exists. Returns the generated password if
    one was created without VERBATIM_ADMIN_PASSWORD (caller should print it)."""
    if not auth_enabled():
        return None
    if _load_users()["users"]:
        return None
    password = os.environ.get("VERBATIM_ADMIN_PASSWORD")
    generated = None
    if not password:
        password = generated = secrets.token_urlsafe(12)
    create_user("admin", password, ROLE_ADMIN)
    return generated


# --------------------------------------------------------------------------- #
# Login / sessions
# --------------------------------------------------------------------------- #
def authenticate(username: str, password: str) -> Optional[User]:
    """Verify credentials, enforcing the lockout. Returns None on failure."""
    now = time.time()
    throttle = _THROTTLE.setdefault(username, {"failures": 0, "locked_until": 0.0})
    if now < throttle["locked_until"]:
        return None

    data = _load_users()
    record = _find(data, username)
    ok = (
        record is not None
        and not record.get("disabled", False)
        and verify_password(password, record)
    )
    if not ok:
        # Hash anyway when the user doesn't exist so timing doesn't reveal
        # valid usernames.
        if record is None:
            verify_password(password, hash_password("invalid"))
        throttle["failures"] += 1
        if throttle["failures"] >= LOCKOUT_THRESHOLD:
            throttle["locked_until"] = now + LOCKOUT_SECONDS
            throttle["failures"] = 0
        return None

    _THROTTLE.pop(username, None)
    return User(username=record["username"], role=record["role"])


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = {
        "username": user.username,
        "role": user.role,
        "expires": time.time() + SESSION_TTL_SECONDS,
    }
    return token


def get_session_user(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    sess = _SESSIONS.get(token)
    if sess is None:
        return None
    now = time.time()
    if now > sess["expires"]:
        _SESSIONS.pop(token, None)
        return None
    sess["expires"] = now + SESSION_TTL_SECONDS  # sliding expiry
    return User(username=sess["username"], role=sess["role"])


def destroy_session(token: Optional[str]) -> None:
    if token:
        _SESSIONS.pop(token, None)


def revoke_user_sessions(username: str) -> None:
    for token in [t for t, s in _SESSIONS.items() if s["username"] == username]:
        _SESSIONS.pop(token, None)


# --------------------------------------------------------------------------- #
# FastAPI dependencies
# --------------------------------------------------------------------------- #
from fastapi import HTTPException, Request  # noqa: E402


def _request_user(request: Request) -> Optional[User]:
    if not auth_enabled():
        return User(username="local", role=ROLE_ADMIN)
    return get_session_user(request.cookies.get(SESSION_COOKIE))


def require_attorney(request: Request) -> User:
    user = _request_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> User:
    user = require_attorney(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli(argv: List[str]) -> int:
    import argparse
    import getpass

    parser = argparse.ArgumentParser(prog="python -m app.security", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("adduser")
    p_add.add_argument("username")
    p_add.add_argument("--role", choices=ROLES, default=ROLE_ATTORNEY)
    p_add.add_argument("--password", help="omit to be prompted")
    p_pw = sub.add_parser("passwd")
    p_pw.add_argument("username")
    p_pw.add_argument("--password", help="omit to be prompted")
    p_dis = sub.add_parser("disable")
    p_dis.add_argument("username")
    p_en = sub.add_parser("enable")
    p_en.add_argument("username")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "adduser":
            pw = args.password or getpass.getpass("Password: ")
            create_user(args.username, pw, args.role)
            print(f"Created {args.role} {args.username!r}")
        elif args.cmd == "passwd":
            pw = args.password or getpass.getpass("New password: ")
            set_password(args.username, pw)
            print(f"Password updated for {args.username!r}")
        elif args.cmd == "disable":
            set_disabled(args.username, True)
            print(f"Disabled {args.username!r}")
        elif args.cmd == "enable":
            set_disabled(args.username, False)
            print(f"Enabled {args.username!r}")
        elif args.cmd == "list":
            for u in list_users():
                state = "disabled" if u["disabled"] else "active"
                print(f"{u['username']:<20} {u['role']:<10} {state}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
