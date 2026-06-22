"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { api, type Experiment, type ExperimentVariantResult, type TestRunSummary } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type MetricRow = {
  label: string;
  hint?: string;
  // değer + "daha iyisi" yönü (yüksek/düşük) → kazananı vurgulamak için
  get: (s: TestRunSummary | null) => number | null;
  fmt: (v: number | null) => string;
  better: "high" | "low";
};

const METRICS: MetricRow[] = [
  {
    label: "Geçme oranı",
    hint: "passed / total",
    get: (s) => (s ? s.pass_rate : null),
    fmt: (v) => (v == null ? "—" : `${Math.round(v * 100)}%`),
    better: "high",
  },
  {
    label: "Geçen / toplam",
    get: (s) => (s ? s.passed : null),
    fmt: (v) => (v == null ? "—" : String(v)),
    better: "high",
  },
  {
    label: "Ort. cevap süresi",
    get: (s) => (s ? s.avg_latency_ms : null),
    fmt: (v) => (v == null ? "—" : `${(v / 1000).toFixed(2)}s`),
    better: "low",
  },
  {
    label: "Judge skoru",
    hint: "çıktı kalitesi dahil",
    get: (s) => (s ? s.avg_judge_score ?? null : null),
    fmt: (v) => (v == null ? "—" : v.toFixed(2)),
    better: "high",
  },
  {
    label: "Maliyet",
    get: (s) => (s ? s.total_cost_usd ?? null : null),
    fmt: (v) => (v == null ? "—" : `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`),
    better: "low",
  },
  {
    label: "Token",
    get: (s) => (s ? s.total_tokens ?? null : null),
    fmt: (v) => (v == null ? "—" : v.toLocaleString()),
    better: "low",
  },
];

function bestIndex(row: MetricRow, variants: ExperimentVariantResult[]): number | null {
  let best: number | null = null;
  let bestVal: number | null = null;
  variants.forEach((v, i) => {
    const val = row.get(v.summary);
    if (val == null) return;
    if (bestVal == null || (row.better === "high" ? val > bestVal : val < bestVal)) {
      bestVal = val;
      best = i;
    }
  });
  return best;
}

export default function ExperimentComparisonPage() {
  const { id, experimentId } = useParams<{ id: string; experimentId: string }>();
  const [exp, setExp] = useState<Experiment | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .get<Experiment>(`/test-suites/${id}/experiments/${experimentId}`)
      .then(setExp)
      .catch(() => setError("Deney bulunamadı."));
  }, [id, experimentId]);

  useEffect(() => {
    load();
  }, [load]);

  // Çalışırken her 3sn'de bir yenile
  useEffect(() => {
    if (!exp || exp.status !== "running") return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [exp, load]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  if (!exp) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  const variants = exp.variants;

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <Link
        href={`/test-suites/${id}`}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Suite
      </Link>

      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-zinc-100">A/B Karşılaştırma</h1>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          {exp.status === "running" && <Spinner className="h-3.5 w-3.5" />}
          <Badge variant={exp.status === "completed" ? "green" : "indigo"}>{exp.status}</Badge>
        </div>
      </div>

      {/* Karşılaştırma tablosu: satır = metrik, sütun = varyant */}
      <div className="mb-8 overflow-x-auto rounded-xl border border-zinc-800/80">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/40">
              <th className="px-4 py-3 text-left text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                Metrik
              </th>
              {variants.map((v) => (
                <th key={v.run_id} className="px-4 py-3 text-left">
                  <span className="text-zinc-200">{v.variant_label ?? "—"}</span>
                  <Badge variant={statusVariant(v.status)} className="ml-2">
                    {v.status}
                  </Badge>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map((row) => {
              const best = variants.length > 1 ? bestIndex(row, variants) : null;
              return (
                <tr key={row.label} className="border-t border-zinc-800/60">
                  <td className="px-4 py-2.5 text-xs text-zinc-400">
                    {row.label}
                    {row.hint && <span className="block text-[10px] text-zinc-600">{row.hint}</span>}
                  </td>
                  {variants.map((v, i) => {
                    const raw = row.get(v.summary);
                    const display =
                      row.label === "Geçen / toplam" && v.summary
                        ? `${v.summary.passed}/${v.summary.total}`
                        : row.fmt(raw);
                    return (
                      <td
                        key={v.run_id}
                        className={cn(
                          "px-4 py-2.5 font-medium",
                          best === i ? "text-green-400" : "text-zinc-200",
                        )}
                      >
                        {display}
                        {best === i && variants.length > 1 && raw != null && (
                          <span className="ml-1 text-[10px] text-green-600">en iyi</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Her varyantın system prompt'u + run detay linki */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Varyantlar</h2>
      <div className="flex flex-col gap-3">
        {variants.map((v) => (
          <div key={v.run_id} className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-zinc-200">{v.variant_label ?? "—"}</span>
              <Link
                href={`/test-runs/${v.run_id}`}
                className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
              >
                Run detayı
                <ChevronRight size={13} />
              </Link>
            </div>
            <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg border border-zinc-800/60 bg-zinc-950/50 p-3 text-[11px] text-zinc-400">
              {v.system_prompt_override ?? "(override yok)"}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
