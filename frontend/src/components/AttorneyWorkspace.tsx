import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Folder,
  FileText,
  Cpu,
  Wand2,
  Loader2,
  Download,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Quote,
  ShieldAlert,
  Info,
  X,
  Eye,
  ChevronDown,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { api, TemplateInfo, FillResult, DocText } from "@/api/client";
import FilledDocument from "@/components/FilledDocument";
import { useFill } from "@/components/FillContext";

const SourceInspector = ({
  matterId,
  templateId,
}: {
  matterId: string;
  templateId: string;
}) => {
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState<DocText[] | null>(null);
  const [tmpl, setTmpl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [d, t] = await Promise.all([
        matterId ? api.matterText(matterId) : Promise.resolve([] as DocText[]),
        templateId ? api.templateText(templateId) : Promise.resolve({ text: "" }),
      ]);
      setDocs(d);
      setTmpl(t.text);
    } catch {
      setDocs([]);
      setTmpl("");
    } finally {
      setLoading(false);
    }
  };

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && docs === null) load();
  };

  if (!matterId && !templateId) return null;

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-card-foreground flex items-center justify-between text-lg">
          <button onClick={toggle} className="flex items-center gap-2">
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            <Eye className="h-5 w-5 text-muted-foreground" />
            Inspect sources
          </button>
          {open && (
            <Button variant="outline" size="sm" onClick={load} disabled={loading} className="border-border">
              <RefreshCw className={"h-4 w-4 " + (loading ? "animate-spin" : "")} />
            </Button>
          )}
        </CardTitle>
        <CardDescription>
          See exactly what the model reads (the extracted text of each case
          document and the template with its detected blanks).
        </CardDescription>
      </CardHeader>
      {open && (
        <CardContent className="space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Reading sources…</p>}

          {tmpl != null && (
            <div className="rounded-lg border border-border">
              <div className="px-3 py-2 text-sm font-medium text-foreground border-b border-border">
                Template
              </div>
              <pre className="p-3 text-xs whitespace-pre-wrap font-mono max-h-48 overflow-y-auto text-muted-foreground">
                {tmpl || "(empty)"}
              </pre>
            </div>
          )}

          {docs?.map((d) => (
            <div key={d.filename} className="rounded-lg border border-border">
              <button
                onClick={() => setExpanded(expanded === d.filename ? null : d.filename)}
                className="w-full flex items-center justify-between px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2 font-medium text-foreground truncate">
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="truncate">{d.filename}</span>
                </span>
                <Badge
                  variant="outline"
                  className={d.chars === 0 ? "text-amber-700 border-amber-400" : ""}
                >
                  {d.chars === 0 ? "no readable text" : `${d.chars.toLocaleString()} chars`}
                </Badge>
              </button>
              {expanded === d.filename && (
                <pre className="px-3 pb-3 text-xs whitespace-pre-wrap font-mono max-h-64 overflow-y-auto text-muted-foreground border-t border-border pt-2">
                  {d.text || "(no extractable text — scanned/encrypted, or empty)"}
                </pre>
              )}
            </div>
          ))}
          {docs?.length === 0 && !loading && (
            <p className="text-sm text-muted-foreground">No documents in this matter.</p>
          )}
        </CardContent>
      )}
    </Card>
  );
};

