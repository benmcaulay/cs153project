# Security

Verbatim's core security property is architectural: **no case data ever leaves
the host.** The only outbound network call in the entire application is to an
Ollama runtime on the local host (`OLLAMA_HOST`, default `localhost:11434`).
There is no telemetry, no third-party API, and no cloud dependency.

## Threat model

Verbatim is designed for deployment on hardware controlled by a law firm — a
workstation or an internal server. The assets being protected are privileged
case files, attorney work product, and PHI. The primary threats addressed:

| Threat | Control |
|---|---|
| Case data exfiltration to a third party | Architecturally impossible: no outbound calls except local Ollama |
| Unauthorized API access on a shared host/network | Bearer-token auth (`VERBATIM_API_TOKEN`) |
| Reading derived case facts off disk | Encryption at rest for run records + config (`VERBATIM_DATA_KEY`) |
| Path traversal via uploaded filenames | Sanitization in `catalog.safe_filename` / `safe_matter_folder` |
| Oversized uploads | 25 MB per-file limit |
| Cross-origin requests from arbitrary sites | CORS restricted to local origins (extend via `VERBATIM_ALLOWED_ORIGINS`) |
| Fabricated legal facts (the domain's defining risk) | Grounding validation + `NEEDS_REVIEW` contract, measured by the eval harness |

## Configuration

```bash
# Require a bearer token on every /api/* request (except /api/health):
export VERBATIM_API_TOKEN="$(openssl rand -hex 32)"

# Encrypt run records and config at rest (Fernet / AES-128-CBC + HMAC):
export VERBATIM_DATA_KEY="$(python -m app.security --generate-key)"

# Allow an additional origin (e.g. an internal hostname):
export VERBATIM_ALLOWED_ORIGINS="http://verbatim.firm.internal:8000"
```

Both controls are **off by default** so the single-user, single-command local
demo works unchanged. Enable both for any multi-user or networked deployment.

## Scope of encryption at rest

`VERBATIM_DATA_KEY` encrypts what Verbatim *derives*: run records (which embed
extracted case facts, quotes, and filled documents) and the local config.
Source case documents are intentionally not re-encrypted by the application —
they live in the firm's document store and should be protected by full-disk
encryption (FileVault, BitLocker, LUKS) or the DMS's own controls. Records
written before a key was configured remain readable after enabling encryption;
all subsequent writes are encrypted. A wrong key fails loudly rather than
silently skipping records.

## Known limitations (single-host prototype boundary)

These are required before deployment beyond a single trusted host:

- **No multi-user RBAC** — one token grants full access; there are no per-user
  identities, roles, or matter-level permissions (ethical walls).
- **No audit log** — run records are immutable but access is not logged.
- **No TLS termination** — bind to 127.0.0.1 or put a reverse proxy with TLS
  in front for any network exposure.
- **No SSO/SCIM** — required for firm-wide identity integration.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository, or contact the
maintainer directly. Please do not file public issues for vulnerabilities.
