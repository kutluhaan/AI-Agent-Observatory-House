"use client";

import { useEffect, useState } from "react";
import { Plug, Plus, Trash2, Search } from "lucide-react";
import { api, ApiError, type McpServer, type McpToolInfo } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function McpServersPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // yeni sunucu formu
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [adding, setAdding] = useState(false);

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
