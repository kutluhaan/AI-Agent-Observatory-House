/**
 * API client — backend ile konuşan tek nokta.
 *
 * - httpOnly cookie auth: tüm isteklerde `credentials: "include"`.
 * - Backend zarfı: { success, data, meta } | { success:false, error:{code,message} }.
 *   Başarıda `data` döner; hatada ApiError fırlatılır.
 * - 401'de bir kez /auth/refresh denenir, başarılıysa orijinal istek tekrarlanır
 *   (M13 kriteri: token expire olunca otomatik refresh).
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Tipler ──────────────────────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: "owner" | "admin" | "member";
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  is_verified: boolean;
  avatar_url: string | null;
  // Aktif org context'i (token'dan; org yoksa null)
  org_id: string | null;
  org_name: string | null;
  org_slug: string | null;
  role: "owner" | "admin" | "member" | null;
  organizations: Organization[];
}

// ── M14: Agent / Trace / HITL tipleri ───────────────────────

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
  prompt_version: number;
  tool_names: string[];
  hitl_tool_names: string[];
  file_system_enabled: boolean;
  is_active: boolean;
  endpoint_url: string | null;
  has_endpoint_api_key: boolean;
  mcp_tools: AgentMcpTool[] | null;
  custom_tool_ids: string[] | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

// loop it.6: prompt sürümü (agent config snapshot'ı)
export interface PromptVersion {
  version: number;
  system_prompt: string;
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number | null;
  tool_names: string[];
  hitl_tool_names: string[];
  note: string | null;
  created_at: string;
}

export interface PromptVersionList {
  active_version: number;
  versions: PromptVersion[];
}

// F7.2 — MCP
export interface McpServer {
  id: string;
  name: string;
  url: string;
  has_api_key: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// loop it.9: GitHub bağlantısı (org PAT — token şifreli, dönmez)
export interface GithubConnection {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

// loop it.8: Veritabanı bağlantısı (org DB — DSN şifreli, dönmez)
export interface DbConnection {
  id: string;
  name: string;
  db_type: string;
  is_active: boolean;
  created_at: string;
}

// D: Bildirim akışı girdisi (feed) — kanal config'iyle karıştırma
export interface AppNotification {
  id: string;
  kind: "sent" | "system";
  level: "info" | "success" | "error";
  title: string;
  body: string;
  source: string | null;
  is_read: boolean;
  created_at: string;
}

// loop it.4: Bildirim kanalı (org webhook — URL şifreli, dönmez)
export interface NotificationChannel {
  id: string;
  name: string;
  channel_type: string;
  is_active: boolean;
  created_at: string;
}

// D/#2: Resmi MCP Registry'den sadeleştirilmiş kayıt
export interface McpRegistryEntry {
  name: string;
  description: string;
  version: string | null;
  repository_url: string | null;
  remote_url: string | null;
  addable: boolean;
  requires_auth: boolean;
  icon_url: string | null;
  popularity: number;
}

export interface McpToolInfo {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface AgentMcpTool {
  server_id: string;
  tool_name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

// B1 — Kullanıcı tanımlı HTTP tool'ları
export interface CustomTool {
  id: string;
  name: string;
  description: string;
  method: string;
  url: string;
  parameters: Record<string, unknown>;
  timeout_seconds: number;
  header_names: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// G1 — Servis bağlantıları (OAuth, Gmail)
export interface ServiceConnection {
  provider: string;
  account_email: string | null;
  scopes: string[];
  connected_at: string;
  updated_at: string;
}

// F8 — Agent ekipleri
export interface RoleInfo {
  role: string;
  label: string;
  default_prompt: string;
}

export interface TeamMember {
  id: string;
  agent_id: string;
  agent_name: string | null;
  role: string;
  role_prompt: string;
  position: number;
}

export interface TeamMemberInput {
  agent_id: string;
  role: string;
  role_prompt?: string;
  position?: number;
}

export interface Team {
  id: string;
  name: string;
  description: string | null;
  members: TeamMember[];
  shared_instructions: string | null;
  max_delegations: number;
  run_timeout_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface TeamRun {
  id: string;
  team_id: string;
  status: string;
  input: string;
  final_output: string | null;
  error_message: string | null;
  conversation_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface TodoItem { content: string; status: "pending" | "in_progress" | "completed" }

export interface TeamRunMessage {
  id: string;
  kind: string; // delegate | result | board | final | tool
  from_role: string | null;
  to_role: string | null;
  title: string | null;
  content: string;
  payload?: { query?: string; url?: string; urls?: string[]; todos?: TodoItem[]; [k: string]: unknown } | null;
  created_at: string;
}

export interface TeamRunDetail {
  run: TeamRun;
  messages: TeamRunMessage[];
}

// B2: Ekip Knowledge Base öğesi
export interface TeamKnowledge {
  id: string;
  kind: "constitution" | "rule" | "instruction" | "prompt";
  name: string;
  content: string;
  is_active: boolean;
  created_at: string;
}

export interface TeamConversation {
  conversation_id: string;
  first_input: string;
  turns: number;
  last_status: string;
  created_at: string;
  updated_at: string;
}

export interface TeamStats {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  success_rate: number | null;
  avg_duration_ms: number | null;
  latest_status: string | null;
  trend: { run_id: string; created_at: string; status: string; duration_ms: number | null }[];
}

export interface AgentFile {
  path: string;
  is_dir: boolean;
  size_bytes: number;
  updated_at: string;
}

export type KnowledgeKind = "constitution" | "rule" | "instruction" | "prompt" | "skill";

export interface AgentKnowledge {
  id: string;
  kind: KnowledgeKind;
  name: string;
  content: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentTool {
  name: string;
  description: string;
  parameters?: Record<string, unknown>;
  category?: string | null;
}

export interface ToolCategory {
  key: string;
  label: string;
  note: string;
  managed_by_file_system: boolean;
  coming_soon: boolean;
  tools: { name: string; description: string }[];
}

export interface TraceSummary {
  trace_id: string;
  name: string;
  status: string;
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

export interface HitlRequest {
  request_id: string;
  trace_id: string;
  org_id: string;
  tool_name: string;
  tool_arguments: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "modified";
  created_at: string;
  expires_at: string;
  reason: string | null;
  modified_arguments: Record<string, unknown> | null;
}

// ── M15: Test Suite / Run tipleri ───────────────────────────

export interface TestSuite {
  id: string;
  name: string;
  description: string | null;
  config_yaml: string;
  kpis: string[] | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

// F5.2 — org dashboard
export interface OrgLeaderboardEntry {
  agent_id: string;
  name: string;
  pass_rate: number | null;
  avg_judge_score: number | null;
  avg_latency_ms: number | null;
  total_cases: number;
}

export interface TeamLeaderboardEntry {
  team_id: string;
  name: string;
  members: number;
  total_runs: number;
  success_rate: number | null;
  avg_duration_ms: number | null;
}

export interface OrgDashboard {
  counts: { agents: number; suites: number; total_runs: number; completed_runs: number; teams?: number };
  success_run_rate: number | null;
  avg_pass_rate: number | null;
  avg_latency_ms: number | null;
  avg_cost_usd: number | null;
  avg_judge_score: number | null;
  trend: SuiteTrendPoint[];
  agents_evaluated: number;
  leaderboard: OrgLeaderboardEntry[];
  teams_evaluated: number;
  team_leaderboard: TeamLeaderboardEntry[];
}

// F5.1 — agent performans paneli
export interface AgentTrendPoint {
  run_id: string;
  created_at: string;
  pass_rate: number | null;
  avg_latency_ms: number | null;
  cases: number;
}

export interface RagTrendPoint {
  run_id: string;
  created_at: string;
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_recall: number | null;
  context_precision: number | null;
}

export interface AgentRagStats {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_recall: number | null;
  context_precision: number | null;
  cases_with_rag: number;
  trend: RagTrendPoint[];
}

export interface AgentStats {
  total_cases: number;
  passed_cases: number;
  pass_rate: number | null;
  avg_latency_ms: number | null;
  avg_cost_usd: number | null;
  total_tokens: number | null;
  avg_judge_score: number | null;
  runs_count: number;
  trend: AgentTrendPoint[];
  rag: AgentRagStats | null;
}

export type KpiUnit = "percent" | "ms" | "usd" | "score" | "count";

export interface KpiCatalogItem {
  key: string;
  label: string;
  unit: KpiUnit;
  description: string;
}

export interface KpiCatalog {
  catalog: KpiCatalogItem[];
  defaults: string[];
}

export interface TestRunSummary {
  total: number;
  passed: number;
  failed: number;
  error: number;
  pass_rate: number;
  avg_latency_ms: number | null;
  total_tokens: number | null;
  total_cost_usd?: number | null;
  avg_judge_score?: number | null;
}

export interface TrajectoryStep {
  name: string;
  arguments: Record<string, unknown>;
  result: string;
  ok: boolean;
}

export interface JudgeResult {
  type: string;
  name?: string;
  score: number | null;
  passed: boolean | null;
  threshold: number;
  rationale?: string;
  error?: string;
}

export interface ConsistencyRun {
  passed: boolean;
  latency_ms?: number;
  total_tokens?: number | null;
  cost_usd?: number | null;
  errored?: boolean;
}

export interface ConsistencyInfo {
  runs: number;
  passed_runs: number;
  errored_runs?: number;
  pass_rate: number;
  min_pass_rate: number;
  runs_detail: ConsistencyRun[];
}

export interface SuiteTrendPoint {
  run_id: string;
  created_at: string;
  pass_rate: number | null;
  avg_latency_ms: number | null;
  total_cost_usd: number | null;
  total_tokens: number | null;
  avg_judge_score: number | null;
}

export interface SuiteStats {
  total_runs: number;
  completed_runs: number;
  success_run_rate: number | null;
  avg_pass_rate: number | null;
  latest_pass_rate: number | null;
  avg_latency_ms: number | null;
  avg_cost_usd: number | null;
  avg_judge_score: number | null;
  trend: SuiteTrendPoint[];
}

export interface TestRun {
  id: string;
  suite_id: string;
  status: string;
  parallel: boolean;
  started_at: string | null;
  ended_at: string | null;
  summary: TestRunSummary | null;
  experiment_id: string | null;
  variant_label: string | null;
  created_at: string;
}

// F4.3 — A/B prompt deneyi
export interface PromptVariant {
  label: string;
  system_prompt: string;
}

export interface ExperimentVariantResult {
  run_id: string;
  variant_label: string | null;
  status: string;
  summary: TestRunSummary | null;
  system_prompt_override: string | null;
}

export interface Experiment {
  experiment_id: string;
  suite_id: string;
  created_at: string;
  status: string; // running | completed
  variants: ExperimentVariantResult[];
}

export interface AssertionResult {
  type?: string;
  passed: boolean;
  detail?: string;
  [key: string]: unknown;
}

// F6 — senaryo adım sonucu
export interface StepResult {
  step: number;
  input: string;
  output: string | null;
  passed: boolean;
  latency_ms?: number | null;
  error?: string;
  assertions_results: AssertionResult[];
}

export interface TestCaseResult {
  id: string;
  case_id: string;
  status: string;
  output: string | null;
  trace_id: string | null;
  latency_ms: number | null;
  steps_taken: number | null;
  total_tokens: number | null;
  assertions_results: AssertionResult[];
  rag_metrics: Record<string, unknown> | null;
  trajectory: TrajectoryStep[] | null;
  judge_results: JudgeResult[] | null;
  consistency: ConsistencyInfo | null;
  steps_results: StepResult[] | null;
  cost_usd: number | null;
  error_message: string | null;
  created_at: string;
}

export interface TestRunDetail {
  run: TestRun;
  case_results: TestCaseResult[];
}

// ── Faz 1: Conversation (sohbet thread) tipleri ─────────────

export interface ConversationSummary {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  last_message_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  segments: unknown[] | null;
  trace_id: string | null;
  error: string | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  messages: ConversationMessage[];
}

// ── Hata ────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// ── Core ────────────────────────────────────────────────────

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(
  method: Method,
  path: string,
  body?: unknown,
  isRetry = false,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // 401 → bir kez refresh + retry (refresh çağrısının kendisi hariç)
  if (res.status === 401 && !isRetry && path !== "/auth/refresh") {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(method, path, body, true);
    }
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    // boş/JSON olmayan gövde
  }

  if (!res.ok) {
    const err = (payload as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "UNKNOWN_ERROR",
      err?.message ?? `Request failed with status ${res.status}.`,
      err?.details ?? {},
    );
  }

  return (payload as { data?: T } | null)?.data as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T = void>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T = void>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
};
