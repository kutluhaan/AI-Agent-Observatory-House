// ── Agent ───────────────────────────────────────────────────

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number | null;
  max_steps: number;
  timeout_seconds: number;
  tool_names: string[];
  hitl_tool_names: string[];
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

// ── Trace ───────────────────────────────────────────────────

export interface TraceSummary {
  trace_id: string;
  name: string;
  status: "running" | "done" | "error" | string;
  started_at: string | null;
  ended_at: string | null;
}

export interface TraceEvent {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string | null;
}

export interface TraceDetail extends TraceSummary {
  events: TraceEvent[];
}

// ── SSE ─────────────────────────────────────────────────────

export type SseEventType =
  | "token"
  | "tool_call_start"
  | "tool_call_end"
  | "hitl_requested"
  | "hitl_resolved"
  | "step_done"
  | "done"
  | "error";

export interface SseEvent {
  type: SseEventType;
  // token
  content?: string;
  // tool call
  tool_name?: string;
  tool_arguments?: Record<string, unknown>;
  tool_result?: string;
  // step
  step?: number;
  // done
  finish_reason?: string;
  trace_id?: string;
  steps_taken?: number;
  total_usage?: { prompt_tokens: number; completion_tokens: number; total_tokens?: number };
  // error
  error_code?: string;
  error_message?: string;
  // hitl
  hitl_request_id?: string;
  hitl_action?: string;
  hitl_modified_arguments?: Record<string, unknown>;
}

// ── Chat UI model ────────────────────────────────────────────

export interface ToolCallRecord {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "running" | "done";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCallRecord[];
  isStreaming: boolean;
  isError?: boolean;
  traceId?: string;
  usage?: { prompt_tokens: number; completion_tokens: number };
}

export interface HitlPending {
  requestId: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
}
