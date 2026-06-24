"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, StickyNote, CheckCircle2, ChevronDown, Wrench, Search, Link2, Circle, CircleDot, ListChecks } from "lucide-react";
import { api, type TeamRunDetail, type TeamRunMessage, type Team, type TodoItem } from "@/lib/api";
import { roleIcon, roleColor } from "@/lib/team-roles";
import { subscribeTeamRuns } from "@/lib/ws";
import { Badge, statusVariant } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";

export default function TeamRunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<TeamRunDetail | null>(null);
  const [team, setTeam] = useState<Team | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get<TeamRunDetail>(`/team-runs/${id}`).then((d) => {
      setData(d);
      if (d.run.team_id) api.get<Team>(`/teams/${d.run.team_id}`).then(setTeam).catch(() => {});
    }).catch(() => setError("Bulunamadı."));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // C2: canlı — WS ping geldiğinde bu run'ı yeniden çek
  useEffect(() => {
    const unsub = subscribeTeamRuns((ev) => {
      if (ev.run_id === id) load();
    });
    return unsub;
  }, [id, load]);

  // WS düşerse yedek: çalışırken yavaş poll
  useEffect(() => {
    if (!data || (data.run.status !== "running" && data.run.status !== "pending")) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [data, load]);

  if (error) return <div className="mx-auto max-w-2xl px-6 py-10"><Alert variant="error">{error}</Alert></div>;
  if (!data) return <div className="flex justify-center py-20"><Spinner className="h-5 w-5" /></div>;

  const { run, messages } = data;
  const board = messages.filter((m) => m.kind === "board");
  const roleName = new Map((team?.members ?? []).map((m) => [m.role, m.agent_name ?? m.role]));
  const nameOf = (r: string | null) => (r ? roleName.get(r) ?? r : "—");

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Link href={`/teams/${run.team_id}`} className="mb-6 inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300">
        <ArrowLeft size={13} />Ekip
      </Link>

      <div className="mb-4 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-zinc-100">Ekip çalıştırması</h1>
        <div className="flex items-center gap-2">
          {(run.status === "running" || run.status === "pending") && <Spinner className="h-3.5 w-3.5" />}
          <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
        </div>
      </div>

      <div className="mb-6 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
        <p className="text-[11px] uppercase tracking-wide text-zinc-600">Görev</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-300">{run.input}</p>
      </div>

      {run.error_message && <Alert variant="error" className="mb-6">{run.error_message}</Alert>}

      {/* Final output */}
      {run.final_output && (
        <div className="mb-6 rounded-xl border border-green-500/20 bg-green-500/5 p-4">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-green-400">
            <CheckCircle2 size={12} />Final çıktı
          </p>
          <div className="text-sm text-zinc-200">
            <Markdown>{run.final_output}</Markdown>
          </div>
        </div>
      )}

      {/* Paylaşılan pano */}
      {board.length > 0 && (
        <>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Paylaşılan pano</h2>
          <div className="mb-6 flex flex-col gap-2">
            {board.map((m) => (
              <div key={m.id} className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-3">
                <p className="flex items-center gap-1.5 text-xs text-amber-300">
                  <StickyNote size={12} />
                  {m.title} <span className="text-zinc-600">· {nameOf(m.from_role)}</span>
                </p>
                <div className="mt-1 text-xs text-zinc-400"><Markdown>{m.content}</Markdown></div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Delegasyon timeline'ı */}
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">İşbirliği akışı</h2>
      {messages.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-800 py-8 text-center text-xs text-zinc-600">
          {run.status === "running" || run.status === "pending" ? "Çalışıyor…" : "Mesaj yok."}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {messages.map((m) => <MessageRow key={m.id} m={m} name={nameOf} />)}
        </div>
      )}
    </div>
  );
}

function Who({ role, name }: { role: string | null; name: (r: string | null) => string }) {
  const I = role ? roleIcon(role) : Wrench;
  return (
    <span className="inline-flex items-center gap-1">
      <I size={12} className={cn("shrink-0", role ? roleColor(role) : "text-zinc-500")} />
      <span className="font-medium text-zinc-200">{name(role)}</span>
    </span>
  );
}

function MessageRow({ m, name }: { m: TeamRunMessage; name: (r: string | null) => string }) {
  const [open, setOpen] = useState(false);
  if (m.kind === "board" || m.kind === "final") return null;
  const p = m.payload ?? {};

  if (m.kind === "tool") {
    // write_todos → checkbox listesi
    if (m.title === "write_todos" && Array.isArray(p.todos)) {
      const todos = p.todos as TodoItem[];
      const done = todos.filter((t) => t.status === "completed").length;
      return (
        <div className="ml-6 rounded-lg border border-zinc-800/50 bg-zinc-950/30 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[11px]">
            <Who role={m.from_role} name={name} />
            <ListChecks size={12} className="text-indigo-400" /><span className="text-zinc-500">görev listesi</span>
            <span className="ml-auto text-zinc-600">{done}/{todos.length}</span>
          </div>
          <div className="mt-1.5 flex flex-col gap-1">
            {todos.map((t, i) => {
              const Icon = t.status === "completed" ? CheckCircle2 : t.status === "in_progress" ? CircleDot : Circle;
              return (
                <div key={i} className="flex items-start gap-1.5 text-[11px]">
                  <Icon size={12} className={cn("mt-0.5 shrink-0", t.status === "completed" ? "text-green-400" : t.status === "in_progress" ? "text-indigo-400" : "text-zinc-600")} />
                  <span className={cn("leading-snug", t.status === "completed" ? "text-zinc-600 line-through" : "text-zinc-300")}>{t.content}</span>
                </div>
              );
            })}
          </div>
        </div>
      );
    }
    const argNode = p.query
      ? <span className="inline-flex min-w-0 items-center gap-1 text-zinc-600"><Search size={10} className="shrink-0" /><span className="truncate">{p.query}</span></span>
      : p.url
        ? <span className="inline-flex min-w-0 items-center gap-1 text-zinc-600"><Link2 size={10} className="shrink-0" /><span className="truncate">{p.url}</span></span>
        : Array.isArray(p.urls) ? <span className="text-zinc-600">{p.urls.length} URL</span>
        : <span className="truncate text-zinc-600">· {m.content}</span>;
    return (
      <div className="ml-6 rounded-lg border border-zinc-800/50 bg-zinc-950/30">
        <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left transition-colors hover:bg-zinc-900/40">
          <Who role={m.from_role} name={name} />
          <Wrench size={10} className="shrink-0 text-amber-400" />
          <span className="shrink-0 text-[11px] font-medium text-zinc-400">{m.title}</span>
          <span className="min-w-0 flex-1 text-[11px]">{argNode}</span>
          <ChevronDown size={11} className={cn("ml-auto shrink-0 text-zinc-700 transition-transform", open && "rotate-180")} />
        </button>
        {open && <p className="max-h-56 overflow-y-auto whitespace-pre-wrap border-t border-zinc-800/50 px-3 py-1.5 text-[11px] text-zinc-400">{m.content}</p>}
      </div>
    );
  }

  const isDelegate = m.kind === "delegate";
  return (
    <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-zinc-900/50">
        <span className="flex shrink-0 flex-wrap items-center gap-1 text-[11px]">
          <Who role={m.from_role} name={name} />
          {isDelegate ? <ArrowRight size={11} className="text-zinc-600" /> : <span className="text-zinc-600">↩</span>}
          <Who role={m.to_role} name={name} />
          <span className="text-zinc-600">· {isDelegate ? "görev" : "sonuç"}</span>
        </span>
        {!open && <span className="min-w-0 flex-1 truncate text-[11px] text-zinc-600">{m.content}</span>}
        <ChevronDown size={12} className={cn("ml-auto shrink-0 text-zinc-600 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="max-h-72 overflow-y-auto border-t border-zinc-800/60 px-3 py-2 text-xs text-zinc-300">
          <Markdown>{m.content}</Markdown>
        </div>
      )}
    </div>
  );
}
