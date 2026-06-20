"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Send,
  Wrench,
  ShieldCheck,
  Activity,
  User as UserIcon,
  Bot,
  Plus,
  MessageSquare,
  Trash2,
  Brain,
  ListChecks,
  CheckCircle2,
  Circle,
  CircleDot,
  HelpCircle,
  FolderTree,
  AlertTriangle,
  ChevronDown,
  BookOpen,
  Settings2,
} from "lucide-react";
import { friendlyError } from "@/lib/errors";
import {
  api,
  ApiError,
  type Agent,
  type ConversationSummary,
  type ConversationDetail,
  type ConversationMessage,
} from "@/lib/api";
import { streamConversationMessage, type AgentStreamEvent } from "@/lib/stream";
import { toolLabel, formatArgs } from "@/lib/tools";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";

// ── Mesaj modeli ────────────────────────────────────────────

interface ToolBlock {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "running" | "done";
}
type Segment = { kind: "text"; text: string } | { kind: "tool"; tool: ToolBlock };
interface ChatMessage {
  role: "user" | "assistant";
  segments: Segment[];
  traceId?: string;
  error?: string;
  errorCode?: string;
  running?: boolean;
}
interface HitlState {
  requestId: string;
  toolName: string;
  args: Record<string, unknown>;
}
interface QuestionState {
  requestId: string;
  question: string;
  options: string[];
  multi: boolean;
}
interface TodoItem {
  content: string;
  status: "pending" | "in_progress" | "completed";
}

