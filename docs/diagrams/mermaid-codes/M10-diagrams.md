# M10 Diyagramları — HITL Engine

## 1. M10 Dosya Yapısı

```mermaid
graph LR
    ROOT["backend/app/"]

    ROOT --> SVC["services/"]
    ROOT --> API["api/v1/"]
    ROOT --> MDL["models/"]
    ROOT --> SCH["schemas/"]
    ROOT --> ALM["alembic/versions/"]
    ROOT --> TST["tests/"]

    SVC --> HITL["hitl.py ★ YENİ\nHITLEngine\nHITLRequest + HITLResolution\ninit_hitl_engine() / get_hitl_engine()"]
    SVC --> AGT["agent/"]
    AGT --> BASE["base.py ★ GÜNCELLENDİ\nAgentConfig.hitl_tool_names\nHITLRejectedError + HITLTimeoutError\nAgentStreamEvent: hitl_* field'ları"]
    AGT --> RUNNER["runner.py ★ GÜNCELLENDİ\n_hitl_gate() — sync path\nstream() inline HITL gate\nHITL-aware timeout"]

    API --> HITL_EP["hitl.py ★ YENİ\nGET /{id}\nPOST /{id}/approve\nPOST /{id}/reject\nPOST /{id}/modify"]
    API --> AGENTS["agents.py ★ GÜNCELLENDİ\nhitl_tool_names ⊆ tool_names doğrulama\n_build_runner: HITLEngine inject\nHITL-aware timeout uzatma"]

    MDL --> MAGT["agent.py ★ GÜNCELLENDİ\nhitl_tool_names: JSONB"]
    SCH --> SAGT["agents.py ★ GÜNCELLENDİ\nhitl_tool_names field (Create/Update/Response)"]
    ALM --> MIG["0004_add_hitl_tool_names.py ★ YENİ"]

    TST --> UNIT["unit/test_hitl.py ★ YENİ\n11 unit test"]
    TST --> INT["integration/test_hitl_flow.py ★ YENİ\n12 integration test"]

    style HITL fill:#4ade80,stroke:#166534,color:#000
    style HITL_EP fill:#4ade80,stroke:#166534,color:#000
    style MIG fill:#4ade80,stroke:#166534,color:#000
    style BASE fill:#fbbf24,stroke:#92400e,color:#000
    style RUNNER fill:#fbbf24,stroke:#92400e,color:#000
    style AGENTS fill:#fbbf24,stroke:#92400e,color:#000
    style MAGT fill:#fbbf24,stroke:#92400e,color:#000
    style SAGT fill:#fbbf24,stroke:#92400e,color:#000
```

---

## 2. HITL Tam Akışı (Stream Path)

```mermaid
sequenceDiagram
    actor Human as İnsan (UI)
    participant API as agents.py /run
    participant Runner as AgentRunner.stream()
    participant HITLEng as HITLEngine
    participant Redis
    participant WS as WebSocket Manager
    participant LLM as LLM Provider

    Human->>API: POST /agents/{id}/run {stream:true, input:"..."}
    API->>Runner: stream(user_input)
    Runner->>LLM: stream(messages, tools)
    LLM-->>Runner: token... token... tool_call(echo, {text:"delete db"})

    Runner-->>Human: SSE: tool_call_start {name:"echo", args:{text:"delete db"}}

    Note over Runner: hitl_tool_names içinde "echo" var → HITL gate devreye girer

    Runner->>HITLEng: create_request(trace_id, org_id, tool_name, tool_arguments)
    HITLEng->>Redis: SETEX hitl:{request_id} 600s JSON
    HITLEng-->>Runner: request_id

    Runner-->>Human: SSE: hitl_requested {request_id, tool_name, tool_arguments}
    Runner->>WS: broadcast(org_id, {type:"hitl_requested", request_id, ...})

    Note over Runner: wait_for_resolution() — asyncio.Event bekler (max 10 dk)

    Human->>API: POST /hitl/{request_id}/approve
    API->>HITLEng: get(request_id) → org kontrol → resolve("approved")
    HITLEng->>Redis: SETEX hitl:{request_id} 120s {status:"approved"}
    HITLEng->>HITLEng: event.set() → Runner uyandırılır

    Runner->>Runner: resolution = HITLResolution(action="approved")
    Runner-->>Human: SSE: hitl_resolved {hitl_action:"approved"}

    Runner->>Runner: _execute_tool("echo", {text:"delete db"})
    Runner-->>Human: SSE: tool_call_end {result:"delete db"}

    Runner->>LLM: stream(messages + tool_result)
    LLM-->>Runner: "Tool executed."
    Runner-->>Human: SSE: done {trace_id, steps_taken}
```

