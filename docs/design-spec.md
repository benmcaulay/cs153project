# Verbatim — Visual & Brand Spec for Claude Design

**Purpose.** This document gives Claude Design everything needed to produce
on-brand slideshows and interactive graphics for **Verbatim** — a
privacy-preserving, self-hosted legal template assistant. The goal is that any
deck, animation, or interactive demo *looks like it came from the same studio
as the product*. Pixel values, colors, fonts, and component anatomy below are
extracted verbatim from the shipping app, not approximated.

> One-line positioning (use as the spine of every narrative):
> **"Your firm's privileged case files never leave the building — and Verbatim
> never guesses."**

---

## 0. How to use this spec

- Treat **Section 2 (Design tokens)** as the single source of truth for color,
  type, spacing, and radius. Don't invent new colors; pull from the palette.
- When recreating a product screen, use **Section 4 (Signature components)** —
  each lists exact classes/values so a mock matches the real UI.
- For motion, use **Section 6**. Keep it restrained: this is legal software,
  not a consumer app. Confidence reads as *calm*, not *flashy*.
- The two ideas every artifact must communicate are in **Section 1**. If a
  slide doesn't serve one of them, cut it.

---

## 1. Brand essence (the two non-negotiable ideas)

Verbatim's entire pitch reduces to two visual/emotional beats. Every graphic
should reinforce at least one:

1. **Local-only / custody.** Nothing leaves the firm's hardware. Visual
   language: a boundary, a building, a single machine, an air-gap, a severed
   network line. The hero moment in the live demo is *pulling the ethernet cable
   and the fill still completes.* Recreate that feeling — containment, not cloud.

2. **Refuses to guess / grounded.** Every filled value carries a verbatim quote
   and its source document; anything ungroundable is flagged `NEEDS REVIEW`
   rather than fabricated. Visual language: a highlighted value tethered to its
   source quote; a calm amber "needs review" marker that reads as *responsible*,
   not *error*.

**Tone:** authoritative, precise, understated, trustworthy. Think a modern
law-firm brand crossed with developer-grade precision. Avoid: AI clichés (glowing
brains, neon gradients, robot imagery), playful illustration, hype.

**Brand names:** Product is **Verbatim**. The demo firm is the fictional
**Straus Meyers LLP** (steel-blue wordmark, "‖" divider glyph between the two
words). Tagline under the logo: *"Local legal template assistant."*

---

## 2. Design tokens (source of truth)

### 2.1 Color — light mode (primary)

The product is a **steel-blue legal theme** on near-white. All values are the
real CSS variables; hex equivalents are provided for tools that prefer hex.

| Role | HSL | Hex | Usage |
|---|---|---|---|
| `background` | `210 20% 98%` | `#F9FAFB` | App canvas / slide background |
| `foreground` | `210 50% 15%` | `#132639` | Primary text (near-navy, not black) |
| `card` | `210 15% 97%` | `#F6F7F8` | Card / panel surfaces |
| `primary` (steel-500) | `210 35% 45%` | `#4B739B` | **Brand color** — buttons, links, highlights |
| `muted` | `210 15% 92%` | `#E8EBEE` | Subtle fills, toggle tracks |
| `muted-foreground` | `210 25% 45%` | `#56738F` | Secondary text, labels |
| `border` | `210 20% 85%` | `#D1D9E0` | Hairline borders (1px) |
| `destructive` | `0 84% 60%` | `#EF4444` | Errors only |

**Steel-blue scale** (the signature ramp — use for depth, charts, gradients):

| Step | Hex | | Step | Hex |
|---|---|---|---|---|
| 50 | `#EEF2F6` | | 500 | `#4B739B` ← brand |
| 100 | `#E3E9F0` | | 600 | `#36597D` |
| 200 | `#C6D3E0` | | 700 | `#23405C` |
| 300 | `#A9BCD0` | | 800 | `#15293D` |
| 400 | `#6A8CAF` | | 900 | `#0E1F2F` |

**Semantic accents** (used sparingly, only with meaning):
- **Success / "filled" / "runtime online":** Tailwind `green-600` `#16A34A`,
  on `green-50` `#F0FDF4` with `green-300` border.
- **Caution / "needs review":** Tailwind `amber` — text `amber-900` `#78350F`,
  fill `amber-100` `#FEF3C7`, ring `amber-400` `#FBBF24`. **This amber is a
  brand-critical color** — it's the visual signature of "we abstained
  responsibly." Always reads warm/calm, never alarming.
