"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, BookOpen, Plus, Trash2, Check, Power } from "lucide-react";
import { api, ApiError, type TeamKnowledge, type Team } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dropdown } from "@/components/ui/dropdown";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

const KINDS = [
  { value: "constitution", label: "Anayasa" },
  { value: "rule", label: "Kural" },
  { value: "instruction", label: "Talimat" },
  { value: "prompt", label: "Prompt" },
];
const kindLabel = (k: string) => KINDS.find((x) => x.value === k)?.label ?? k;

export default function TeamKnowledgePage() {
  const { id } = useParams<{ id: string }>();
  const [team, setTeam] = useState<Team | null>(null);
  const [items, setItems] = useState<TeamKnowledge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("rule");
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [adding, setAdding] = useState(false);

  function load() {
    api.get<TeamKnowledge[]>(`/teams/${id}/knowledge`).then(setItems).catch(() => setError("Yüklenemedi.")).finally(() => setLoading(false));
  }
  useEffect(() => {
    api.get<Team>(`/teams/${id}`).then(setTeam).catch(() => {});
    load();
  }, [id]);

  async function add() {
    setAdding(true);
    setError("");
    try {
      await api.post(`/teams/${id}/knowledge`, { kind, name, content, is_active: true });
      setName(""); setContent(""); setKind("rule");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eklenemedi.");
    } finally {
      setAdding(false);
    }
  }

  async function toggle(k: TeamKnowledge) {
    try {
      await api.patch(`/teams/${id}/knowledge/${k.id}`, { kind: k.kind, name: k.name, content: k.content, is_active: !k.is_active });
      setItems((xs) => xs.map((x) => (x.id === k.id ? { ...x, is_active: !x.is_active } : x)));
    } catch { /* ignore */ }
  }

  async function remove(kid: string) {
    if (!window.confirm("Bu bilgi öğesini sil?")) return;
    try { await api.delete(`/teams/${id}/knowledge/${kid}`); setItems((xs) => xs.filter((x) => x.id !== kid)); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Silinemedi."); }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link href={`/teams/${id}/chat`} className="mb-5 inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Sohbete dön
      </Link>

      <div className="mb-2 flex items-center gap-2">
        <BookOpen size={18} className="text-indigo-400" />
        <h1 className="text-xl font-semibold text-zinc-100">Ekip Knowledge Base</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        {team?.name ? <span className="text-zinc-300">{team.name}</span> : "Ekip"} — buradaki <span className="text-zinc-300">aktif</span> öğeler
        ekip çalışırken <span className="text-zinc-300">tüm üyelerin</span> sistem promptuna eklenir (ortak anayasa/kural/talimat).
      </p>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      <div className="mb-8 flex flex-col gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
        <p className="text-sm font-medium text-zinc-200">Bilgi öğesi ekle</p>
        <div className="grid grid-cols-[140px_1fr] gap-3">
          <Dropdown label="Tür" value={kind} options={KINDS} onChange={setKind} />
          <Input label="Ad" value={name} onChange={(e) => setName(e.target.value)} placeholder="Risk kuralı" />
        </div>
        <Textarea label="İçerik" value={content} onChange={(e) => setContent(e.target.value)} rows={3}
          placeholder="Ör. Asla %2'den fazla pozisyon önerme; her öneride risk notu ekle." />
        <div>
          <Button size="sm" onClick={add} loading={adding} disabled={!name.trim() || !content.trim()}>
            <Plus size={13} />Ekle
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="h-5 w-5" /></div>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-600">
          Henüz bilgi öğesi yok. Ekibin ortak kurallarını buraya ekle.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((k) => (
            <div key={k.id} className={cn("rounded-xl border bg-zinc-900/40 p-3", k.is_active ? "border-zinc-800/80" : "border-zinc-800/40 opacity-60")}>
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-300">{kindLabel(k.kind)}</span>
                <span className="flex-1 truncate text-sm font-medium text-zinc-200">{k.name}</span>
                {k.is_active && <span className="flex items-center gap-1 text-[10px] text-green-400"><Check size={11} />aktif</span>}
                <button onClick={() => toggle(k)} title={k.is_active ? "Pasifleştir" : "Aktifleştir"}
                  className="rounded-md p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"><Power size={13} /></button>
                <button onClick={() => remove(k.id)} title="Sil"
                  className="rounded-md p-1 text-zinc-500 hover:bg-red-500/10 hover:text-red-400"><Trash2 size={13} /></button>
              </div>
              {k.content && <p className="mt-1.5 whitespace-pre-wrap text-xs text-zinc-500">{k.content}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
