"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, Send, Plus, MessageSquare, Trash2, Users, Settings2,
  ArrowRight, Wrench, StickyNote, ChevronDown, CheckCircle2, User as UserIcon,
  BookOpen, Eye,
} from "lucide-react";
import {
  api, ApiError,
  type Team, type TeamRun, type TeamRunDetail, type TeamRunMessage, type TeamConversation, type Agent,
} from "@/lib/api";
import { roleIcon, roleColor } from "@/lib/team-roles";
import { subscribeTeamRuns } from "@/lib/ws";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Markdown } from "@/components/ui/markdown";
import { Modal } from "@/components/ui/modal";
import { cn } from "@/lib/utils";

interface Turn {
  runId: string | null;
  input: string;
  detail: TeamRunDetail | null;
}

const topBtn = "flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "şimdi";
  if (m < 60) return `${m} dk`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} sa`;
  return `${Math.floor(h / 24)} g`;
}

export default function TeamChatPage() {
  const { id } = useParams<{ id: string }>();
  const [team, setTeam] = useState<Team | null>(null);
  const [conversations, setConversations] = useState<TeamConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showTeam, setShowTeam] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(() => {
    api.get<TeamConversation[]>(`/teams/${id}/conversations`).then(setConversations).catch(() => {});
  }, [id]);

  useEffect(() => {
    api.get<Team>(`/teams/${id}`).then(setTeam).catch(() => setError("Ekip bulunamadı."));
    api.get<Agent[]>("/agents").then(setAgents).catch(() => {});
    refreshConversations();
  }, [id, refreshConversations]);

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [turns]);

  const refreshRun = useCallback(async (runId: string) => {
    try {
      const detail = await api.get<TeamRunDetail>(`/team-runs/${runId}`);
      setTurns((prev) => prev.map((t) => (t.runId === runId ? { ...t, detail } : t)));
    } catch { /* ignore */ }
  }, []);

  // Canlı: WS ping → ilgili turu yenile
  useEffect(() => {
    const unsub = subscribeTeamRuns((ev) => {
      if (turns.some((t) => t.runId === ev.run_id)) refreshRun(ev.run_id);
    });
    return unsub;
  }, [turns, refreshRun]);

  // Çalışan tur için yedek poll
  useEffect(() => {
    const active = turns.find((t) => t.runId && t.detail && (t.detail.run.status === "running" || t.detail.run.status === "pending"));
    if (!active?.runId) return;
    const intv = setInterval(() => refreshRun(active.runId!), 3500);
    return () => clearInterval(intv);
  }, [turns, refreshRun]);

  async function openConversation(convId: string) {
    setActiveConvId(convId);
    setTurns([]);
    setError("");
    try {
      const runs = await api.get<TeamRun[]>(`/teams/${id}/conversations/${convId}`);
      const details = await Promise.all(runs.map((r) => api.get<TeamRunDetail>(`/team-runs/${r.id}`).catch(() => null)));
      setTurns(runs.map((r, i) => ({ runId: r.id, input: r.input, detail: details[i] })));
    } catch {
      setError("Sohbet yüklenemedi.");
    }
  }

  function newChat() {
    setActiveConvId(null);
    setTurns([]);
    setInput("");
    setError("");
  }

  async function deleteConversation(convId: string) {
    try { await api.delete(`/teams/${id}/conversations/${convId}`); } catch { /* ignore */ }
    setConversations((prev) => prev.filter((c) => c.conversation_id !== convId));
    if (activeConvId === convId) newChat();
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setError("");
    setInput("");
    setTurns((prev) => [...prev, { runId: null, input: text, detail: null }]);
    try {
      const run = await api.post<TeamRun>(`/teams/${id}/run`, { input: text, conversation_id: activeConvId });
      setActiveConvId(run.conversation_id);
      setTurns((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.runId === null) last.runId = run.id;
        return next;
      });
      refreshRun(run.id);
      refreshConversations();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gönderilemedi.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-[calc(100dvh-3rem)] overflow-hidden">
      {/* Sohbet kenar çubuğu */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-zinc-900 sm:flex">
        <div className="flex items-center gap-2 px-3 py-3">
          <Link href={`/teams/${id}`} className="text-zinc-600 transition-colors hover:text-zinc-300">
            <ArrowLeft size={15} />
          </Link>
          <span className="flex-1 truncate text-xs font-medium text-zinc-300">{team?.name ?? "…"}</span>
        </div>
        <div className="px-3 pb-2">
          <Button size="sm" variant="outline" className="w-full" onClick={newChat}>
            <Plus size={13} />Yeni sohbet
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-1">
          {conversations.length === 0 ? (
            <p className="px-2 py-4 text-center text-[11px] text-zinc-600">Henüz sohbet yok</p>
          ) : (
            conversations.map((c) => (
              <div
                key={c.conversation_id}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors",
                  activeConvId === c.conversation_id ? "bg-zinc-900 text-zinc-100" : "text-zinc-400 hover:bg-zinc-900/50",
                )}
              >
                <button onClick={() => openConversation(c.conversation_id)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
                  <MessageSquare size={12} className="shrink-0 text-zinc-600" />
                  <span className="flex-1 truncate">{c.first_input}</span>
                </button>
                <span className="shrink-0 text-[10px] text-zinc-700">{relativeTime(c.updated_at)}</span>
                <button
                  onClick={() => deleteConversation(c.conversation_id)}
                  className="shrink-0 text-zinc-700 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Sohbet alanı */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-zinc-900 px-6 py-3">
          <div className="flex items-center gap-2">
            <Users size={15} className="text-indigo-400" />
            <span className="text-sm font-medium text-zinc-100">{team?.name ?? "…"}</span>
            <span className="hidden text-[11px] text-zinc-600 md:inline">{team?.members.map((m) => m.role).join(" · ")}</span>
          </div>
          {team && (
            <div className="flex items-center gap-2">
              <Link href={`/teams/${id}/knowledge`} className={topBtn}>
                <BookOpen size={12} />Knowledge Base
              </Link>
              <button type="button" onClick={() => setShowTeam(true)} className={topBtn}>
                <Eye size={12} />Ekibi Tanı
              </button>
              <Link href={`/teams/${id}`} className={topBtn}>
                <Settings2 size={12} />Düzenle
              </Link>
            </div>
          )}
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
            {turns.length === 0 && (
              <div className="py-20 text-center">
                <Users size={28} className="mx-auto mb-3 text-zinc-700" />
                <p className="text-sm text-zinc-500">Ekiple sohbete başla — Coordinator görevi alıp üyelere dağıtır.</p>
                <p className="mt-1 text-xs text-zinc-600">İşbirliğini canlı, yanıtı en sonda görürsün.</p>
              </div>
            )}
            {turns.map((t, i) => <TurnBubble key={t.runId ?? `pending-${i}`} turn={t} />)}
          </div>
        </div>

        <div className="border-t border-zinc-900 px-6 py-4">
          {error && <Alert variant="error" className="mx-auto mb-2 max-w-3xl">{error}</Alert>}
          <form onSubmit={handleSend} className="mx-auto flex w-full max-w-3xl items-end gap-2">
            <div className="flex-1">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void handleSend(e); } }}
                placeholder="Ekibe görev yaz…  (Enter = gönder, Shift+Enter = yeni satır)"
                rows={1}
                className="resize-none"
              />
            </div>
            <Button type="submit" size="lg" disabled={sending || !input.trim()}>
              {sending ? <Spinner className="h-4 w-4" /> : <Send size={15} />}
            </Button>
          </form>
        </div>
      </div>

      <TeamModal open={showTeam} onClose={() => setShowTeam(false)} team={team} agents={agents} />
    </div>
  );
}

// ── Ekibi Tanı modalı: üyeler + roller + her agent'ın tool'ları ──

function TeamModal({ open, onClose, team, agents }: { open: boolean; onClose: () => void; team: Team | null; agents: Agent[] }) {
  if (!open || !team) return null;
  const byId = new Map(agents.map((a) => [a.id, a]));
  return (
    <Modal open title={`Ekibi Tanı — ${team.name}`} onClose={onClose} className="max-w-xl">
      <div className="flex flex-col gap-3">
        {team.description && <p className="text-xs text-zinc-500">{team.description}</p>}
        <p className="text-[11px] text-zinc-600">{team.members.length} üye · max {team.max_delegations} delege · {team.run_timeout_seconds}s üst süre</p>
        <div className="flex max-h-[55vh] flex-col gap-2 overflow-y-auto">
          {team.members.map((m) => {
            const RI = roleIcon(m.role);
            const a = m.agent_id ? byId.get(m.agent_id) : undefined;
            const tools = a?.tool_names ?? [];
            return (
              <div key={m.id} className="rounded-lg border border-zinc-800/70 bg-zinc-900/40 p-3">
                <div className="flex items-center gap-2">
                  <RI size={16} className={cn("shrink-0", roleColor(m.role))} />
                  <span className="text-sm font-medium text-zinc-200">{m.agent_name ?? "—"}</span>
                  <span className="rounded-md bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300">{m.role}</span>
                  {a && <span className="ml-auto text-[10px] text-zinc-600">{a.provider} · {a.model}</span>}
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {a?.file_system_enabled && <ToolTag label="dosya sistemi" />}
                  {tools.length === 0 && !a?.file_system_enabled ? (
                    <span className="text-[10px] text-zinc-600">tool yok</span>
                  ) : tools.map((t) => <ToolTag key={t} label={t} />)}
                </div>
              </div>
            );
          })}
        </div>
        {team.shared_instructions && (
          <div className="rounded-lg border border-zinc-800/60 bg-zinc-950/40 p-2.5">
            <p className="text-[10px] uppercase tracking-wide text-zinc-600">Ekip promptu</p>
            <p className="mt-1 text-xs text-zinc-400">{team.shared_instructions}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

function ToolTag({ label }: { label: string }) {
  return <span className="rounded bg-zinc-800/70 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">{label}</span>;
}

// ── Tur baloncuğu (kullanıcı + ekip yanıtı) ─────────────────

function TurnBubble({ turn }: { turn: Turn }) {
  const d = turn.detail;
  const status = d?.run.status;
  const running = !d || status === "running" || status === "pending";
  const collab = (d?.messages ?? []).filter((m) => m.kind !== "final");

  return (
    <>
      {/* Kullanıcı mesajı (sağ) */}
      <div className="flex flex-row-reverse gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
          <UserIcon size={14} className="text-zinc-400" />
        </div>
        <div className="max-w-[85%]">
          <div className="whitespace-pre-wrap rounded-xl bg-indigo-600 px-3.5 py-2.5 text-sm leading-relaxed text-white">
            {turn.input}
          </div>
        </div>
      </div>

      {/* Ekip yanıtı (sol) */}
      <div className="flex gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10">
          <Users size={14} className="text-indigo-400" />
        </div>
        <div className="flex max-w-[85%] flex-col gap-2">
          {collab.length > 0 && <Collaboration messages={collab} running={running} />}
          {running && collab.length === 0 && (
            <div className="flex items-center gap-2 px-1 text-xs text-zinc-600"><Spinner className="h-3 w-3" />ekip çalışıyor…</div>
          )}
          {d?.run.error_message && <Alert variant="error">{d.run.error_message}</Alert>}
          {d?.run.final_output && (
            <div className="rounded-xl bg-zinc-900/70 px-3.5 py-2.5 text-sm leading-relaxed text-zinc-200">
              <Markdown>{d.run.final_output}</Markdown>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Collaboration({ messages, running }: { messages: TeamRunMessage[]; running: boolean }) {
  const [open, setOpen] = useState(true);
  // Final hazır olunca işbirliğini varsayılan kapat (yanıt öne çıksın)
  useEffect(() => { if (!running) setOpen(false); }, [running]);
  return (
    <div className="w-full rounded-lg border border-zinc-800/60 bg-zinc-900/40 text-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-zinc-900/70"
      >
        {running ? <Spinner className="h-3 w-3" /> : <CheckCircle2 size={12} className="text-green-400" />}
        <span className="font-medium text-zinc-300">İşbirliği</span>
        <span className="text-zinc-600">· {messages.length} adım</span>
        <ChevronDown size={12} className={cn("ml-auto transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="flex flex-col gap-1.5 border-t border-zinc-800/60 px-3 py-2">
          {messages.map((m) => <MsgLine key={m.id} m={m} />)}
        </div>
      )}
    </div>
  );
}

function MsgLine({ m }: { m: TeamRunMessage }) {
  const [open, setOpen] = useState(false);
  const FromI = m.from_role ? roleIcon(m.from_role) : Wrench;

  if (m.kind === "board") {
    return (
      <div className="rounded-md border border-zinc-800/50 bg-zinc-950/30">
        <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-1.5 px-2 py-1 text-left text-[11px] text-amber-300/90">
          <StickyNote size={11} className="shrink-0" />
          <span className="font-medium">{m.title}</span>
          <span className="text-zinc-600">· {m.from_role}</span>
          <ChevronDown size={10} className={cn("ml-auto transition-transform", open && "rotate-180")} />
        </button>
        {open && <div className="border-t border-zinc-800/50 px-2 py-1 text-[11px] text-zinc-400"><Markdown>{m.content}</Markdown></div>}
      </div>
    );
  }

  if (m.kind === "tool") {
    return (
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-1.5 text-left text-[11px]">
        <FromI size={11} className={cn("shrink-0", m.from_role ? roleColor(m.from_role) : "text-amber-400")} />
        <Wrench size={10} className="shrink-0 text-amber-400" />
        <span className="shrink-0 text-zinc-400">{m.title}</span>
        <span className={cn("min-w-0 flex-1 text-zinc-600", !open && "truncate")}>· {open ? m.content.slice(0, 400) : m.content}</span>
      </button>
    );
  }

  // delegate | result
  const isDelegate = m.kind === "delegate";
  const ToI = m.to_role ? roleIcon(m.to_role) : null;
  return (
    <div className="flex flex-col">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-1.5 text-left text-[11px]">
        <span className="flex shrink-0 items-center gap-1 pt-0.5">
          {FromI && <FromI size={11} className={roleColor(m.from_role ?? "")} />}
          <ArrowRight size={9} className="text-zinc-600" />
          {ToI && <ToI size={11} className={roleColor(m.to_role ?? "")} />}
          <span className="text-zinc-600">{isDelegate ? "delege" : "↩ sonuç"}</span>
        </span>
        <span className={cn("min-w-0 flex-1 text-zinc-400", !open && "truncate")}>{m.content}</span>
        <ChevronDown size={10} className={cn("ml-auto mt-0.5 shrink-0 text-zinc-700 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="mt-1 max-h-72 overflow-y-auto rounded-md bg-zinc-950/40 px-2 py-1.5 text-[11px] text-zinc-300">
          <Markdown>{m.content}</Markdown>
        </div>
      )}
    </div>
  );
}