- **Info / diagnostics:** Tailwind `sky` — `sky-50` bg `#F0F9FF`, `sky-300`
  border, `sky-900` text.

**Signature gradient** (`gradient-steel`): `linear-gradient(135deg, #36597D 0%, #6A8CAF 100%)`
— steel-600 → steel-400. Use for hero panels, cover slides, section dividers.

### 2.2 Color — dark mode (optional, for dramatic cover/section slides)

Deep navy canvas: `background 210 55% 8%` `#091521`, `card #0D1B2A`,
`foreground 210 20% 95%` `#EDF1F4`, `primary` brightens to `210 35% 55%`
`#6A8CAF`. Use dark mode for cover/transition slides and the "local & private"
hero; use light mode for anything replicating the actual product UI.

### 2.3 Typography

- **Family:** `Inter` (system-ui / sans-serif fallback). Everything is Inter.
  Monospace (for filenames, code, docket numbers) is the platform mono stack
  (`ui-monospace, SFMono-Regular, Menlo, monospace`).
- **Scale & weight** (as used in product):
  - Page title (`H1`): 30–36px, **bold (700)**, color `foreground`.
  - Section/card title: 18–20px, **semibold (600)**.
  - Body / subtitle: 16–18px, regular, `muted-foreground`.
  - Metric value: 20px, **bold**.
  - Labels / chips / captions: 12px, medium, `muted-foreground`, often
    uppercase-tracked for role badges (e.g. `ADMIN`).
  - Provenance quote: 12px, *italic*, `muted-foreground`.
- **Tracking:** tight on headlines (`tracking-tight`), normal elsewhere.

### 2.4 Spacing, radius, shadow

- **Radius:** base `--radius: 0.5rem` (8px). Cards/buttons `lg = 8px`,
  inner chips `md = 6px`, small `sm = 4px`. Dashed dropzones `8px`.
- **Container:** centered, max-width **1400px**, horizontal padding `2rem`.
- **Card padding:** 20–24px; compact panels 12px.
- **Borders:** 1px hairline in `border` `#D1D9E0`. The aesthetic is
  **border-defined, low-shadow** — depth comes from hairlines and subtle
  `muted` fills, not heavy drop shadows. Header uses a soft `backdrop-blur` with
  an 80%-opacity card background.
- **Gaps:** grid gaps 12–24px; icon-to-text gap 8px.

### 2.5 Iconography

- **Library:** Lucide (thin, 1.5–2px stroke). Never use filled/3D icons.
- **Canonical icons** (reuse these exact metaphors for consistency):
  `Scale` (Attorney Workspace), `Wrench` (Developer Console), `FolderUp` /
  `FilePlus2` (Library/upload), `ShieldCheck` (runtime online / privacy),
  `ShieldOff`/`ShieldAlert` (offline / caution), `Lock` (auth), `Quote`
  (provenance), `CheckCircle2` (filled), `AlertTriangle` (needs review),
  `Clock` (latency), `Cpu` (model), `Info` (diagnostics).
- Icon size in UI: 16px (`h-4 w-4`) inline, 20px (`h-5 w-5`) in titles.

---

## 3. Layout system

- **App shell:** sticky top **Header** (logo left, nav/controls right) over a
  full-width canvas; content in the centered 1400px container.
- **Header anatomy** (recreate for product-frame slides): firm logo (44px tall)
  + a vertical divider + stacked wordmark ("**Verbatim**" bold / "Local legal
  template assistant" 12px muted). Right side holds the **surface toggle** (a
  segmented pill control) and, when authed, a user chip (`UserCircle2` + name +
  uppercase role badge) and a "Sign out" button.
- **Surface toggle:** a `rounded-lg` pill with `muted/40` track and 1px border;
  the active segment is a solid **primary** (`#4B739B`) chip with white text and
  an icon; inactive segments are `muted-foreground` text only. Three segments:
  *Attorney Workspace · Library · Developer Console*.
- **Status badge** (top-right of a surface): pill, 1px border, 12px medium text
  with a leading icon. Online = green family (`ShieldCheck`, green-50/green-300/
  green-700). Offline = amber family (`ShieldOff`).
- **Vertical rhythm:** stacked cards separated by 24px; each card = title row +
  optional description + content.

---

## 4. Signature components (replicate these exactly)

These four are what make a screenshot unmistakably *Verbatim*. Prioritize them.

### 4.1 The Fill form (the "one button" hero)

