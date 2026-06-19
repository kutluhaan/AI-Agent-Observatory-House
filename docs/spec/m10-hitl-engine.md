# M10 — HITL Engine (Human-in-the-Loop)

**Milestone hedefi:** Agent kritik bir tool çağrısında durur, kullanıcı onaylar/reddeder/değiştirir, agent kaldığı yerden devam eder.

Bu doküman mevcut implementasyonu belgeler (kod tamam).

---

## Tasarım Kararları

| Karar | Seçim | Gerekçe |
|---|---|---|
| Bekleme mekanizması | Redis (metadata) + in-memory `asyncio.Event` | Endpoint runner'ı uyandırır; süreç içi, hızlı |
| API şekli | `create_request` + `wait_for_resolution` ayrı | Stream path'te SSE event'leri arasında yield için |
| Timeout | 10 dakika (`HITL_TIMEOUT=600`) | Spec; sonra `HITLTimeoutError` |
| Çözüm sonrası | Redis kaydı 2 dk daha yaşar | Audit / tekrar sorgu |
| Hangi tool'lar | Agent config'indeki `hitl_tool_names` | `tool_names`'in alt kümesi olmalı (422 değilse) |

---

## Akış

```
AgentRunner tool çağrısına gelir
   tool_name ∈ hitl_tool_names ?
        │ evet
        ▼
HITLEngine.create_request()  → Redis'e metadata (status=pending, TTL 10dk) + asyncio.Event
        │
   SSE: hitl_requested yield + WebSocket bildirimi
        │
HITLEngine.wait_for_resolution()  ← bloklar (Event.wait, 10dk timeout)
        │
İnsan: POST /hitl/{id}/approve | reject | modify
        ▼
HITLEngine.resolve()  → Redis status günceller, Event.set()
        │
   wait_for_resolution döner → HITLResolution
        ├─ approved  → tool çalışır
        ├─ modified  → modified_arguments ile tool çalışır
        └─ rejected  → HITLRejectedError (agent durur)
```

Hem sync (`run`/`_execute`) hem stream path'te HITL gate vardır; stream path ek olarak `hitl_requested`/`hitl_resolved` SSE event'leri yield eder.

---

## Bileşenler

```
app/services/hitl.py    — HITLEngine, HITLRequest, HITLResolution, singleton init/get
app/api/v1/hitl.py      — GET/approve/reject/modify endpoint'leri
app/models/agent.py     — hitl_tool_names kolonu (migration 0004)
```

Singleton: `init_hitl_engine(redis)` startup'ta (lifespan) bir kez; `get_hitl_engine()` endpoint'lerden.

---

## Endpoint'ler

| Method | Path | Min Rol | Açıklama |
|---|---|---|---|
| GET | `/hitl/{request_id}` | member | İstek durumu (pending/approved/rejected/modified) |
| POST | `/hitl/{request_id}/approve` | member | Tool çağrısını onayla |
| POST | `/hitl/{request_id}/reject` | member | Reddet (opsiyonel `reason`) → agent durur |
| POST | `/hitl/{request_id}/modify` | member | `modified_arguments` ile devam |

Tüm endpoint'ler org-scoped — istek başka org'a aitse erişilemez.

---

## Hata Kodları

| Code | HTTP | Açıklama |
|---|---|---|
| `HITL_NOT_FOUND` | 404 | request_id yok ya da expire oldu |
| `HITL_ALREADY_RESOLVED` | 409 | İstek zaten çözümlendi (çift approve) |
| `HITL_FORBIDDEN` | 403/404 | İstek farklı org'a ait |
| `HITL_REJECTED` | 422 | (agent tarafı) insan reddetti |
| `HITL_TIMEOUT` | 408 | 10 dk içinde yanıt gelmedi |

---

## Tamamlanma Kriterleri

- [x] Agent HITL noktasına gelince duruyor (`hitl_requested` event + WS bildirimi)
- [x] Onay sonrası agent kaldığı yerden devam ediyor
- [x] `modify` ile argümanlar değiştirilerek devam edilebiliyor
- [x] `reject` agent'ı gracefully durduruyor (`HITL_REJECTED`)
- [x] Timeout sonrası `HITL_TIMEOUT`
- [x] Unit + integration testler geçiyor (sync + SSE path)

---

## Sonraki Adım

M11 Test Core: agent davranışını YAML test suite'leri ile doğrulama.