---

## 3. HITL Durum Makinesi (State Machine)

```mermaid
stateDiagram-v2
    [*] --> pending : create_request()
    pending --> approved : /approve
    pending --> rejected : /reject
    pending --> modified : /modify
    pending --> expired : TTL=600s (Redis key silinir)

    approved --> [*] : Runner devam eder
    rejected --> [*] : HITLRejectedError → agent durur
    modified --> [*] : Runner modified_arguments ile devam eder
    expired --> [*] : HITLTimeoutError → agent durur

    note right of pending
        asyncio.Event bekliyor
        Redis'te TTL=600s
    end note

    note right of approved
        Redis TTL → 120s (audit)
        event.set() → runner uyanır
    end note
```

---

## 4. HITLEngine İç Mimarisi

```mermaid
graph TD
    subgraph HITLEngine["HITLEngine (singleton)"]
        REDIS["redis: Redis\nmetadata kalıcılığı"]
        PENDING["_pending: dict[str, (Event, list[Resolution])]\nin-memory, tek process"]

        CR["create_request(trace_id, org_id, tool_name, tool_arguments)\n→ request_id\nRedis'e SETEX\nEvent oluştur + _pending'e ekle"]

        WFR["wait_for_resolution(request_id)\nasyncio.wait_for(event.wait(), 600s)\n→ HITLResolution\nTimeoutError → HITLTimeoutError"]

        RES["resolve(request_id, action, ...)\nRedis status güncelle (SETEX 120s)\nResolution'ı list'e ekle\nevent.set() → waiter uyandır"]

        GET["get(request_id)\nRedis'ten oku\n→ HITLRequest | None"]
    end

    CR --> REDIS
    CR --> PENDING
    WFR --> PENDING
    RES --> REDIS
    RES --> PENDING
    GET --> REDIS

    style CR fill:#60a5fa,stroke:#1e40af,color:#000
    style WFR fill:#60a5fa,stroke:#1e40af,color:#000
    style RES fill:#60a5fa,stroke:#1e40af,color:#000
    style GET fill:#60a5fa,stroke:#1e40af,color:#000
```

---

## 5. HITL Org İzolasyonu (Security)

```mermaid
sequenceDiagram
    actor Attacker as Saldırgan (Org B)
    participant API as hitl.py endpoint
    participant HITLEng as HITLEngine
    participant Redis

    Note over HITLEng,Redis: Org A'nın HITL request'i: request_id=X, org_id=A

    Attacker->>API: POST /hitl/X/approve (Org B token'ı ile)
    API->>HITLEng: get(request_id=X)
    HITLEng->>Redis: GET hitl:X
    Redis-->>HITLEng: {org_id: "A", ...}
    HITLEng-->>API: HITLRequest {org_id="A"}
    API->>API: _assert_org("A", ctx.org_id="B") → MISMATCH!
    API-->>Attacker: 403 HITL_FORBIDDEN

    Note over API: resolve() ÇAĞRILMADI — runner hâlâ bekliyor
```

---

## 6. Sync Path HITL Gate (_hitl_gate)

```mermaid
sequenceDiagram
    participant Runner as AgentRunner._execute()
    participant Gate as _hitl_gate()
    participant HITLEng as HITLEngine
    participant Tracer

    Runner->>Runner: tool_call geldi: "echo"
    Runner->>Runner: hitl_tool_names içinde mi? → EVET
    Runner->>Gate: _hitl_gate("echo", arguments, step)

    Gate->>HITLEng: create_request(...)
    HITLEng-->>Gate: request_id

    Gate->>Tracer: event("hitl_requested", {...})
    Gate->>Gate: wait_for_resolution(request_id) ← bloklar

    Note over Gate: 10 dakikaya kadar bekler

    alt Human → approved
        Gate-->>Runner: arguments (değişmez)
        Runner->>Runner: _execute_tool("echo", arguments)
    else Human → modified
        Gate-->>Runner: resolution.modified_arguments
        Runner->>Runner: _execute_tool("echo", modified_arguments)
    else Human → rejected
        Gate->>Gate: raise HITLRejectedError("echo", reason)
        Gate-->>Runner: HITLRejectedError propagate
        Runner-->>Runner: exception handler → tracer.end("error")
    else Timeout
        Gate->>Gate: raise HITLTimeoutError(request_id)
    end
```

---

## 7. Timeout Katmanları

