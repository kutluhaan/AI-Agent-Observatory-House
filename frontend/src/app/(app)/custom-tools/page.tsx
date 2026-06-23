"use client";

import { useEffect, useState } from "react";
import { Wrench, Plus, Trash2, Play } from "lucide-react";
import { api, ApiError, type CustomTool } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => ({ value: m, label: m }));
const DEFAULT_PARAMS = `{
  "type": "object",
  "properties": {
    "city": { "type": "string", "description": "Şehir adı" }
  },
  "required": ["city"]
}`;

export default function CustomToolsPage() {
  const [tools, setTools] = useState<CustomTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [method, setMethod] = useState("GET");
  const [url, setUrl] = useState("");
  const [headers, setHeaders] = useState("");
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [adding, setAdding] = useState(false);

  function load() {
    api.get<CustomTool[]>("/custom-tools").then(setTools).catch(() => setError("Yüklenemedi.")).finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function add() {
    setAdding(true);
    setError("");
    try {
      let parametersObj: unknown = { type: "object", properties: {} };
      let headersObj: Record<string, string> | null = null;
      try { parametersObj = params.trim() ? JSON.parse(params) : parametersObj; } catch { throw new Error("Parametreler geçerli JSON değil."); }
      if (headers.trim()) { try { headersObj = JSON.parse(headers); } catch { throw new Error("Header'lar geçerli JSON değil."); } }
      await api.post("/custom-tools", { name, description, method, url, headers: headersObj, parameters: parametersObj });
      setName(""); setDescription(""); setUrl(""); setHeaders(""); setParams(DEFAULT_PARAMS); setMethod("GET");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message || "Eklenemedi.");
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Bu tool'u sil?")) return;
    try { await api.delete(`/custom-tools/${id}`); setTools((t) => t.filter((x) => x.id !== id)); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Silinemedi."); }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <div className="mb-2 flex items-center gap-2">
        <Wrench size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Özel Araçlar (HTTP)</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Kendi HTTP endpoint&apos;ini bir tool olarak tanımla; agent oluştururken seç. Org genelinde kullanılır.
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {/* Yeni tool */}
      <div className="mb-8 flex flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
        <p className="text-sm font-medium text-zinc-200">Tool ekle</p>
        <div className="grid grid-cols-[1fr_auto] gap-3">
          <Input label="Ad (LLM'e görünür)" value={name} onChange={(e) => setName(e.target.value)} placeholder="get_weather" />
          <Dropdown label="Metot" value={method} options={METHODS} onChange={setMethod} />
        </div>
        <Input label="Açıklama" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Şehrin hava durumunu getirir" />
        <Input label="URL ({param} placeholder olabilir)" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://api.example.com/{city}/weather" />
        <Textarea label="Header'lar (JSON, opsiyonel — gizli)" value={headers} onChange={(e) => setHeaders(e.target.value)} rows={2} className="font-mono text-xs" placeholder={'{ "X-Api-Key": "..." }'} />
        <Textarea label="Parametreler (JSON Schema — LLM bunları doldurur)" value={params} onChange={(e) => setParams(e.target.value)} rows={7} className="font-mono text-xs" />
        <div>
          <Button size="sm" onClick={add} loading={adding} disabled={!name.trim() || !url.trim()}>
            <Plus size={13} />Ekle
          </Button>
        </div>
      </div>

      {/* Liste */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="h-5 w-5" /></div>
      ) : tools.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">Henüz özel tool yok.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {tools.map((t) => <ToolCard key={t.id} tool={t} onDelete={() => remove(t.id)} />)}
        </div>
      )}
    </div>
  );
}

function ToolCard({ tool, onDelete }: { tool: CustomTool; onDelete: () => void }) {
  const [argsJson, setArgsJson] = useState("{}");
  const [result, setResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [open, setOpen] = useState(false);

  async function test() {
    setTesting(true);
    setResult(null);
    try {
      let args: unknown = {};
      try { args = argsJson.trim() ? JSON.parse(argsJson) : {}; } catch { setResult("Argümanlar geçerli JSON değil."); setTesting(false); return; }
      const r = await api.post<{ result: string }>(`/custom-tools/${tool.id}/test`, { arguments: args });
      setResult(r.result);
    } catch (err) {
      setResult(err instanceof ApiError ? err.message : "Test başarısız.");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <div className="flex items-center gap-3">
        <span className="rounded-md bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-300">{tool.method}</span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-sm text-zinc-200">{tool.name}</p>
          <p className="truncate text-[11px] text-zinc-600">{tool.url}{tool.header_names.length ? ` · 🔑 ${tool.header_names.join(", ")}` : ""}</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}><Play size={12} />Test</Button>
        <button onClick={onDelete} title="Sil" className="rounded-md p-1.5 text-zinc-500 hover:bg-red-500/10 hover:text-red-400"><Trash2 size={14} /></button>
      </div>
      {tool.description && <p className="mt-1.5 text-xs text-zinc-500">{tool.description}</p>}
      {open && (
        <div className="mt-3 flex flex-col gap-2 border-t border-zinc-800/60 pt-3">
          <Textarea label="Örnek argümanlar (JSON)" value={argsJson} onChange={(e) => setArgsJson(e.target.value)} rows={2} className="font-mono text-xs" />
          <div><Button size="sm" onClick={test} loading={testing}>Çalıştır</Button></div>
          {result !== null && (
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border border-zinc-800/60 bg-zinc-950/50 p-2 text-[11px] text-zinc-400">{result}</pre>
          )}
        </div>
      )}
    </div>
  );
}
