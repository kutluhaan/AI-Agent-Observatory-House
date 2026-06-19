"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, RefreshCw, ChevronRight } from "lucide-react";
import { api, type TraceSummary } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<TraceSummary[]>("/traces?limit=100")
      .then(setTraces)
      .catch(() => setError("Failed to load traces."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Traces</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Every agent run, step by step.
          </p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : traces.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <Activity size={28} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">No traces yet.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Run an agent to produce a trace.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {traces.map((t, i) => (
            <Link
              key={t.trace_id}
              href={`/traces/${t.trace_id}`}
              className={cn_row(i)}
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <Badge variant={statusVariant(t.status)}>{t.status}</Badge>
                <span className="truncate text-sm text-zinc-200">{t.name}</span>
              </div>
              <span className="shrink-0 text-[11px] text-zinc-600">
                {relativeTime(t.started_at)}
              </span>
              <ChevronRight size={14} className="shrink-0 text-zinc-700" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function cn_row(i: number): string {
  return [
    "flex items-center gap-4 px-4 py-3 transition-colors hover:bg-zinc-900/60",
    i > 0 ? "border-t border-zinc-800/60" : "",
  ].join(" ");
}
