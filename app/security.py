"""
Security primitives: encryption-at-rest and API authentication config.

Encryption at rest (NFR-4, optional)
------------------------------------
Run records and the local config contain extracted case facts — the most
sensitive *derived* data Verbatim produces. When `VERBATIM_DATA_KEY` is set to a
Fernet key, those JSON artifacts are written encrypted (AES-128-CBC + HMAC via
`cryptography.fernet`) and decrypted transparently on read. Plaintext files
written before a key was configured remain readable, so enabling encryption is
non-destructive; new writes are always encrypted once a key is present.

Generate a key:

    python -m app.security --generate-key

Source case documents are intentionally *not* re-encrypted by the application:
they live wherever the firm's document store puts them and should be covered by
full-disk encryption (FileVault / BitLocker / LUKS) or the DMS's own controls.
Re-encrypting them inside Verbatim would duplicate sensitive bytes, not reduce
them. This boundary is documented in SECURITY.md.

API authentication (NFR-5, optional)
------------------------------------
When `VERBATIM_API_TOKEN` is set, every `/api/*` request must carry
`Authorization: Bearer <token>`. Comparison is constant-time. When unset (the
default for a single-user trusted host), the API is open on 127.0.0.1 exactly
as before — the one-command demo still works.
"""
from __future__ import annotations

import hmac
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

# Fernet tokens are URL-safe base64 and always begin with this prefix
# (version byte 0x80). Used to detect encrypted-vs-plaintext files on read.
FERNET_PREFIX = b"gAAAA"


def data_key() -> Optional[bytes]:
    """The configured at-rest key, or None when encryption is disabled."""
    key = os.environ.get("VERBATIM_DATA_KEY", "").strip()
    return key.encode("utf-8") if key else None


def _fernet() -> Optional[Fernet]:
    key = data_key()
    if not key:
        return None
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "VERBATIM_DATA_KEY is not a valid Fernet key. Generate one with: "
            "python -m app.security --generate-key"
        ) from exc


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt `data` if a key is configured; otherwise return it unchanged."""
    f = _fernet()
    return f.encrypt(data) if f else data


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt `data` if it is an encrypted artifact; pass plaintext through.

    Raises RuntimeError when the file is encrypted but no/incorrect key is
    configured — the caller should surface this, never silently skip records.
    """
    if not data.startswith(FERNET_PREFIX):
        return data  # legacy plaintext artifact
    f = _fernet()
    if f is None:
        raise RuntimeError(
            "Encrypted data found but VERBATIM_DATA_KEY is not set. "
            "Set the key used to write this data."
        )
    try:
        return f.decrypt(data)
    except InvalidToken as exc:
        raise RuntimeError(
            "VERBATIM_DATA_KEY does not match the key this data was written with."
        ) from exc


def encryption_enabled() -> bool:
    return data_key() is not None


# --------------------------------------------------------------------------- #
# API token
# --------------------------------------------------------------------------- #
def api_token() -> Optional[str]:
    token = os.environ.get("VERBATIM_API_TOKEN", "").strip()
    return token or None


def check_bearer(authorization: Optional[str]) -> bool:
    """Constant-time check of an Authorization header against the configured token.

    Returns True when auth is disabled (no token configured) or the header
    matches `Bearer <token>`.
    """
    expected = api_token()
    if expected is None:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    supplied = authorization[len("Bearer "):].strip()
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


if __name__ == "__main__":
    import sys

    if "--generate-key" in sys.argv:
        print(Fernet.generate_key().decode("ascii"))
    else:
        print("Usage: python -m app.security --generate-key", file=sys.stderr)
        sys.exit(2)
