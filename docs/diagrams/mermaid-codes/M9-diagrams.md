# M9 Diyagramları — Agent Engine

## 1. M9 Dosya Yapısı

```mermaid
graph LR
    ROOT["backend/app/"]

    ROOT --> SVC["services/"]
    ROOT --> API["api/v1/"]
    ROOT --> SCH["schemas/"]
    ROOT --> MDL["models/"]

    SVC --> AGT["agent/"]
    AGT --> BASE["base.py\nAgentConfig, AgentResult\nAgentStreamEvent, hata sınıfları"]
    AGT --> RUNNER["runner.py\nAgentRunner (ReAct döngüsü)\nrun() + stream()"]
    AGT --> REGISTRY["registry.py\nToolRegistry + ToolHandler\nToolContext"]
    AGT --> TOOLS["tools/"]
    TOOLS --> BUILTIN["builtin.py\necho, calculator, call_agent"]

    SVC --> PROV["providers/"]
    PROV --> PBAS["base.py\nBaseLLMProvider"]
    PROV --> OAI["openai_provider.py"]
    PROV --> ANT["anthropic_provider.py"]
    PROV --> OLL["ollama_provider.py"]
    PROV --> FAC["factory.py\nget_provider()"]

    SVC --> TRACE["trace_collector.py\nTracer — Redis XADD"]

    API --> AGENTS["agents.py\nPOST /agents\nGET /agents\nGET /agents/{id}\nPATCH /agents/{id}\nDELETE /agents/{id}\nGET /agents/tools\nPOST /agents/{id}/run"]

    SCH --> SAGT["agents.py\nCreateAgentRequest\nUpdateAgentRequest\nAgentResponse\nRunAgentRequest"]

    MDL --> MAGT["agent.py\nAgent SQLAlchemy model"]

    style BASE fill:#4ade80,stroke:#166534,color:#000
    style RUNNER fill:#4ade80,stroke:#166534,color:#000
    style REGISTRY fill:#4ade80,stroke:#166534,color:#000
    style BUILTIN fill:#4ade80,stroke:#166534,color:#000
    style AGENTS fill:#4ade80,stroke:#166534,color:#000
    style SAGT fill:#4ade80,stroke:#166534,color:#000
    style MAGT fill:#4ade80,stroke:#166534,color:#000
    style PROV fill:#60a5fa,stroke:#1e40af,color:#000
    style TRACE fill:#60a5fa,stroke:#1e40af,color:#000
```

---

## 2. ReAct Execution Loop (run — blocking path)

```mermaid
sequenceDiagram
    actor User
    participant API as agents.py
    participant Runner as AgentRunner
    participant LLM as BaseLLMProvider
    participant TR as ToolRegistry
    participant Tracer

    User->>API: POST /agents/{id}/run {input, stream:false}
    API->>Runner: AgentRunner(config, provider, tracer)
    API->>Runner: run(user_input)
    Runner->>Tracer: start() → agent_start event → Redis

    loop ReAct döngüsü (max_steps)
        Runner->>LLM: complete(messages, tools)
        LLM-->>Runner: CompletionResult {content, finish_reason, tool_calls}
        Runner->>Tracer: event("llm_call_end", {...})

        alt finish_reason == "stop"
            Runner->>Tracer: end(status="completed")
            Runner-->>API: AgentResult {content, steps_taken, trace_id}
        else finish_reason == "tool_calls"
            loop Her tool call için
                Runner->>TR: get(tool_name) → ToolHandler
                Runner->>Tracer: event("tool_call_start", {...})
                Runner->>TR: execute(tool_name, arguments)
                TR-->>Runner: result: str
                Runner->>Tracer: event("tool_call_end", {...})
                Runner->>Runner: messages.append(role="tool", content=result)
            end
            Note over Runner: Bir sonraki adıma geç
        end
    end

    Runner->>Tracer: end(status="max_steps_exceeded")
    Runner-->>API: AgentMaxStepsError
    API-->>User: 422 AGENT_MAX_STEPS_EXCEEDED
```