A single card titled **"Fill a template from a matter"** with a wand icon. Below
a one-line description, **three dropdowns in a row** — *Matter · Template ·
Local model* (each a bordered `select` with a chevron; the model select shows a
`Cpu` glyph and a monospace model id like `qwen2.5:7b`). A helper line reads
*"Engagement Letter has [9 blanks] to fill."* with the count in a small chip.
Then a **full-width primary Fill button** with a wand icon. This is the
"three selections and one button" promise — keep it that clean.

### 4.2 In-place highlighted document ★ (the core visual)

The filled document rendered as flowing text with substitutions highlighted
**in place**. This is the single most important visual in the product.

- **Transcribed value** — wrapped in a `<mark>`:
  `background: primary @ 15% opacity` (`#4B739B26`), `text: primary` `#4B739B`,
  **medium weight**, `4px` radius, `1px` ring at `primary @ 30%`, `4px`
  horizontal padding. On hover, a tooltip shows `source_document: "quote"`.
- **Needs-review marker** — a `<span>`: `background amber-100` `#FEF3C7`,
  `text amber-900` `#78350F`, **semibold**, `1px` amber-400 ring, rendered as
  `[Field Label — NEEDS REVIEW]`.
- Document container: `muted/20` fill, `20px` padding, `8px` radius, 1px border,
  scrollable (max-height ~28rem). Body text 14px, relaxed leading, sans.
- **A legend sits above it:** two tiny swatches — a primary swatch labeled
  *"transcribed value"* and an amber swatch labeled *"needs review."* Always
  include this legend; it teaches the metaphor in one glance.

### 4.3 Fill-summary metric cards

A 4-up grid (2-up on mobile) of small stat cards, each: `muted/30` fill, 1px
border, 8px radius, 12px padding. Top row = 12px muted label + tiny icon; below
= 20px bold value. Tones: **filled** value in green-600, **needs-review** in
amber-600 when > 0, others in foreground. The four metrics:
*Blanks filled `0/9` · Needs review `9` · Inference time `0.00s` · Model
`qwen2.5:7b`*. A green **"Export .docx"** primary button sits in the card title
row (download icon).

### 4.4 Provenance panel ★ (the "refuses to guess" proof)

A card titled **"Provenance"** (`Quote` icon). Each field is a bordered
`8px`-radius row:
- Left: field **label** (14px medium).
- Right: if filled — an optional `conf 92%` outline badge + a **value badge** in
  primary-15% fill / primary text. If not — a **`NEEDS REVIEW`** outline badge in
  amber-700 with amber-400 border.
- Below, for filled fields: an *italic* 12px quote line with a `Quote` glyph —
  `"verbatim quote" — filename, p. 3` (filename in mono).
- For review fields: a 12px amber line explaining why, optionally with the
  model's own note in italics (*Model's note: "conflicting amounts…"*).

This panel is the literal embodiment of the safety claim — feature it whenever
the narrative is about trust/grounding.

### 4.5 Supporting UI (for completeness)

- **Login screen:** centered max-width card, `Lock` title "Sign in to Verbatim",
  subtitle *"Case material is privileged. Access requires a firm account."*,
  username/password fields, full-width primary "Sign in", and a footer line with
  a `ShieldCheck`: *"Authentication, like everything else in Verbatim, is local
  to this host. No identity provider or third-party service is contacted."*
- **Developer Console:** tabbed card (*Models & Styles · Performance · Run Audit
  · Access*) with data tables; the **Access** tab shows a users table (role
  badges) and a **tamper-evident audit trail** with a green "hash chain intact"
  / red "TAMPERED at line N" status — good material for the security slide.
- **Status diagnostics:** amber alert box (`AlertTriangle`, amber border/bg) for
  "Inference did not complete," sky-blue info box for partial fills. These model
  the product's honesty — it explains *why* a blank is empty.

---

## 5. Diagram & graphic vocabulary (for original slides)

When making *new* explanatory graphics (not screen recreations), use this
consistent visual grammar:

- **The pipeline** (recurring hero diagram). Left→right flow:
  `case files (PDF · DOCX · EML · XLSX) → ingest + chunk → retrieve → local LLM
  (Ollama, temp 0, JSON) → grounded fill + provenance → NEEDS_REVIEW flags`.
  Render as connected nodes in steel-blue; the **LLM node sits inside a labeled
  boundary box** ("the firm's hardware / localhost only") with **no arrow
  leaving it** — visually proving nothing exits. A single dotted line to a
  greyed-out "Cloud" node, crossed out, drives the point home.
- **Custody boundary:** a rounded container (the office/building/box) enclosing
  all compute; client data dots stay inside; the only port is `localhost:11434`.
