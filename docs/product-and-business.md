# Verbatim — Product & Business Overview

**Companion to `docs/design-spec.md`.** The design spec governs how artifacts
*look*; this document governs what they *say*. Hand both to Claude Design (or any
collaborator) when producing slideshows, interactive graphics, one-pagers, or
investor/firm materials. It is also a standalone explainer for friends, firms,
and investors.

**Honesty markers used below** (keep them straight when building decks):
- **[BUILT]** — exists and is verifiable in the repository today.
- **[DIRECTION]** — strategy/intent we believe but haven't executed.
- **[TO VALIDATE]** — a claim (market size, pricing, traction) not yet proven;
  do **not** present as established fact on a slide.

---

## 1. One-liner & elevator

**Verbatim is a privacy-preserving, self-hosted legal template assistant. It
fills a firm's document templates with facts transcribed from a matter's case
file — and every value carries a verbatim source quote, or it's flagged for a
human. All computation runs on hardware the firm controls; nothing privileged
ever leaves the building.**

Two ideas carry the whole product. Every slide should serve at least one:

1. **Custody / local-only.** The only network endpoint is a local model
   runtime (`localhost:11434`). No cloud, no telemetry, no third party — not
   even for login. A managing partner can tell a client *"your case never left
   our office"* and mean it literally.
2. **Refuses to guess.** A filled value must be grounded in the case file with a
   verbatim quote; anything ungroundable returns **`NEEDS REVIEW`** instead of a
   fabrication. *A blank left for a human is correct; a plausible-but-unsupported
   value is a defect.*

---

## 2. The problem

Lawyers spend hours transcribing the same facts — names, dates, dollar figures,
docket numbers — from a case file into firm templates (engagement letters,
demand letters, petitions, affidavits). It's rote, billable-hour-eroding, and
error-prone.

Generative AI is the obvious fix, but it collides with the one thing law firms
cannot compromise: **client confidentiality and privilege.** Sending privileged
case files to a third-party cloud model raises duties under the rules of
professional conduct, and — concretely — exposes that data to subpoena and
retention risk a firm doesn't control.

**Why now / why this is sharper than "firms are nervous about AI":** [BUILT as
research, see below]
- There is **no "AI privilege."** Material handed to a third-party model is
  reachable by subpoena; OpenAI's own CEO has publicly *asked* for such a
  privilege, which is an admission it doesn't exist.
- **Courts have already overridden vendor retention promises** — a 2025 order in
  *NYT v. OpenAI* forced preservation of logs users had "deleted," and notably
  exempted only the zero-data-retention API tier. Whether a firm's data gets
  swept into *someone else's* lawsuit depended on a contractual tier most firms
  never see.
- **The regulatory layer is churning** (state AI laws vs. federal preemption
  efforts), which means compliance-by-contract has to be continuously
  re-verified — and the target customer has no one whose job that is.

**The framing that wins:** *compliance by architecture, not by contract.* A cloud
assurance is a stack of promises (vendor terms, the upstream provider's tier, the
current regulatory moment). "It never left the building" is one sentence that
needs no re-checking when the rules shift. (Caveat for honesty: cloud AI is
*permitted* by current bar guidance with safeguards — Verbatim's edge is
removing the ongoing burden and the residual exposure, not claiming cloud is
forbidden.)

---

## 3. Who it's for

- **Primary segment [DIRECTION]:** small-to-mid US law firms (roughly under ~50
  attorneys) that hold privileged/PHI-laden matters but have **no procurement
  team, no in-house counsel for vendor DPAs, and no security staff** to vet a
  cloud tool. They feel the confidentiality risk most acutely and can least
  afford to manage it contractually.
- **The user:** an attorney or paralegal who needs a template filled and
  reviewed — three selections and one button.
- **The economic buyer:** the **managing partner** (risk + cost owner).
- **The gatekeeper:** the firm's **MSP / outside IT consultant** — the person who
  asks "is this safe, and who manages the box?" (`docs/security.md` is written
  for exactly this person.)
