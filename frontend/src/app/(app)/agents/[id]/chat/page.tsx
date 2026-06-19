"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
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
} from "lucide-react";
import { api, ApiError, type Agent } from "@/lib/api";
import { runAgentStream, type AgentStreamEvent } from "@/lib/stream";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { cn } from "@/lib/utils";

// ── Mesaj modeli ────────────────────────────────────────────

interface ToolBlock {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "running" | "done";
}
type Segment =
  | { kind: "text"; text: string }
  | { kind: "tool"; tool: ToolBlock };
interface ChatMessage {
  role: "user" | "assistant";
  segments: Segment[];
  traceId?: string;
  error?: string;
  running?: boolean;
}

interface HitlState {
  requestId: string;
  toolName: string;
  args: Record<string, unknown>;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [loadError, setLoadError] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [hitl, setHitl] = useState<HitlState | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get<Agent>(`/agents/${id}`)
      .then(setAgent)
      .catch(() => setLoadError("Agent not found."));
  }, [id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, hitl]);

  // Son assistant mesajını fonksiyonel olarak güncelle
  const patchAssistant = useCallback(
    (fn: (m: ChatMessage) => ChatMessage) => {
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
    },
    [],
  );

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
                segs[i] = {
                  kind: "tool",
                  tool: { ...s.tool, result: ev.tool_result, status: "done" },
                };
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

        case "done":
          patchAssistant((m) => ({ ...m, running: false, traceId: ev.trace_id }));
          setRunning(false);
          break;

        case "error":
          patchAssistant((m) => ({
            ...m,
            running: false,
            error: ev.error_message ?? ev.error_code ?? "Agent error.",
          }));
          setRunning(false);
          setHitl(null);
          break;
      }
    },
    [patchAssistant],
  );

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || running) return;

    setInput("");
    setRunning(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", segments: [{ kind: "text", text }] },
      { role: "assistant", segments: [], running: true },
    ]);

    try {
      await runAgentStream(id, text, handleEvent);
    } catch (err) {
      patchAssistant((m) => ({
        ...m,
        running: false,
        error: err instanceof Error ? err.message : "Stream failed.",
      }));
      setRunning(false);
    }
  }

  // ── HITL eylemleri ────────────────────────────────────────
  async function resolveHitl(
    action: "approve" | "reject",
    reason?: string,
  ) {
    if (!hitl) return;
    try {
      await api.post(`/hitl/${hitl.requestId}/${action}`, reason ? { reason } : undefined);
      // Modal'ı kapatmıyoruz; stream'den gelen hitl_resolved kapatacak.
    } catch (err) {
      // Çözülmüş/expire — yine de kapat
      if (err instanceof ApiError) setHitl(null);
    }
  }

  async function modifyHitl(argsText: string) {
    if (!hitl) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(argsText);
    } catch {
      return; // geçersiz JSON — modal içinde uyarı gösterilir
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
    <div className="flex flex-1 flex-col">
      {/* Header */}
      <div className="border-b border-zinc-900 px-6 py-3">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/agents"
              className="text-zinc-600 transition-colors hover:text-zinc-300"
            >
              <ArrowLeft size={16} />
            </Link>
            <div>
              <p className="text-sm font-medium text-zinc-100">
                {agent?.name ?? "…"}
              </p>
              {agent && (
                <p className="text-[11px] text-zinc-600">
                  {agent.provider} · {agent.model}
                </p>
              )}
            </div>
          </div>
          {agent && agent.hitl_tool_names.length > 0 && (
            <Badge variant="amber">
              <ShieldCheck size={10} />
              HITL enabled
            </Badge>
          )}
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {messages.length === 0 && (
            <div className="py-20 text-center">
              <Bot size={28} className="mx-auto mb-3 text-zinc-700" />
              <p className="text-sm text-zinc-500">
                Send a message to run this agent.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-zinc-900 px-6 py-4">
        <form onSubmit={handleSend} className="mx-auto flex w-full max-w-3xl items-end gap-2">
          <div className="flex-1">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend(e);
                }
              }}
              placeholder="Message the agent…  (Enter to send, Shift+Enter for newline)"
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

      {/* HITL Modal */}
      <HitlModal
        state={hitl}
        onApprove={() => resolveHitl("approve")}
        onReject={(reason) => resolveHitl("reject", reason)}
        onModify={(args) => modifyHitl(args)}
      />
    </div>
  );
}

