"use client";

import { useEffect, useState } from "react";
import { Plug, Trash2, Search, ExternalLink, Lock, Plus, CheckCircle2 } from "lucide-react";
import { api, ApiError, type McpServer, type McpToolInfo, type McpRegistryEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

function deriveName(regName: string): string {
  const seg = regName.split("/").pop() ?? regName;
  return seg.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 60);
}

export default function McpServersPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loadingServers, setLoadingServers] = useState(true);
  const [error, setError] = useState("");

  function loadServers() {
    api.get<McpServer[]>("/mcp-servers").then(setServers).catch(() => setError("Sunucular yüklenemedi.")).finally(() => setLoadingServers(false));
  }
  useEffect(loadServers, []);

  const addedUrls = new Set(servers.map((s) => s.url));

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <div className="mb-2 flex items-center gap-2">
        <Plug size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">MCP Sunucuları</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Resmi <span className="text-zinc-300">MCP Registry</span>&apos;den Streamable HTTP destekli sunucuları ara ve tek tıkla ekle.
        Eklediklerin agent oluştururken tool olarak seçilebilir.
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {/* Registry tarayıcı (varsayılan) */}
      <RegistryBrowser addedUrls={addedUrls} onAdded={loadServers} />

      {/* Ekli sunucular */}
      <h2 className="mb-2 mt-8 text-xs font-medium uppercase tracking-wide text-zinc-500">Ekli sunucular</h2>
      {loadingServers ? (
        <div className="flex justify-center py-8"><Spinner className="h-5 w-5" /></div>
      ) : servers.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">
          Henüz MCP sunucusu eklemedin. Yukarıdan registry&apos;den ekle.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {servers.map((s) => (
            <ServerCard key={s.id} server={s} onDelete={() => setServers((x) => x.filter((y) => y.id !== s.id))} setError={setError} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Registry tarayıcı (inline, varsayılan) ──────────────────

function RegistryBrowser({ addedUrls, onAdded }: { addedUrls: Set<string>; onAdded: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<McpRegistryEntry[]>([]);
  const [searching, setSearching] = useState(true);
  const [error, setError] = useState("");

  async function search(q: string) {
    setSearching(true);
    setError("");
    try {
      const r = await api.get<McpRegistryEntry[]>(`/mcp-registry/search?q=${encodeURIComponent(q)}&limit=25`);
      setResults(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registry'e ulaşılamadı.");
    } finally {
      setSearching(false);
    }
  }
  useEffect(() => { search(""); }, []); // varsayılan: popüler sunucular

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-4">
      <form onSubmit={(e) => { e.preventDefault(); void search(query); }} className="mb-3 flex items-end gap-2">
        <div className="relative flex-1">
          <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="MCP ara: github, notion, filesystem…"
            className="w-full rounded-lg border border-zinc-800 bg-zinc-950 py-2 pl-9 pr-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-700 focus:outline-none" />
        </div>
        <Button size="sm" type="submit" loading={searching}>Ara</Button>
      </form>

      {error && <Alert variant="error">{error}</Alert>}

      <div className="max-h-[420px] overflow-y-auto pr-1">
        {searching && results.length === 0 ? (
          <div className="flex justify-center py-8"><Spinner className="h-5 w-5" /></div>
        ) : results.length === 0 ? (
          <p className="py-6 text-center text-xs text-zinc-600">Sonuç yok.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {results.map((r) => <RegistryRow key={r.name} entry={r} added={!!r.remote_url && addedUrls.has(r.remote_url)} onAdded={onAdded} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function RegistryIcon({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  const letter = (deriveName(name)[0] || "?").toUpperCase();
  if (!url || failed) {
    return (
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-indigo-500/10 text-xs font-semibold text-indigo-300">
        {letter}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" onError={() => setFailed(true)}
      className="h-8 w-8 shrink-0 rounded-md bg-white/5 object-contain p-0.5" />
  );
}

function RegistryRow({ entry, added, onAdded }: { entry: McpRegistryEntry; added: boolean; onAdded: () => void }) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(added);

  async function add() {
    if (!entry.remote_url) return;
    setBusy(true);
    setErr("");
    try {
      await api.post("/mcp-servers", { name: deriveName(entry.name), url: entry.remote_url, api_key: key || null });
      setDone(true);
      onAdded();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Eklenemedi.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-800/70 bg-zinc-950/40 p-3">
      <div className="flex items-start gap-3">
        <RegistryIcon url={entry.icon_url} name={entry.name} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-sm font-medium text-zinc-200">{deriveName(entry.name)}</span>
            {entry.version && <span className="shrink-0 text-[10px] text-zinc-600">v{entry.version}</span>}
            {entry.requires_auth && <Lock size={10} className="shrink-0 text-amber-400" />}
          </div>
          {entry.description && <p className="mt-0.5 line-clamp-2 text-[11px] text-zinc-500">{entry.description}</p>}
          <div className="mt-1 flex items-center gap-2 text-[10px] text-zinc-600">
            <span className="truncate font-mono">{entry.name}</span>
            {entry.repository_url && (
              <a href={entry.repository_url} target="_blank" rel="noreferrer" className="flex shrink-0 items-center gap-0.5 hover:text-indigo-400">
                <ExternalLink size={9} />repo
              </a>
            )}
          </div>
        </div>
        <div className="shrink-0">
          {!entry.addable ? <span className="text-[10px] text-zinc-600">HTTP yok</span>
            : done ? <span className="flex items-center gap-1 text-[10px] text-green-400"><CheckCircle2 size={11} />ekli</span>
            : <Button size="sm" variant="outline" onClick={add} loading={busy}><Plus size={12} />Ekle</Button>}
        </div>
      </div>
      {entry.addable && !done && entry.requires_auth && (
        <Input className="mt-2" type="password" value={key} onChange={(e) => setKey(e.target.value)}
          placeholder="API anahtarı (bu sunucu istiyor) — opsiyonel, sonra da eklenebilir" />
      )}
      {err && <p className="mt-1.5 text-[11px] text-red-400">{err}</p>}
    </div>
  );
}

function ServerCard({ server, onDelete, setError }: { server: McpServer; onDelete: () => void; setError: (s: string) => void }) {
  const [tools, setTools] = useState<McpToolInfo[] | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState("");

  async function discover() {
    setDiscovering(true);
    setDiscoverError("");
    try { setTools(await api.get<McpToolInfo[]>(`/mcp-servers/${server.id}/tools`)); }
    catch (err) { setDiscoverError(err instanceof ApiError ? err.message : "Bağlanılamadı."); }
    finally { setDiscovering(false); }
  }

  async function remove() {
    if (!window.confirm("Bu MCP sunucusunu sil?")) return;
    try { await api.delete(`/mcp-servers/${server.id}`); onDelete(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Silinemedi."); }
  }

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-zinc-200">{server.name}</p>
          <p className="text-[11px] text-zinc-600">{server.url}{server.has_api_key ? " · 🔑" : ""}</p>
        </div>
        <Button size="sm" variant="outline" onClick={discover} loading={discovering}><Search size={13} />Tool&apos;ları keşfet</Button>
        <button onClick={remove} title="Sil" className="rounded-md p-1.5 text-zinc-500 hover:bg-red-500/10 hover:text-red-400"><Trash2 size={14} /></button>
      </div>
      {discoverError && <p className="mt-2 text-xs text-red-400">{discoverError}</p>}
      {tools && (
        <div className="mt-3 border-t border-zinc-800/60 pt-3">
          {tools.length === 0 ? <p className="text-xs text-zinc-600">Sunucu hiç tool sunmuyor.</p> : (
            <div className="flex flex-col gap-1.5">
              {tools.map((t) => (
                <div key={t.name} className="text-xs">
                  <span className="font-mono text-indigo-300">{t.name}</span>
                  {t.description && <span className="text-zinc-600"> — {t.description}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
