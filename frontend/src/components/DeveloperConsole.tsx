import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Cpu,
  Layers,
  BarChart3,
  ClipboardCheck,
  Check,
  X,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  UserPlus,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  OllamaModel,
  TemplateInfo,
  ModelStyleStats,
  FillResult,
  UserInfo,
  AuditLog,
} from "@/api/client";

const STYLES = ["litigation", "transactional", "family-law", "estate", "unassigned"];

interface DeveloperConsoleProps {
  currentUser: string;
}

const DeveloperConsole = ({ currentUser }: DeveloperConsoleProps) => {
  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="text-card-foreground flex items-center">
          <Layers className="mr-2 h-5 w-5 text-muted-foreground" />
          Developer Console
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="models">
          <TabsList className="grid w-full grid-cols-4 mb-6 bg-muted/40">
            <TabsTrigger value="models">Models &amp; Styles</TabsTrigger>
            <TabsTrigger value="performance">Performance</TabsTrigger>
            <TabsTrigger value="audit">Run Audit</TabsTrigger>
            <TabsTrigger value="access">Access</TabsTrigger>
          </TabsList>
          <TabsContent value="models">
            <ModelsAndStyles />
          </TabsContent>
          <TabsContent value="performance">
            <Performance />
          </TabsContent>
          <TabsContent value="audit">
            <RunAudit />
          </TabsContent>
          <TabsContent value="access">
            <Access currentUser={currentUser} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

/* ---------------- Access: users, roles & the tamper-evident audit trail --- */
const Access = ({ currentUser }: { currentUser: string }) => {
  const { toast } = useToast();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLog | null>(null);
  const [newName, setNewName] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"attorney" | "admin">("attorney");
  const [busy, setBusy] = useState(false);

  const refresh = () => {
    api.users().then(setUsers).catch(() => setUsers([]));
    api.auditLog().then(setAuditLog).catch(() => setAuditLog(null));
  };
  useEffect(refresh, []);

  const addUser = async () => {
    setBusy(true);
    try {
      await api.createUser(newName.trim(), newPassword, newRole);
      toast({ title: `Created ${newRole} “${newName.trim()}”` });
      setNewName("");
      setNewPassword("");
      refresh();
    } catch (e) {
      toast({
        title: "Could not create user",
        description: String(e),
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const toggleDisabled = async (u: UserInfo) => {
    try {
      await api.setUserState(u.username, !u.disabled);
      refresh();
    } catch (e) {
      toast({ title: "Update failed", description: String(e), variant: "destructive" });
    }
  };

  return (
    <div className="space-y-8">
      <section>
        <h3 className="mb-1 text-sm font-semibold text-foreground">Firm accounts</h3>
        <p className="mb-3 text-sm text-muted-foreground">
          Attorneys see the Workspace and Library; admins also see this console.
          Passwords are scrypt-hashed in a local file — no identity provider is
          contacted.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.username}>
                <TableCell className="font-medium">{u.username}</TableCell>
                <TableCell>
                  <Badge variant={u.role === "admin" ? "default" : "secondary"}>
                    {u.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  {u.disabled ? (
                    <Badge variant="destructive">disabled</Badge>
                  ) : (
                    <Badge variant="outline">active</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={u.username === currentUser}
                    onClick={() => toggleDisabled(u)}
                  >
                    {u.disabled ? "Enable" : "Disable"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <div className="mt-4 flex flex-wrap items-end gap-2">
          <div className="w-44">
            <Input
              placeholder="username"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <div className="w-44">
            <Input
              type="password"
              placeholder="password (8+ chars)"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <Select value={newRole} onValueChange={(v) => setNewRole(v as "attorney" | "admin")}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="attorney">attorney</SelectItem>
              <SelectItem value="admin">admin</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={addUser}
            disabled={busy || !newName.trim() || newPassword.length < 8}
          >
            <UserPlus className="mr-1 h-4 w-4" /> Add user
          </Button>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center gap-3">
          <h3 className="text-sm font-semibold text-foreground">Audit trail</h3>
          {auditLog &&
            (auditLog.intact ? (
              <span className="flex items-center gap-1 text-xs font-medium text-green-700">
                <ShieldCheck className="h-4 w-4" /> hash chain intact
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs font-medium text-destructive">
                <ShieldAlert className="h-4 w-4" /> TAMPERED at line {auditLog.broken_at_line}
              </span>
            ))}
        </div>
        <p className="mb-3 text-sm text-muted-foreground">
          Every login, fill, export, upload, and admin action — each record is
          chained to the previous one's SHA-256, so edits are detectable. Case
          content never appears here, only identifiers.
        </p>
        <div className="max-h-80 overflow-y-auto rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>OK</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(auditLog?.records ?? []).map((r, i) => (
                <TableRow key={i}>
                  <TableCell className="whitespace-nowrap text-xs">{r.ts}</TableCell>
                  <TableCell className="text-xs">{r.user}</TableCell>
                  <TableCell className="text-xs font-mono">{r.action}</TableCell>
                  <TableCell className="max-w-64 truncate text-xs">{r.resource ?? ""}</TableCell>
                  <TableCell>
                    {r.ok ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <X className="h-4 w-4 text-destructive" />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
};

/* --------------------------- Models & Styles (FR-11, FR-12) --------------- */
const ModelsAndStyles = () => {
  const { toast } = useToast();
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [available, setAvailable] = useState(true);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);

  const refresh = () => {
    api.models().then((r) => {
      setModels(r.models);
      setAvailable(r.available);
    });
    api.templates().then(setTemplates);
  };
  useEffect(refresh, []);

  const assign = async (id: string, style: string) => {
    await api.setStyle(id, style);
    toast({ title: "Style assigned", description: `Template style set to ${style}.` });
    refresh();
  };

  const fmtSize = (b?: number) =>
    b ? `${(b / 1e9).toFixed(1)} GB` : "—";

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
          <Cpu className="h-4 w-4 text-muted-foreground" /> Installed local models
        </h3>
        {!available && (
          <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3 mb-3">
            <AlertTriangle className="h-4 w-4" />
            Ollama runtime unreachable. Start it on the local host to enumerate models.
          </div>
        )}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead>Parameters</TableHead>
              <TableHead>Quantization</TableHead>
              <TableHead>Size</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((m) => (
              <TableRow key={m.name}>
                <TableCell className="font-mono text-sm">{m.name}</TableCell>
                <TableCell>{m.parameter_size ?? "—"}</TableCell>
                <TableCell>{m.quantization ?? "—"}</TableCell>
                <TableCell>{fmtSize(m.size)}</TableCell>
              </TableRow>
            ))}
            {models.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-6">
                  No models installed / runtime unreachable.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
          <Layers className="h-4 w-4 text-muted-foreground" /> Template → style assignment
        </h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Template</TableHead>
              <TableHead>Blanks</TableHead>
              <TableHead>Style</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {templates.map((t) => (
              <TableRow key={t.id}>
                <TableCell className="font-medium">{t.name}</TableCell>
                <TableCell>{t.fields.length}</TableCell>
                <TableCell>
                  <Select
                    value={t.style ?? "unassigned"}
                    onValueChange={(v) => assign(t.id, v)}
                  >
                    <SelectTrigger className="w-48 h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STYLES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

/* ------------------------------ Performance (FR-14) ----------------------- */
const Performance = () => {
  const [rows, setRows] = useState<ModelStyleStats[]>([]);
  useEffect(() => {
    api.report().then(setRows);
  }, []);

  const pct = (v: number | null) => (v == null ? "—" : `${Math.round(v * 100)}%`);
  const accuracy = (r: ModelStyleStats) =>
    r.fields_flagged === 0 ? null : r.fields_correct / r.fields_flagged;
  const nrRate = (r: ModelStyleStats) =>
    r.total_fields === 0 ? null : r.needs_review_fields / r.total_fields;

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-muted-foreground" />
        Per-(model, style) accuracy
      </h3>
      <p className="text-sm text-muted-foreground mb-4">
        Aggregated from administrator flags. Fit the smallest model that meets
        your accuracy bar for each document class (§14).
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            <TableHead>Style</TableHead>
            <TableHead>Runs</TableHead>
            <TableHead>Accuracy</TableHead>
            <TableHead>Needs-review rate</TableHead>
            <TableHead>Avg inference</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={`${r.model}|${r.style}`}>
              <TableCell className="font-mono text-sm">{r.model}</TableCell>
              <TableCell>
                <Badge variant="outline">{r.style}</Badge>
              </TableCell>
              <TableCell>{r.runs}</TableCell>
              <TableCell>
                {accuracy(r) == null ? (
                  <span className="text-muted-foreground">no flags</span>
                ) : (
                  <span className="font-semibold">{pct(accuracy(r))}</span>
                )}
                <span className="text-xs text-muted-foreground ml-1">
                  ({r.fields_correct}/{r.fields_flagged})
                </span>
              </TableCell>
              <TableCell>{pct(nrRate(r))}</TableCell>
              <TableCell>{r.avg_inference_seconds.toFixed(2)}s</TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground py-6">
                No runs recorded yet. Run a fill in the Attorney Workspace.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
};

/* ------------------------------- Run Audit (FR-13) ------------------------ */
const RunAudit = () => {
  const [runs, setRuns] = useState<FillResult[]>([]);
  const [selected, setSelected] = useState<FillResult | null>(null);

  const refresh = () => api.runs().then(setRuns);
  useEffect(() => {
    refresh();
  }, []);

  const flag = async (key: string, value: "correct" | "incorrect" | null) => {
    if (!selected) return;
    const updated = await api.flag(selected.run_id, key, value);
    setSelected(updated);
    refresh();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-1">
        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-muted-foreground" /> Runs
        </h3>
        <div className="space-y-2 max-h-[30rem] overflow-y-auto">
          {runs.map((r) => (
            <button
              key={r.run_id}
              onClick={() => setSelected(r)}
              className={
                "w-full text-left rounded-lg border p-3 transition-colors " +
                (selected?.run_id === r.run_id
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-accent/50")
              }
            >
              <div className="text-sm font-medium">{r.template_name}</div>
              <div className="text-xs text-muted-foreground">
                {r.matter_name} · <span className="font-mono">{r.model}</span>
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {new Date(r.timestamp).toLocaleString()} ·{" "}
                {r.blanks_filled}/{r.blanks_total} filled
              </div>
            </button>
          ))}
          {runs.length === 0 && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No runs yet.
            </p>
          )}
        </div>
      </div>

      <div className="lg:col-span-2">
        <h3 className="text-sm font-semibold mb-2">Field-level flags</h3>
        {!selected ? (
          <p className="text-sm text-muted-foreground py-4">
            Select a run to flag each field correct or incorrect.
          </p>
        ) : (
          <div className="space-y-2">
            {selected.fields.map((f) => (
              <div
                key={f.key}
                className="rounded-lg border border-border p-3 flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium">{f.label}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {f.found ? f.value : "NEEDS REVIEW"}
                    {f.source_document ? ` · ${f.source_document}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    size="sm"
                    variant={f.admin_flag === "correct" ? "default" : "outline"}
                    className={f.admin_flag === "correct" ? "bg-green-600 hover:bg-green-600/90" : ""}
                    onClick={() => flag(f.key, f.admin_flag === "correct" ? null : "correct")}
                    disabled={!f.found}
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant={f.admin_flag === "incorrect" ? "default" : "outline"}
                    className={f.admin_flag === "incorrect" ? "bg-red-600 hover:bg-red-600/90" : ""}
                    onClick={() => flag(f.key, f.admin_flag === "incorrect" ? null : "incorrect")}
                    disabled={!f.found}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DeveloperConsole;
