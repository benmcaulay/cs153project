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
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  CaseInfo,
  TemplateInfo,
  OllamaModel,
  FillResult,
} from "@/api/client";
import FilledDocument from "@/components/FilledDocument";

const AttorneyWorkspace = () => {
  const { toast } = useToast();
  const [matters, setMatters] = useState<CaseInfo[]>([]);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [modelsAvailable, setModelsAvailable] = useState(true);

  const [matterId, setMatterId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [model, setModel] = useState("");

  const [filling, setFilling] = useState(false);
  const [result, setResult] = useState<FillResult | null>(null);

  useEffect(() => {
    api.matters().then(setMatters).catch(() => setMatters([]));
    api.templates().then(setTemplates).catch(() => setTemplates([]));
    api
      .models()
      .then((r) => {
        setModels(r.models);
        setModelsAvailable(r.available);
        if (r.available && r.models[0]) setModel(r.models[0].name);
      })
      .catch(() => setModelsAvailable(false));
  }, []);

  const template = templates.find((t) => t.id === templateId);

  const handleFill = async () => {
    if (!matterId || !templateId || !model) {
      toast({
        title: "Three selections required",
        description: "Choose a matter, a template, and a model.",
        variant: "destructive",
      });
      return;
    }
    setFilling(true);
    setResult(null);
    try {
      const r = await api.fill(matterId, templateId, model);
      setResult(r);
      if (r.status === "model_timeout") {
        toast({
          title: "Model timed out",
          description: r.message ?? "The model did not respond in time.",
          variant: "destructive",
        });
      } else if (r.status === "model_unreachable") {
        toast({
          title: "Model runtime unreachable",
          description:
            "Every field is marked for review. Start Ollama on the local host and try again.",
          variant: "destructive",
        });
      } else if (r.status !== "ok") {
        toast({ title: "Fill incomplete", description: r.message ?? "", variant: "destructive" });
      } else {
        toast({
          title: "Fill complete",
          description: `${r.blanks_filled} filled · ${r.blanks_needs_review} need review.`,
        });
      }
    } catch (e: any) {
      toast({ title: "Fill failed", description: String(e.message ?? e), variant: "destructive" });
    } finally {
      setFilling(false);
    }
  };

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
              {modelsAvailable && models.length > 0 ? (
                <Select value={model} onValueChange={setModel}>
                  <SelectTrigger className="border-border">
                    <SelectValue placeholder="Choose a model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models.map((m) => (
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

          <Button
            onClick={handleFill}
            disabled={filling || !matterId || !templateId || !model}
            className="w-full bg-primary hover:bg-primary/90"
          >
            {filling ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Filling…
              </>
            ) : (
              <>
                <Wand2 className="mr-2 h-4 w-4" />
                Fill
              </>
            )}
          </Button>
        </CardContent>
      </Card>

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

const ResultView = ({ result }: { result: FillResult }) => {
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

      {/* Summary metrics (§10.2) */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-card-foreground flex items-center justify-between">
            <span className="flex items-center">
              <CheckCircle2 className="mr-2 h-5 w-5 text-muted-foreground" />
              Fill summary
            </span>
            <a href={api.exportUrl(result.run_id)} download>
              <Button size="sm" className="bg-primary hover:bg-primary/90">
                <Download className="mr-2 h-4 w-4" />
                Export .docx
              </Button>
            </a>
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
                  </span>
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