```mermaid
graph TB
    subgraph EndpointSync["Endpoint (Sync /run)"]
        EOT["asyncio.wait_for\ntimeout = agent.timeout_seconds\n         + HITL_TIMEOUT (600s)\n         + 5s margin"]
    end

    subgraph Runner["AgentRunner.run()"]
        ROT["asyncio.wait_for(_execute)\ntimeout = config.timeout_seconds\n         + HITL_TIMEOUT (600s)\n         [hitl_tool_names varsa]"]
    end

    subgraph Gate["_hitl_gate / wait_for_resolution"]
        HOT["asyncio.wait_for(event.wait)\ntimeout = HITL_TIMEOUT (600s)\n→ HITLTimeoutError"]
    end

    subgraph SSEGen["_sse_generator (Stream /run)"]
        SOT["timeout_at + 5s margin\nhitl_requested gelince\n+= HITL_TIMEOUT (600s)"]
    end

    EOT -->|en dışta| Runner
    Runner -->|içeride| Gate
    SOT -.->|stream path'te ayrı| Gate

    style EOT fill:#fbbf24,stroke:#92400e,color:#000
    style ROT fill:#60a5fa,stroke:#1e40af,color:#000
    style HOT fill:#4ade80,stroke:#166534,color:#000
    style SOT fill:#fbbf24,stroke:#92400e,color:#000
```

---

## 8. HITL API Endpoint'leri

```mermaid
graph LR
    subgraph HITLRouter["POST /hitl — Router"]
        GET_EP["GET /{id}\ndurum sorgula\n→ HITLRequestResponse"]
        APP_EP["POST /{id}/approve\norijinal args ile devam\n→ HITLRequestResponse"]
        REJ_EP["POST /{id}/reject\n{reason?}\nAgent durur\n→ HITLRequestResponse"]
        MOD_EP["POST /{id}/modify\n{arguments, reason?}\nModified args ile devam\n→ HITLRequestResponse"]
    end

    subgraph Flow["Her endpoint akışı"]
        A1["1. get(request_id) — 404 if not found"]
        A2["2. _assert_org() — 403 if different org"]
        A3["3. resolve(action) — 409 if already resolved"]
        A4["4. success(HITLRequestResponse)"]
    end

    APP_EP --> A1
    REJ_EP --> A1
    MOD_EP --> A1
    A1 --> A2 --> A3 --> A4

    style APP_EP fill:#4ade80,stroke:#166534,color:#000
    style REJ_EP fill:#f87171,stroke:#991b1b,color:#000
    style MOD_EP fill:#fbbf24,stroke:#92400e,color:#000
```

---

## 9. hitl_tool_names Validasyonu

```mermaid
graph LR
    subgraph Create["POST /agents (create)"]
        C1["body.hitl_tool_names: list[str]"]
        C2{"hitl_tool_names\n⊆ tool_names?"}
        C3["422 HITL_TOOL_NOT_IN_TOOL_NAMES"]
        C4["Agent kaydedildi"]
    end

    subgraph Update["PATCH /agents/{id} (update)"]
        U1["body.hitl_tool_names: list[str] | None"]
        U2{"hitl_tool_names\n⊆ effective_tool_names?\n(yeni veya mevcut)"}
        U3["422 HITL_TOOL_NOT_IN_TOOL_NAMES"]
        U4["Agent güncellendi"]
    end

    C1 --> C2
    C2 -->|HAYIR| C3
    C2 -->|EVET| C4

    U1 --> U2
    U2 -->|HAYIR| U3
    U2 -->|EVET| U4

    style C3 fill:#f87171,stroke:#991b1b,color:#000
    style U3 fill:#f87171,stroke:#991b1b,color:#000
    style C4 fill:#4ade80,stroke:#166534,color:#000
    style U4 fill:#4ade80,stroke:#166534,color:#000
```

---

## 10. SSE Event Tipleri (M10 ile genişledi)

```mermaid
graph TD
    subgraph Events["AgentStreamEvent.type"]
        TOK["token\nLLM metin parçası"]
        TCS["tool_call_start\ntool çalışmaya başladı"]
        TCE["tool_call_end\ntool sonuçlandı"]
        HR["hitl_requested ★ YENİ\naskıya alındı, insan bekleniyor\n+ hitl_request_id"]
        HRE["hitl_resolved ★ YENİ\ninsan kararı geldi\n+ hitl_action, hitl_modified_arguments"]
        SD["step_done\nbir LLM turu bitti"]
        DN["done\ntüm çalıştırma bitti"]
        ER["error\nkurtarılamaz hata"]
    end

    style HR fill:#4ade80,stroke:#166534,color:#000
    style HRE fill:#4ade80,stroke:#166534,color:#000
```