- **[TO VALIDATE]** market size and willingness-to-pay. There are tens of
  thousands of US firms in this band; the precise serviceable number and price
  point are not yet validated and should not be asserted as fact.

---

## 4. How it works (plain-language functionality)

Everything in this section is **[BUILT]** and demonstrable in the running app.

### 4.1 The three surfaces
- **Attorney Workspace** — pick a *matter*, a *template*, and a local *model*;
  press **Fill**. Get the filled document with each substituted value
  highlighted in place, a summary, a provenance panel, and `.docx` export.
- **Library** — create matters and upload case documents (drag-and-drop);
  upload firm templates. Nothing leaves the host.
- **Developer Console** (admin-only) — enumerate installed local models, assign
  a *style* to each template, flag filled fields correct/incorrect, read a
  per-(model, style) accuracy/latency report, manage user accounts, and inspect
  the audit trail.

### 4.2 The fill pipeline (the engine)
`case files → ingest + chunk → retrieve relevant passages → local LLM
(temperature 0, JSON mode) → ground every value against the source → assemble +
flag → immutable run record`. The model proposes; the system independently
**re-locates each value in the retrieved source text** and downgrades anything it
can't find to `NEEDS REVIEW`. Safety does not depend on the model obeying the
prompt.

### 4.3 Grounding & provenance (the trust layer)
Every filled value shows a **verbatim supporting quote and its source document
(and page, for PDFs)**. Conflicts between two candidate values abstain rather
than guess. The system prompt is hardened against prompt injection from
adversarial documents (opposing-counsel files are untrusted input) and is
**versioned**, so every run is attributable to the exact prompt that produced it.

### 4.4 Inputs it understands
PDF (incl. **OCR** for scanned/image PDFs), DOCX, TXT, MD, **EML** (email —
headers, body, and recursively the **content of attachments**), and **XLSX**
(spreadsheets, including computed totals). Oversized/hostile files are bounded.

### 4.5 Security controls
Authentication on by default (local accounts, hashed passwords, session
cookies, brute-force lockout), **role-based access control** (attorney vs.
admin, enforced server-side), **encryption at rest** for run records, and a
**tamper-evident, hash-chained audit log**. All local; no identity provider is
contacted. Full model and roadmap in `docs/security.md`.

### 4.6 It's measured, not asserted
An **evaluation harness** scores each field as correct, correct-abstention,
**fabrication** (the critical failure), wrong-value, or miss — and runs without a
live model so the safety contract is testable in CI. The headline so far: with
the runtime down, the pipeline fabricated **0** values and abstained correctly
**100%** of the time. **[TO VALIDATE]** live-model accuracy on real matters
(no GPU on the dev machine yet — see §7).

---

## 5. Why it's different / defensible

- **Architectural moat, not a prompt.** The differentiator is the
  *measured grounding contract* + local-only enforcement, not clever wording. A
  weekend Ollama-wrapper has neither the abstention guarantee nor the eval
  discipline.
- **Legal-specific machinery [BUILT].** Real firm blanks aren't `{{mustache}}` —
  they're underscores, `[ ]` checkboxes, `Label:` pairs, ALL-CAPS sentinels. A
  deterministic detector normalizes them (a shipped real template went from **0
  → 19** detected blanks). Plus per-field provenance and conflict abstention.
- **Incumbents structurally won't follow on-prem [DIRECTION].** Clio/Harvey/
  Spellbook own cloud workflow; shipping local inference breaks their SaaS
  economics and ops model. The self-hosted segment is the wedge they'll cede.
- **Next moat layer [DIRECTION]:** per-matter access walls (ethical/conflict
  walls) — legal's distinctive requirement — and SSO, both already isolated
  behind the auth layer so they swap in without touching enforcement.

---

## 6. Business model & go-to-market [DIRECTION / TO VALIDATE]

- **Form factor: an appliance, not software.** A small on-prem box (e.g. a Mac
  Mini-class machine, ~$1.5–2.5k) plugged into the firm's LAN; attorneys browse
  to it. Setup under an hour. *"Software is soft. Verbatim is not software."*
