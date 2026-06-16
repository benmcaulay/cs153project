import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Folder,
  FolderPlus,
  FileText,
  Trash2,
  X,
  Loader2,
  FilePlus2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { api, CaseInfo, TemplateInfo } from "@/api/client";

const DOC_ACCEPT = ".pdf,.docx,.txt,.md,.eml,.xlsx";
const TEMPLATE_ACCEPT = ".docx,.txt,.md";

const Library = () => {
  const { toast } = useToast();
  const [matters, setMatters] = useState<CaseInfo[]>([]);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [newMatter, setNewMatter] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = () => {
    api.matters().then(setMatters).catch(() => {});
    api.templates().then(setTemplates).catch(() => {});
  };
  useEffect(refresh, []);

  const err = (e: unknown) =>
    toast({ title: "Upload failed", description: String((e as Error).message ?? e), variant: "destructive" });

  const createMatter = async () => {
    if (!newMatter.trim()) return;
    setBusy(true);
    try {
      await api.createMatter(newMatter.trim());
      setNewMatter("");
      toast({ title: "Matter created", description: "Now add case documents to it." });
      refresh();
    } catch (e) {
      err(e);
    } finally {
      setBusy(false);
    }
  };

  const uploadDocs = async (matterId: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    try {
      const updated = await api.uploadDocuments(matterId, files);
      toast({ title: "Documents added", description: `${updated.documents.length} file(s) in matter.` });
      refresh();
    } catch (e) {
      err(e);
    }
  };

  const removeDoc = async (matterId: string, filename: string) => {
    try {
      await api.deleteDocument(matterId, filename);
      refresh();
    } catch (e) {
      err(e);
    }
  };

  const removeMatter = async (m: CaseInfo) => {
    if (!confirm(`Delete matter "${m.name}" and all its documents?`)) return;
    try {
      await api.deleteMatter(m.id);
      refresh();
    } catch (e) {
      err(e);
    }
  };

  const uploadTemplate = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    try {
      for (const f of Array.from(files)) {
        const t = await api.uploadTemplate(f);
        toast({ title: "Template uploaded", description: `${t.name}: ${t.fields.length} blank(s) detected.` });
      }
      refresh();
    } catch (e) {
      err(e);
    }
  };

  const removeTemplate = async (t: TemplateInfo) => {
    if (!confirm(`Delete template "${t.name}"?`)) return;
    try {
      await api.deleteTemplate(t.id);
      refresh();
    } catch (e) {
      err(e);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ---------------- Matters & case files ---------------- */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center">
            <Folder className="mr-2 h-5 w-5 text-muted-foreground" />
            Matters &amp; case files
          </CardTitle>
          <CardDescription>
            Create a matter, then upload its source documents (.pdf, .docx, .txt,
            .md, .eml, .xlsx). Everything stays on this host.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="New matter name, e.g. Smith v. Johnson"
              value={newMatter}
              onChange={(e) => setNewMatter(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createMatter()}
            />
            <Button onClick={createMatter} disabled={busy || !newMatter.trim()}>
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FolderPlus className="h-4 w-4" />
              )}
              <span className="ml-2 hidden sm:inline">Create</span>
            </Button>
          </div>

          <div className="space-y-3">
            {matters.map((m) => (
              <div key={m.id} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Folder className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="font-medium truncate">{m.name}</span>
                    <Badge variant="secondary" className="shrink-0">
                      {m.documents.length} doc(s)
                    </Badge>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => removeMatter(m)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>

                {m.documents.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {m.documents.map((d) => (
                      <div
                        key={d}
                        className="flex items-center justify-between text-sm rounded px-2 py-1 hover:bg-accent/50"
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span className="truncate">{d}</span>
                        </span>
                        <button
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => removeDoc(m.id, d)}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <FileDropzone
                  accept={DOC_ACCEPT}
                  onFiles={(files) => uploadDocs(m.id, files)}
                  className="mt-2 py-3"
                  label={
                    <>
                      <FilePlus2 className="h-4 w-4 shrink-0" /> Drag &amp; drop case
                      files here, or click to browse
                    </>
                  }
                />
              </div>
            ))}
            {matters.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No matters yet. Create one above.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ---------------- Firm templates ---------------- */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center">
            <FileText className="mr-2 h-5 w-5 text-muted-foreground" />
            Firm templates
          </CardTitle>
          <CardDescription>
            Upload templates (.docx, .txt, .md). Mark blanks with{" "}
            <code className="text-xs bg-muted px-1 rounded">{"{{key}}"}</code> or{" "}
            <code className="text-xs bg-muted px-1 rounded">{"[[key]]"}</code>,
            optionally{" "}
            <code className="text-xs bg-muted px-1 rounded">{"{{key | instruction}}"}</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FileDropzone
            accept={TEMPLATE_ACCEPT}
            onFiles={uploadTemplate}
            className="p-6"
            label="Drag & drop a template here, or click to browse"
          />

          <div className="space-y-2">
            {templates.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between rounded-lg border border-border p-3"
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">{t.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {t.fields.length} blank(s){t.style ? ` · ${t.style}` : ""} ·{" "}
                    <span className="font-mono">{t.filename}</span>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive shrink-0"
                  onClick={() => removeTemplate(t)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {templates.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No templates yet. Upload one above.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

/* Reusable drag-and-drop + click-to-browse zone for uploads (matters & templates). */
const FileDropzone = ({
  accept,
  onFiles,
  label,
  className = "",
}: {
  accept: string;
  onFiles: (files: FileList | null) => void;
  label: React.ReactNode;
  className?: string;
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onFiles(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      className={
        "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed cursor-pointer transition-colors " +
        (over ? "border-primary bg-primary/5" : "border-border hover:bg-accent/30") +
        " " +
        className
      }
    >
      <span className="flex items-center gap-2 text-sm text-muted-foreground text-center">
        {label}
      </span>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        className="hidden"
        onChange={(e) => {
          onFiles(e.target.files);
          e.currentTarget.value = "";
        }}
      />
    </div>
  );
};

export default Library;
