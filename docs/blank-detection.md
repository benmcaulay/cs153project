# Blank Detection — Design Notes

**Issue:** "How am I going to get the computer to recognize what blanks look
like? What degree of standardization is necessary / what can the model infer?"

**Observed symptom:** Four real firm templates (`Allstate_Depo_SUR_Template.docx`,
`Depo_SUR_Template.docx`, `Affidavit_of_Heirs.docx`, `Caption.doc`) all imported
as **0 blanks**.

## Why everything scored 0

The current detector recognizes exactly one convention: `{{key}}` / `[[key]]`
(optionally `{{key | instruction}}`). **None** of the real templates use it.
Lawyers don't author templates in mustache syntax — they mark blanks the way
they've marked them on paper for 40 years. So the detector found nothing.

The lesson: we cannot assume the firm's existing library is, or ever will be,
authored in our markup. Detection has to meet the documents where they are.

## What blanks actually look like (evidence from the 4 templates)

Every one of these is a real "fill-in" the detector must learn to see:

| # | Convention | Real examples | Signal type |
|---|-----------|---------------|-------------|
| 1 | **Underscore runs** | `residing at ____________`, `____ years old`, `20______`, signature `____________` lines | text (regex) |
| 2 | **Yellow highlighting** | Allstate/Depo mark *every* matter-specific field in yellow: `XXX@allstate.com`, `Claim No.`, `Case No.`, `Date of Loss`, caption, `Dear XXX:` (38 and 35 highlighted runs respectively) | **formatting (OOXML)** |
| 3 | **ALL-CAPS sentinel tokens** | `NAME`, `XXX`, `XXXX`, `XXX@allstate.com` | text + semantics |
| 4 | **Bracketed spaced spans** | Caption: `[                     ]`, `DATED:[           ]` | text (regex) |
| 5 | **Checkbox brackets** | Caption proof-of-service: `[  ]` / `[X]` (select-one / multi) | text (regex) |
| 6 | **Label : value pairs** | `Claim No. :`, `Case No. :`, `Date of Loss :`, `Our File No. :` | text (pattern) |
| 7 | **Empty table cells / repeating rows** | Affidavit children & siblings grids — whole empty rows, one per child | **structure (OOXML)** |
| 8 | **Inline instructions written as prose** | `3 Sentences of Info from Database`, `On date, 2023`, literal lowercase `caption` | **semantics (needs LLM)** |
| 9 | **Inline choice prompts** | `Yes / No`, `a.m./p.m.`, `adopted or step-child`, `his (or her)` | semantics |

Note #2 especially: the firm has *already done our job for us* by highlighting
variable fields in yellow. Plain-text extraction throws that signal away. We
must read the `.docx` at the OOXML run level (`<w:highlight>`, `<w:u>`), not as
flattened text.

Also note `Depo_SUR_Template.docx` is a **filled** example (the Little/Marriott
narrative) while `Allstate_Depo_SUR_Template.docx` is the **blanked** version of
the same letter (`NAME`, `3 Sentences of Info from Database`). The diff between a
filled instance and its template is itself a strong blank-detection signal.

## Recommended approach: normalize-at-import, three tiers

The key reframing: **detection runs once, at template import, and produces a
canonical template a human approves.** We don't detect blanks at generation
time. We convert messy → canonical, show the human what we found, let them
fix/confirm, and store the result. After approval, generation is deterministic.

So the question "what degree of standardization is necessary?" has a freeing
answer: **almost none on the input.** We standardize the *output* of detection
(a canonical schema), not the documents the firm already owns.

### Tier 1 — Canonical markup (the standard we enforce going forward)
Adopt `{{key}}` and `{{key | instruction}}` as the stored, post-approval format.
New templates *can* be authored directly in it (highest precision, zero
guessing). Every legacy template gets converted into it by Tiers 2–3.

### Tier 2 — Deterministic heuristics (cheap, local, explainable)
Regex/structure rules for the unambiguous physical signals — conventions
1, 2, 4, 5, 6, 7 above. These need no model, run instantly, and we can show the
user exactly why each was flagged. Examples:
- `_{3,}` → free-text blank (length hints at expected size)
- `\[\s{2,}\]` → bracketed blank; `\[\s*[Xx ]\s*\]` → checkbox
- OOXML run with `w:highlight="yellow"` → blank (carry the existing text as the
  default/example value and as a naming hint)
