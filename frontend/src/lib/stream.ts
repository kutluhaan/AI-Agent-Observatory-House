/**
 * Agent SSE stream client.
 *
 * Backend `text/event-stream` döner (`event: <type>\ndata: <json>\n\n`).
 * Native EventSource yalnızca GET yaptığı için fetch + ReadableStream ile elle
 * parse ediyoruz. Aynı bağlantı HITL beklemesi boyunca açık kalır.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface AgentStreamEvent {
  type:
    | "token"
    | "tool_call_start"
    | "tool_call_end"
    | "hitl_requested"
    | "hitl_resolved"
    | "ask_user_requested"
    | "ask_user_answered"
    | "step_done"
    | "done"
    | "error";
  content?: string;
  tool_name?: string;
  tool_arguments?: Record<string, unknown>;
  tool_result?: string;
  step?: number;
  finish_reason?: string;
  trace_id?: string;
  steps_taken?: number;
  total_usage?: Record<string, number>;
  error_code?: string;
  error_message?: string;
  hitl_request_id?: string;
  hitl_action?: string;
  hitl_modified_arguments?: Record<string, unknown>;
  // ask_user
  question?: string;
  question_options?: string[];
  question_multi?: boolean;
  answer?: string;
}

async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    let message = `Request failed (${res.status}).`;
    try {
      const b = await res.json();
      message = b?.error?.message ?? message;
    } catch {
      /* ignore */
    }
    onEvent({ type: "error", error_code: "RUN_FAILED", error_message: message });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      if (!frame.trim()) continue;
      let eventType = "";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) eventType = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!eventType) continue;
      try {
        const payload = data ? JSON.parse(data) : {};
        onEvent({ type: eventType as AgentStreamEvent["type"], ...payload });
      } catch {
        /* parse edilemeyen frame atlanır */
      }
    }
  }
}

/** Tek-atışlık agent çalıştırma (conversation'sız). */
export function runAgentStream(
  agentId: string,
  input: string,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE(`/agents/${agentId}/run`, { input, stream: true }, onEvent, signal);
}

/** Bir sohbet thread'ine mesaj gönderir; agent thread hafızasıyla çalışır. */
export function streamConversationMessage(
  conversationId: string,
  input: string,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE(
    `/conversations/${conversationId}/messages`,
    { input, stream: true },
    onEvent,
    signal,
  );
}
