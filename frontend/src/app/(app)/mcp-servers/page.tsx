"use client";

import { useEffect, useState } from "react";
import { Plug, Plus, Trash2, Search, Globe, ExternalLink, Lock } from "lucide-react";
import { api, ApiError, type McpServer, type McpToolInfo, type McpRegistryEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Modal } from "@/components/ui/modal";

export default function McpServersPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // yeni sunucu formu
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [adding, setAdding] = useState(false);
  const [registryOpen, setRegistryOpen] = useState(false);

  function load() {
    api.get<McpServer[]>("/mcp-servers").then(setServers).catch(() => setError("Yüklenemedi.")).finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function addServer() {
    setAdding(true);
    setError("");
    try {
      await api.post("/mcp-servers", { name, url, api_key: apiKey || null });
      setName(""); setUrl(""); setApiKey("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eklenemedi.");
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Bu MCP sunucusunu sil?")) return;
    try {
      await api.delete(`/mcp-servers/${id}`);
      setServers((s) => s.filter((x) => x.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Silinemedi.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <Plug size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">MCP Sunucuları</h1>
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => setRegistryOpen(true)}>
          <Globe size={13} />Registry&apos;den keşfet
        </Button>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Dış <span className="text-zinc-300">Model Context Protocol</span> (Streamable HTTP) sunucularını
        org&apos;a ekle; agent oluştururken tool&apos;larını seç.
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {/* Yeni sunucu */}
      <div className="mb-8 flex flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
        <p className="text-sm font-medium text-zinc-200">Sunucu ekle</p>
        <div className="grid grid-cols-2 gap-3">
          <Input label="Ad" value={name} onChange={(e) => setName(e.target.value)} placeholder="my-tools" />
          <Input label="API anahtarı (opsiyonel)" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Bearer token" />
        </div>
        <Input label="URL (Streamable HTTP)" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://mcp.example.com/mcp" />
        <div>
          <Button size="sm" onClick={addServer} loading={adding} disabled={!name.trim() || !url.trim()}>
            <Plus size={13} />
            Ekle
          </Button>
        </div>
      </div>

      {/* Liste */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="h-5 w-5" /></div>
      ) : servers.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">
          Henüz MCP sunucusu yok.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {servers.map((s) => (
            <ServerCard key={s.id} server={s} onDelete={() => remove(s.id)} />
          ))}
        </div>
      )}

      <RegistryModal open={registryOpen} onClose={() => setRegistryOpen(false)} onAdded={load} />
    </div>
  );
}

// ── Resmi MCP Registry keşfi (D/#2) ─────────────────────────

function deriveName(regName: string): string {
  const seg = regName.split("/").pop() ?? regName;
  return seg.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 60);
}

function RegistryModal({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<McpRegistryEntry[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [addedNames, setAddedNames] = useState<Set<string>>(new Set());

  async function search() {
    setSearching(true);
    setError("");
    try {
      const r = await api.get<McpRegistryEntry[]>(`/mcp-registry/search?q=${encodeURIComponent(query)}&limit=25`);
      setResults(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registry'e ulaşılamadı.");
    } finally {
      setSearching(false);
    }
  }

  // İlk açılışta popüler sunucuları getir
  useEffect(() => {
    if (open && results.length === 0) void search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <Modal open title="MCP Registry — sunucu keşfet" onClose={onClose} className="max-w-xl">
      <div className="flex flex-col gap-3">
        <p className="text-xs text-zinc-500">
          Resmi <span className="text-zinc-300">MCP Registry</span>&apos;de ara, Streamable HTTP destekli bir
          sunucuyu tek tıkla org&apos;una ekle.
        </p>
        <form onSubmit={(e) => { e.preventDefault(); void search(); }} className="flex items-end gap-2">
          <div className="flex-1">
            <Input label="Ara" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="github, notion, filesystem…" />
          </div>
          <Button size="sm" type="submit" loading={searching}><Search size={13} />Ara</Button>
        </form>

        {error && <Alert variant="error">{error}</Alert>}

        <div className="max-h-[50vh] overflow-y-auto pr-1">
          {searching && results.length === 0 ? (
            <div className="flex justify-center py-10"><Spinner className="h-5 w-5" /></div>
          ) : results.length === 0 ? (
            <p className="py-8 text-center text-xs text-zinc-600">Sonuç yok.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {results.map((r) => (
                <RegistryRow
                  key={r.name}
                  entry={r}
                  added={addedNames.has(r.name)}
                  onAdd={() => setAddedNames((prev) => new Set(prev).add(r.name))}
                  onAdded={onAdded}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

function RegistryRow({ entry, added, onAdd, onAdded }: {
  entry: McpRegistryEntry;
  added: boolean;
  onAdd: () => void;
  onAdded: () => void;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function add() {
    if (!entry.remote_url) return;
    setBusy(true);
    setErr("");
    try {
      await api.post("/mcp-servers", { name: deriveName(entry.name), url: entry.remote_url, api_key: key || null });
      onAdd();
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
          {!entry.addable ? (
            <span className="text-[10px] text-zinc-600">HTTP remote yok</span>
          ) : added ? (
            <span className="text-[10px] text-green-400">✓ eklendi</span>
          ) : (
            <Button size="sm" variant="outline" onClick={add} loading={busy}><Plus size={12} />Ekle</Button>
          )}
        </div>
      </div>
      {entry.addable && !added && entry.requires_auth && (
        <Input
          className="mt-2"
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="API anahtarı (bu sunucu istiyor) — opsiyonel, sonra da eklenebilir"
        />
      )}
      {err && <p className="mt-1.5 text-[11px] text-red-400">{err}</p>}
    </div>
  );
}

function ServerCard({ server, onDelete }: { server: McpServer; onDelete: () => void }) {
  const [tools, setTools] = useState<McpToolInfo[] | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState("");

  async function discover() {
    setDiscovering(true);
    setDiscoverError("");
    try {
      const t = await api.get<McpToolInfo[]>(`/mcp-servers/${server.id}/tools`);
      setTools(t);
    } catch (err) {
      setDiscoverError(err instanceof ApiError ? err.message : "Bağlanılamadı.");
    } finally {
      setDiscovering(false);
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-zinc-200">{server.name}</p>
          <p className="text-[11px] text-zinc-600">{server.url}{server.has_api_key ? " · 🔑" : ""}</p>
        </div>
        <Button size="sm" variant="outline" onClick={discover} loading={discovering}>
          <Search size={13} />
          Tool&apos;ları keşfet
        </Button>
        <button onClick={onDelete} title="Sil" className="rounded-md p-1.5 text-zinc-500 hover:bg-red-500/10 hover:text-red-400">
          <Trash2 size={14} />
        </button>
      </div>

      {discoverError && <p className="mt-2 text-xs text-red-400">{discoverError}</p>}
      {tools && (
        <div className="mt-3 border-t border-zinc-800/60 pt-3">
          {tools.length === 0 ? (
            <p className="text-xs text-zinc-600">Sunucu hiç tool sunmuyor.</p>
          ) : (
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
