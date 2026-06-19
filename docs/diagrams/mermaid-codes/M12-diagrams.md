# M12 Diyagramları — Personal Research Agent

## 1. M12 Dosya Yapısı

```mermaid
graph LR
    ROOT["backend/app/"]

    ROOT --> SVC["services/"]
    ROOT --> CORE["core/"]
    ROOT --> TST["tests/"]

    SVC --> TOOLS["agent/tools/"]
    TOOLS --> BUILTIN["builtin.py\necho, calculator, call_agent"]
    TOOLS --> RESEARCH["research.py ★ YENİ\nweb_search · read_url\nsummarize · save_note · get_notes\nRESEARCH_AGENT_SYSTEM_PROMPT"]

    CORE --> CFG["config.py ★ GÜNCELLENDİ\ntavily_api_key: str"]

    ROOT2["backend/"]
    ROOT2 --> PROJ["pyproject.toml ★ GÜNCELLENDİ\ntavily-python>=0.7.0\ntrafilatura>=2.0.0"]
    ROOT2 --> ENV[".env.example ★ GÜNCELLENDİ\nTAVILY_API_KEY="]

    ROOT3["backend/app/"]
    ROOT3 --> MAIN["main.py ★ GÜNCELLENDİ\nregister_research_tools()\nlifespan'e eklendi"]

    TST --> UNIT["tests/unit/\ntest_m12_research_tools.py ★ YENİ\n20 unit test"]

    style RESEARCH fill:#4ade80,stroke:#166534,color:#000
    style CFG fill:#fbbf24,stroke:#92400e,color:#000
    style MAIN fill:#fbbf24,stroke:#92400e,color:#000
    style PROJ fill:#fbbf24,stroke:#92400e,color:#000
    style ENV fill:#fbbf24,stroke:#92400e,color:#000
    style UNIT fill:#4ade80,stroke:#166534,color:#000
```

---

## 2. Research Agent Tam Akışı (ReAct + Paralel Tool Kullanımı)

```mermaid
sequenceDiagram
    actor User as Kullanıcı
    participant API as POST /agents/{id}/run
    participant Runner as AgentRunner (ReAct)
    participant LLM as LLM Provider
    participant WS as web_search (Tavily)
    participant RU as read_url (httpx+trafilatura)
    participant SUM as summarize (local)
    participant SN as save_note (Redis)
    participant GN as get_notes (Redis)

    User->>API: "Türkiye'deki AI startup ekosistemi araştır"
    API->>Runner: run(input)
    Runner->>LLM: messages + tool tanımları (5 tool)

    Note over LLM: Phase 1 — Discovery (parallel)
    LLM-->>Runner: tool_calls: [web_search("AI startups Turkey"),\n web_search("yapay zeka girişimleri 2025")]
    par Parallel tool execution
        Runner->>WS: web_search("AI startups Turkey")
        WS-->>Runner: 5 sonuç (title+URL+snippet)
    and
        Runner->>WS: web_search("yapay zeka girişimleri 2025")
        WS-->>Runner: 5 sonuç
    end

    Note over LLM: Phase 2 — Deep reading (parallel)
    LLM-->>Runner: tool_calls: [read_url(url1), read_url(url2), read_url(url3)]
    par
        Runner->>RU: read_url(url1, max_chars=4000)
        RU-->>Runner: temiz metin (trafilatura)
    and
        Runner->>RU: read_url(url2, max_chars=4000)
        RU-->>Runner: temiz metin
    and
        Runner->>RU: read_url(url3, max_chars=4000)
        RU-->>Runner: temiz metin
    end

    Note over LLM: Phase 3 — Summarize + Note taking
    LLM-->>Runner: tool_calls: [summarize(text1), summarize(text2)]
    par
        Runner->>SUM: extractive summarize
        SUM-->>Runner: 8 anahtar cümle
    and
        Runner->>SUM: extractive summarize
        SUM-->>Runner: 8 anahtar cümle
    end

    LLM-->>Runner: tool_calls: [save_note("Ekosistem Genel"), save_note("Öne Çıkan Girişimler")]
    par
        Runner->>SN: hset key title content
        SN-->>Runner: "Note saved: Ekosistem Genel"
    and
        Runner->>SN: hset key title content
        SN-->>Runner: "Note saved: Öne Çıkan Girişimler"
    end

    Note over LLM: Phase 4 — Synthesis
    LLM-->>Runner: tool_call: get_notes()
    Runner->>GN: hgetall key
    GN-->>Runner: tüm notlar

    LLM-->>Runner: finish_reason=stop\n"## Türkiye AI Startup Ekosistemi Raporu..."
    Runner-->>API: AgentResult(content=rapor)
    API-->>User: JSON response
```

