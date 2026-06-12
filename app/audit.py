"""
Append-only, tamper-evident audit log (data/audit.log).

Every security-relevant action — logins, fills, exports, uploads, deletions,
user administration — is appended as one JSON line. Each record embeds the
SHA-256 of the previous record, so editing or deleting any line breaks the
chain for everything after it:

    {"ts": ..., "user": ..., "action": ..., "resource": ..., "ok": ...,
     "prev": <hash of previous record>, "hash": <hash of this record>}

Records reference matters/templates/runs by id and name only — never case
content — so the log itself is not privileged material. Verify integrity with:

    python -m app.audit verify
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from typing import List, Optional

_GENESIS = "0" * 64


def _log_path() -> str:
    from .store import DATA_DIR

    return os.path.join(DATA_DIR, "audit.log")


def _record_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def _last_hash(path: str) -> str:
    if not os.path.exists(path):
        return _GENESIS
    last = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = line
    if last is None:
        return _GENESIS
    try:
        return json.loads(last).get("hash", _GENESIS)
    except json.JSONDecodeError:
        return _GENESIS


def log(user: str, action: str, resource: Optional[str] = None, ok: bool = True) -> None:
    path = _log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "user": user,
        "action": action,
        "resource": resource,
        "ok": ok,
        "prev": _last_hash(path),
    }
    record["hash"] = _record_hash(record)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def read(limit: int = 200) -> List[dict]:
    """Most recent `limit` records, newest first."""
    path = _log_path()
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    records.append({"error": "unparseable record", "raw": line.strip()})
    return list(reversed(records[-limit:]))


def verify() -> Optional[int]:
    """Walk the hash chain. Returns the 1-based line number of the first
    broken record, or None if the chain is intact."""
    path = _log_path()
    if not os.path.exists(path):
        return None
    prev = _GENESIS
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return i
            if record.get("prev") != prev or record.get("hash") != _record_hash(record):
                return i
            prev = record["hash"]
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        broken = verify()
        if broken is None:
            print("audit log intact")
        else:
            print(f"audit log TAMPERED at line {broken}", file=sys.stderr)
            raise SystemExit(1)
    else:
        for r in read(limit=50):
            print(json.dumps(r))
