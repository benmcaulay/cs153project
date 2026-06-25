import { FillResult, FilledField } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { Quote } from "lucide-react";

/**
 * Renders the filled document with every substituted value highlighted in
 * place, and ungrounded blanks rendered distinctly as review markers (FR-9).
 *
 * It reconstructs the document from the original template text by replacing
 * each blank's literal placeholder token with a styled span keyed to its
 * FilledField, so the attorney sees exactly what changed.
 *
 * Each value is also a live citation: it carries a numbered marker that matches
 * its entry in the Provenance panel, shows the supporting quote inline on hover,
 * and scrolls to (and flashes) that panel entry on click — so a value's source
 * is reachable in context, not just by scanning a flat list. `onCite` performs
 * that navigation; `fieldNumber` maps each field key to its panel number.
 */

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const FilledDocument = ({
  result,
  onCite,
}: {
  result: FillResult;
  onCite?: (key: string) => void;
}) => {
  // Map each placeholder token -> field (last spec wins on duplicate keys).
  const byPlaceholder = new Map<string, FilledField>();
  for (const f of result.fields) {
    byPlaceholder.set(f.key, f);
  }
  // Citation numbers mirror the Provenance panel, which lists result.fields in
  // order — same source, same order, so the markers line up.
  const fieldNumber = new Map<string, number>();
  result.fields.forEach((f, i) => fieldNumber.set(f.key, i + 1));

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
    const num = fieldNumber.get(key);
    if (field && field.found) {
      nodes.push(
        <HoverCard key={i++} openDelay={120} closeDelay={80}>
          <HoverCardTrigger asChild>
            <button
              type="button"
              onClick={() => onCite?.(key)}
              className="rounded bg-primary/15 text-primary px-1 font-medium ring-1 ring-primary/30 hover:bg-primary/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 cursor-pointer"
            >
              {field.value}
              {num != null && (
                <sup className="ml-0.5 text-[0.62em] font-semibold tabular-nums">
                  [{num}]
                </sup>
              )}
            </button>
          </HoverCardTrigger>
          <HoverCardContent align="start" className="w-80 text-left space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-foreground">
                {field.label}
              </span>
              {field.confidence != null && (
                <Badge variant="outline" className="text-xs shrink-0">
                  conf {Math.round(field.confidence * 100)}%
                </Badge>
              )}
            </div>
            {field.source_quote ? (
              <p className="text-xs text-muted-foreground italic flex items-start gap-1">
                <Quote className="h-3 w-3 mt-0.5 shrink-0" />
                <span>“{field.source_quote}”</span>
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                No supporting quote was recorded.
              </p>
            )}
            <p className="text-xs font-mono text-muted-foreground">
              {field.source_document ?? "source"}
              {field.source_page ? `, p. ${field.source_page}` : ""}
            </p>
            <p className="text-[0.7rem] text-muted-foreground/80">
              Click to view in Provenance ↓
            </p>
          </HoverCardContent>
        </HoverCard>
      );
    } else {
      nodes.push(
        <button
          key={i++}
          type="button"
          onClick={() => onCite?.(key)}
          className="rounded bg-amber-100 text-amber-900 px-1 font-semibold ring-1 ring-amber-400 hover:bg-amber-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 cursor-pointer"
        >
          [{field?.label ?? key} — NEEDS REVIEW]
          {num != null && (
            <sup className="ml-0.5 text-[0.62em] font-semibold tabular-nums">
              [{num}]
            </sup>
          )}
        </button>
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
