"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, ChevronRight, SlidersHorizontal } from "lucide-react";
import {
  api,
  ApiError,
  type TestSuite,
  type TestRun,
  type SuiteStats,
  type SuiteTrendPoint,
  type KpiCatalog,
  type KpiCatalogItem,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export default function TestSuiteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [stats, setStats] = useState<SuiteStats | null>(null);
  const [kpiCatalog, setKpiCatalog] = useState<KpiCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [parallel, setParallel] = useState(false);
  const [starting, setStarting] = useState(false);

  const loadRuns = useCallback(() => {
    api.get<TestRun[]>(`/test-suites/${id}/runs`).then(setRuns).catch(() => {});
    api.get<SuiteStats>(`/test-suites/${id}/stats`).then(setStats).catch(() => {});
  }, [id]);

  useEffect(() => {
    api
      .get<TestSuite>(`/test-suites/${id}`)
      .then(setSuite)
      .catch(() => setError("Test suite not found."))
      .finally(() => setLoading(false));
    api.get<KpiCatalog>(`/test-suites/kpi-catalog`).then(setKpiCatalog).catch(() => {});
    loadRuns();
  }, [id, loadRuns]);

  // KPI seçimini kalıcı kaydet (suite'e PATCH) — boş → null (= varsayılan)
  const saveKpis = useCallback(
    async (keys: string[]) => {
      const payload = keys.length ? keys : null;
      const updated = await api.patch<TestSuite>(`/test-suites/${id}`, { kpis: payload });
      setSuite(updated);
    },
    [id],
  );

  async function handleRun() {
    setStarting(true);
    setError("");
    try {
      const run = await api.post<TestRun>(`/test-suites/${id}/run`, { parallel });
      router.push(`/test-runs/${run.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start run.");
      setStarting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  if (error && !suite) {
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link
        href="/test-suites"
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Test suites
      </Link>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">{suite?.name}</h1>
          {suite?.description && (
            <p className="mt-1 text-sm text-zinc-500">{suite.description}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-500">
            <input
              type="checkbox"
              checked={parallel}
              onChange={(e) => setParallel(e.target.checked)}
              className="accent-indigo-500"
            />
            Parallel
          </label>
          <Button size="sm" onClick={handleRun} loading={starting}>
            <Play size={13} />
            Run
          </Button>
        </div>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {/* YAML */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
        Configuration
      </h2>
      <pre className="mb-8 overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 text-xs text-zinc-400">
        {suite?.config_yaml}
      </pre>

      {/* Performans (kalıcı: tamamlanmış run'lardan + suite'e kayıtlı KPI seçimi) */}
      {stats && stats.completed_runs > 0 && kpiCatalog && (
        <>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            Performans · {stats.completed_runs} tamamlanan run
          </h2>
          <PerformancePanel
            stats={stats}
            catalog={kpiCatalog}
            selected={suite?.kpis ?? kpiCatalog.defaults}
            onSave={saveKpis}
          />
        </>
      )}

      {/* Runs */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
        Runs
      </h2>
      {runs.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">
          No runs yet. Hit Run to start one.
        </p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {runs.map((run, i) => (
            <Link
              key={run.id}
              href={`/test-runs/${run.id}`}
              className={
                "flex items-center gap-4 px-4 py-3 transition-colors hover:bg-zinc-900/60 " +
                (i > 0 ? "border-t border-zinc-800/60" : "")
              }
            >
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
              <span className="flex-1 text-xs text-zinc-500">
                {run.summary
                  ? `${run.summary.passed}/${run.summary.total} passed`
                  : run.parallel
                    ? "parallel"
                    : "sequential"}
              </span>
              <span className="text-[11px] text-zinc-600">
                {new Date(run.created_at).toLocaleString()}
              </span>
              <ChevronRight size={14} className="text-zinc-700" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Performans paneli (kalıcı: tamamlanmış run özetlerinden) ──

function fmtPct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function fmtUsd(v: number | null): string {
  if (v == null) return "—";
  return `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`;
}

function kpiValue(stats: SuiteStats, item: KpiCatalogItem): string {
  const raw = (stats as unknown as Record<string, number | null>)[item.key];
  if (raw == null) return "—";
  switch (item.unit) {
    case "percent":
      return fmtPct(raw);
    case "ms":
      return `${(raw / 1000).toFixed(2)}s`;
    case "usd":
      return fmtUsd(raw);
    case "score":
      return raw.toFixed(2);
    case "count":
      return String(raw);
    default:
      return String(raw);
  }
}

function PerformancePanel({
  stats,
  catalog,
  selected,
  onSave,
}: {
  stats: SuiteStats;
  catalog: KpiCatalog;
  selected: string[];
  onSave: (keys: string[]) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>(selected);
  const [saving, setSaving] = useState(false);

  // Katalog sırasını koruyarak seçili KPI'ları çöz (bilinmeyen anahtarları at)
  const shown = catalog.catalog.filter((c) => selected.includes(c.key));

  function toggle(key: string) {
    setDraft((d) => (d.includes(key) ? d.filter((k) => k !== key) : [...d, key]));
  }

  async function save() {
    setSaving(true);
    try {
      // Katalog sırasına göre normalize et
      const ordered = catalog.catalog.filter((c) => draft.includes(c.key)).map((c) => c.key);
      await onSave(ordered);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mb-8 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[11px] text-zinc-600">İzlenen KPI&apos;lar</span>
        <button
          onClick={() => {
            setDraft(selected);
            setEditing((e) => !e);
          }}
          className="flex items-center gap-1 text-[11px] text-zinc-500 transition-colors hover:text-zinc-300"
        >
          <SlidersHorizontal size={12} />
          {editing ? "Kapat" : "KPI düzenle"}
        </button>
      </div>

      {editing ? (
        <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {catalog.catalog.map((c) => (
              <label
                key={c.key}
                className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-zinc-900"
                title={c.description}
              >
                <input
                  type="checkbox"
                  checked={draft.includes(c.key)}
                  onChange={() => toggle(c.key)}
                  className="mt-0.5 accent-indigo-500"
                />
                <span>
                  <span className="text-zinc-200">{c.label}</span>
                  <span className="block text-[10px] text-zinc-600">{c.description}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <Button size="sm" onClick={save} loading={saving}>
              Kaydet
            </Button>
            <span className="text-[10px] text-zinc-600">
              Seçim suite&apos;e kaydedilir; çıkış yapsan da kalır. Boş bırakırsan varsayılana döner.
            </span>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {shown.length === 0 ? (
            <p className="col-span-full text-xs text-zinc-600">Hiç KPI seçili değil.</p>
          ) : (
            shown.map((c) => (
              <Kpi
                key={c.key}
                label={c.label}
                value={kpiValue(stats, c)}
                hint={c.description}
                accent={c.key === "success_run_rate"}
              />
            ))
          )}
        </div>
      )}

      {stats.trend.length > 1 && (
        <div className="mt-4">
          <p className="mb-1.5 text-[11px] text-zinc-600">Geçme oranı trendi (eski → yeni)</p>
          <PassRateTrend trend={stats.trend} />
        </div>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
      <p className="text-[10px] uppercase tracking-wide text-zinc-600">{label}</p>
      <p className={cn("mt-0.5 text-lg font-semibold", accent ? "text-green-400" : "text-zinc-100")}>
        {value}
      </p>
      {hint && <p className="text-[10px] text-zinc-700">{hint}</p>}
    </div>
  );
}

function PassRateTrend({ trend }: { trend: SuiteTrendPoint[] }) {
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
            title={`${new Date(p.created_at).toLocaleString()} · ${Math.round(r * 100)}%${lat}`}
            className={cn("min-w-[6px] flex-1 rounded-sm", color)}
            style={{ height: `${Math.max(6, r * 100)}%` }}
          />
        );
      })}
    </div>
  );
}
