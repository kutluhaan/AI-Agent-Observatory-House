/**
 * Test-run WebSocket aboneliği (M15).
 *
 * Backend `WS /ws/test-runs` org-bazlı yayın yapar; handshake'te httpOnly
 * access_token cookie'si otomatik gönderilir (same-site). Sunucu org'un TÜM
 * run event'lerini yayınlar — çağıran taraf run_id'ye göre filtreler.
 */
import type { TestRunSummary } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TestRunEvent {
  type: "case_completed" | "case_failed" | "run_completed";
  run_id: string;
  case_id?: string;
  case_name?: string;
  status?: string;
  latency_ms?: number | null;
  assertions_passed?: number;
  assertions_total?: number;
  summary?: TestRunSummary;
}

/** Test-run event akışına abone olur. Aboneliği kapatan fonksiyon döner. */
export function subscribeTestRuns(
  onEvent: (event: TestRunEvent) => void,
): () => void {
  return _subscribe("/ws/test-runs", onEvent);
}

// C2 — ekip-run canlı akışı
export interface TeamRunEvent {
  type: "team_run_updated";
  run_id: string;
}

/** Ekip-run event akışına abone olur. Aboneliği kapatan fonksiyon döner. */
export function subscribeTeamRuns(
  onEvent: (event: TeamRunEvent) => void,
): () => void {
  return _subscribe("/ws/team-runs", onEvent);
}

function _subscribe<T>(path: string, onEvent: (event: T) => void): () => void {
  const wsUrl = BASE_URL.replace(/^http/, "ws") + path;
  let ws: WebSocket | null = null;
  try {
    ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        /* parse edilemeyen mesaj atlanır */
      }
    };
  } catch {
    /* WS kurulamadı — sayfa polling/refresh'e düşebilir */
  }
  return () => {
    try {
      ws?.close();
    } catch {
      /* ignore */
    }
  };
}
