"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, RefreshCw, ChevronRight, Search, Users, Zap } from "lucide-react";
import { api, type TraceSummary } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

type SourceFilter = "all" | "agent" | "team";

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<SourceFilter>("all");

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<TraceSummary[]>("/traces?limit=200")
      .then(setTraces)
      .catch(() => setError("Failed to load traces."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let list = traces;
    if (source === "agent") list = list.filter((t) => !t.name.toLowerCase().startsWith("team"));
    if (source === "team") list = list.filter((t) => t.name.toLowerCase().startsWith("team"));
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((t) => t.name.toLowerCase().includes(q));
    }
    return list;
  }, [traces, source, search]);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Traces</h1>
          <p className="mt-1 text-sm text-zinc-500">Her agent çalışması, adım adım.</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
        >
          <RefreshCw size={12} />
          Yenile
        </button>
      </div>

      {/* Filtre bar */}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Trace ara…"
            className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 py-1.5 pl-8 pr-3 text-xs text-zinc-200 placeholder-zinc-600 focus:border-indigo-500 focus:outline-none"
          />
        </div>
        <div className="inline-flex rounded-lg border border-zinc-800 bg-zinc-950/50 p-0.5 text-xs">
          {(["all", "agent", "team"] as SourceFilter[]).map((v) => {
            const Icon = v === "agent" ? Zap : v === "team" ? Users : Activity;
            const labels = { all: "Tümü", agent: "Agent", team: "Ekip" };
            return (
              <button
                key={v}
                onClick={() => setSource(v)}
                className={cn(
                  "flex items-center gap-1 rounded-md px-2.5 py-1 font-medium transition-colors",
                  source === v ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300",
                )}
              >
                <Icon size={11} />
                {labels[v]}
              </button>
            );
          })}
        </div>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <Activity size={28} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">{traces.length === 0 ? "Henüz trace yok." : "Filtre eşleşmedi."}</p>
          {traces.length === 0 && (
            <p className="mt-1 text-xs text-zinc-600">Bir agent çalıştırarak trace oluştur.</p>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {filtered.map((t, i) => (
            <Link
              key={t.trace_id}
              href={`/traces/${t.trace_id}`}
              className={cn(
                "flex items-center gap-4 px-4 py-3 transition-colors hover:bg-zinc-900/60",
                i > 0 && "border-t border-zinc-800/60",
              )}
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
