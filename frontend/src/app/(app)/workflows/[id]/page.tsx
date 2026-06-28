"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Play, Clock } from "lucide-react";
import { api, ApiError, type WorkflowData } from "@/lib/api";
import { WorkflowCanvas, type GraphJson } from "@/components/workflow/canvas";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS: WorkflowData["status"][] = ["active", "unavailable", "completed"];
const STATUS_LABEL: Record<WorkflowData["status"], string> = {
  active: "Aktif",
  unavailable: "Devre dışı",
  completed: "Tamamlandı",
};

interface Run {
  id: string;
  status: string;
  trigger_kind: string;
  started_at: string;
  ended_at: string | null;
  error: string | null;
}

const RUN_STATUS_CLS: Record<string, string> = {
  running: "text-yellow-400",
  completed: "text-emerald-400",
  failed: "text-red-400",
  cancelled: "text-zinc-500",
};

export default function WorkflowDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [wf, setWf] = useState<WorkflowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.get<WorkflowData>(`/workflows/${id}`)
      .then((w) => { setWf(w); setName(w.name); })
      .catch(console.error)
      .finally(() => setLoading(false));
    loadRuns();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function loadRuns() {
    api.get<Run[]>(`/workflows/${id}/runs`).then(setRuns).catch(() => {});
  }

  async function handleSave(graph: GraphJson) {
    setSaving(true);
    try {
      const updated = await api.patch<WorkflowData>(`/workflows/${id}`, {
        name: name.trim() || undefined,
        graph_json: graph,
      });
      setWf(updated);
    } catch (err) {
      console.error(err instanceof ApiError ? err.message : err);
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(status: WorkflowData["status"]) {
    const updated = await api.patch<WorkflowData>(`/workflows/${id}`, { status });
    setWf(updated);
  }

  async function handleTestRun() {
    setRunning(true);
    try {
      await api.post(`/workflows/${id}/runs`);
      loadRuns();
    } catch (err) {
      console.error(err instanceof ApiError ? err.message : err);
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return <div className="flex h-64 items-center justify-center"><Spinner className="h-5 w-5" /></div>;
  }

  return (
    <div className="flex h-[calc(100dvh-48px)] flex-col">
      <WorkflowCanvas
        initialGraph={wf?.graph_json as GraphJson | null}
        onSave={handleSave}
        saving={saving}
        topBar={
          <div className="flex items-center gap-3">
            <Link href="/workflows" className="text-zinc-600 hover:text-zinc-300">
              <ArrowLeft size={16} />
            </Link>
            <input
              className="rounded border border-transparent bg-transparent px-1 py-0.5 text-sm font-medium text-zinc-100 focus:border-zinc-700 focus:bg-zinc-900 focus:outline-none"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Workflow adı"
            />
            {wf && (
              <select
                className="rounded border border-zinc-800 bg-zinc-900 px-2 py-0.5 text-xs text-zinc-400 focus:outline-none"
                value={wf.status}
                onChange={(e) => handleStatusChange(e.target.value as WorkflowData["status"])}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                ))}
              </select>
            )}
          </div>
        }
        extraActions={
          <div className="flex items-center gap-2">
            {/* Run history popover */}
            {runs.length > 0 && (
              <div className="relative group">
                <button className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-400 hover:text-zinc-200">
                  <Clock size={12} />
                  {runs.length} run
                </button>
                <div className="absolute right-0 top-8 z-50 hidden group-hover:block w-72 rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
                  <p className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold text-zinc-500 uppercase">Run Geçmişi</p>
                  <div className="max-h-64 overflow-y-auto">
                    {runs.map((r) => (
                      <Link
                        key={r.id}
                        href={`/workflow-runs/${r.id}`}
                        className="flex items-center justify-between px-3 py-2 text-xs hover:bg-zinc-800/60"
                      >
                        <span className={cn("font-medium", RUN_STATUS_CLS[r.status] ?? "text-zinc-400")}>
                          {r.status}
                        </span>
                        <span className="text-zinc-600">
                          {new Date(r.started_at).toLocaleString("tr-TR")}
                        </span>
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={handleTestRun}
              disabled={running}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {running ? <Spinner className="h-3 w-3" /> : <Play size={12} />}
              Test Et
            </button>
          </div>
        }
      />
    </div>
  );
}
