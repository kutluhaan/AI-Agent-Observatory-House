"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Square } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface NodeResult {
  id: string;
  node_id: string;
  status: string;
  input: string | null;
  output: string | null;
  error: string | null;
  started_at: string | null;
  ended_at: string | null;
}

interface RunDetail {
  id: string;
  workflow_id: string;
  status: string;
  trigger_kind: string;
  error: string | null;
  started_at: string;
  ended_at: string | null;
  node_results: NodeResult[];
}

const STATUS_CLS: Record<string, string> = {
  running: "border-yellow-500/40 bg-yellow-500/5 text-yellow-300",
  completed: "border-emerald-500/40 bg-emerald-500/5 text-emerald-300",
  failed: "border-red-500/40 bg-red-500/5 text-red-300",
  cancelled: "border-zinc-700 bg-zinc-900/40 text-zinc-500",
  pending: "border-zinc-800 bg-zinc-900/20 text-zinc-500",
};

const DOT_CLS: Record<string, string> = {
  running: "bg-yellow-400 animate-pulse",
  completed: "bg-emerald-400",
  failed: "bg-red-400",
  cancelled: "bg-zinc-600",
  pending: "bg-zinc-700",
};

export default function WorkflowRunPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchRun() {
    try {
      const data = await api.get<RunDetail>(`/workflow-runs/${id}`);
      setRun(data);
      // Stop polling when done
      if (data.status !== "running" && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch (err) {
      console.error(err instanceof ApiError ? err.message : err);
    }
  }

  useEffect(() => {
    fetchRun().finally(() => setLoading(false));
    intervalRef.current = setInterval(fetchRun, 2000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleCancel() {
    setCancelling(true);
    try {
      await api.patch(`/workflow-runs/${id}/cancel`);
      fetchRun();
    } catch (err) {
      console.error(err instanceof ApiError ? err.message : err);
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return <div className="flex h-64 items-center justify-center"><Spinner className="h-5 w-5" /></div>;
  }

  if (!run) {
    return <div className="p-10 text-sm text-zinc-500">Run bulunamadı.</div>;
  }

  const elapsed = run.ended_at
    ? ((new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1) + "s"
    : null;

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link
        href={`/workflows/${run.workflow_id}`}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        Workflow'a dön
      </Link>

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border", STATUS_CLS[run.status] ?? STATUS_CLS.pending)}>
              <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLS[run.status] ?? DOT_CLS.pending)} />
              {run.status}
            </span>
            {elapsed && <span className="text-xs text-zinc-600">{elapsed}</span>}
          </div>
          <p className="mt-2 font-mono text-xs text-zinc-600">{run.id}</p>
          <p className="mt-1 text-xs text-zinc-500">
            {new Date(run.started_at).toLocaleString("tr-TR")}
          </p>
        </div>
        {run.status === "running" && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="flex items-center gap-1.5 rounded-lg border border-red-800/50 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 disabled:opacity-50"
          >
            {cancelling ? <Spinner className="h-3 w-3" /> : <Square size={12} />}
            Durdur
          </button>
        )}
      </div>

      {run.error && (
        <div className="mb-4 rounded-xl border border-red-800/40 bg-red-500/5 px-4 py-3 text-xs text-red-400">
          {run.error}
        </div>
      )}

      {/* Node results */}
      <div className="flex flex-col gap-2">
        {run.node_results.length === 0 ? (
          <p className="text-sm text-zinc-600">Henüz node çalışmadı.</p>
        ) : run.node_results.map((nr) => (
          <div
            key={nr.id}
            className={cn("rounded-xl border transition-colors", STATUS_CLS[nr.status] ?? STATUS_CLS.pending)}
          >
            <button
              className="flex w-full items-center gap-3 px-4 py-3 text-left"
              onClick={() => setExpanded(expanded === nr.id ? null : nr.id)}
            >
              <span className={cn("h-2 w-2 shrink-0 rounded-full", DOT_CLS[nr.status] ?? DOT_CLS.pending)} />
              <span className="flex-1 font-mono text-xs font-medium">{nr.node_id}</span>
              <span className="text-[11px] opacity-60">{nr.status}</span>
              {nr.started_at && nr.ended_at && (
                <span className="text-[11px] opacity-50">
                  {((new Date(nr.ended_at).getTime() - new Date(nr.started_at).getTime()) / 1000).toFixed(1)}s
                </span>
              )}
            </button>
            {expanded === nr.id && (
              <div className="border-t border-current/10 px-4 pb-3">
                {nr.output && (
                  <div className="mt-2">
                    <p className="mb-1 text-[10px] uppercase opacity-50">Çıktı</p>
                    <pre className="whitespace-pre-wrap text-[11px] opacity-80">{nr.output}</pre>
                  </div>
                )}
                {nr.error && (
                  <div className="mt-2">
                    <p className="mb-1 text-[10px] uppercase opacity-50">Hata</p>
                    <pre className="whitespace-pre-wrap text-[11px] text-red-400">{nr.error}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
