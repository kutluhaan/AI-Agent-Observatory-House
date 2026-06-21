"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Activity, CheckCircle2, XCircle, Wrench, AlertTriangle, Gavel, Download } from "lucide-react";
import {
  api,
  type TestRunDetail,
  type TestCaseResult,
  type TrajectoryStep,
  type JudgeResult,
  type ConsistencyInfo,
} from "@/lib/api";
import { subscribeTestRuns } from "@/lib/ws";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";
import { toolLabel, formatArgs } from "@/lib/tools";
import { cn } from "@/lib/utils";

function fmtCost(c: number | null | undefined): string | null {
  if (c == null) return null;
  if (c === 0) return "$0";
  if (c < 0.01) return `$${c.toFixed(5)}`;
  return `$${c.toFixed(4)}`;
}

async function downloadXlsx(runId: string) {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/test-runs/${runId}/export.xlsx`, {
    credentials: "include",
  });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `test-run-${runId.slice(0, 8)}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

const JUDGE_LABELS: Record<string, string> = {
  task_completion: "Görev tamamlama",
  answer_correctness: "Cevap doğruluğu",
  rubric: "Rubrik",
  step_efficiency: "Adım verimliliği",
  argument_correctness: "Argüman doğruluğu",
  reasoning_quality: "Akıl yürütme",
  safety: "Güvenlik",
};

function isLive(status: string | undefined): boolean {
  return status === "pending" || status === "running";
}

export default function TestRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<TestRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const liveRef = useRef(false);

  const fetchDetail = useCallback(async () => {
    try {
      const d = await api.get<TestRunDetail>(`/test-runs/${id}`);
      setDetail(d);
      liveRef.current = isLive(d.run.status);
      return d.run.status;
    } catch {
      setError("Test run not found.");
      return "error";
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // Canlı ilerleme: WS event'i + güvenlik amaçlı poll (run bitene kadar)
  const live = isLive(detail?.run.status);
  useEffect(() => {
    if (!live) return;

    const unsubscribe = subscribeTestRuns((ev) => {
      if (ev.run_id === id) fetchDetail();
    });
    const poll = setInterval(() => {
      if (liveRef.current) fetchDetail();
      else clearInterval(poll);
    }, 2000);

    return () => {
      unsubscribe();
      clearInterval(poll);
    };
  }, [live, id, fetchDetail]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Alert variant="error">{error || "Test run not found."}</Alert>
      </div>
    );
  }

  const { run, case_results } = detail;
  const s = run.summary;

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link
        href={`/test-suites/${run.suite_id}`}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Suite
      </Link>

      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-xl font-semibold text-zinc-100">Test run</h1>
        <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        {live && (
          <span className="flex items-center gap-1.5 text-xs text-indigo-400">
            <Spinner className="h-3 w-3" />
            running…
          </span>
        )}
        {!live && case_results.length > 0 && (
          <button
            onClick={() => void downloadXlsx(id)}
            className="ml-auto flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
          >
            <Download size={13} />
            Excel&apos;e aktar
          </button>
        )}
      </div>

      {/* Summary */}
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Total" value={s ? String(s.total) : String(case_results.length)} />
        <Metric label="Passed" value={s ? String(s.passed) : "—"} accent="green" />
        <Metric
          label="Failed"
          value={s ? String(s.failed + s.error) : "—"}
          accent={s && s.failed + s.error > 0 ? "red" : undefined}
        />
        <Metric
          label="Pass rate"
          value={s ? `${Math.round(s.pass_rate * 100)}%` : "—"}
        />
      </div>

      {s && (s.avg_latency_ms != null || s.total_tokens != null || s.total_cost_usd != null) && (
        <div className="mb-8 flex flex-wrap gap-4 text-xs text-zinc-500">
          {s.avg_latency_ms != null && (
            <span>Avg latency: {(s.avg_latency_ms / 1000).toFixed(2)}s</span>
          )}
          {s.total_tokens != null && <span>Total tokens: {s.total_tokens.toLocaleString()}</span>}
          {s.total_cost_usd != null && (
            <span>
              Est. cost: <span className="text-zinc-300">{fmtCost(s.total_cost_usd)}</span>
            </span>
          )}
          {s.avg_judge_score != null && (
            <span>
              Avg judge: <span className="text-zinc-300">{Math.round(s.avg_judge_score * 100)}%</span>
            </span>
          )}
        </div>
      )}

      {/* Case results */}
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
        Cases ({case_results.length})
      </h2>
      {case_results.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">
          {live ? "Waiting for results…" : "No case results."}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {case_results.map((cr) => (
            <CaseRow key={cr.id} cr={cr} />
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "green" | "red";
}) {
  const valueColor =
    accent === "green"
      ? "text-green-400"
      : accent === "red"
        ? "text-red-400"
        : "text-zinc-100";
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3.5">
      <p className="text-[11px] uppercase tracking-wide text-zinc-600">{label}</p>
      <p className={"mt-1 text-lg font-semibold " + valueColor}>{value}</p>
    </div>
  );
}

function CaseRow({ cr }: { cr: TestCaseResult }) {
  const [open, setOpen] = useState(false);
  const passedCount = cr.assertions_results.filter((a) => a.passed).length;
  const totalCount = cr.assertions_results.length;

  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <Badge variant={statusVariant(cr.status)}>{cr.status}</Badge>
        <span className="flex-1 truncate text-sm text-zinc-200">
          {totalCount > 0 ? `${passedCount}/${totalCount} assertions` : cr.status}
        </span>
        <span className="flex shrink-0 items-center gap-2.5 text-[11px] text-zinc-600">
          {cr.consistency && (
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 tabular-nums",
                cr.consistency.passed_runs === cr.consistency.runs
                  ? "bg-green-500/10 text-green-400"
                  : "bg-amber-500/10 text-amber-400",
              )}
              title="Tutarlılık: geçen / toplam tekrar"
            >
              {cr.consistency.passed_runs}/{cr.consistency.runs}×
            </span>
          )}
          {cr.steps_taken != null && <span>{cr.steps_taken} adım</span>}
          {cr.total_tokens != null && <span>{cr.total_tokens.toLocaleString()} tok</span>}
          {fmtCost(cr.cost_usd) && <span>{fmtCost(cr.cost_usd)}</span>}
          {cr.latency_ms != null && <span>{(cr.latency_ms / 1000).toFixed(2)}s</span>}
        </span>
      </button>

      {open && (
        <div className="border-t border-zinc-800/60 px-4 py-3 text-xs">
          {cr.error_message && (
            <Alert variant="error" className="mb-3">{cr.error_message}</Alert>
          )}

          {cr.assertions_results.length > 0 && (
            <div className="mb-3 flex flex-col gap-1">
              {cr.assertions_results.map((a, i) => (
                <div key={i} className="flex items-center gap-2 text-zinc-400">
                  {a.passed ? (
                    <CheckCircle2 size={13} className="shrink-0 text-green-400" />
                  ) : (
                    <XCircle size={13} className="shrink-0 text-red-400" />
                  )}
                  <span className="font-mono">{a.type ?? "assertion"}</span>
                  {a.detail && <span className="text-zinc-600">— {a.detail}</span>}
                </div>
              ))}
            </div>
          )}

          {cr.consistency && (
            <div className="mb-3">
              <p className="mb-1.5 text-[11px] uppercase tracking-wide text-zinc-600">
                Tutarlılık — {cr.consistency.runs}× çalıştırıldı
              </p>
              <ConsistencyView c={cr.consistency} />
            </div>
          )}

          {cr.judge_results && cr.judge_results.length > 0 && (
            <div className="mb-3">
              <p className="mb-1.5 text-[11px] uppercase tracking-wide text-zinc-600">
                LLM-as-judge metrikleri
              </p>
              <div className="flex flex-col gap-1.5">
                {cr.judge_results.map((j, i) => (
                  <JudgeView key={i} judge={j} />
                ))}
              </div>
            </div>
          )}

          {cr.trajectory && cr.trajectory.length > 0 && (
            <div className="mb-3">
              <p className="mb-1.5 text-[11px] uppercase tracking-wide text-zinc-600">
                Trajectory — agent ne yaptı ({cr.trajectory.length} adım)
              </p>
              <TrajectoryView steps={cr.trajectory} />
            </div>
          )}

          {cr.rag_metrics && Object.keys(cr.rag_metrics).length > 0 && (
            <div className="mb-3">
              <p className="mb-1 text-[11px] uppercase tracking-wide text-zinc-600">
                RAG metrics
              </p>
              <pre className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950/60 p-2 text-[11px] text-zinc-400">
                {JSON.stringify(cr.rag_metrics, null, 2)}
              </pre>
            </div>
          )}

          {cr.output && (
            <div className="mb-3">
              <p className="mb-1 text-[11px] uppercase tracking-wide text-zinc-600">
                Output
              </p>
              <p className="whitespace-pre-wrap text-zinc-400">{cr.output}</p>
            </div>
          )}

          {cr.trace_id && (
            <Link
              href={`/traces/${cr.trace_id}`}
              className="flex items-center gap-1 text-[11px] text-zinc-600 transition-colors hover:text-indigo-400"
            >
              <Activity size={11} />
              View trace
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

// ── Trajectory: agent'ın test sırasında attığı adımlar ──────

function TrajectoryView({ steps }: { steps: TrajectoryStep[] }) {
  return (
    <ol className="flex flex-col gap-1.5">
      {steps.map((step, i) => (
        <TrajectoryRow key={i} index={i} step={step} />
      ))}
    </ol>
  );
}

function TrajectoryRow({ index, step }: { index: number; step: TrajectoryStep }) {
  const [open, setOpen] = useState(false);
  const args = formatArgs(step.arguments)
    .map((r) => `${r.label}: ${r.value}`)
    .join("  ·  ");
  return (
    <li
      className={cn(
        "rounded-lg border px-2.5 py-2",
        step.ok ? "border-zinc-800 bg-zinc-950/40" : "border-red-500/25 bg-red-500/5",
      )}
    >
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 text-left">
        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-zinc-800 text-[9px] text-zinc-400">
          {index + 1}
        </span>
        {step.ok ? (
          <Wrench size={11} className="shrink-0 text-amber-400" />
        ) : (
          <AlertTriangle size={11} className="shrink-0 text-red-400" />
        )}
        <span className="shrink-0 font-medium text-zinc-300">{toolLabel(step.name)}</span>
        {args && <span className="truncate text-zinc-600">{args}</span>}
      </button>
      {open && (
        <pre className="mt-1.5 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-zinc-950/60 p-2 text-[11px] text-zinc-400">
          {step.result || "(boş sonuç)"}
        </pre>
      )}
    </li>
  );
}

// ── LLM-as-judge metrik kartı ───────────────────────────────

function JudgeView({ judge }: { judge: JudgeResult }) {
  const label = JUDGE_LABELS[judge.type] ?? judge.type;
  const isError = judge.score == null;
  const pct = judge.score != null ? Math.round(judge.score * 100) : 0;
  const passed = judge.passed === true;
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2 text-zinc-300">
      <div className="flex items-center gap-2">
        <Gavel size={11} className="shrink-0 text-indigo-400" />
        <span className="font-medium">{judge.name ?? label}</span>
        {isError ? (
          <span className="ml-auto text-[11px] text-amber-400">judge hatası</span>
        ) : (
          <span className="ml-auto flex items-center gap-1.5">
            <span className={cn("tabular-nums", passed ? "text-green-400" : "text-red-400")}>{pct}%</span>
            {passed ? (
              <CheckCircle2 size={12} className="text-green-400" />
            ) : (
              <XCircle size={12} className="text-red-400" />
            )}
          </span>
        )}
      </div>
      {!isError && (
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-zinc-800">
          <div
            className={cn("h-full rounded-full", passed ? "bg-green-500/70" : "bg-red-500/70")}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      {(judge.rationale || judge.error) && (
        <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-500">
          {judge.rationale || judge.error}
          {!isError && (
            <span className="text-zinc-700"> · eşik {Math.round(judge.threshold * 100)}%</span>
          )}
        </p>
      )}
    </div>
  );
}

// ── Tutarlılık: N tekrarın geçme oranı + tekrar tekrar nokta görünümü ──

function ConsistencyView({ c }: { c: ConsistencyInfo }) {
  const rate = Math.round(c.pass_rate * 100);
  const ok = c.pass_rate >= c.min_pass_rate;
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-2.5 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("font-medium tabular-nums", ok ? "text-green-400" : "text-red-400")}>
          {c.passed_runs}/{c.runs} geçti · %{rate}
        </span>
        <span className="text-zinc-700">eşik %{Math.round(c.min_pass_rate * 100)}</span>
        {c.errored_runs ? <span className="text-amber-400">{c.errored_runs} hata</span> : null}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {c.runs_detail.map((r, i) => (
          <span
            key={i}
            title={r.errored ? "hata" : r.passed ? "geçti" : "kaldı"}
            className={cn(
              "h-4 w-4 rounded-sm",
              r.errored ? "bg-amber-500/40" : r.passed ? "bg-green-500/60" : "bg-red-500/60",
            )}
          />
        ))}
      </div>
    </div>
  );
}
