"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Send, Plus, MessageSquare, ArrowRight, Wrench, StickyNote, ChevronDown, CheckCircle2 } from "lucide-react";
import {
  api, ApiError,
  type Team, type TeamRun, type TeamRunDetail, type TeamRunMessage, type TeamConversation,
} from "@/lib/api";
import { roleIcon, roleColor } from "@/lib/team-roles";
import { subscribeTeamRuns } from "@/lib/ws";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";

interface Turn {
  runId: string | null;
  input: string;
  detail: TeamRunDetail | null;
}

export default function TeamChatPage() {
  const { id } = useParams<{ id: string }>();
  const [team, setTeam] = useState<Team | null>(null);
  const [conversations, setConversations] = useState<TeamConversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(() => {
    api.get<TeamConversation[]>(`/teams/${id}/conversations`).then(setConversations).catch(() => {});
  }, [id]);

  useEffect(() => {
    api.get<Team>(`/teams/${id}`).then(setTeam).catch(() => setError("Ekip bulunamadı."));
    loadConversations();
  }, [id, loadConversations]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  // Bir run'ın detayını çek + ilgili turu güncelle
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

  // Çalışan tur varsa yedek poll
  useEffect(() => {
    const active = turns.find((t) => t.runId && t.detail && (t.detail.run.status === "running" || t.detail.run.status === "pending"));
    if (!active?.runId) return;
    const intv = setInterval(() => refreshRun(active.runId!), 3000);
    return () => clearInterval(intv);
  }, [turns, refreshRun]);

  async function loadConversation(convId: string) {
    setError("");
    try {
      const runs = await api.get<TeamRun[]>(`/teams/${id}/conversations/${convId}`);
      const details = await Promise.all(runs.map((r) => api.get<TeamRunDetail>(`/team-runs/${r.id}`).catch(() => null)));
      setConversationId(convId);
      setTurns(runs.map((r, i) => ({ runId: r.id, input: r.input, detail: details[i] })));
    } catch {
      setError("Sohbet yüklenemedi.");
    }
  }

  function newChat() {
    setConversationId(null);
    setTurns([]);
    setError("");
  }

  async function send() {
    const text = input.trim();
    if (!text) return;
    setSending(true);
    setError("");
    setInput("");
    setTurns((prev) => [...prev, { runId: null, input: text, detail: null }]);
    try {
      const run = await api.post<TeamRun>(`/teams/${id}/run`, { input: text, conversation_id: conversationId });
      setConversationId(run.conversation_id);
      setTurns((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.runId === null) last.runId = run.id;
        return next;
      });
      refreshRun(run.id);
      loadConversations();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gönderilemedi.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] w-full max-w-3xl flex-col px-6 py-6">
      {/* Başlık */}
      <div className="mb-3 flex items-center gap-3">
        <Link href="/teams" className="text-zinc-500 hover:text-zinc-300"><ArrowLeft size={16} /></Link>
        <div className="flex-1">
          <h1 className="text-sm font-semibold text-zinc-100">{team?.name ?? "Ekip"}</h1>
          <p className="text-[11px] text-zinc-600">
            {team?.members.map((m) => m.role).join(" · ")}
          </p>
        </div>
        {conversations.length > 0 && (
          <select
            value={conversationId ?? ""}
            onChange={(e) => (e.target.value ? loadConversation(e.target.value) : newChat())}
            className="max-w-[180px] rounded-md border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-300"
          >
            <option value="">— sohbet seç —</option>
            {conversations.map((c) => (
              <option key={c.conversation_id} value={c.conversation_id}>
                {c.first_input.slice(0, 30)} ({c.turns})
              </option>
            ))}
          </select>
        )}
        <Button size="sm" variant="outline" onClick={newChat}><Plus size={13} />Yeni</Button>
      </div>

      {error && <Alert variant="error" className="mb-3">{error}</Alert>}

      {/* Mesajlar */}
      <div className="flex-1 overflow-y-auto rounded-xl border border-zinc-800/60 bg-zinc-950/30 p-4">
        {turns.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-zinc-600">
            <MessageSquare size={28} className="mb-3 text-zinc-700" />
            <p className="text-sm">Ekiple sohbet et — Coordinator görevi alıp üyelere dağıtır.</p>
            <p className="mt-1 text-xs">Her mesajda işbirliği akışını canlı görürsün.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {turns.map((t, i) => <TurnView key={t.runId ?? `pending-${i}`} turn={t} />)}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Girdi */}
      <div className="mt-3 flex items-end gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          rows={2}
          placeholder="Ekibe görevi yaz… (Enter ile gönder)"
          className="flex-1"
        />
        <Button onClick={send} loading={sending} disabled={!input.trim()}><Send size={14} /></Button>
      </div>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const d = turn.detail;
  const status = d?.run.status;
  const running = !d || status === "running" || status === "pending";
  const collab = (d?.messages ?? []).filter((m) => m.kind !== "final");

  return (
    <div className="flex flex-col gap-2">
      {/* Kullanıcı mesajı */}
      <div className="self-end max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-500/15 px-3.5 py-2 text-sm text-zinc-100">
        {turn.input}
      </div>

      {/* Ekip işbirliği + yanıt */}
      <div className="max-w-[92%] self-start">
        {collab.length > 0 && <Collaboration messages={collab} running={running} />}
        {running && collab.length === 0 && (
          <p className="flex items-center gap-2 text-xs text-zinc-500"><Spinner className="h-3.5 w-3.5" />Ekip çalışıyor…</p>
        )}
        {d?.run.error_message && <Alert variant="error" className="mt-2">{d.run.error_message}</Alert>}
        {d?.run.final_output && (
          <div className="mt-2 rounded-2xl rounded-bl-sm border border-zinc-800/80 bg-zinc-900/50 px-4 py-3 text-sm text-zinc-200">
            <Markdown>{d.run.final_output}</Markdown>
          </div>
        )}
      </div>
    </div>
  );
}

function Collaboration({ messages, running }: { messages: TeamRunMessage[]; running: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-lg border border-zinc-800/50 bg-zinc-950/40">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[11px] text-zinc-500 hover:text-zinc-300"
      >
        {running ? <Spinner className="h-3 w-3" /> : <CheckCircle2 size={12} className="text-green-400" />}
        İşbirliği · {messages.length} adım
        <ChevronDown size={11} className={cn("ml-auto transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="flex flex-col gap-1 border-t border-zinc-800/50 px-3 py-2">
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
      <div className="flex items-start gap-1.5 text-[11px] text-amber-300/80">
        <StickyNote size={11} className="mt-0.5 shrink-0" />
        <span><span className="font-medium">{m.title}</span> <span className="text-zinc-600">· {m.from_role}</span></span>
      </div>
    );
  }
  if (m.kind === "tool") {
    return (
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-1.5 text-left text-[11px] text-zinc-500">
        <FromI size={11} className={m.from_role ? roleColor(m.from_role) : "text-amber-400"} />
        <Wrench size={10} className="text-amber-400" />
        <span className="text-zinc-400">{m.title}</span>
        <span className="min-w-0 flex-1 truncate text-zinc-600">{!open && `· ${m.content}`}</span>
        {open && <span className="text-zinc-500">{m.content.slice(0, 300)}</span>}
      </button>
    );
  }
  // delegate | result
  const isDelegate = m.kind === "delegate";
  const ToI = m.to_role ? roleIcon(m.to_role) : null;
  return (
    <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-1.5 text-left text-[11px]">
      <span className="flex shrink-0 items-center gap-1">
        {FromI && <FromI size={11} className={roleColor(m.from_role ?? "")} />}
        <ArrowRight size={9} className="text-zinc-600" />
        {ToI && <ToI size={11} className={roleColor(m.to_role ?? "")} />}
        <span className="text-zinc-600">{isDelegate ? "" : "↩"}</span>
      </span>
      <span className={cn("min-w-0 flex-1 text-zinc-400", !open && "truncate")}>{m.content}</span>
    </button>
  );
}
