import { useEffect, useState } from "react";
import Header from "@/components/Header";
import AttorneyWorkspace from "@/components/AttorneyWorkspace";
import DeveloperConsole from "@/components/DeveloperConsole";
import { Scale, Wrench, ShieldCheck, ShieldOff } from "lucide-react";
import { api } from "@/api/client";

type Surface = "attorney" | "developer";

const Index = () => {
  const [surface, setSurface] = useState<Surface>("attorney");
  const [ollamaUp, setOllamaUp] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => setOllamaUp(h.ollama_available))
      .catch(() => setOllamaUp(false));
  }, []);

  const SurfaceToggle = (
    <div className="flex items-center rounded-lg border border-border bg-muted/40 p-1">
      <button
        onClick={() => setSurface("attorney")}
        className={
          "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
          (surface === "attorney"
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground")
        }
      >
        <Scale className="h-4 w-4" />
        <span className="hidden sm:inline">Attorney Workspace</span>
      </button>
      <button
        onClick={() => setSurface("developer")}
        className={
          "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
          (surface === "developer"
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground")
        }
      >
        <Wrench className="h-4 w-4" />
        <span className="hidden sm:inline">Developer Console</span>
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <Header right={SurfaceToggle} />

      <div className="container mx-auto px-4 py-8">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-2">
              {surface === "attorney" ? "Attorney Workspace" : "Developer Console"}
            </h1>
            <p className="text-muted-foreground text-base md:text-lg max-w-2xl">
              {surface === "attorney"
                ? "Transcribe facts from a matter's case file into a firm template — grounded, provenance-backed, and private."
                : "Manage local models, assign template styles, and measure which model fits each document class."}
            </p>
          </div>
          {ollamaUp !== null && (
            <div
              className={
                "hidden md:flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium " +
                (ollamaUp
                  ? "border-green-300 bg-green-50 text-green-700"
                  : "border-amber-300 bg-amber-50 text-amber-700")
              }
            >
              {ollamaUp ? (
                <ShieldCheck className="h-4 w-4" />
              ) : (
                <ShieldOff className="h-4 w-4" />
              )}
              {ollamaUp ? "Local model runtime online" : "Model runtime offline"}
            </div>
          )}
        </div>

        {surface === "attorney" ? <AttorneyWorkspace /> : <DeveloperConsole />}
      </div>
    </div>
  );
};

export default Index;
