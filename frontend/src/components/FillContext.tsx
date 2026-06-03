/**
 * FillProvider — owns the fill lifecycle so a running query survives tab
 * navigation. The Attorney Workspace component unmounts when the user switches
 * to Library or Developer Console; if the fill lived in that component its
 * result would be dropped when the request finally resolved. Holding it here
 * (mounted once, above the tab switch) keeps the request, the live elapsed
 * clock, and the result alive while the user moves around the app.
 */
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from "react";
import { api, CaseInfo, FillResult, OllamaModel, TemplateInfo } from "@/api/client";
import { useToast } from "@/hooks/use-toast";

interface FillState {
  matters: CaseInfo[];
  templates: TemplateInfo[];
  models: OllamaModel[];
  modelsAvailable: boolean;

  matterId: string;
  templateId: string;
  model: string;
  setMatterId: (v: string) => void;
  setTemplateId: (v: string) => void;
  setModel: (v: string) => void;

  filling: boolean;
  elapsedMs: number; // live wall-clock for the in-flight (or last) fill
  result: FillResult | null;

  runFill: () => void;
  cancel: () => void;
}

const Ctx = createContext<FillState | null>(null);

export const useFill = (): FillState => {
  const v = useContext(Ctx);
  if (!v) throw new Error("useFill must be used within a FillProvider");
  return v;
};

export const FillProvider = ({ children }: { children: ReactNode }) => {
  const { toast } = useToast();

  const [matters, setMatters] = useState<CaseInfo[]>([]);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [modelsAvailable, setModelsAvailable] = useState(true);

  const [matterId, setMatterId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [model, setModel] = useState("");

  const [filling, setFilling] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [result, setResult] = useState<FillResult | null>(null);

  const tickRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load selectable data once; the provider stays mounted for the app's life.
  useEffect(() => {
    api.matters().then(setMatters).catch(() => setMatters([]));
    api.templates().then(setTemplates).catch(() => setTemplates([]));
    api
      .models()
      .then((r) => {
        setModels(r.models);
        setModelsAvailable(r.available);
        // Default to the first *generation* model (never an embedder).
        const firstGen = r.models.find((m) => !m.embedding);
        if (r.available && firstGen) setModel(firstGen.name);
      })
      .catch(() => setModelsAvailable(false));
    return () => stopTick();
  }, []);

  const stopTick = () => {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  };

  const runFill = () => {
    if (filling) return;
    if (!matterId || !templateId || !model) {
      toast({
        title: "Three selections required",
        description: "Choose a matter, a template, and a model.",
        variant: "destructive",
      });
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    const startedAt = Date.now();
    setResult(null);
    setElapsedMs(0);
    setFilling(true);

    stopTick();
    tickRef.current = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 100);

    api
      .fill(matterId, templateId, model, controller.signal)
      .then((r) => {
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
            description: "Every field is marked for review. Start Ollama and try again.",
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
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") {
          toast({ title: "Fill cancelled", description: "The query was stopped." });
        } else {
          const msg = e instanceof Error ? e.message : String(e);
          toast({ title: "Fill failed", description: msg, variant: "destructive" });
        }
      })
      .finally(() => {
        setElapsedMs(Date.now() - startedAt); // freeze on the final time
        stopTick();
        setFilling(false);
        abortRef.current = null;
      });
  };

  const cancel = () => abortRef.current?.abort();

  return (
    <Ctx.Provider
      value={{
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
      }}
    >
      {children}
    </Ctx.Provider>
  );
};
