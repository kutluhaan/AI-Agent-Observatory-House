"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Workflow, Plus, ChevronRight, Clock, CalendarClock } from "lucide-react";
import { api, type WorkflowData } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<WorkflowData["status"], string> = {
  active: "bg-emerald-500/10 text-emerald-400",
  unavailable: "bg-zinc-500/10 text-zinc-500",
  completed: "bg-indigo-500/10 text-indigo-400",
};

const STATUS_LABEL: Record<WorkflowData["status"], string> = {
  active: "Aktif",
  unavailable: "Devre dışı",
  completed: "Tamamlandı",
};

const RUN_DOT: Record<string, string> = {
  running: "bg-yellow-400 animate-pulse",
  completed: "bg-emerald-400",
  failed: "bg-red-400",
  cancelled: "bg-zinc-600",
};

const RUN_TEXT: Record<string, string> = {
  running: "text-yellow-400",
  completed: "text-emerald-400",
  failed: "text-red-400",
  cancelled: "text-zinc-500",
};

const TRIGGER_ICON: Record<string, React.ElementType> = {
  schedule: CalendarClock,
  manual: Clock,
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "az önce";
  if (m < 60) return `${m}dk önce`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}s önce`;
  return `${Math.floor(h / 24)}g önce`;
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<WorkflowData[]>("/workflows")
      .then(setWorkflows)
      .catch(() => setError("Workflowlar yüklenemedi."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Workflows</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Görsel iş akışları oluştur ve çalıştır.
          </p>
        </div>
        <Link href="/workflows/new">
          <Button size="sm">
            <Plus size={14} />
            Yeni workflow
          </Button>
        </Link>
      </div>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-5 w-5" />
        </div>
      ) : workflows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-800 py-16 text-center">
          <Workflow size={28} className="mx-auto mb-3 text-zinc-700" />
          <p className="text-sm text-zinc-400">Henüz workflow yok.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Sürükle-bırak editörüyle iş akışı oluştur.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-800/80">
          {workflows.map((w, i) => {
            const run = w.last_run;
            const TriggerIcon = run ? (TRIGGER_ICON[run.trigger_kind] ?? Clock) : null;
            return (
              <Link
                key={w.id}
                href={`/workflows/${w.id}`}
                className={cn(
                  "flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-zinc-900/60",
                  i > 0 && "border-t border-zinc-800/60",
                )}
              >
                {/* Icon */}
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10">
                  <Workflow size={15} className="text-indigo-400" />
                </div>

                {/* Name + last run */}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-zinc-200">{w.name}</p>
                  {run ? (
                    <div className="mt-0.5 flex items-center gap-1.5">
                      <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", RUN_DOT[run.status] ?? "bg-zinc-700")} />
                      <span className={cn("text-[11px] font-medium", RUN_TEXT[run.status] ?? "text-zinc-500")}>
                        {run.status}
                      </span>
                      {TriggerIcon && <TriggerIcon size={10} className="text-zinc-600" />}
                      <span className="text-[11px] text-zinc-600">{timeAgo(run.started_at)}</span>
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-600">
                      {new Date(w.updated_at).toLocaleDateString("tr-TR")}
                    </p>
                  )}
                </div>

                {/* Status badge */}
                <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium", STATUS_BADGE[w.status])}>
                  {STATUS_LABEL[w.status]}
                </span>

                <ChevronRight size={14} className="shrink-0 text-zinc-700" />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