---

## 3. Stream Path (SSE)

```mermaid
sequenceDiagram
    actor User
    participant API as agents.py
    participant SSE as _sse_generator
    participant Runner as AgentRunner.stream()
    participant LLM as BaseLLMProvider.stream()

    User->>API: POST /agents/{id}/run {stream:true}
    API->>SSE: StreamingResponse(_sse_generator)
    SSE->>Runner: async for event in runner.stream(input)

    loop
        Runner->>LLM: stream(messages, tools)
        loop LLM token'ları
            LLM-->>Runner: StreamEvent(type="token", content="...")
            Runner-->>SSE: AgentStreamEvent(type="token")
            SSE-->>User: event: token\ndata: {...}
        end
        LLM-->>Runner: StreamEvent(type="done", finish_reason="tool_calls")
        Runner-->>SSE: AgentStreamEvent(type="step_done")

        loop Her tool call için
            Runner-->>SSE: AgentStreamEvent(type="tool_call_start")
            SSE-->>User: event: tool_call_start\ndata: {...}
            Runner->>Runner: tool çalıştır
            Runner-->>SSE: AgentStreamEvent(type="tool_call_end")
            SSE-->>User: event: tool_call_end\ndata: {...}
        end
    end

    Runner-->>SSE: AgentStreamEvent(type="done", trace_id, steps_taken)
    SSE-->>User: event: done\ndata: {...}
```

---

## 4. Tool Registry Mimarisi

```mermaid
graph TD
    subgraph Registry["ToolRegistry (Singleton)"]
        STORE["_registry: dict[str, ToolHandler]"]
        REG["@register(name, description, parameters)\ndecorator"]
        GET["get(name) → ToolHandler"]
        BUILD["build_definitions(names) → LLM tool format"]
        ALL["all_names() → list[str]"]
    end

    subgraph Handler["ToolHandler"]
        NAME["name: str"]
        DESC["description: str"]
        PARAMS["parameters: JSON Schema"]
        FN["fn: async (ctx, **kwargs) → str"]
        EXEC["execute(ctx, arguments) → str"]
    end

    subgraph Context["ToolContext (inject)"]
        ORG["org_id: UUID"]
        TID["trace_id: str"]
        DB["db: AsyncSession"]
        REDIS["redis: Redis"]
    end

    subgraph Builtin["Kayıtlı Tool'lar"]
        ECHO["echo\nmetinleri yankılar"]
        CALC["calculator\nmathematical ifade hesaplar"]
        CALL["call_agent\nbir agent'ı alt-agent olarak çağırır"]
    end

    REG --> STORE
    GET --> STORE
    BUILD --> STORE
    STORE --> Handler
    Handler --> Context
    Builtin --> STORE

    style ECHO fill:#fbbf24,stroke:#92400e,color:#000
    style CALC fill:#fbbf24,stroke:#92400e,color:#000
    style CALL fill:#fbbf24,stroke:#92400e,color:#000
```

---

## 5. Multi-Agent (call_agent) Akışı

```mermaid
sequenceDiagram
    participant ParentRunner as Parent AgentRunner
    participant Builtin as builtin.py._run_sub_agent
    participant DB as PostgreSQL
    participant SubRunner as Sub AgentRunner
    participant SubTracer as Sub Tracer

    ParentRunner->>Builtin: execute("call_agent", {agent_id, user_input})
    Builtin->>DB: SELECT agents WHERE id=? AND org_id=? AND is_active=true
    DB-->>Builtin: Agent row (or None → error string)
    Builtin->>SubTracer: Tracer(parent_trace_id=parent.trace_id)
    Note over SubTracer: parent_trace_id ile trace hiyerarşisi kurulur
    Builtin->>SubRunner: AgentRunner(config, provider, sub_tracer)
    Builtin->>SubRunner: run(user_input)
    SubRunner->>SubTracer: start() → agent_start
    SubRunner-->>SubRunner: ReAct döngüsü
    SubRunner->>SubTracer: end(status="completed")
    SubRunner-->>Builtin: AgentResult.content
    Builtin-->>ParentRunner: result: str
    Note over ParentRunner: Sub-agent sonucu tool result olarak eklenir
```