---

## 3. Tool Mimarisi — Kayıt ve Çalışma Zamanı

```mermaid
graph TD
    LIFESPAN["app lifespan (startup)"]
    LIFESPAN -->|"register_builtin_tools()"| BREG["ToolRegistry:\necho\ncalculator\ncall_agent"]
    LIFESPAN -->|"register_research_tools()"| RREG["ToolRegistry:\nweb_search\nread_url\nsummarize\nsave_note\nget_notes"]

    BREG --> REG["ToolRegistry._tools: dict[str, ToolHandler]"]
    RREG --> REG

    REG -->|"build_definitions(agent.tool_names)"| DEFS["list[ToolDefinition]\n→ provider'a gönderilir"]
    DEFS --> LLM["LLM\n(tool schema + description'ı görür)"]
    LLM -->|"tool_call JSON"| RUNNER["AgentRunner._execute_tool()"]
    RUNNER -->|"ToolRegistry.get(name)"| HANDLER["ToolHandler.handler(ctx, **args)"]
    HANDLER -->|"ctx.redis, ctx.db, ctx.org_id, ctx.trace_id"| TOOLS["web_search | read_url | summarize\nsave_note | get_notes"]

    style BREG fill:#60a5fa,stroke:#1e40af,color:#000
    style RREG fill:#4ade80,stroke:#166534,color:#000
    style REG fill:#f3f4f6,stroke:#6b7280,color:#000
    style TOOLS fill:#4ade80,stroke:#166534,color:#000
```

---

## 4. web_search — Tavily İç Akışı

```mermaid
flowchart TD
    CALL["web_search(ctx, query, max_results, topic, time_range)"]

    CALL --> CHK_KEY{TAVILY_API_KEY\nvar mı?}
    CHK_KEY -->|"hayır"| ERR_KEY["[error: TAVILY_API_KEY not configured]"]
    CHK_KEY -->|"evet"| CHK_IMP{tavily-python\nyüklü mü?}

    CHK_IMP -->|"hayır"| ERR_IMP["[error: pip install tavily-python]"]
    CHK_IMP -->|"evet"| CLIP["max_results = max(1, min(10, max_results))"]

    CLIP --> KWARGS["kwargs = {\n  query, max_results, topic,\n  search_depth='basic',\n  time_range? (opsiyonel)\n}"]

    KWARGS --> API["AsyncTavilyClient.search(**kwargs)\nawait — async HTTP"]

    API -->|"başarısız"| ERR_NET["[error: <exception>]"]
    API -->|"başarılı"| PARSE["response['results'] listesini döngüye al"]

    PARSE -->|"boş"| NO_RES["No results found for: {query}"]
    PARSE -->|"dolu"| FORMAT["Her sonuç için:\n{i}. **title**\nURL: url\nsnippet[:300]"]

    FORMAT --> RETURN["Numaralı liste string olarak döner"]

    style ERR_KEY fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_IMP fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_NET fill:#fca5a5,stroke:#dc2626,color:#000
    style API fill:#4ade80,stroke:#166534,color:#000
    style RETURN fill:#4ade80,stroke:#166534,color:#000
```

---

## 5. read_url — httpx + trafilatura Pipeline

```mermaid
flowchart TD
    CALL["read_url(ctx, url, max_chars=4000)"]

    CALL --> VAL{url http/https\nile başlıyor mu?}
    VAL -->|"hayır"| ERR_URL["[error: invalid URL]"]
    VAL -->|"evet"| CHK_TF{trafilatura\nyüklü mü?}

    CHK_TF -->|"hayır"| ERR_TF["[error: pip install trafilatura]"]
    CHK_TF -->|"evet"| FETCH["httpx.AsyncClient.get(url)\ntimeout=15s, follow_redirects=True\nUser-Agent: ObservatoryResearchBot"]

    FETCH -->|"TimeoutException"| ERR_TO["[error: timed out]"]
    FETCH -->|"RequestError"| ERR_NET["[error: network error]"]
    FETCH -->|"status >= 400"| ERR_HTTP["[error: HTTP {status}]"]
    FETCH -->|"200 OK"| CTYPE{content-type\nhtml veya text?}

    CTYPE -->|"pdf, binary..."| ERR_TYPE["[error: unsupported content type]"]
    CTYPE -->|"text/html"| EXTRACT["trafilatura.extract(\n  html[:2MB],\n  favor_precision=True,\n  include_comments=False,\n  include_tables=False,\n  include_links=False\n)"]

    EXTRACT -->|"text var (>50 chars)"| TRUNC{"len(text)\n> max_chars?"}
    EXTRACT -->|"text yok / çok kısa"| FALLBACK["regex ile HTML tag'lerini sil\nwspc normalize et"]

    FALLBACK -->|"hâlâ boş"| ERR_EXT["[error: could not extract text]"]
    FALLBACK -->|"dolu"| TRUNC

    TRUNC -->|"hayır"| RET["Content from {url}:\n\n{text}"]
    TRUNC -->|"evet"| CUT["text[:max_chars]\ncümle sınırında kes (rfind '. ')\n'[...truncated]' ekle"]
    CUT --> RET

    style ERR_URL fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_TF fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_TO fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_NET fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_HTTP fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_TYPE fill:#fca5a5,stroke:#dc2626,color:#000
    style ERR_EXT fill:#fca5a5,stroke:#dc2626,color:#000
    style EXTRACT fill:#4ade80,stroke:#166534,color:#000
    style RET fill:#4ade80,stroke:#166534,color:#000
```

