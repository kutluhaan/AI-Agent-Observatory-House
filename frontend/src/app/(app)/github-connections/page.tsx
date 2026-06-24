"use client";

import { useEffect, useState } from "react";
import { Github, Plus, Trash2, Plug, CheckCircle2 } from "lucide-react";
import { api, ApiError, type GithubConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

export default function GithubConnectionsPage() {
  const [conns, setConns] = useState<GithubConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [adding, setAdding] = useState(false);

  function load() {
    api.get<GithubConnection[]>("/github-connections").then(setConns).catch(() => setError("Yüklenemedi.")).finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function add() {
    setAdding(true);
    setError("");
    try {
      await api.post("/github-connections", { name, token });
      setName(""); setToken("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eklenemedi.");
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Bu GitHub bağlantısını sil?")) return;
    try {
      await api.delete(`/github-connections/${id}`);
      setConns((c) => c.filter((x) => x.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Silinemedi.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <div className="mb-2 flex items-center gap-2">
        <Github size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">GitHub</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Bir GitHub <span className="text-zinc-300">Personal Access Token</span> ekle. Agent&apos;lara
        <span className="text-zinc-300"> github_search / github_repo_info / github_issues / github_read_file</span> tool&apos;larını
        verince repo/issue/kod arayıp dosya okuyabilir. Token <span className="text-zinc-300">şifreli</span> saklanır, asla geri gösterilmez.
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      <div className="mb-8 flex flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
        <p className="text-sm font-medium text-zinc-200">Bağlantı ekle</p>
        <Input label="Ad" value={name} onChange={(e) => setName(e.target.value)} placeholder="default" />
        <Input label="Personal Access Token" type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="ghp_…" />
        <div>
          <Button size="sm" onClick={add} loading={adding} disabled={!name.trim() || !token.trim()}>
            <Plus size={13} />Ekle
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="h-5 w-5" /></div>
      ) : conns.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">
          Henüz GitHub bağlantısı yok.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {conns.map((c) => <ConnCard key={c.id} conn={c} onDelete={() => remove(c.id)} />)}
        </div>
      )}
    </div>
  );
}

function ConnCard({ conn, onDelete }: { conn: GithubConnection; onDelete: () => void }) {
  const [testing, setTesting] = useState(false);
  const [login, setLogin] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  async function test() {
    setTesting(true);
    setLogin(null);
    setMsg("");
    try {
      const r = await api.post<{ ok: boolean; login: string }>(`/github-connections/${conn.id}/test`);
      setLogin(r.login);
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Başarısız.");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <div className="flex items-center gap-3">
        <Github size={15} className="text-zinc-500" />
        <div className="flex-1">
          <p className="text-sm font-medium text-zinc-200">{conn.name}</p>
          <p className="text-[11px] text-zinc-600">PAT · 🔒 token gizli</p>
        </div>
        {login && <span className="flex items-center gap-1 text-[11px] text-green-400"><CheckCircle2 size={12} />@{login}</span>}
        <Button size="sm" variant="outline" onClick={test} loading={testing}>
          <Plug size={13} />Test
        </Button>
        <button onClick={onDelete} title="Sil" className="rounded-md p-1.5 text-zinc-500 hover:bg-red-500/10 hover:text-red-400">
          <Trash2 size={14} />
        </button>
      </div>
      {msg && <p className="mt-2 text-xs text-red-400">{msg}</p>}
    </div>
  );
}
