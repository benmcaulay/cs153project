import { useEffect, useState } from "react";
import Header from "@/components/Header";
import AttorneyWorkspace from "@/components/AttorneyWorkspace";
import DeveloperConsole from "@/components/DeveloperConsole";
import Library from "@/components/Library";
import LoginPage from "@/components/LoginPage";
import { FillProvider } from "@/components/FillContext";
import {
  Scale,
  Wrench,
  FolderUp,
  ShieldCheck,
  ShieldOff,
  LogOut,
  UserCircle2,
} from "lucide-react";
import { api, AuthMe } from "@/api/client";

type Surface = "attorney" | "library" | "developer";

const SURFACE_TITLE: Record<Surface, string> = {
  attorney: "Attorney Workspace",
  library: "Library",
  developer: "Developer Console",
};

const SURFACE_BLURB: Record<Surface, string> = {
  attorney:
    "Transcribe facts from a matter's case file into a private, provenance-backed template.",
  library:
    "Upload case documents into a matter and add firm templates. Nothing leaves this host.",
  developer:
    "Manage local models, assign template styles, and measure which model fits each document class.",
};

const Index = () => {
  const [surface, setSurface] = useState<Surface>("attorney");
  const [ollamaUp, setOllamaUp] = useState<boolean | null>(null);
  const [me, setMe] = useState<AuthMe | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch(() => setMe({ authenticated: false, auth_enabled: true }));
  }, []);

  useEffect(() => {
    if (!me?.authenticated) return;
    api
      .health()
      .then((h) => setOllamaUp(h.ollama_available))
      .catch(() => setOllamaUp(false));
  }, [me?.authenticated]);

  const isAdmin = me?.role === "admin";

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setSurface("attorney");
      setMe({ authenticated: false, auth_enabled: true });
    }
  };

  if (me === null) {
    return <div className="min-h-screen bg-background" />;
  }

  if (!me.authenticated) {
    return (
      <LoginPage
        onLogin={(user) => setMe({ authenticated: true, auth_enabled: true, ...user })}
      />
    );
  }

  const tabBtn = (key: Surface, icon: React.ReactNode, label: string) => (
    <button
      onClick={() => setSurface(key)}
      className={
        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
        (surface === key
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:text-foreground")
      }
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );

  const HeaderRight = (
    <div className="flex items-center gap-3">
      <div className="flex items-center rounded-lg border border-border bg-muted/40 p-1">
        {tabBtn("attorney", <Scale className="h-4 w-4" />, "Attorney Workspace")}
        {tabBtn("library", <FolderUp className="h-4 w-4" />, "Library")}
        {isAdmin && tabBtn("developer", <Wrench className="h-4 w-4" />, "Developer Console")}
      </div>
      {me.auth_enabled && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="hidden md:flex items-center gap-1.5">
            <UserCircle2 className="h-4 w-4" />
            {me.username}
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide">
              {me.role}
            </span>
          </span>
          <button
            onClick={logout}
            title="Sign out"
            className="flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs font-medium hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      )}
    </div>
  );

  return (
    <FillProvider>
    <div className="min-h-screen bg-background">
      <Header right={HeaderRight} />

      <div className="container mx-auto px-4 py-8">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-2">
              {SURFACE_TITLE[surface]}
            </h1>
            <p className="text-muted-foreground text-base md:text-lg">
              {SURFACE_BLURB[surface]}
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

        {surface === "attorney" && <AttorneyWorkspace />}
        {surface === "library" && <Library />}
        {surface === "developer" && isAdmin && (
          <DeveloperConsole currentUser={me.username ?? ""} />
        )}
      </div>
    </div>
    </FillProvider>
  );
};

export default Index;
