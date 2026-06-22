"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api, type Agent, type AgentStats, type AgentTrendPoint, type RagTrendPoint } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

function fmtPct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function fmtUsd(v: number | null): string {
  if (v == null) return "—";
  return `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`;
}

function fmtScore(v: number | null): string {
  return v == null ? "—" : v.toFixed(2);
}

export default function AgentPerformancePage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Agent>(`/agents/${id}`).then(setAgent),
      api.get<AgentStats>(`/agents/${id}/stats`).then(setStats),
    ])
      .catch(() => setError("Agent performansı yüklenemedi."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  const hasData = stats && stats.total_cases > 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link
        href="/agents"
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Agents
      </Link>

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-zinc-100">{agent?.name} · Performans</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Bu agent&apos;ın tüm test çalıştırmalarındaki birleşik sonuçları (kalıcı).
        </p>
      </div>

      {!hasData ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <p className="text-sm text-zinc-400">Henüz test verisi yok.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Bu agent&apos;ı bir test suite&apos;inde çalıştırınca performansı burada toplanır.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Kpi label="Geçme oranı" value={fmtPct(stats!.pass_rate)} hint={`${stats!.passed_cases}/${stats!.total_cases} case`} accent />
            <Kpi label="Ort. cevap süresi" value={stats!.avg_latency_ms != null ? `${(stats!.avg_latency_ms / 1000).toFixed(2)}s` : "—"} hint="case ortalaması" />
            <Kpi label="Judge skoru" value={stats!.avg_judge_score != null ? stats!.avg_judge_score.toFixed(2) : "—"} hint="çıktı kalitesi dahil" />
            <Kpi label="Ort. maliyet" value={fmtUsd(stats!.avg_cost_usd)} hint="case başına" />
            <Kpi label="Toplam token" value={stats!.total_tokens != null ? stats!.total_tokens.toLocaleString() : "—"} />
            <Kpi label="Çalıştırma" value={String(stats!.runs_count)} hint="run sayısı" />
          </div>

          {stats!.trend.length > 1 && (
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
              <p className="mb-1.5 text-[11px] text-zinc-600">Geçme oranı trendi (eski → yeni · run başına)</p>
              <PassRateTrend trend={stats!.trend} />
            </div>
          )}

          {/* F5.3 — Bilgi etkisi (RAG): yalnızca RAG'li case varsa */}
          {stats!.rag && (
            <div className="mt-6">
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                Bilgi etkisi (RAG) · {stats!.rag.cases_with_rag} case
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Kpi label="Faithfulness" value={fmtScore(stats!.rag.faithfulness)} hint="halüsinasyonsuzluk" />
                <Kpi label="Answer relevancy" value={fmtScore(stats!.rag.answer_relevancy)} hint="soruya uygunluk" />
                <Kpi label="Context recall" value={fmtScore(stats!.rag.context_recall)} hint="bilgiyi yakalama" />
                <Kpi label="Context precision" value={fmtScore(stats!.rag.context_precision)} hint="bilgi isabeti" />
              </div>
              {stats!.rag.trend.length > 1 && (
                <div className="mt-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
                  <p className="mb-1.5 text-[11px] text-zinc-600">Faithfulness trendi (eski → yeni)</p>
                  <ScoreTrend trend={stats!.rag.trend} />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
      <p className="text-[10px] uppercase tracking-wide text-zinc-600">{label}</p>
      <p className={cn("mt-0.5 text-lg font-semibold", accent ? "text-green-400" : "text-zinc-100")}>{value}</p>
      {hint && <p className="text-[10px] text-zinc-700">{hint}</p>}
    </div>
  );
}

function PassRateTrend({ trend }: { trend: AgentTrendPoint[] }) {
  const last = trend.slice(-30);
  return (
    <div className="flex h-16 items-end gap-1">
      {last.map((p) => {
        const r = p.pass_rate ?? 0;
        const color = r >= 0.99 ? "bg-green-500/70" : r >= 0.6 ? "bg-amber-500/70" : "bg-red-500/70";
        const lat = p.avg_latency_ms != null ? ` · ${(p.avg_latency_ms / 1000).toFixed(2)}s` : "";
        return (
          <div
            key={p.run_id}
            title={`${new Date(p.created_at).toLocaleString()} · ${Math.round(r * 100)}% · ${p.cases} case${lat}`}
            className={cn("min-w-[6px] flex-1 rounded-sm", color)}
            style={{ height: `${Math.max(6, r * 100)}%` }}
          />
        );
      })}
    </div>
  );
}

function ScoreTrend({ trend }: { trend: RagTrendPoint[] }) {
  const last = trend.slice(-30);
  return (
    <div className="flex h-16 items-end gap-1">
      {last.map((p) => {
        const r = p.faithfulness ?? 0;
        const color = r >= 0.8 ? "bg-green-500/70" : r >= 0.5 ? "bg-amber-500/70" : "bg-red-500/70";
        return (
          <div
            key={p.run_id}
            title={`${new Date(p.created_at).toLocaleString()} · faithfulness ${r.toFixed(2)}`}
            className={cn("min-w-[6px] flex-1 rounded-sm", color)}
            style={{ height: `${Math.max(6, r * 100)}%` }}
          />
        );
      })}
    </div>
  );
}