---

## 6. summarize — TF-Tabanlı Extractive Algoritma

```mermaid
flowchart TD
    CALL["summarize(ctx, text, focus='', max_sentences=8)"]

    CALL --> SPLIT["Metni cümlelere böl\nre.split(r'(?<=[.!?])\\s+', text)\nlen > 20 char olanları al"]

    SPLIT --> CHK_LEN{"len(sentences)\n<= max_sentences?"}
    CHK_LEN -->|"evet — kısa metin"| PASSTHRU["Metni olduğu gibi döndür"]
    CHK_LEN -->|"hayır — uzun metin"| FREQ["Kelime frekans tablosu oluştur\nCounter — stopwords hariç\n3+ harf, Türkçe+İngilizce"]

    FREQ --> NORM["Frekansları normalleştir\nnorm = freq / max_freq"]

    NORM --> FOCUS["focus terimleri çıkar\nfocus.lower() → kelime seti"]

    FOCUS --> SCORE["Her cümleyi puanla:\nscore = Σ(norm_freq[w]) / len(words)\nfocus terimi varsa × 1.5"]

    SCORE --> RANK["Cümleleri puana göre sırala (azalan)\nilk max_sentences tanesini al"]

    RANK --> SORT["Seçilen indisleri orijinal sıraya göre sırala\n(okuma akışını koru)"]

    SORT --> JOIN["Seçilen cümleleri birleştir → döndür"]

    style PASSTHRU fill:#60a5fa,stroke:#1e40af,color:#000
    style SCORE fill:#4ade80,stroke:#166534,color:#000
    style JOIN fill:#4ade80,stroke:#166534,color:#000
```

---

## 7. save_note / get_notes — Redis Veri Modeli

```mermaid
graph TD
    SN["save_note(ctx, title, content)"]
    GN["get_notes(ctx)"]

    SN -->|"title / content boş?"| ERR["[error: ...]"]
    SN -->|"geçerli"| KEY["key = research_notes:{org_id}:{trace_id}"]
    KEY --> HSET["Redis HSET key title content"]
    HSET --> EXPIRE["Redis EXPIRE key 86400s (24 sa)"]
    EXPIRE --> OK["'Note saved: {title}'"]

    GN --> KEY2["key = research_notes:{org_id}:{trace_id}"]
    KEY2 --> HGETALL["Redis HGETALL key"]
    HGETALL -->|"boş"| EMPTY["'No notes saved yet.'"]
    HGETALL -->|"dolu"| FORMAT["Her (title, content) için:\n'### {title}\\n{content}'\n--- ile ayır"]
    FORMAT --> RETURN["Birleşik not metni"]

    subgraph "Redis HASH Yapısı"
        direction LR
        K["research_notes:{org_id}:{trace_id}"]
        K --> F1["field: 'Ekosistem Genel'\nvalue: '...'"]
        K --> F2["field: 'Öne Çıkan Girişimler'\nvalue: '...'"]
        K --> F3["field: 'Yatırım Verileri'\nvalue: '...'"]
    end

    style ERR fill:#fca5a5,stroke:#dc2626,color:#000
    style HSET fill:#4ade80,stroke:#166534,color:#000
    style RETURN fill:#4ade80,stroke:#166534,color:#000
    style K fill:#f59e0b,stroke:#b45309,color:#000
```

---

## 8. Research Agent — 4 Fazlı Çalışma Modeli

