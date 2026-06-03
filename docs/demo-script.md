# Verbatim — Demo Script (post-intro)
*Page-separated. Each page is one beat. [ON SCREEN] is the action; the rest is spoken. Written for ~10 min at an average pace, so a fast talker lands near 7. Pages 7 and 8 are the easiest to trim if you run long — but do **not** trim Page 6.5, it carries the evaluation points.*

---

## PAGE 0 — Intro  *(ALREADY RECORDED — do not re-record)*

Hello everyone. My name is Ben McAulay, and I'm excited to welcome you to my frontier project demo of Verbatim. The major AI tools in the legal market today are Harvey, CoCounsel, and Lexis+ AI. They are capable systems, and they share one architectural decision: documents are sent off-device and processed in the vendor's cloud. For a large amount of legal work, that is acceptable. But many legal documents being fed through online LLMs today also include medical records, settlement files, and protected health information.

Every transfer to an external server is an additional point of exposure, whether through a breach, a leak, or a discovery request. And as competition for training data increases, the incentives behind these vendors' data practices are likely to grow more aggressive over time, not less. That exposure is the problem Verbatim is built to solve. The question I started with was whether the AI needs to leave the office at all.

Verbatim is a template-based legal document auto-filler that runs entirely locally. The language model runs on-device through Ollama. The OCR pipeline, which reads text from scanned PDFs, also runs locally, through Tesseract and Poppler. No document is sent to the cloud, because there is no external call anywhere in the pipeline. To test it under real conditions, I ran a pilot with Straus Meyers, a midsize insurance defense firm in San Diego.

On my desktop computer, with models as small as 8 billion parameters, I've achieved a high level of accuracy with a runtime within two minutes. As we've heard throughout the class, with the rapid speed of advancement and efficiency of new AI models, fully local and private LLM systems become more feasible every day. I anticipate that in the near future, localized artificial intelligence will be a symbol of ultimate privacy, and nowhere is it in higher demand than the legal sphere.

Verbatim is designed to work alongside an attorney rather than replace one. It handles the repetitive extraction and filling, and the legal judgment stays with the lawyer. Because every step runs on the firm's own hardware, the most sensitive work never leaves the office.

---

## PAGE 1 — Into the demo: the one rule

[ON SCREEN: Attorney Workspace, empty form, "Local model runtime online" badge visible]

Let me show you how it actually works. This is the Attorney Workspace. An attorney makes three choices: a matter, which is the case file for a client, a template to fill, and a local model to run it on. From there, everything happens on this machine.

Under the hood, Verbatim is a retrieval-augmented generation system. But there is one rule that governs everything you are about to see: a value only appears in the finished document if it can be traced back to a specific passage in the case file. Nothing is invented. Let me walk through how that guarantee is built and enforced, one stage at a time.

---

## PAGE 2 — Stage one: ingestion

[ON SCREEN: open the Matter dropdown, select a matter; if possible show the case folder or a scanned PDF in it]

The first stage is ingestion. When I select a matter, Verbatim reads every file in that matter's folder: PDFs, Word documents, plain text, and Markdown. It splits each one into overlapping passages of about eleven hundred characters, and it breaks on paragraph and sentence boundaries, so each passage is a coherent piece of text rather than a fragment cut off mid-sentence.

PDFs are the difficult case, because real firm documents are often scanned images or encrypted files. Verbatim first tries to decrypt with an empty password, which handles the common situation where a document is technically protected but not actually locked. If a page still has no readable text, it falls back to OCR: it rasterizes the page with Poppler and runs Tesseract over the image to recover the words.

That OCR path is optional. The system checks whether Tesseract and Poppler are installed, and if they are not, the document is flagged for review instead of crashing the run. This is a theme you will see throughout: the pipeline never fails silently, and it never fails loudly. It degrades safely.

---

## PAGE 3 — Stage two: making sense of the template

[ON SCREEN: show a raw firm template with underscores, bracketed checkboxes, and yellow-highlighted blanks]

The second stage handles the template, and this is harder than it looks. Lawyers do not mark blanks in any single, consistent way. A few use placeholder markup, but most do not. They use runs of underscores, bracketed checkboxes, a label followed by a colon, all-caps words like NAME, the letters X-X-X, and yellow highlighting.

If a template already uses explicit placeholder markup, Verbatim honors it exactly. When it does not, a blank detector takes over. For Word documents, it reads at the underlying XML level rather than flattening the file to plain text, because flattening would throw away the highlighting, and highlighting is the firm's strongest signal that a spot needs to be filled. It then runs a set of deterministic detectors for underscores, bracket spans, checkboxes, the X-X-X sentinels, and empty table columns, and it gives each blank a key and a readable label taken from the words in front of it.

The payoff is that no matter how the lawyer authored the document, it gets rewritten into one canonical form. Everything after this point, the detection, the filling, and the provenance, operates on that single representation.

---

## PAGE 4 — Stage three: retrieval, and the bug that taught me the most

[ON SCREEN: press Fill; the run starts; if there is a retrieval-mode or progress indicator, point to it]

Now I press Fill, and the third stage begins: retrieval. For each blank, Verbatim builds a search query from the blank's key, its label, and any instruction attached to it, and it finds the passages in the case file most likely to contain that answer.

It chooses its retrieval method automatically. If an embedding model is installed, it uses dense semantic search over embeddings generated locally through Ollama, and it caches those embeddings so it is not rebuilding the index on every run. If no embedding model is present, it falls back to a pure-Python keyword index, so the tool still works on a minimal install.

There is one design choice here worth calling out, because it was the single biggest fix in the project. Early on, the first few blanks would consume the entire context budget and leave the later blanks with nothing, so most of the document came back unfilled. The fix was to interleave passages round-robin: every blank contributes its best passage before any blank contributes its second. That one change is the difference between a document with thirty blanks filling correctly and one that comes back as mostly review flags.