// Backend'de saklanan mesajı UI mesajına çevir
function toChatMessage(m: ConversationMessage): ChatMessage {
  if (m.role === "user") {
    return { role: "user", segments: [{ kind: "text", text: m.content }] };
  }
  const segs: Segment[] = [];
  for (const raw of (m.segments ?? []) as Array<Record<string, unknown>>) {
    if (raw.kind === "text") {
      segs.push({ kind: "text", text: String(raw.text ?? "") });
    } else if (raw.kind === "tool") {
      const t = raw.tool as Record<string, unknown>;
      segs.push({
        kind: "tool",
        tool: {
          id: `${String(t.name)}-${segs.length}`,
          name: String(t.name),
          args: (t.args as Record<string, unknown>) ?? {},
          result: t.result ? String(t.result) : undefined,
          status: t.status === "running" ? "running" : "done",
        },
      });
    }
  }
  if (segs.length === 0 && m.content) segs.push({ kind: "text", text: m.content });
  return {
    role: "assistant",
    segments: segs,
    traceId: m.trace_id ?? undefined,
    error: m.error ?? undefined,
  };
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "şimdi";
  if (m < 60) return `${m} dk`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} sa`;
  return `${Math.floor(h / 24)} g`;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [loadError, setLoadError] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [hitl, setHitl] = useState<HitlState | null>(null);
  const [question, setQuestion] = useState<QuestionState | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    try {
      const list = await api.get<ConversationSummary[]>(`/agents/${id}/conversations`);
      setConversations(list);
      return list;
    } catch {
      return [];
    }
  }, [id]);

  // İlk yükleme: agent + thread'ler; ?c= varsa o thread'i, yoksa en yeniyi aç
  useEffect(() => {
    api.get<Agent>(`/agents/${id}`).then(setAgent).catch(() => setLoadError("Agent not found."));
    refreshConversations().then((list) => {
      const wanted = new URLSearchParams(window.location.search).get("c");
      if (wanted && list.some((c) => c.id === wanted)) void openConversation(wanted);
      else if (list.length > 0) void openConversation(list[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, hitl, question]);

  async function openConversation(conversationId: string) {
    setActiveId(conversationId);
    setMessages([]);
    try {
      const detail = await api.get<ConversationDetail>(`/conversations/${conversationId}`);
      setMessages(detail.messages.map(toChatMessage));
    } catch {
      setMessages([]);
    }
  }

  function newChat() {
    setActiveId(null);
    setMessages([]);
    setInput("");
  }

  async function deleteConversation(conversationId: string) {
    try {
      await api.delete(`/conversations/${conversationId}`);
    } catch {
      /* ignore */
    }
    setConversations((prev) => prev.filter((c) => c.id !== conversationId));
    if (activeId === conversationId) newChat();
  }

  const patchAssistant = useCallback((fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === "assistant") {
          next[i] = fn(next[i]);
          break;
        }
      }
      return next;
    });
  }, []);

  const handleEvent = useCallback(
    (ev: AgentStreamEvent) => {
      switch (ev.type) {
        case "token":
          if (!ev.content) break;
          patchAssistant((m) => {
            const segs = [...m.segments];
            const last = segs[segs.length - 1];
            if (last && last.kind === "text") {
              segs[segs.length - 1] = { kind: "text", text: last.text + ev.content };
            } else {
              segs.push({ kind: "text", text: ev.content! });
            }
            return { ...m, segments: segs };
          });
          break;
        case "tool_call_start":
          patchAssistant((m) => ({
            ...m,
            segments: [
              ...m.segments,
              {
                kind: "tool",
                tool: {
                  id: `${ev.tool_name}-${m.segments.length}`,
                  name: ev.tool_name ?? "tool",
                  args: ev.tool_arguments ?? {},
                  status: "running",
                },
              },
            ],
          }));
          break;
        case "tool_call_end":
          patchAssistant((m) => {
            const segs = [...m.segments];
            for (let i = segs.length - 1; i >= 0; i--) {
              const s = segs[i];
              if (s.kind === "tool" && s.tool.name === ev.tool_name && s.tool.status === "running") {
                segs[i] = { kind: "tool", tool: { ...s.tool, result: ev.tool_result, status: "done" } };
                break;
              }
            }
            return { ...m, segments: segs };
          });
          break;
        case "hitl_requested":
          if (ev.hitl_request_id) {
            setHitl({
              requestId: ev.hitl_request_id,
              toolName: ev.tool_name ?? "tool",
              args: ev.tool_arguments ?? {},
            });
          }
          break;
        case "hitl_resolved":
          setHitl(null);
          break;
        case "ask_user_requested":
          if (ev.hitl_request_id) {
            setQuestion({
              requestId: ev.hitl_request_id,
              question: ev.question ?? "",
              options: ev.question_options ?? [],
              multi: ev.question_multi ?? false,
            });
          }
          break;
        case "ask_user_answered":
          setQuestion(null);
          break;
        case "done":
          patchAssistant((m) => ({ ...m, running: false, traceId: ev.trace_id }));
          setRunning(false);
          break;
        case "error":
          patchAssistant((m) => ({
            ...m,
            running: false,
            error: ev.error_message ?? ev.error_code ?? "Agent error.",
            errorCode: ev.error_code,
          }));
          setRunning(false);
          setHitl(null);
          setQuestion(null);
          break;
      }
    },
    [patchAssistant],
  );

  async function submitAnswer(answer: string) {
    if (!question) return;
    try {
      await api.post(`/hitl/${question.requestId}/answer`, { answer });
    } catch (err) {
      if (err instanceof ApiError) setQuestion(null);
    }
  }

  async function ensureConversation(): Promise<string> {
    if (activeId) return activeId;
    const conv = await api.post<ConversationSummary>(`/agents/${id}/conversations`, {});
    setActiveId(conv.id);
    setConversations((prev) => [conv, ...prev]);
    return conv.id;
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || running) return;

    setInput("");
    setRunning(true);

    let convId: string;
    try {
      convId = await ensureConversation();
    } catch (err) {
      setRunning(false);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", segments: [], error: err instanceof ApiError ? err.message : "Could not start chat." },
      ]);
      return;
    }

    setMessages((prev) => [
      ...prev,
      { role: "user", segments: [{ kind: "text", text }] },
      { role: "assistant", segments: [], running: true },
    ]);

    try {
      await streamConversationMessage(convId, text, handleEvent);
    } catch (err) {
      patchAssistant((m) => ({
        ...m,
        running: false,
        error: err instanceof Error ? err.message : "Stream failed.",
      }));
      setRunning(false);
    }
    void refreshConversations();
  }

  async function resolveHitl(action: "approve" | "reject", reason?: string) {
    if (!hitl) return;
    try {
      await api.post(`/hitl/${hitl.requestId}/${action}`, reason ? { reason } : undefined);
    } catch (err) {
      if (err instanceof ApiError) setHitl(null);
    }
  }

  async function modifyHitl(argsText: string) {
    if (!hitl) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(argsText);
    } catch {
      return;
    }
    try {
      await api.post(`/hitl/${hitl.requestId}/modify`, { arguments: parsed });
    } catch (err) {
      if (err instanceof ApiError) setHitl(null);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Alert variant="error">{loadError}</Alert>
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sohbet kenar çubuğu */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-zinc-900 sm:flex">
        <div className="flex items-center gap-2 px-3 py-3">
          <Link href="/agents" className="text-zinc-600 transition-colors hover:text-zinc-300">
            <ArrowLeft size={15} />
          </Link>
          <span className="flex-1 truncate text-xs font-medium text-zinc-300">
            {agent?.name ?? "…"}
          </span>
        </div>
        <div className="px-3 pb-2">
          <Button size="sm" variant="outline" className="w-full" onClick={newChat}>
            <Plus size={13} />
            Yeni sohbet
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-1">
          {conversations.length === 0 ? (
            <p className="px-2 py-4 text-center text-[11px] text-zinc-600">Henüz sohbet yok</p>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors",
                  activeId === c.id ? "bg-zinc-900 text-zinc-100" : "text-zinc-400 hover:bg-zinc-900/50",
                )}
              >
                <button onClick={() => openConversation(c.id)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
                  <MessageSquare size={12} className="shrink-0 text-zinc-600" />
                  <span className="flex-1 truncate">{c.title}</span>
                </button>
                <span className="shrink-0 text-[10px] text-zinc-700">{relativeTime(c.last_message_at)}</span>
                <button
                  onClick={() => deleteConversation(c.id)}
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
            <Bot size={15} className="text-indigo-400" />
            <span className="text-sm font-medium text-zinc-100">{agent?.name ?? "…"}</span>
            {agent && <span className="text-[11px] text-zinc-600">{agent.provider} · {agent.model}</span>}
          </div>
          <div className="flex items-center gap-2">
            {agent && (
              <Link
                href={`/agents/${id}/knowledge`}
                className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
              >
                <BookOpen size={12} />
                Bilgi
              </Link>
            )}
            {agent?.file_system_enabled && (
              <Link
                href={`/agents/${id}/files`}
                className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
              >
                <FolderTree size={12} />
                Dosyalar
              </Link>
            )}
            {agent && (
              <Link
                href={`/agents/${id}/edit`}
                className="flex items-center gap-1.5 rounded-md border border-zinc-800 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-200"
              >
                <Settings2 size={12} />
                Düzenle
              </Link>
            )}
            {agent && agent.hitl_tool_names.length > 0 && (
              <Badge variant="amber">
                <ShieldCheck size={10} />
                Onay gerektiren araçlar
              </Badge>
            )}
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
            {messages.length === 0 && (
              <div className="py-20 text-center">
                <Bot size={28} className="mx-auto mb-3 text-zinc-700" />
                <p className="text-sm text-zinc-500">Sohbete başlamak için bir mesaj gönder.</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <MessageBubble
                key={i}
                msg={msg}
                traceSuffix={`?agent=${id}${activeId ? `&c=${activeId}` : ""}`}
              />
            ))}
          </div>
        </div>

        <div className="border-t border-zinc-900 px-6 py-4">
          <form onSubmit={handleSend} className="mx-auto flex w-full max-w-3xl items-end gap-2">
            <div className="flex-1">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleSend(e);
                  }
                }}
                placeholder="Mesaj yaz…  (Enter = gönder, Shift+Enter = yeni satır)"
                rows={1}
                disabled={running}
                className="resize-none"
              />
            </div>
            <Button type="submit" size="lg" disabled={running || !input.trim()}>
              {running ? <Spinner className="h-4 w-4" /> : <Send size={15} />}
            </Button>
          </form>
        </div>
      </div>

      <HitlModal
        state={hitl}
        onApprove={() => resolveHitl("approve")}
        onReject={(reason) => resolveHitl("reject", reason)}
        onModify={(args) => modifyHitl(args)}
      />

      <QuestionModal state={question} onSubmit={submitAnswer} />
    </div>
  );
}

// ── Mesaj baloncuğu ─────────────────────────────────────────

function MessageBubble({ msg, traceSuffix }: { msg: ChatMessage; traceSuffix: string }) {
  const isUser = msg.role === "user";
  // Sadece SON write_todos segmenti panel olarak render edilir (canlı güncellenir)
  let lastTodosIdx = -1;
  msg.segments.forEach((s, i) => {
    if (s.kind === "tool" && s.tool.name === "write_todos") lastTodosIdx = i;
  });
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", isUser ? "bg-zinc-800" : "bg-indigo-500/10")}>
        {isUser ? <UserIcon size={14} className="text-zinc-400" /> : <Bot size={14} className="text-indigo-400" />}
      </div>
      <div className={cn("flex max-w-[85%] flex-col gap-2", isUser && "items-end")}>
        {msg.segments.map((seg, i) => {
          if (seg.kind === "text") {
            if (!seg.text) return null;
            return (
              <div
                key={i}
                className={cn(
                  "rounded-xl px-3.5 py-2.5 text-sm leading-relaxed",
                  isUser
                    ? "whitespace-pre-wrap bg-indigo-600 text-white"
                    : "bg-zinc-900/70 text-zinc-200",
                )}
              >
                {isUser ? seg.text : <Markdown>{seg.text}</Markdown>}
              </div>
            );
          }
          const name = seg.tool.name;
          if (name === "think") {
            return <ReasoningBlock key={i} thought={String(seg.tool.args.thought ?? "")} />;
          }
          if (name === "write_todos") {
            return i === lastTodosIdx ? (
              <TodosPanel key={i} todos={(seg.tool.args.todos as TodoItem[]) ?? []} />
            ) : null;
          }
          return <ToolCard key={i} tool={seg.tool} />;
        })}
        {msg.running && msg.segments.every((s) => s.kind !== "text" || !s.text) && (
          <div className="flex items-center gap-2 px-1 text-xs text-zinc-600">
            <Spinner className="h-3 w-3" />
            düşünüyor…
          </div>
        )}
        {msg.error && <ErrorBlock code={msg.errorCode} message={msg.error} />}
        {msg.traceId && (
          <Link
            href={`/traces/${msg.traceId}${traceSuffix}`}
            className="flex items-center gap-1 px-1 text-[11px] text-zinc-600 transition-colors hover:text-indigo-400"
          >
            <Activity size={11} />
            İzi görüntüle
          </Link>
        )}
      </div>
    </div>
  );
}

function ToolCard({ tool }: { tool: ToolBlock }) {
  const rows = formatArgs(tool.args);
  return (
    <div className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2.5 text-xs">
      <div className="flex items-center gap-2">
        <Wrench size={12} className="text-amber-400" />
        <span className="font-medium text-zinc-300">{toolLabel(tool.name)}</span>
        {tool.status === "running" ? <Spinner className="h-3 w-3" /> : <Badge variant="green">tamam</Badge>}
      </div>
      {rows.length > 0 && (
        <div className="mt-1.5 flex flex-col gap-0.5">
          {rows.map((r, i) => (
            <div key={i} className="flex gap-1.5 text-[11px]">
              <span className="text-zinc-600">{r.label}:</span>
              <span className="text-zinc-400">{r.value}</span>
            </div>
          ))}
        </div>
      )}
      {tool.result && (
        <p className="mt-1.5 line-clamp-4 whitespace-pre-wrap text-[11px] text-zinc-400">{tool.result}</p>
      )}
    </div>
  );
}

// ── Hata bloğu (anlamlı + katlanır teknik detay) ────────────

function ErrorBlock({ code, message }: { code?: string; message: string }) {
  const [open, setOpen] = useState(false);
  const e = friendlyError(code, message);
  return (
    <div className="w-full rounded-lg border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-sm text-red-300">
      <div className="flex items-start gap-2.5">
        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-red-400" />
        <div className="flex-1">
          <p className="leading-relaxed">{e.title}</p>
          {e.hint && <p className="mt-1 text-xs text-red-300/70">{e.hint}</p>}
          {e.detail && (
            <>
              <button
                onClick={() => setOpen((o) => !o)}
                className="mt-1.5 flex items-center gap-1 text-[11px] text-red-300/60 transition-colors hover:text-red-300"
              >
                <ChevronDown size={11} className={cn("transition-transform", open && "rotate-180")} />
                Teknik detay
              </button>
              {open && (
                <pre className="mt-1.5 overflow-x-auto whitespace-pre-wrap rounded bg-red-950/30 p-2 text-[11px] text-red-300/80">
                  {e.detail}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Reasoning (think) bloğu ─────────────────────────────────

function ReasoningBlock({ thought }: { thought: string }) {
  return (
    <div className="flex gap-2 rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-3 py-2 text-xs text-zinc-400">
      <Brain size={13} className="mt-0.5 shrink-0 text-violet-400" />
      <span className="whitespace-pre-wrap italic leading-relaxed">{thought}</span>
    </div>
  );
}

// ── To-do paneli (write_todos) ──────────────────────────────

function TodosPanel({ todos }: { todos: TodoItem[] }) {
  if (!todos || todos.length === 0) return null;
  const done = todos.filter((t) => t.status === "completed").length;
  return (
    <div className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2.5 text-xs">
      <div className="mb-2 flex items-center gap-2 text-zinc-300">
        <ListChecks size={13} className="text-indigo-400" />
        <span className="font-medium">Görevler</span>
        <span className="text-zinc-600">
          {done}/{todos.length}
        </span>
      </div>
      <div className="flex flex-col gap-1">
        {todos.map((t, i) => (
          <div key={i} className="flex items-start gap-2">
            {t.status === "completed" ? (
              <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-green-400" />
            ) : t.status === "in_progress" ? (
              <CircleDot size={13} className="mt-0.5 shrink-0 text-indigo-400" />
            ) : (
              <Circle size={13} className="mt-0.5 shrink-0 text-zinc-600" />
            )}
            <span
              className={cn(
                "leading-relaxed",
                t.status === "completed" ? "text-zinc-600 line-through" : "text-zinc-300",
              )}
            >
              {t.content}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ask_user soru formu ─────────────────────────────────────

function QuestionModal({
  state,
  onSubmit,
}: {
  state: QuestionState | null;
  onSubmit: (answer: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (state) {
      setSelected([]);
      setFreeText("");
      setBusy(false);
    }
  }, [state]);

  if (!state) return null;

  function toggle(opt: string) {
    if (state!.multi) {
      setSelected((prev) => (prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt]));
    } else {
      setSelected([opt]);
    }
  }

  function submit() {
    const parts = [...selected];
    if (freeText.trim()) parts.push(freeText.trim());
    const answer = parts.join(state!.multi ? ", " : " — ") || "(boş)";
    setBusy(true);
    onSubmit(answer);
  }

  const canSubmit = selected.length > 0 || freeText.trim().length > 0;

  return (
    <Modal open title="Agent sana bir soru soruyor">
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-2.5 text-sm text-zinc-200">
          <HelpCircle size={16} className="mt-0.5 shrink-0 text-indigo-400" />
          <span className="leading-relaxed">{state.question}</span>
        </div>

        {state.options.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {state.options.map((opt) => {
              const isSel = selected.includes(opt);
              const Icon = isSel ? (state.multi ? CheckCircle2 : CircleDot) : Circle;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => toggle(opt)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors",
                    isSel
                      ? "border-indigo-500/40 bg-indigo-500/10 text-zinc-100"
                      : "border-zinc-800 text-zinc-300 hover:border-zinc-700",
                  )}
                >
                  <Icon size={15} className={isSel ? "text-indigo-400" : "text-zinc-600"} />
                  <span>{opt}</span>
                </button>
              );
            })}
            {state.multi && (
              <p className="px-1 text-[11px] text-zinc-600">Birden fazla seçebilirsin.</p>
            )}
          </div>
        )}

        <Textarea
          label={state.options.length > 0 ? "Veya kendi yanıtını yaz" : "Yanıtın"}
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          rows={2}
          placeholder="Serbest metin…"
        />

        <div className="flex justify-end">
          <Button size="sm" onClick={submit} disabled={busy || !canSubmit}>
            Gönder
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ── HITL modal (düz metin) ──────────────────────────────────

function HitlModal({
  state,
  onApprove,
  onReject,
  onModify,
}: {
  state: HitlState | null;
  onApprove: () => void;
  onReject: (reason?: string) => void;
  onModify: (args: string) => void;
}) {
  const [mode, setMode] = useState<"view" | "modify">("view");
  const [argsText, setArgsText] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (state) {
      setMode("view");
      setArgsText(JSON.stringify(state.args, null, 2));
      setBusy(false);
    }
  }, [state]);

  if (!state) return null;
  const rows = formatArgs(state.args);

  function wrap(fn: () => void) {
    setBusy(true);
    fn();
  }

  return (
    <Modal open title="Onayın gerekiyor">
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-2.5 text-sm text-zinc-300">
          <ShieldCheck size={16} className="mt-0.5 shrink-0 text-amber-400" />
          <span>
            Agent şunu yapmak istiyor:{" "}
            <span className="font-medium text-zinc-100">{toolLabel(state.toolName)}</span>
          </span>
        </div>

        {mode === "view" ? (
          rows.length > 0 ? (
            <div className="flex flex-col gap-1.5 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-sm">
              {rows.map((r, i) => (
                <div key={i} className="flex gap-2">
                  <span className="shrink-0 text-zinc-500">{r.label}:</span>
                  <span className="break-words text-zinc-200">{r.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-500">Bu işlem ek parametre içermiyor.</p>
          )
        ) : (
          <Textarea
            label="Parametreleri düzenle (JSON)"
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            rows={6}
            className="font-mono text-xs"
          />
        )}

        <p className="text-xs text-zinc-600">
          Onaylarsan agent bu işlemi yapar; reddedersen durur; düzenlersen değiştirdiğin
          parametrelerle devam eder.
        </p>

        <div className="flex items-center justify-end gap-2">
          {mode === "view" ? (
            <>
              <Button variant="outline" size="sm" onClick={() => setMode("modify")} disabled={busy}>
                Düzenle
              </Button>
              <Button variant="danger" size="sm" onClick={() => wrap(() => onReject())} disabled={busy}>
                Reddet
              </Button>
              <Button size="sm" onClick={() => wrap(onApprove)} disabled={busy}>
                Onayla
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={() => setMode("view")} disabled={busy}>
                Geri
              </Button>
              <Button size="sm" onClick={() => wrap(() => onModify(argsText))} disabled={busy}>
                Değişiklikle onayla
              </Button>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
