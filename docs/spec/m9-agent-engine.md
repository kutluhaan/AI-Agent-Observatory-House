# M9 — Agent Engine

**Milestone hedefi:** Agent çalışır, her adım trace edilir, tool calling ve streaming desteklenir.

Bu doküman mevcut implementasyonu belgeler (kod tamam).

---

## M1–M8'den Gelen Taban

| Dosya | M9'da Kullanımı |
|---|---|
| `app/services/providers/*` | LLM çağrıları (provider-agnostik `Message`/`StreamEvent`) |
| `app/services/trace_collector.py` | Her adım `Tracer` ile Redis Stream'e yazılır |
| `app/api/deps.py` | `require_role`, `TenantContext` — agent'lar org-scoped |
| `app/services/providers/factory.py` | Agent'ın provider'ı org credential'ından çözülür |

---

## Bileşenler

```
app/services/agent/
├── base.py        — BaseAgent, AgentConfig, AgentResult, AgentStreamEvent, hata sınıfları
├── runner.py      — AgentRunner: ReAct execution loop (run + stream)
├── registry.py    — ToolRegistry, ToolContext, ToolDefinition
└── tools/
    ├── builtin.py  — echo, calculator, call_agent (multi-agent), ...
    └── research.py — M12 araştırma tool'ları
app/models/agent.py     — Agent tablosu (migration 0003, hitl_tool_names 0004)
app/schemas/agents.py
app/api/v1/agents.py    — CRUD + /run
```

### ReAct Execution Loop (`AgentRunner`)

1. `system_prompt` + `user_input` ile mesaj geçmişi kurulur.
2. `provider.complete()` (veya `stream()`) tool tanımlarıyla çağrılır.
3. `finish_reason == "stop"` → biter, `AgentResult` döner.
4. `finish_reason == "tool_calls"` → her tool `ToolRegistry` üzerinden çalıştırılır, sonuç `role=tool` mesajı olarak eklenir → 2'ye döner.
5. `max_steps` aşılırsa `AgentMaxStepsError`; `timeout_seconds` aşılırsa `AgentTimeoutError`.

Tüm adımlar `Tracer` ile event üretir: `agent_start → llm_call_start/end → tool_call_start/end → agent_end`. `tracer.end()` idempotent — `GeneratorExit` (SSE erken kapanış) dahil her yolda `agent_end` garantili.

### Streaming (SSE)

`stream()` token-token `AgentStreamEvent` yield eder; `to_sse()` ile `event: <type>\ndata: <json>\n\n` formatına çevrilir. Tipler: `token`, `tool_call_start/end`, `hitl_requested/resolved` (M10), `step_done`, `done`, `error`.

### Tool Registry

`@ToolRegistry.register(name, description, parameters)` ile tool kaydedilir. Built-in tool'lar startup'ta `register_builtin_tools()` ile yüklenir. Tool handler `(ctx: ToolContext, **arguments) -> str` imzasına sahiptir; hata fırlatmaz, hatayı string döner. `call_agent` tool'u multi-agent orkestrasyon sağlar (DB/Redis için `ToolContext` inject edilir).

---

## Endpoint'ler

| Method | Path | Min Rol | Açıklama |
|---|---|---|---|
| POST | `/agents` | admin | Agent oluştur (tool_names kayıtlı olmalı, yoksa 422) |
| GET | `/agents` | member | Org'un agent'ları |
| GET | `/agents/tools` | member | Kayıtlı tool listesi (name + description + schema) |
| GET | `/agents/{id}` | member | Agent detayı |
| PATCH | `/agents/{id}` | admin | Agent güncelle |
| DELETE | `/agents/{id}` | admin | Agent sil |
| POST | `/agents/{id}/run` | member | Çalıştır. `?stream=true` → SSE token akışı; aksi halde sync `AgentResult` |

---

## Hata Kodları

| Code | HTTP | Açıklama |
|---|---|---|
| `AGENT_NOT_FOUND` | 404 | Agent yok ya da başka org'a ait |
| `UNKNOWN_TOOL` / validation | 422 | tool_names içinde kayıtsız tool |
| `AGENT_MAX_STEPS_EXCEEDED` | 422 | max_steps aşıldı (sonsuz döngü koruması) |
| `AGENT_TIMEOUT` | 408 | timeout_seconds aşıldı |
| `AGENT_TOOL_ERROR` | 502 | tool handler kurtarılamaz hata |
| `PROVIDER_*` | — | M7 provider hataları aynen iletilir |

---

## Tamamlanma Kriterleri

- [x] Tool'lu bir agent çalışıyor (sync ve SSE)
- [x] Her adım trace UI'a (Redis Stream → ClickHouse) düşüyor
- [x] Agent sonsuz döngüye giremez (max_steps + timeout)
- [x] İki agent birbirini çağırabilir (`call_agent`) ve trace'de görünür
- [x] Unit + integration testler geçiyor

---

## Sonraki Adım

M10 HITL: kritik tool çağrılarında agent insan onayı için duraklatılır (`hitl_tool_names`).