---

## PAGE 5 — Stage four: extraction

[ON SCREEN: the run in progress; the model working locally]

The retrieved passages and the full list of blanks are assembled into a single grounded prompt and sent to the local model through Ollama. The model runs in JSON mode at temperature zero, so the output is structured and repeatable rather than creative, and the context window is raised so a prompt built from several documents is not quietly truncated.

The extractor is a swappable component, and that detail matters more than it sounds. Because the model is injected rather than hard-wired in, I can run the exact same pipeline with no model at all, as an offline baseline. That is how I measure whether the system is actually adding value over a naive approach, instead of just trusting that it is. And when the model answers, Verbatim is forgiving about the shape of that answer: whether it returns the agreed format, a flat object, or a plain list, the fields are matched back to the template by key and then by label, so a slightly off-format response still fills blanks instead of being discarded.

---

## PAGE 6 — Stage five: grounding and provenance  *(the core of the project)*

[ON SCREEN: the filled template appears; zoom on a filled blank and its provenance line; click through to the source passage; then show the .docx export with the provenance appendix]

This last stage is the one that matters most, and it is where the privacy promise becomes an accuracy promise. For every blank, the model's answer is checked against the actual text of the case file. Verbatim looks for that answer as a direct quote inside a retrieved passage, or as a strong word-for-word overlap with one. If the answer is supported by the source text, it becomes a filled value, and it carries the exact quote and the source document along with it. If the answer cannot be located in the case file, it is not trusted. It is marked Needs Review.

That is what you are seeing under each filled blank: a provenance line showing the source document, the page it came from, and the exact passage. The reviewing attorney does not have to read the whole record to verify a value, because the citation is already attached. To my knowledge this is the first feature of its kind in this category, and it was the capability the partners at the pilot firm rated most highly.

When the run finishes, the whole run is saved: the timings, the counts, the retrieval method, the reason for every single field, and the raw model output. I can export the filled document to Word with a provenance appendix attached to the back. And if the model is ever unreachable or times out, every field simply returns as Needs Review. The system will never fabricate a value to fill a gap.

---

## PAGE 6.5 — Proof it works  *(evaluation — do not trim)*

[ON SCREEN: terminal, run `python -m eval.run_eval --engine offline` then `--engine baseline`; then `pytest -q`; then flash `docs/ai-and-attribution.md`]

A claim like "it never fabricates" is only worth anything if it's measured, so I built an evaluation harness that scores produced fields against hand-labeled gold answers, optimizing for the one metric that matters here: fabrications — confident guesses on facts that aren't in the file.

With the runtime deliberately down, the offline engine produces zero fabrications and one hundred percent correct abstention — the safety guarantee holds even on failure. The naive baseline engine is the comparison, and it earned its keep by surfacing a real bug: it grabbed the intake attorney as the responsible attorney. Good evaluation catches things you would otherwise ship. On top of that, the suite has more than forty automated tests, including the anti-hallucination tests: ungrounded values are downgraded, not trusted, and a runtime going down never crashes and never fabricates — both are tested, not assumed.

One note on integrity: the front-end was scaffolded with Lovable and shadcn UI, which is cited in full in the repository. The backend, the grounding contract, and this evaluation are my own work, and these numbers are reproduced by running the harness on the code — not asserted.

---

## PAGE 7 — The Library  *(trim candidate if long)*

[ON SCREEN: navigate to the Library page]

That was the attorney's view. The Library is the administrator's view. From here, a system administrator uploads the firm's own cases and templates. And because the whole storage layer is abstracted behind a single interface, Verbatim is architected to plug into the document systems a firm already runs — NetDocuments, Centerbase, or anything else with a document-access API — so the data can stay in the systems where it already lives. That connector is the most immediate thing I would build next; today the store is the local folder you see here.

---

## PAGE 8 — The Developer Console: measuring the thing  *(trim candidate if long)*

[ON SCREEN: navigate to the Developer Console / analytics view]

The Developer Console is where the per-firm measurement lives. Because every run is recorded, the firm's technical staff can see which local models perform best on their specific templates and case types, the needs-review rate as a percentage, and the average inference time per run. This is where the offline baseline I mentioned becomes useful in practice: a firm can compare models, tune for its own document styles, and watch its accuracy improve. All of that happens on a machine inside the office. None of this telemetry leaves the building either.

---

## PAGE 9 — Who this is for, and why it matters

[ON SCREEN: closing-themed slide, or return to the filled document]

So who is this for. The pilot was an insurance defense firm, but the need is far broader. Solo practitioners and small firms that cannot afford an enterprise AI contract. Public defenders handling sensitive client records. Legal teams that touch protected health information and are bound by HIPAA. Government offices that are not permitted to send case files to a third-party cloud at all.

For every one of these, the deciding factor is not the feature list. It is that the data physically cannot leave their control. Verbatim treats that constraint as the design center rather than an afterthought. The larger point is data sovereignty: the most privileged work in the profession should not have to be uploaded to someone else's servers just to benefit from a language model.

---

## PAGE 10 — What I would add, and close

[ON SCREEN: final slide]

What would I add next. Faster, fine-tuned models trained on a firm's own template library. The document-system connectors I mentioned. Reasoning across several documents in a matter at once. A complete audit log for every run, and a packaged on-premise installer, so a firm can stand this up without ever touching a command line.

I built all of this, the ingestion, the OCR, the blank detection, the retrieval, the grounding, and the interface, as one person with AI tools in hand. That was the point of the project: to see how far a single person can now go, and to build the version of legal AI that the current market is not building. The one where your data never leaves the room.

That is Verbatim. Thank you.