- `<label> :` at line/cell start with empty value → labeled field, key = label
- empty `<w:tc>` cells in a table → tabular/repeating field group

### Tier 3 — LLM inference (the ambiguous, semantic cases)
Conventions 3, 8, 9 can't be caught by regex without huge false-positive risk
("NAME" vs. a real surname, prose-instructions vs. boilerplate). Hand the
document to the model and ask it to: locate likely blanks, propose a `key`, a
human-readable `label`, an `instruction` (e.g. *"3 sentences summarizing prior
claims, sourced from case DB"*), and a `confidence`. The model is also what
reads conventions like `Yes / No` and proposes an enum field.

### The human-in-the-loop step (this is what makes low standardization safe)
Import produces a **review screen**: each candidate blank shows its location,
detected type, proposed key/instruction, source signal, and confidence.
High-confidence Tier-2 hits are pre-checked; low-confidence Tier-3 guesses ask
for confirmation. The lawyer corrects once, and we persist the canonical
template. This converts "the model has to be perfect" into "the model has to be
a good first draft" — a far lower bar, and it's auditable.

## Proposed normalized schema (output of detection)

```jsonc
{
  "templateId": "allstate_depo_sur",
  "format": "docx",
  "blanks": [
    {
      "key": "claim_no",
      "label": "Claim No.",
      "type": "text",            // text | date | currency | enum | longform | table
      "instruction": null,        // free-text guidance for the generator/LLM
      "source": "highlight",      // highlight | underscore | bracket | checkbox | label | table | llm
      "confidence": 0.95,
      "anchor": { "para": 7, "run": 3 },  // where to write back in the OOXML
      "example": "1E01E014381047A"        // value found in the template, if any
    },
    {
      "key": "deposition_background",
      "label": "Background",
      "type": "longform",
      "instruction": "3 sentences of background info, sourced from case database",
      "source": "llm",
      "confidence": 0.6
    }
    // enum example: { "key": "service_method", "type": "enum",
    //                 "options": ["mail","personal","facsimile","overnight","electronic"] }
    // table example: { "key": "decedent_children", "type": "table",
    //                  "columns": ["name","age","address","living","date_of_death"] }
  ]
}
```

## Implementation status

**Tier 1 (markup) and Tier 2 (deterministic) are implemented** in
`app/blank_detect.py`, wired into `app/templates.py:read_template_text`.
Normalization rewrites every detected blank to canonical `{{key | instruction}}`
at read time, so detection, filling, and provenance work unchanged. The `.docx`
reader operates at the OOXML run level, preserving the yellow-highlight signal.

Detected on the example templates (previously **0** for all):

| Template | Blanks detected | Primary signals |
|----------|-----------------|-----------------|
| Allstate Depo SUR | 10 | highlighted runs |
| Depo SUR | 10 | highlighted runs |
| Affidavit of Heirs | 36 | underscore fill-lines + empty table columns |

Sample templates (`demand_letter` 14, `engagement_letter` 9, `probate_petition`
9) are unchanged — existing markup is protected and signature underscores that
hug a `{{field}}` are suppressed. Covered by `tests/test_blank_detect.py`.

**Not yet implemented:** Tier 3 (LLM inference for free-form ALL-CAPS sentinels,
inline prose instructions, choice prompts), the import review screen (FR-5.3),
and legacy binary `.doc` parsing (only `.docx`/`.txt`/`.md` today).

## Concrete next steps
1. Parse `.docx`/`.doc` at the OOXML level so the **yellow-highlight** signal
   (the firm's strongest intentional marker) survives. Don't detect on flattened
   text.
2. Build the Tier-2 deterministic pass first — it alone would turn these four
   "0 blank" templates into dozens of correct hits.
3. Layer Tier-3 LLM inference for sentinels/instructions/choices.
4. Ship the import review screen; persist approved templates as canonical
   `{{key}}` markup with the schema above.
5. Use filled/blank pairs (like the two Depo letters) as eval fixtures to
   measure detection precision/recall.