- **Pricing [TO VALIDATE]:** sell the hardware at/near cost (or let the channel
  supply it); charge **per-seat, per-month** for the software, priced against a
  paralegal hour. Specific numbers are unvalidated — don't print them as fact.
- **Channel: MSPs [DIRECTION].** Firms under ~50 attorneys use managed service
  providers, not in-house IT. MSPs decide what hardware enters the office and
  profit from managing it. Motion: win 2–3 reference firms directly, then sell
  *through* MSPs who install, update, and support the box.
- **Demo motion [BUILT/DIRECTION]:** bring the box; fill one of the firm's *own*
  templates live; **pull the network cable mid-fill and watch it still complete**
  — proving local-only in thirty seconds no cloud demo can match.

---

## 7. Status — honest snapshot

- **[BUILT]** End-to-end product: ingestion (6 formats + OCR + email
  attachments), retrieval, grounded fill with provenance and abstention,
  in-place highlighting, `.docx` export, run records. Auth + RBAC + encryption
  at rest + tamper-evident audit log. Hardened, versioned prompt. Evaluation
  harness with a measured zero-fabrication floor. ~65 passing tests. Runs fully
  offline; degrades gracefully when the runtime is down.
- **[TO VALIDATE] — the two gaps that matter most for a pitch:**
  1. **Users.** No paying firms yet. Reference pilots/usage are the single
     highest-value thing to obtain before an investor conversation.
  2. **Live accuracy number.** The dev machine has no GPU, so there's no
     published 7B–70B accuracy figure yet — only the model-off safety floor.
     One run on a model-capable machine closes this.
- **Roadmap [DIRECTION]:** per-matter ethical walls → SSO (OIDC/SAML) → TLS +
  hardened sessions → envelope key management → document-store encryption →
  SOC 2 on the management plane. Ordered in `docs/security.md`.

---

## 8. Suggested deck blueprint (for Claude Design)

A 10–12 slide arc that pairs with the visuals in `docs/design-spec.md`. Each
beat notes which brand idea (§1) and which diagram (design-spec §5) it uses.

1. **Cover** — wordmark on the steel gradient; the one-liner. *(custody)*
2. **The problem** — lawyers retype facts; AI is the fix but privilege is the
   wall. *(refuses-to-guess + custody)*
3. **Why now** — no AI privilege; courts override retention; regulatory churn.
   Compliance-by-architecture vs -by-contract. *(custody)*
4. **What Verbatim does** — the Attorney Workspace screen; three selections, one
   button. *(product screen, design-spec §4.1)*
5. **The core demo** — in-place highlighted document + provenance panel; the
   grounding tether diagram. *(refuses-to-guess, §4.2 + §4.4)*
6. **Refuses to guess** — the abstention fork (guess ✗ vs NEEDS REVIEW → human
   ✓); the zero-fabrication eval result. *(refuses-to-guess, §5 diagram)*
7. **Local-only** — the pipeline-with-custody-boundary diagram; the cable-pull
   beat. *(custody, §5 + §6 motion)*
8. **Security/trust** — auth, RBAC, encryption, the tamper-evident audit trail.
   *(product screen)*
9. **Who it's for + the appliance** — the box in the office, LAN to desks, no
   line to the internet. *(custody, §5 appliance diagram)*
10. **Go-to-market** — direct → MSP channel; the demo motion.
11. **Status & ask** — honest snapshot (§7); what's built, what's next, the ask.
12. **Close** — *"Your privileged files never leave the building — and Verbatim
    never guesses."*

> Guardrail for the deck: keep **[TO VALIDATE]** items (market size, pricing,
> traction, live accuracy) visibly hypothesis-framed. Verbatim's credibility
> comes from intellectual honesty — a deck that overclaims undercuts the very
> trustworthiness that is the product's whole thesis.

---

*Substance derived from the Verbatim codebase, `SPEC.md`, `docs/security.md`,
`docs/technical-analysis.md`, and founder strategy. Where this doc and the
running product disagree, the product is authoritative; where a business claim
isn't marked [BUILT], treat it as direction to validate, not fact.*
