"use client";

import React from "react";
import {
  Handle,
  Position,
  type NodeProps,
} from "@xyflow/react";
import {
  Play, Zap, Users, Link2, GitBranch, RefreshCw, FileText, Square, Plus, X
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Shared wrapper ────────────────────────────────────────────

function NodeShell({
  selected,
  accent,
  icon: Icon,
  title,
  note,
  children,
  runStatus,
}: {
  selected?: boolean;
  accent: string;
  icon: React.ElementType;
  title: string;
  note?: string;
  children?: React.ReactNode;
  runStatus?: string;
}) {
  const borderColor = runStatus === "running"
    ? "border-yellow-500"
    : runStatus === "completed"
    ? "border-emerald-500"
    : runStatus === "failed"
    ? "border-red-500"
    : selected
    ? "border-indigo-500"
    : "border-zinc-800";

  return (
    <div className={cn("min-w-[180px] rounded-xl border bg-zinc-950 shadow-xl", borderColor)}>
      <div className={cn("flex items-center gap-2 rounded-t-xl px-3 py-2", accent)}>
        <Icon size={11} />
        <span className="text-[11px] font-semibold tracking-wide">{title}</span>
        {runStatus && (
          <span className={cn(
            "ml-auto rounded-full px-1.5 py-0.5 text-[9px] font-medium",
            runStatus === "running" ? "bg-yellow-500/20 text-yellow-300"
            : runStatus === "completed" ? "bg-emerald-500/20 text-emerald-300"
            : "bg-red-500/20 text-red-300"
          )}>
            {runStatus}
          </span>
        )}
      </div>
      {children && <div className="px-3 py-2">{children}</div>}
      {note && !children && (
        <p className="px-3 pb-2 text-[11px] text-zinc-500 line-clamp-2">{note}</p>
      )}
      {note && children && (
        <p className="border-t border-zinc-800/60 px-3 py-2 text-[11px] text-zinc-500 line-clamp-2">{note}</p>
      )}
    </div>
  );
}

// ── Node types ────────────────────────────────────────────────

export function StartNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <NodeShell selected={selected} accent="bg-emerald-500/15 text-emerald-300" icon={Play} title="Başlangıç" note={d.note} runStatus={d.run_status}>
        <p className="text-[11px] text-zinc-400">
          {d.trigger_kind === "schedule" ? `⏱ ${d.cron || "cron"}` : d.trigger_kind === "event" ? "📡 Event" : "▶ Manuel"}
        </p>
      </NodeShell>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-2 !border-emerald-500 !bg-zinc-950" />
    </>
  );
}

export function AgentNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-indigo-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-indigo-500/15 text-indigo-300" icon={Zap} title={d.label || "Agent"} note={d.note} runStatus={d.run_status}>
        {d.agent_id && (
          <p className="font-mono text-[10px] text-zinc-600 truncate">{d.agent_id.slice(0, 8)}…</p>
        )}
      </NodeShell>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-2 !border-indigo-500 !bg-zinc-950" />
    </>
  );
}

export function TeamNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-violet-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-violet-500/15 text-violet-300" icon={Users} title={d.label || "Ekip"} note={d.note} runStatus={d.run_status}>
        {d.team_id && (
          <p className="font-mono text-[10px] text-zinc-600 truncate">{d.team_id.slice(0, 8)}…</p>
        )}
      </NodeShell>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-2 !border-violet-500 !bg-zinc-950" />
    </>
  );
}

export function IntegrationNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-amber-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-amber-500/15 text-amber-300" icon={Link2} title={d.label || "Entegrasyon"} note={d.note} runStatus={d.run_status}>
        {d.operation && <p className="text-[11px] text-zinc-400">{d.operation}</p>}
      </NodeShell>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-2 !border-amber-500 !bg-zinc-950" />
    </>
  );
}

export function DecisionNode({ data, selected }: NodeProps) {
  const d = data as { label?: string; note?: string; run_status?: string; conditions?: Array<{ handle: string; label: string }> };
  const conditions = d.conditions ?? [{ handle: "evet", label: "Evet" }, { handle: "hayir", label: "Hayır" }];
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-yellow-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-yellow-500/15 text-yellow-300" icon={GitBranch} title={d.label || "Karar"} note={d.note} runStatus={d.run_status}>
        <div className="flex flex-col gap-1">
          {conditions.map((c) => (
            <div key={c.handle} className="flex items-center justify-between text-[11px]">
              <span className="text-zinc-400">{c.label}</span>
              <span className="rounded-full bg-yellow-500/10 px-1.5 py-0.5 text-[10px] text-yellow-400">{c.handle}</span>
            </div>
          ))}
        </div>
      </NodeShell>
      {conditions.map((c, i) => (
        <Handle
          key={c.handle}
          id={c.handle}
          type="source"
          position={Position.Bottom}
          style={{ left: `${((i + 1) / (conditions.length + 1)) * 100}%` }}
          className="!h-2.5 !w-2.5 !border-2 !border-yellow-500 !bg-zinc-950"
        />
      ))}
    </>
  );
}

export function LoopNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-cyan-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-cyan-500/15 text-cyan-300" icon={RefreshCw} title={d.label || "Döngü"} note={d.note} runStatus={d.run_status}>
        <p className="text-[11px] text-zinc-400">
          {d.max_iterations ? `Max: ${d.max_iterations}` : "Sonsuz"}
        </p>
      </NodeShell>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-2 !border-cyan-500 !bg-zinc-950" />
    </>
  );
}

export function NoteNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-zinc-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-zinc-700/30 text-zinc-400" icon={FileText} title="Not" runStatus={d.run_status}>
        {d.note ? (
          <p className="text-[12px] text-zinc-300 whitespace-pre-wrap">{d.note}</p>
        ) : (
          <p className="text-[11px] text-zinc-600 italic">Not ekle…</p>
        )}
      </NodeShell>
      <Handle type="source" position={Position.Bottom} className="!h-2.5 !w-2.5 !border-2 !border-zinc-500 !bg-zinc-950" />
    </>
  );
}

export function EndNode({ data, selected }: NodeProps) {
  const d = data as Record<string, string>;
  return (
    <>
      <Handle type="target" position={Position.Top} className="!h-2.5 !w-2.5 !border-2 !border-red-500 !bg-zinc-950" />
      <NodeShell selected={selected} accent="bg-red-500/15 text-red-300" icon={Square} title="Bitiş" note={d.note} runStatus={d.run_status} />
    </>
  );
}

// ── nodeTypes — MUST be defined outside component ─────────────

export const nodeTypes = {
  start: StartNode,
  agent: AgentNode,
  team: TeamNode,
  integration: IntegrationNode,
  decision: DecisionNode,
  loop: LoopNode,
  note: NoteNode,
  end: EndNode,
} as const;
