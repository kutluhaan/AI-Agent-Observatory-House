"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Activity, CheckCircle2, XCircle } from "lucide-react";
import {
  api,
  type TestRunDetail,
  type TestCaseResult,
} from "@/lib/api";
import { subscribeTestRuns } from "@/lib/ws";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";

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

      {s && (s.avg_latency_ms != null || s.total_tokens != null) && (
        <div className="mb-8 flex gap-4 text-xs text-zinc-500">
          {s.avg_latency_ms != null && (
            <span>Avg latency: {(s.avg_latency_ms / 1000).toFixed(2)}s</span>
          )}
          {s.total_tokens != null && <span>Total tokens: {s.total_tokens}</span>}
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
        {cr.latency_ms != null && (
          <span className="text-[11px] text-zinc-600">
            {(cr.latency_ms / 1000).toFixed(2)}s
          </span>
        )}
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