---

## 6. Agent Model + Migration

```mermaid
erDiagram
    AGENTS {
        UUID id PK
        UUID organization_id FK
        UUID created_by FK
        VARCHAR name
        TEXT description
        TEXT system_prompt
        VARCHAR provider
        VARCHAR model
        FLOAT temperature
        INT max_tokens
        INT max_steps
        INT timeout_seconds
        JSONB tool_names
        JSONB hitl_tool_names
        BOOLEAN is_active
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    ORGANIZATIONS ||--o{ AGENTS : "owns"
    USERS ||--o{ AGENTS : "created_by"
```

---

## 7. Katmanlı Mimari (M9 genişlemesi)

```mermaid
graph TB
    subgraph API["API Layer"]
        EP["POST /agents/{id}/run"]
        TOOLS_EP["GET /agents/tools"]
    end

    subgraph Service["Service Layer"]
        RUNNER["AgentRunner\nrun() blocking\nstream() SSE generator"]
        REGISTRY["ToolRegistry\ndecorator tabanlı\nplugin sistemi"]
        HITLSVC["HITLEngine (M10)\naskıya alma + onay"]
    end

    subgraph Provider["Provider Layer (M7)"]
        LLM["BaseLLMProvider\ncomplete() + stream()"]
    end

    subgraph Observability["Observability (M8)"]
        TRACER["Tracer\nRedis XADD"]
        CONSUMER["TraceConsumer\nClickHouse persist"]
        WS["WebSocket Manager\nUI'a canlı ilet"]
    end

    subgraph Storage["Storage"]
        PG["PostgreSQL\nagents tablosu"]
        CH["ClickHouse\ntraces + events"]
        RD["Redis\nStreams + HITL queue"]
    end

    EP --> RUNNER
    RUNNER --> LLM
    RUNNER --> REGISTRY
    RUNNER --> TRACER
    RUNNER --> HITLSVC
    TRACER --> RD
    CONSUMER --> RD
    CONSUMER --> CH
    CONSUMER --> WS
    EP --> PG
```

---

## 8. Hata Kodları

```mermaid
graph LR
    subgraph AgentErrors["Agent Hata Sınıfları"]
        AE["AgentError\n(temel)"]
        AMS["AgentMaxStepsError\nMAX_STEPS_EXCEEDED 422"]
        ATO["AgentTimeoutError\nAGENT_TIMEOUT 408"]
        ATE["AgentToolError\nAGENT_TOOL_ERROR 502"]
        HR["HITLRejectedError\nHITL_REJECTED 422\n(M10)"]
        HT["HITLTimeoutError\nHITL_TIMEOUT 408\n(M10)"]
    end

    AE --> AMS
    AE --> ATO
    AE --> ATE
    AE --> HR
    AE --> HT

    style AE fill:#f87171,stroke:#991b1b,color:#000
    style HR fill:#fbbf24,stroke:#92400e,color:#000
    style HT fill:#fbbf24,stroke:#92400e,color:#000
```

---

## 9. Anthropic Multi-Tool Bug Fix

```mermaid
graph LR
    subgraph Problem["Problem: Consecutive role=user mesajları"]
        A1["role: user\ntool_result: echo"] --> A2["role: user\ntool_result: calc"]
        A2 --> A3["Anthropic API → 400 ERROR\nalternating role ihlali"]
    end

    subgraph Fix["Fix: Birleştirme (_split_system_and_messages)"]
        B1["role: user\ncontent: list\n  tool_result: echo\n  tool_result: calc"]
        B1 --> B2["Anthropic API → 200 OK"]
    end

    style A3 fill:#f87171,stroke:#991b1b,color:#000
    style B2 fill:#4ade80,stroke:#166534,color:#000
```
