import { FillResult, FilledField } from "@/api/client";

/**
 * Renders the filled document with every substituted value highlighted in
 * place, and ungrounded blanks rendered distinctly as review markers (FR-9).
 *
 * It reconstructs the document from the original template text by replacing
 * each blank's literal placeholder token with a styled span keyed to its
 * FilledField, so the attorney sees exactly what changed.
 */

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const FilledDocument = ({ result }: { result: FillResult }) => {
  // Map each placeholder token -> field (last spec wins on duplicate keys).
  const byPlaceholder = new Map<string, FilledField>();
  // We only have placeholders on the template, not on the result; reconstruct
  // from field keys using both {{key}} and [[key]] plus instruction variants is
  // brittle, so instead split on the known placeholder set passed via fields.
  for (const f of result.fields) {
    // The backend's filled_text already substituted values; but to highlight we
    // re-derive from original_text using the field key tokens.
    byPlaceholder.set(f.key, f);
  }

  // Build a regex that matches {{ key ... }} or [[ key ... ]] for any known key.
  const keys = result.fields.map((f) => escapeRe(f.key));
  if (keys.length === 0) {
    return <pre className="whitespace-pre-wrap font-mono text-sm">{result.original_text}</pre>;
  }
  const tokenRe = new RegExp(
    `(?:\\{\\{|\\[\\[)\\s*(${keys.join("|")})\\s*(?:\\|[^}\\]]*)?(?:\\}\\}|\\]\\])`,
    "g"
  );

  const nodes: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  const text = result.original_text;
  while ((m = tokenRe.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const key = m[1];
    const field = byPlaceholder.get(key);
    if (field && field.found) {
      nodes.push(
        <mark
          key={i++}
          title={`${field.source_document ?? "source"}: ${field.source_quote ?? ""}`}
          className="rounded bg-primary/15 text-primary px-1 font-medium ring-1 ring-primary/30"
        >
          {field.value}
        </mark>
      );
    } else {
      nodes.push(
        <span
          key={i++}
          className="rounded bg-amber-100 text-amber-900 px-1 font-semibold ring-1 ring-amber-400"
        >
          [{field?.label ?? key} — NEEDS REVIEW]
        </span>
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));

  return (
    <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-card-foreground">
      {nodes}
    </pre>
  );
};

export default FilledDocument;
