"use client";

import React, { useEffect, useState } from "react";
import { Zap, Users, Link2, Shapes, Play, GitBranch, RefreshCw, FileText, Square, Mail, Calendar, FolderOpen, Github, Database, Server, Globe } from "lucide-react";
import { api, type Agent, type Team } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";

const TABS = [
  { id: "agents", label: "Agents", icon: Zap },
  { id: "teams", label: "Teams", icon: Users },
  { id: "integrations", label: "Entegrasyon", icon: Link2 },
  { id: "elements", label: "Elementler", icon: Shapes },
] as const;

type TabId = typeof TABS[number]["id"];

const INTEGRATIONS = [
  { service: "gmail", label: "Gmail", icon: Mail },
  { service: "gcalendar", label: "Google Calendar", icon: Calendar },
  { service: "gdrive", label: "Google Drive", icon: FolderOpen },
  { service: "github", label: "GitHub", icon: Github },
  { service: "db", label: "Veritabanı", icon: Database },
  { service: "mcp", label: "MCP Server", icon: Server },
  { service: "http", label: "HTTP", icon: Globe },
];

const ELEMENTS = [
  { type: "start", label: "Başlangıç", icon: Play, color: "text-emerald-400", data: { label: "Başlangıç", trigger_kind: "manual" } },
  { type: "decision", label: "Karar", icon: GitBranch, color: "text-yellow-400", data: { label: "Karar", conditions: [{ handle: "evet", label: "Evet" }, { handle: "hayir", label: "Hayır" }] } },
  { type: "loop", label: "Döngü", icon: RefreshCw, color: "text-cyan-400", data: { label: "Döngü", max_iterations: "5" } },
  { type: "note", label: "Not", icon: FileText, color: "text-zinc-400", data: { note: "" } },
  { type: "end", label: "Bitiş", icon: Square, color: "text-red-400", data: { label: "Bitiş" } },
];

function DraggableItem({
  nodeType,
  nodeData,
  icon: Icon,
  label,
  color,
}: {
  nodeType: string;
  nodeData: Record<string, unknown>;
  icon: React.ElementType;
  label: string;
  color?: string;
}) {
  const onDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData(
      "application/reactflow",
      JSON.stringify({ type: nodeType, data: nodeData })
    );
    e.dataTransfer.effectAllowed = "move";
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="flex cursor-grab items-center gap-2.5 rounded-lg border border-zinc-800/60 bg-zinc-900/40 px-3 py-2.5 text-xs text-zinc-300 transition-colors hover:border-zinc-700 hover:bg-zinc-800/60 active:cursor-grabbing"
    >
      <Icon size={13} className={color ?? "text-zinc-400"} />
      <span className="font-medium">{label}</span>
    </div>
  );
}

export function LeftPanel() {
  const [tab, setTab] = useState<TabId>("agents");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tab !== "agents" && tab !== "teams") return;
    setLoading(true);
    Promise.all([
      api.get<Agent[]>("/agents").catch(() => [] as Agent[]),
      api.get<Team[]>("/teams").catch(() => [] as Team[]),
    ]).then(([a, t]) => {
      setAgents(a);
      setTeams(t);
    }).finally(() => setLoading(false));
  // ponytail: only refetch when switching to these tabs
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab === "agents" || tab === "teams" ? tab : null]);

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-800/80 bg-zinc-950">
      {/* Tab bar */}
      <div className="grid grid-cols-4 border-b border-zinc-800/80">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            title={label}
            className={cn(
              "flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors",
              tab === id ? "text-indigo-300 border-b-2 border-indigo-500" : "text-zinc-600 hover:text-zinc-400",
            )}
          >
            <Icon size={14} />
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="flex justify-center py-8"><Spinner className="h-4 w-4" /></div>
        ) : tab === "agents" ? (
          <div className="flex flex-col gap-1.5">
            {agents.length === 0 ? (
              <p className="py-6 text-center text-[11px] text-zinc-600">Agent bulunamadı</p>
            ) : agents.map((a) => (
              <DraggableItem
                key={a.id}
                nodeType="agent"
                nodeData={{ agent_id: a.id, label: a.name, note: "" }}
                icon={Zap}
                label={a.name}
                color="text-indigo-400"
              />
            ))}
          </div>
        ) : tab === "teams" ? (
          <div className="flex flex-col gap-1.5">
            {teams.length === 0 ? (
              <p className="py-6 text-center text-[11px] text-zinc-600">Ekip bulunamadı</p>
            ) : teams.map((t) => (
              <DraggableItem
                key={t.id}
                nodeType="team"
                nodeData={{ team_id: t.id, label: t.name, note: "" }}
                icon={Users}
                label={t.name}
                color="text-violet-400"
              />
            ))}
          </div>
        ) : tab === "integrations" ? (
          <div className="flex flex-col gap-1.5">
            {INTEGRATIONS.map((it) => (
              <DraggableItem
                key={it.service}
                nodeType="integration"
                nodeData={{ service: it.service, label: it.label, note: "" }}
                icon={it.icon}
                label={it.label}
                color="text-amber-400"
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {ELEMENTS.map((el) => (
              <DraggableItem
                key={el.type}
                nodeType={el.type}
                nodeData={el.data}
                icon={el.icon}
                label={el.label}
                color={el.color}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
