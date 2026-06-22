"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, ChevronRight, Crown } from "lucide-react";
import { api, ApiError, type Team, type TeamRun } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

export default function TeamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [team, setTeam] = useState<Team | null>(null);
  const [runs, setRuns] = useState<TeamRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [input, setInput] = useState("");
  const [starting, setStarting] = useState(false);

  const loadRuns = useCallback(() => {
    api.get<TeamRun[]>(`/teams/${id}/runs`).then(setRuns).catch(() => {});
  }, [id]);

  useEffect(() => {
    api.get<Team>(`/teams/${id}`).then(setTeam).catch(() => setError("Ekip bulunamadı.")).finally(() => setLoading(false));
    loadRuns();
  }, [id, loadRuns]);

  async function run() {
    setStarting(true);
    setError("");
    try {
      const r = await api.post<TeamRun>(`/teams/${id}/run`, { input });
      router.push(`/team-runs/${r.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Başlatılamadı.");
      setStarting(false);
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-5 w-5" /></div>;
  if (error && !team) return <div className="mx-auto max-w-2xl px-6 py-10"><Alert variant="error">{error}</Alert></div>;

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link href="/teams" className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Ekipler
      </Link>

      <h1 className="text-xl font-semibold text-zinc-100">{team?.name}</h1>
      {team?.description && <p className="mt-1 text-sm text-zinc-500">{team.description}</p>}

      {error && <Alert variant="error" className="my-4">{error}</Alert>}

      {/* Üyeler */}
      <h2 className="mb-2 mt-6 text-xs font-medium uppercase tracking-wide text-zinc-500">Üyeler</h2>
      <div className="mb-6 overflow-hidden rounded-xl border border-zinc-800/80">
        {team?.members.map((m, i) => (
          <div key={m.id} className={"flex items-center gap-3 px-4 py-3 " + (i > 0 ? "border-t border-zinc-800/60" : "")}>
            {m.role === "coordinator" ? <Crown size={14} className="text-amber-400" /> : <span className="w-3.5" />}
            <Badge variant={m.role === "coordinator" ? "indigo" : "zinc"}>{m.role}</Badge>
            <span className="flex-1 text-sm text-zinc-300">{m.agent_name ?? "—"}</span>
          </div>
        ))}
      </div>

      {/* Çalıştır */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Görev ver</h2>
      <div className="mb-8 flex flex-col gap-2">
        <Textarea value={input} onChange={(e) => setInput(e.target.value)} rows={3} placeholder="Ekibe görevi yaz… (Coordinator delege edecek)" />
        <div>
          <Button size="sm" onClick={run} loading={starting} disabled={!input.trim()}><Play size={13} />Ekibi çalıştır</Button>
        </div>
      </div>

      {/* Çalıştırmalar */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Çalıştırmalar</h2>
      {runs.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">Henüz çalıştırma yok.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {runs.map((r, i) => (
            <Link key={r.id} href={`/team-runs/${r.id}`} className={"flex items-center gap-4 px-4 py-3 transition-colors hover:bg-zinc-900/60 " + (i > 0 ? "border-t border-zinc-800/60" : "")}>
              <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
              <span className="flex-1 truncate text-xs text-zinc-500">{r.input}</span>
              <span className="text-[11px] text-zinc-600">{new Date(r.created_at).toLocaleString()}</span>
              <ChevronRight size={14} className="text-zinc-700" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