// ── Mesaj baloncuğu ─────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
          isUser ? "bg-zinc-800" : "bg-indigo-500/10",
        )}
      >
        {isUser ? (
          <UserIcon size={14} className="text-zinc-400" />
        ) : (
          <Bot size={14} className="text-indigo-400" />
        )}
      </div>

      <div className={cn("flex max-w-[85%] flex-col gap-2", isUser && "items-end")}>
        {msg.segments.map((seg, i) =>
          seg.kind === "text" ? (
            seg.text ? (
              <div
                key={i}
                className={cn(
                  "whitespace-pre-wrap rounded-xl px-3.5 py-2.5 text-sm leading-relaxed",
                  isUser
                    ? "bg-indigo-600 text-white"
                    : "bg-zinc-900/70 text-zinc-200",
                )}
              >
                {seg.text}
              </div>
            ) : null
          ) : (
            <ToolCard key={i} tool={seg.tool} />
          ),
        )}

        {msg.running && msg.segments.every((s) => s.kind !== "text" || !s.text) && (
          <div className="flex items-center gap-2 px-1 text-xs text-zinc-600">
            <Spinner className="h-3 w-3" />
            thinking…
          </div>
        )}

        {msg.error && <Alert variant="error">{msg.error}</Alert>}

        {msg.traceId && (
          <Link
            href={`/traces/${msg.traceId}`}
            className="flex items-center gap-1 px-1 text-[11px] text-zinc-600 transition-colors hover:text-indigo-400"
          >
            <Activity size={11} />
            View trace
          </Link>
        )}
      </div>
    </div>
  );
}

function ToolCard({ tool }: { tool: ToolBlock }) {
  return (
    <div className="w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2.5 text-xs">
      <div className="flex items-center gap-2">
        <Wrench size={12} className="text-amber-400" />
        <span className="font-medium text-zinc-300">{tool.name}</span>
        {tool.status === "running" ? (
          <Spinner className="h-3 w-3" />
        ) : (
          <Badge variant="green">done</Badge>
        )}
      </div>
      {Object.keys(tool.args).length > 0 && (
        <pre className="mt-1.5 overflow-x-auto rounded bg-zinc-950/60 p-2 text-[11px] text-zinc-500">
          {JSON.stringify(tool.args, null, 2)}
        </pre>
      )}
      {tool.result && (
        <p className="mt-1.5 line-clamp-4 whitespace-pre-wrap text-[11px] text-zinc-400">
          {tool.result}
        </p>
      )}
    </div>
  );
}

// ── HITL modal ──────────────────────────────────────────────

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

  function wrap(fn: () => void) {
    setBusy(true);
    fn();
  }

  return (
    <Modal open title="Approval required">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2 text-sm text-zinc-300">
          <ShieldCheck size={15} className="text-amber-400" />
          The agent wants to call{" "}
          <span className="font-medium text-zinc-100">{state.toolName}</span>
        </div>

        {mode === "view" ? (
          <pre className="max-h-48 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-xs text-zinc-400">
            {JSON.stringify(state.args, null, 2)}
          </pre>
        ) : (
          <Textarea
            label="Modified arguments (JSON)"
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            rows={6}
            className="font-mono text-xs"
          />
        )}

        <div className="flex items-center justify-end gap-2">
          {mode === "view" ? (
            <>
              <Button variant="outline" size="sm" onClick={() => setMode("modify")} disabled={busy}>
                Modify
              </Button>
              <Button variant="danger" size="sm" onClick={() => wrap(() => onReject())} disabled={busy}>
                Reject
              </Button>
              <Button size="sm" onClick={() => wrap(onApprove)} disabled={busy}>
                Approve
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={() => setMode("view")} disabled={busy}>
                Cancel
              </Button>
              <Button size="sm" onClick={() => wrap(() => onModify(argsText))} disabled={busy}>
                Approve with changes
              </Button>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
