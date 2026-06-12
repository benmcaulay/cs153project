"""
Encryption at rest for Verbatim-derived artifacts (NFR-2 hardening).

Run records contain extracted facts, verbatim quotes, and the filled document
text — privileged material derived from the case file. They are encrypted on
disk with Fernet (AES-128-CBC + HMAC-SHA256, from the already-required
`cryptography` package).

Key management, in order of precedence:
  1. VERBATIM_DATA_KEY    — a Fernet key (urlsafe base64), e.g. injected by a
                            secrets manager in a real deployment.
  2. data/.keys/data.key  — generated on first use with 0600 permissions.

Encrypted files carry the MAGIC prefix so plaintext records written by earlier
versions still load; they are re-encrypted the next time they are saved.
Disable with VERBATIM_ENCRYPT=0 (e.g. to inspect run records during dev).

Scope note: case files under data/matters/ are the firm's own source documents
and stay in the firm's filesystem, where full-disk encryption (BitLocker /
FileVault / LUKS) is the appropriate control — see docs/security.md.
"""
from __future__ import annotations

import os
import stat

from cryptography.fernet import Fernet, InvalidToken

MAGIC = b"VBTENC1\n"


def encryption_enabled() -> bool:
    return os.environ.get("VERBATIM_ENCRYPT", "1") != "0"


def _key_path() -> str:
    from .store import DATA_DIR

    return os.path.join(DATA_DIR, ".keys", "data.key")


def _load_or_create_key() -> bytes:
    env = os.environ.get("VERBATIM_DATA_KEY")
    if env:
        return env.encode("ascii")
    path = _key_path()
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return fh.read().strip()
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key)
    return key


def _fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt for storage. Pass-through when encryption is disabled."""
    if not encryption_enabled():
        return data
    return MAGIC + _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt stored bytes. Plaintext (legacy / encryption-off) passes through."""
    if not data.startswith(MAGIC):
        return data
    try:
        return _fernet().decrypt(data[len(MAGIC):])
    except InvalidToken as exc:
        raise ValueError(
            "Cannot decrypt record: wrong or missing data key "
            "(VERBATIM_DATA_KEY / data/.keys/data.key)"
        ) from exc