- **Grounding tether:** a filled value connected by a short line to a quoted
  snippet of a source document — the atomic unit of "provenance."
- **Abstention, not fabrication:** a fork — one path "guess" (red, crossed out),
  one path "NEEDS REVIEW → human" (amber, checkmarked). Always frame abstention
  as the *correct* branch.
- **Appliance / MSP story:** a single physical box icon in an office, LAN lines
  to attorney desks, no line to the internet. (Tagline the founder likes:
  *"Software is soft. Verbatim is not software."*)
- **Charts:** use the steel-blue ramp for series; amber only for a
  "fabrication / risk" series so it stands out as the thing to avoid. Keep
  axes hairline `#D1D9E0`, labels in `muted-foreground`. Flat, no 3D, no heavy
  gridlines.

---

## 6. Motion & interaction (for interactive graphics / animated slides)

Restrained, purposeful, fast. The product's own animations are the reference:

- **Entrances:** `fade-in` = opacity 0→1 + 10px upward translate, **300ms
  ease-out**. `scale-in` = 0.95→1 scale + fade, **200ms ease-out**. Use these
  for cards/elements appearing; never bounce.
- **Reveal the fill:** animate values dropping into blanks sequentially, each
  with a brief highlight "pulse" (ring opacity 30%→60%→30%). Then reveal the
  provenance quote underneath. This staged reveal *is* the demo.
- **The cable-pull beat:** for the privacy hero, animate a network line
  severing / a cloud node greying out while the local pipeline keeps running and
  completes a fill — proving local-only. This is the highest-impact moment;
  give it room.
- **Hover affordances:** subtle — background shifts to `accent/30`, links
  underline, buttons darken to `primary/90`. Transitions ~150ms.
- **Tone:** ease-out, short durations (150–300ms), no springy overshoot. Calm
  and exact, matching the "meticulous transcription" brand.

---

## 7. Copy & voice

- **Voice:** precise, plain, quietly confident. Short declaratives. No hype words
  ("revolutionary," "magic," "AI-powered"). Let the mechanism impress.
- **Reusable lines** (already brand-true):
  - *"Transcribe facts from a matter's case file into a private,
    provenance-backed template."*
  - *"Refuses to guess. Every value carries a verbatim quote and its source —
    or it's flagged for review."*
  - *"All computation runs on hardware the firm controls. The only network
    endpoint is a local Ollama runtime."*
  - *"A blank left for human review is correct. A plausible-but-unsupported
    value is a defect."*
  - *"Draft only — a licensed attorney reviews and finalizes every output."*
- **Capitalization:** product surfaces are Title Case ("Attorney Workspace");
  the abstention sentinel is always literal uppercase **`NEEDS REVIEW`** /
  `NEEDS_REVIEW`.
- **Numbers/provenance formatting:** `"quote" — filename.pdf, p. 3`
  (filename monospace). Model ids monospace (`llama3.1:8b`).

---

## 8. Asset checklist for Claude Design

To perfectly replicate, have these ready / generate these:

- [ ] **Logo:** Straus Meyers LLP wordmark (steel-blue, "STRAUS ‖ MEYERS / LLP").
      If the real PNG isn't supplied, recreate as an Inter-bold wordmark with the
      `‖` divider glyph in `primary`.
- [ ] **Font:** Inter (all weights 400/500/600/700) embedded.
- [ ] **Color styles:** load the Section 2 palette as named styles/variables
      (don't hand-pick hex per element).
- [ ] **Component library:** build the four signature components (4.1–4.4) once
      as reusable blocks, then compose slides from them.
- [ ] **Screenshot frames:** a light-mode "product window" frame (rounded corners,
      hairline border, subtle top chrome) to drop UI mocks into.
- [ ] **Icon set:** Lucide, thin stroke, in `foreground`/`muted-foreground`/
      `primary` per context.

---

## 9. Do / Don't

**Do:** steel-blue + near-white, hairline borders, Inter, calm amber for
abstention, lots of whitespace, border-defined depth, restrained ease-out
motion, the pipeline-with-boundary diagram, provenance tethers.

**Don't:** pure black text (use `#132639`), heavy drop shadows, neon/glow,
gradients outside the steel ramp, AI-brain/robot imagery, playful illustration,
red except for true errors, amber used as "error" (it means *responsible
abstention*), bouncy/springy animation, more than the three brand color
families on one artifact.

---

*Spec derived directly from the Verbatim codebase (Tailwind theme, `index.css`
tokens, and the Attorney Workspace / FilledDocument / Provenance components).
When in doubt, the running product at the steel-blue light theme is the
authority.*
