"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, ChevronRight, MessageSquare, Settings } from "lucide-react";
import { api, ApiError, type Team, type TeamRun, type TeamStats } from "@/lib/api";
import { roleIcon, roleColor } from "@/lib/team-roles";
import { Button } from "@/components/ui/button";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export default function TeamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [team, setTeam] = useState<Team | null>(null);
  const [runs, setRuns] = useState<TeamRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [input, setInput] = useState("");
  const [starting, setStarting] = useState(false);
  const [stats, setStats] = useState<TeamStats | null>(null);
  // Ekip ayarları editörü
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  async function saveSettings(patch: Partial<Pick<Team, "shared_instructions" | "max_delegations" | "run_timeout_seconds">>) {
    setSavingSettings(true);
    try {
      const updated = await api.patch<Team>(`/teams/${id}`, patch);
      setTeam(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kaydedilemedi.");
    } finally {
      setSavingSettings(false);
    }
  }

  const loadRuns = useCallback(() => {
    api.get<TeamRun[]>(`/teams/${id}/runs`).then(setRuns).catch(() => {});
    api.get<TeamStats>(`/teams/${id}/stats`).then(setStats).catch(() => {});
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

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">{team?.name}</h1>
          {team?.description && <p className="mt-1 text-sm text-zinc-500">{team.description}</p>}
        </div>
        <Link href={`/teams/${id}/chat`}>
          <Button size="sm"><MessageSquare size={13} />Sohbet</Button>
        </Link>
      </div>

      {error && <Alert variant="error" className="my-4">{error}</Alert>}

      {/* Üyeler */}
      <h2 className="mb-2 mt-6 text-xs font-medium uppercase tracking-wide text-zinc-500">Üyeler</h2>
      <div className="mb-6 overflow-hidden rounded-xl border border-zinc-800/80">
        {team?.members.map((m, i) => {
          const RI = roleIcon(m.role);
          return (
            <div key={m.id} className={"flex items-center gap-3 px-4 py-3 " + (i > 0 ? "border-t border-zinc-800/60" : "")}>
              <RI size={15} className={roleColor(m.role)} />
              <Badge variant={m.role === "coordinator" ? "indigo" : "zinc"}>{m.role}</Badge>
              <span className="flex-1 text-sm text-zinc-300">{m.agent_name ?? "—"}</span>
            </div>
          );
        })}
      </div>

      {/* Ekip ayarları (prompt + bütçe) */}
      {team && (
        <div className="mb-6">
          <button
            onClick={() => setSettingsOpen((o) => !o)}
            className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-zinc-500 hover:text-zinc-300"
          >
            <Settings size={12} className={cn("transition-transform", settingsOpen && "rotate-90")} />
            Ekip ayarları (prompt & bütçe)
          </button>
          {settingsOpen && <TeamSettings team={team} saving={savingSettings} onSave={saveSettings} />}
        </div>
      )}

      {/* Çalıştır */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Görev ver</h2>
      <div className="mb-8 flex flex-col gap-2">
        <Textarea value={input} onChange={(e) => setInput(e.target.value)} rows={3} placeholder="Ekibe görevi yaz… (Coordinator delege edecek)" />
        <div>
          <Button size="sm" onClick={run} loading={starting} disabled={!input.trim()}><Play size={13} />Ekibi çalıştır</Button>
        </div>
      </div>

      {/* Performans (C3) */}
      {stats && stats.total_runs > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-zinc-800/60 bg-zinc-900/30 px-4 py-3">
          <span className="flex items-baseline gap-1.5">
            <span className={"text-sm font-semibold " + (stats.success_rate != null && stats.success_rate >= 0.99 ? "text-green-400" : stats.success_rate != null && stats.success_rate >= 0.6 ? "text-amber-400" : "text-zinc-100")}>
              {stats.success_rate == null ? "—" : `${Math.round(stats.success_rate * 100)}%`}
            </span>
            <span className="text-[11px] text-zinc-600">başarı</span>
          </span>
          <span className="flex items-baseline gap-1.5"><span className="text-sm font-semibold text-zinc-100">{stats.total_runs}</span><span className="text-[11px] text-zinc-600">çalıştırma</span></span>
          <span className="flex items-baseline gap-1.5"><span className="text-sm font-semibold text-zinc-100">{stats.completed_runs}/{stats.failed_runs}</span><span className="text-[11px] text-zinc-600">tamam/hata</span></span>
          <span className="flex items-baseline gap-1.5"><span className="text-sm font-semibold text-zinc-100">{stats.avg_duration_ms == null ? "—" : (stats.avg_duration_ms / 1000).toFixed(1) + "s"}</span><span className="text-[11px] text-zinc-600">ort. süre</span></span>
        </div>
      )}

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

function TeamSettings({ team, saving, onSave }: {
  team: Team;
  saving: boolean;
  onSave: (patch: { shared_instructions?: string | null; max_delegations?: number; run_timeout_seconds?: number }) => void;
}) {
  const [si, setSi] = useState(team.shared_instructions ?? "");
  const [maxD, setMaxD] = useState(team.max_delegations);
  const [timeout, setTimeoutS] = useState(team.run_timeout_seconds);
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-zinc-800/60 bg-zinc-950/40 p-3">
      <Textarea
        label="Ekip promptu (tüm üyelere eklenir)"
        value={si}
        onChange={(e) => setSi(e.target.value)}
        rows={3}
        className="text-xs"
        placeholder="Ortak kurallar: kısa/odaklı çalış, az arama yap, Türkçe yaz…"
      />
      <div className="grid grid-cols-2 gap-3">
        <Input label="Max delege" type="number" value={String(maxD)} onChange={(e) => setMaxD(Math.max(1, Math.min(50, Number(e.target.value) || 10)))} />
        <Input label="Üst süre (sn)" type="number" value={String(timeout)} onChange={(e) => setTimeoutS(Math.max(30, Math.min(3600, Number(e.target.value) || 600)))} />
      </div>
      <div>
        <Button size="sm" loading={saving} onClick={() => onSave({ shared_instructions: si || null, max_delegations: maxD, run_timeout_seconds: timeout })}>
          Ayarları kaydet
        </Button>
      </div>
      <p className="text-[11px] text-zinc-600">
        Max delege: bir çalıştırmada Coordinator&apos;ın yapabileceği max delege (sonsuz tur/token israfını önler).
        Üst süre: tüm ekip çalıştırması için tavan.
      </p>
    </div>
  );
}