const AttorneyWorkspace = () => {
  const {
    matters,
    templates,
    models,
    modelsAvailable,
    matterId,
    templateId,
    model,
    setMatterId,
    setTemplateId,
    setModel,
    filling,
    elapsedMs,
    result,
    runFill,
    cancel,
  } = useFill();

  // Embedding models (e.g. nomic-embed-text) power retrieval but cannot generate
  // text — keep them out of the generation-model picker.
  const genModels = models.filter((m) => !m.embedding);
  const template = templates.find((t) => t.id === templateId);
  const elapsedLabel = `${(elapsedMs / 1000).toFixed(1)}s`;

  return (
    <div className="space-y-6">
      {/* Selection card — three selections + one button (NFR-4) */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center">
            <Wand2 className="mr-2 h-5 w-5 text-muted-foreground" />
            Fill a template from a matter
          </CardTitle>
          <CardDescription>
            Select a matter, a template, and a local model. Verbatim transcribes
            facts from the case file into the template — and marks anything it
            can't ground for your review.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Matter */}
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-2">
                Matter
              </label>
              <Select value={matterId} onValueChange={setMatterId}>
                <SelectTrigger className="border-border">
                  <SelectValue placeholder="Choose a matter" />
                </SelectTrigger>
                <SelectContent>
                  {matters.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      <div className="flex items-center gap-2">
                        <Folder className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="font-medium">{m.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {m.documents.length} document(s)
                          </div>
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                  {matters.length === 0 && (
                    <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                      No matters found in data/matters.
                    </div>
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* Template */}
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-2">
                Template
              </label>
              <Select value={templateId} onValueChange={setTemplateId}>
                <SelectTrigger className="border-border">
                  <SelectValue placeholder="Choose a template" />
                </SelectTrigger>
                <SelectContent>
                  {templates.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-primary" />
                        <div>
                          <div className="font-medium">{t.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {t.fields.length} blank(s)
                            {t.style ? ` · ${t.style}` : ""}
                          </div>
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Model */}
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-2">
                Local model
              </label>
              {modelsAvailable && genModels.length > 0 ? (
                <Select value={model} onValueChange={setModel}>
                  <SelectTrigger className="border-border">
                    <SelectValue placeholder="Choose a model" />
                  </SelectTrigger>
                  <SelectContent>
                    {genModels.map((m) => (
                      <SelectItem key={m.name} value={m.name}>
                        <div className="flex items-center gap-2">
                          <Cpu className="h-4 w-4 text-muted-foreground" />
                          <span className="font-mono text-sm">{m.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  className="border-border font-mono"
                  placeholder="e.g. llama3.1:8b"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              )}
            </div>
          </div>

          {!modelsAvailable && (
            <div className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>
                Local model runtime not detected. You can still run a fill — every
                field will return as <strong>NEEDS REVIEW</strong> until Ollama is
                started on the local host.
              </span>
            </div>
          )}

          {template && (
            <div className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{template.name}</span>{" "}
              has{" "}
              <Badge variant="secondary">{template.fields.length} blanks</Badge>{" "}
              to fill.
            </div>
          )}

          <div className="flex gap-2">
            <Button
              onClick={runFill}
              disabled={filling || !matterId || !templateId || !model}
              className="flex-1 bg-primary hover:bg-primary/90"
            >
              {filling ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Filling… <span className="ml-1 font-mono tabular-nums">{elapsedLabel}</span>
                </>
              ) : (
                <>
                  <Wand2 className="mr-2 h-4 w-4" />
                  Fill
                </>
              )}
            </Button>
            {filling && (
              <Button variant="outline" onClick={cancel} className="border-border">
                <X className="mr-1 h-4 w-4" />
                Cancel
              </Button>
            )}
          </div>
          {filling && (
            <p className="text-xs text-muted-foreground">
              Running locally — this keeps going if you switch tabs. Larger models
              and first-time loads can take a few minutes.
            </p>
          )}
        </CardContent>
      </Card>

      <SourceInspector matterId={matterId} templateId={templateId} />

      {result && <ResultView result={result} />}
    </div>
  );
};

const Metric = ({
  icon,
  label,
  value,
  tone = "default",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "default" | "good" | "warn";
}) => (
  <div className="rounded-lg border border-border bg-muted/30 p-3">
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      {icon}
      {label}
    </div>
    <div
      className={
        "text-xl font-bold mt-1 " +
        (tone === "warn"
          ? "text-amber-600"
          : tone === "good"
          ? "text-green-600"
          : "text-card-foreground")
      }
    >
      {value}
    </div>
  </div>
);

const REVIEW_REASONS: Record<string, string> = {
  no_context: "No matching passage was retrieved from the case file.",
  model_blanked: "The model found nothing it could ground in the sources.",
  ungrounded: "The model proposed a value, but its quote wasn't found in the sources.",
  missing_key: "The model omitted this field from its response.",
  model_unreachable: "The model runtime was unavailable.",
  no_documents: "No readable case text was available.",
};

const ResultView = ({ result }: { result: FillResult }) => {
  const incomplete = result.status === "ok" && result.blanks_filled < result.blanks_total;
  return (
    <>
      {/* Why everything is for review, when inference didn't complete */}
      {result.status !== "ok" && (
        <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">
              {result.status === "model_timeout"
                ? "Inference timed out — no values were transcribed."
                : result.status === "model_unreachable"
                ? "Model runtime unavailable — no values were transcribed."
                : "Inference did not complete."}
            </span>
            {result.message && <div className="mt-0.5">{result.message}</div>}
          </div>
        </div>
      )}

      {/* The fill completed but blanks remain — explain why, so 0/N isn't a mystery */}
      {incomplete && result.message && (
        <div className="flex items-start gap-2 rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold">
              {result.blanks_filled} of {result.blanks_total} blanks filled.
            </span>{" "}
            {result.message}
          </div>
        </div>
      )}

      {/* Summary metrics (§10.2) */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-card-foreground flex items-center justify-between">
            <span className="flex items-center">
              <CheckCircle2 className="mr-2 h-5 w-5 text-muted-foreground" />
              Fill summary
            </span>
            <Button
              size="sm"
              className="bg-primary hover:bg-primary/90"
              onClick={async () => {
                try {
                  const blob = await api.exportDocx(result.run_id);
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${result.template_name.replace(/ /g, "_")}_filled.docx`;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch (e) {
                  console.error("Export failed", e);
                }
              }}
            >
              <Download className="mr-2 h-4 w-4" />
              Export .docx
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            label="Blanks filled"
            value={`${result.blanks_filled}/${result.blanks_total}`}
            tone="good"
          />
          <Metric
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
            label="Needs review"
            value={`${result.blanks_needs_review}`}
            tone={result.blanks_needs_review > 0 ? "warn" : "default"}
          />
          <Metric
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Inference time"
            value={`${result.inference_seconds.toFixed(2)}s`}
          />
          <Metric
            icon={<Cpu className="h-3.5 w-3.5" />}
            label="Model"
            value={result.model}
          />
        </CardContent>
      </Card>

      {/* Filled document with in-place highlights (FR-9) */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-card-foreground flex items-center justify-between">
            <span className="flex items-center">
              <FileText className="mr-2 h-5 w-5 text-muted-foreground" />
              {result.template_name}
            </span>
            <span className="flex items-center gap-2 text-xs font-normal text-muted-foreground">
              <Badge variant="outline">retrieval: {result.retrieval_mode}</Badge>
              <Badge variant="outline">{result.matter_name}</Badge>
            </span>
          </CardTitle>
          <CardDescription className="flex items-center gap-3 pt-1">
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded bg-primary/15 ring-1 ring-primary/30" />
              transcribed value
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-3 w-3 rounded bg-amber-100 ring-1 ring-amber-400" />
              needs review
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="bg-muted/20 rounded-lg p-5 max-h-[28rem] overflow-y-auto border border-border">
            <FilledDocument result={result} />
          </div>
        </CardContent>
      </Card>

      {/* Provenance panel (FR-7) */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-card-foreground flex items-center">
            <Quote className="mr-2 h-5 w-5 text-muted-foreground" />
            Provenance
          </CardTitle>
          <CardDescription>
            Every transcribed value carries a verbatim supporting quote from the
            case file. Confidence is an advisory model self-report.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {result.fields.map((f) => (
            <div
              key={f.key}
              className="rounded-lg border border-border p-3 flex flex-col gap-1"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground">{f.label}</span>
                {f.found ? (
                  <div className="flex items-center gap-2">
                    {f.confidence != null && (
                      <Badge variant="outline" className="text-xs">
                        conf {Math.round(f.confidence * 100)}%
                      </Badge>
                    )}
                    <Badge className="bg-primary/15 text-primary hover:bg-primary/15">
                      {f.value}
                    </Badge>
                  </div>
                ) : (
                  <Badge variant="outline" className="text-amber-700 border-amber-400">
                    NEEDS REVIEW
                  </Badge>
                )}
              </div>
              {f.found && f.source_quote && (
                <div className="text-xs text-muted-foreground italic flex items-start gap-1">
                  <Quote className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>
                    “{f.source_quote}” — <span className="font-mono">{f.source_document}</span>
                    {f.source_page ? <span className="font-mono">, p. {f.source_page}</span> : null}
                  </span>
                </div>
              )}
              {!f.found && f.review_reason && REVIEW_REASONS[f.review_reason] && (
                <div className="text-xs text-amber-700/90 flex items-start gap-1">
                  <Info className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>{REVIEW_REASONS[f.review_reason]}</span>
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Professional responsibility notice (NG-1, §13) */}
      <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/40 border border-border rounded-md p-3">
        <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0" />
        <span>
          Draft only. Verbatim does not provide legal advice or exercise legal
          judgment. A licensed attorney is responsible for reviewing and
          finalizing every output.
        </span>
      </div>
    </>
  );
};

export default AttorneyWorkspace;
