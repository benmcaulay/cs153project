# Security model

Verbatim's pitch is that privileged case material never leaves hardware the
firm controls. That claim is only as good as the controls around the host, so
this document states (1) the threat model, (2) what is implemented **today**
and how to verify it, (3) what is deliberately delegated to the deployment
environment, and (4) the production roadmap. It is written to be handed to a
firm's IT reviewer.

## 1. Threat model

In scope:

- **Network exfiltration** — case content leaving the host. Mitigated
  architecturally: the only outbound call in the codebase is to the local
  Ollama runtime (`app/ollama_client.py`); there is no telemetry, no analytics,
  no third-party API. Authentication is also local — no identity provider is
  contacted.
- **Unauthorized use of the application** — someone on the host or LAN reaching
  the API without credentials, or a paralegal/attorney reaching admin surfaces.
- **Casual disk access** — a copied backup, a shared workstation, or a stolen
  laptop exposing Verbatim's derived artifacts (run records contain extracted
  facts, verbatim quotes, and complete filled documents).
- **Repudiation** — no record of who filled, exported, or deleted what, or a
  record that can be silently edited.

Out of scope for the application layer (and why):

- **A compromised host or OS-level attacker.** Software on the same machine
  with the user's privileges can read what the user can read. This is the
  domain of endpoint security and full-disk encryption, not the app.
- **Physical theft of an unencrypted disk.** Mitigated by full-disk encryption
  (BitLocker / FileVault / LUKS), which firms should — and under most security
  policies already do — run on any machine holding client files.
- **Malicious admin.** The audit log makes admin actions visible and
  tamper-evident, but a local admin ultimately controls the host.

## 2. Implemented today

### Authentication (`app/security.py`)

- Local accounts in `data/users.json`: passwords hashed with **scrypt**
  (stdlib, per-user 16-byte random salt, N=2¹⁴ r=8 p=1); the file is written
  0600 and never contains plaintext secrets.
- Sessions are 256-bit random tokens in an **HttpOnly, SameSite=Lax** cookie,
  held server-side with a sliding 12-hour expiry. Restarting the server
  invalidates all sessions.
- **Brute-force lockout**: 5 consecutive failures locks the username for 60 s;
  nonexistent users are hashed anyway so response timing does not reveal valid
  usernames.
- **Bootstrap**: first start creates `admin` from `VERBATIM_ADMIN_PASSWORD`,
  or generates a password and prints it once to the console.
- `VERBATIM_AUTH=0` disables authentication for local demos/dev. The default
  is **on**.

### Role-based access control

Two roles, enforced **server-side on every endpoint** (FastAPI dependencies),
not merely hidden in the UI:

| Capability | attorney | admin |
|---|---|---|
| Workspace: matters, templates, models, fill, export | ✓ | ✓ |
| Library: upload/delete case documents and templates | ✓ | ✓ |
| Developer Console: runs, field flags, styles, reports | — | ✓ |
| User management, audit trail | — | ✓ |

Disabling a user revokes their live sessions immediately. Admins cannot
disable their own account (no lockout-by-accident).

### Encryption at rest (`app/crypto.py`)

- **Run records** — the artifacts Verbatim itself derives from privileged
  material — are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before
  touching disk. A wrong or missing key fails closed.
- Key precedence: `VERBATIM_DATA_KEY` (for a secrets manager), else
  `data/.keys/data.key`, generated 0600 on first use.
- **Boundary, stated honestly:** case files under `data/matters/` are the
  firm's *source* documents. Verbatim reads them in place and does not copy
  them elsewhere; encrypting them inside the app would break the
  drop-files-in-a-folder workflow while adding little, because the documents
  already exist in the firm's filesystem. The correct control for source files
  is full-disk encryption on the host. Verbatim encrypts everything it
  *creates* from them.

### Tamper-evident audit log (`app/audit.py`)

Every login (including failures), fill, export, upload, deletion, flag, style
change, and user-admin action is appended to `data/audit.log` as a JSON line
carrying the SHA-256 of the previous record. Editing or deleting any line
breaks the chain for every record after it.

- Verify: `python -m app.audit verify` (also surfaced, with the recent trail,
  in Developer Console → Access).
- Records reference matters/templates/runs by **identifier only** — case
  content never appears in the log, so the log itself is not privileged.

### Verifying all of the above

`tests/test_security.py` (part of `pytest -q`) asserts the contract: requests
without a session are 401, attorneys get 403 on admin endpoints over the live
API, run records on disk do not contain the extracted facts, a wrong key fails
closed, legacy plaintext records still load, and a doctored audit line is
detected at the right position.

## 3. Deployment guidance (single host, today)

- Keep the bind on `127.0.0.1`. To serve a small office LAN, put the app
  behind a TLS reverse proxy (Caddy makes this a two-line config) — the
  session cookie should then be marked `Secure`.
- Run full-disk encryption on the host. Include `data/.keys/` in a key-escrow
  or backup procedure **separate** from backups of `data/` itself.
- Set `VERBATIM_ADMIN_PASSWORD` on first start, or change the printed one
  immediately: `python -m app.security passwd admin`.
- Back up `data/audit.log` append-only (e.g., shipped to a log host) if the
  firm needs an audit trail that survives the machine.

## 4. Production roadmap

In priority order, with the reasoning a buyer will care about:

1. **SSO (OIDC, then SAML)** — firms above ~20 seats run Entra ID/Okta and
   will not provision local accounts. The session and RBAC layers already
   isolate identity behind `app/security.py`, so this swaps the *authenticator*
   without touching endpoint enforcement. Local accounts remain as the
   break-glass path (and the only path for air-gapped deployments).
2. **Per-matter access control (ethical walls)** — legal's distinctive
   requirement: conflicts of interest mean *this attorney must not see this
   matter*. The data model already keys everything by `matter_id`; this adds a
   matter↔user/group ACL checked in `catalog` and `filler`, and turns role
   checks into (role, matter) checks.
3. **TLS by default + hardened sessions** — built-in cert provisioning for
   LAN deployments; `Secure` cookies; optional mTLS between Verbatim and a
   remote-but-still-on-prem Ollama box (firms will want one shared GPU host).
4. **Key management** — envelope encryption so the data key can be wrapped by
   an OS keystore (DPAPI/Keychain) or a firm HSM/KMS; key rotation
   (re-encrypting run records is already a pure function of the store).
5. **Document-store encryption** — once uploads become the primary ingestion
   path (rather than files dropped into folders), uploaded case files get the
   same envelope encryption as run records, closing the FDE delegation.
6. **Compliance posture** — SOC 2 Type I on the hosted-management plane (the
   inference plane stays on-prem, which is the product), structured audit
   export (CEF/syslog) for the firm's SIEM, and a documented retention/
   deletion policy per matter.

The order matters: 1–2 are what legal IT actually asks first; 3–5 harden the
host story; 6 is what procurement asks last but takes the longest lead time.
