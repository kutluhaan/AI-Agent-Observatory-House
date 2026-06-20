"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Play,
  Square,
  Wrench,
  Brain,
  ShieldCheck,
  AlertTriangle,
  Cpu,
} from "lucide-react";
import { api, type TraceDetail, type TraceEvent } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge, statusVariant } from "@/components/ui/badge";

// ── Event görsel eşlemesi ───────────────────────────────────

function eventIcon(type: string) {
  if (type === "agent_start") return Play;
  if (type === "agent_end") return Square;
  if (type.startsWith("tool_call")) return Wrench;
  if (type.startsWith("llm_call")) return Cpu;
  if (type === "reasoning") return Brain;
  if (type.startsWith("hitl")) return ShieldCheck;
  if (type === "error") return AlertTriangle;
  return Cpu;
}

function eventColor(type: string): string {
  if (type === "error") return "text-red-400";
  if (type.startsWith("hitl")) return "text-amber-400";
  if (type.startsWith("tool_call")) return "text-amber-300";
  if (type === "agent_start" || type === "agent_end") return "text-indigo-400";
  return "text-zinc-500";
}

function timeOf(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ── Metrik türetme ──────────────────────────────────────────

function deriveMetrics(trace: TraceDetail) {
  const events = trace.events;
  const toolCalls = events.filter((e) => e.type === "tool_call_start").length;
  const steps = events.filter((e) => e.type === "llm_call_start").length;

  let tokens = 0;
  const end = events.find((e) => e.type === "agent_end");
  const usage = (end?.payload?.usage ?? {}) as Record<string, number>;
  tokens = (usage.prompt_tokens ?? 0) + (usage.completion_tokens ?? 0);

  let durationMs: number | null = null;
  if (trace.started_at && trace.ended_at) {
    durationMs = new Date(trace.ended_at).getTime() - new Date(trace.started_at).getTime();
  }

  return { toolCalls, steps, tokens, durationMs };
}

export default function TraceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [backToChat, setBackToChat] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TraceDetail>(`/traces/${id}`)
      .then(setTrace)
      .catch(() => setError("Trace not found."))
      .finally(() => setLoading(false));
  }, [id]);

  // Chat'ten gelindiyse (?agent=&c=) sohbete geri dönüş linki kur
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const agent = p.get("agent");
    const c = p.get("c");
    if (agent) setBackToChat(`/agents/${agent}/chat${c ? `?c=${c}` : ""}`);
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Alert variant="error">{error || "Trace not found."}</Alert>
      </div>
    );
  }

  const m = deriveMetrics(trace);

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link
        href={backToChat ?? "/traces"}
        className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-300"
      >
        <ArrowLeft size={13} />
        {backToChat ? "Sohbete dön" : "Traces"}
      </Link>

      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-xl font-semibold text-zinc-100">{trace.name}</h1>
        <Badge variant={statusVariant(trace.status)}>{trace.status}</Badge>
      </div>

      {/* Metric cards */}
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Steps" value={String(m.steps)} />
        <Metric label="Tool calls" value={String(m.toolCalls)} />
        <Metric label="Tokens" value={m.tokens ? String(m.tokens) : "—"} />
        <Metric
          label="Duration"
          value={m.durationMs != null ? `${(m.durationMs / 1000).toFixed(2)}s` : "—"}
        />
      </div>

      {/* Timeline */}
      <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
        Timeline
      </h2>
      <div className="flex flex-col">
        {trace.events.map((ev, i) => (
          <TimelineRow key={i} ev={ev} last={i === trace.events.length - 1} />
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3.5">
      <p className="text-[11px] uppercase tracking-wide text-zinc-600">{label}</p>
      <p className="mt-1 text-lg font-semibold text-zinc-100">{value}</p>
    </div>
  );
}

function TimelineRow({ ev, last }: { ev: TraceEvent; last: boolean }) {
  const [open, setOpen] = useState(false);
  const Icon = eventIcon(ev.type);
  const hasPayload = ev.payload && Object.keys(ev.payload).length > 0;

  return (
    <div className="flex gap-3">
      {/* Rail */}
      <div className="flex flex-col items-center">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900">
          <Icon size={13} className={eventColor(ev.type)} />
        </div>
        {!last && <div className="w-px flex-1 bg-zinc-800/70" />}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <button
          onClick={() => hasPayload && setOpen((o) => !o)}
          className="flex w-full items-center gap-2 text-left"
          disabled={!hasPayload}
        >
          <span className="font-mono text-sm text-zinc-300">{ev.type}</span>
          <span className="text-[11px] text-zinc-600">{timeOf(ev.timestamp)}</span>
        </button>
        {open && hasPayload && (
          <pre className="mt-1.5 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950/60 p-2.5 text-[11px] text-zinc-400">
            {JSON.stringify(ev.payload, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