```mermaid
stateDiagram-v2
    [*] --> Discovery : Kullanıcı prompt'u alındı

    state Discovery {
        direction LR
        s1: web_search (query A)
        s2: web_search (query B)
        s3: web_search (query C)
        s1 --> Results
        s2 --> Results
        s3 --> Results
        note left of s1 : Paralel çalışır
    }

    Discovery --> DeepReading : En ilgili URL'ler seçildi

    state DeepReading {
        direction LR
        r1: read_url(url1)
        r2: read_url(url2)
        r3: read_url(url3)
        r1 --> Texts
        r2 --> Texts
        r3 --> Texts
        note left of r1 : Paralel, 15s timeout
    }

    DeepReading --> NoteTaking : Ham metinler alındı

    state NoteTaking {
        direction LR
        n1: summarize(text1)
        n2: summarize(text2)
        n1 --> KeyFacts
        n2 --> KeyFacts
        KeyFacts --> save_note_A
        KeyFacts --> save_note_B
        note left of n1 : summarize = local (sıfır LLM)
    }

    NoteTaking --> Synthesis : Notlar Redis'te hazır

    state Synthesis {
        g: get_notes()
        g --> compile
        compile: Raporu yaz\n(Executive Summary\nKey Findings\nSources\nGaps)
    }

    Synthesis --> [*] : AgentResult(content=rapor)
```

---

## 9. Hız Optimizasyonu — Neden Bu Tasarım?

```mermaid
graph LR
    subgraph "Yavaş Alternatif"
        direction TB
        S1["web_search #1"] --> S2["web_search #2"]
        S2 --> S3["read_url #1"]
        S3 --> S4["read_url #2"]
        S4 --> S5["LLM summarize #1\n(+ API çağrısı)"]
        S5 --> S6["LLM summarize #2\n(+ API çağrısı)"]
        S6 --> S7["save_note"]
    end

    subgraph "M12 Tasarımı"
        direction TB
        P1["web_search #1\nweb_search #2"] --> P2["read_url #1\nread_url #2\nread_url #3"]
        P2 --> P3["summarize #1\nsummarize #2\n(local — 0ms API)"]
        P3 --> P4["save_note #1\nsave_note #2\n(Redis — ~1ms)"]
    end

    subgraph "Kazanım"
        direction TB
        C1["Paralel tool call:\n↓ latency (sıralı yerine eşzamanlı)"]
        C2["Local summarize:\n0 ekstra LLM token + latency"]
        C3["Redis notes:\nget_notes = tek HGETALL"]
    end

    style P1 fill:#4ade80,stroke:#166534,color:#000
    style P2 fill:#4ade80,stroke:#166534,color:#000
    style P3 fill:#4ade80,stroke:#166534,color:#000
    style P4 fill:#4ade80,stroke:#166534,color:#000
    style S1 fill:#fca5a5,stroke:#dc2626,color:#000
    style S2 fill:#fca5a5,stroke:#dc2626,color:#000
    style S3 fill:#fca5a5,stroke:#dc2626,color:#000
    style S4 fill:#fca5a5,stroke:#dc2626,color:#000
    style S5 fill:#fca5a5,stroke:#dc2626,color:#000
    style S6 fill:#fca5a5,stroke:#dc2626,color:#000
```

---

## 10. Kurulum ve Kullanım

```mermaid
flowchart LR
    ENV["1. .env'e ekle\nTAVILY_API_KEY=tvly-..."]
    DEP["2. Bağımlılıklar\npip install tavily-python trafilatura"]
    START["3. Uygulama başlat\nregister_research_tools() otomatik çalışır"]
    CREATE["4. Agent oluştur\nPOST /agents\ntool_names: [web_search, read_url,\nsummarize, save_note, get_notes]\nsystem_prompt: RESEARCH_AGENT_SYSTEM_PROMPT"]
    RUN["5. Çalıştır\nPOST /agents/{id}/run\n{input: 'Türkiye AI ekosistemi'}"]
    RESULT["6. Yapılandırılmış rapor\nExecutive Summary\nKey Findings\nSources"]

    ENV --> DEP --> START --> CREATE --> RUN --> RESULT

    style ENV fill:#f3f4f6,stroke:#6b7280,color:#000
    style DEP fill:#f3f4f6,stroke:#6b7280,color:#000
    style START fill:#60a5fa,stroke:#1e40af,color:#000
    style CREATE fill:#fbbf24,stroke:#92400e,color:#000
    style RUN fill:#4ade80,stroke:#166534,color:#000
    style RESULT fill:#4ade80,stroke:#166534,color:#000
```
