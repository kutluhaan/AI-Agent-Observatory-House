# M8 — Trace Collector

**Milestone hedefi:** Her agent/LLM eventi otomatik yakalanır → Redis Stream'e yazılır → ClickHouse'a kalıcı kaydedilir → WebSocket ile canlı UI'a iletilir.

Bu spec **taslaktır** — implementasyondan önce onaylanmalı.

---

## Verilen Kararlar (onaylandı)

| Karar | Seçim | Etkisi |
|---|---|---|
| Canlı izleme (WebSocket) | **Şimdi eklenir** | Olaylar hem ClickHouse'a yazılır hem WebSocket'le canlı iletilir |
| Doğrulama yöntemi | **M7 provider çağrılarına bağlanır** | `complete()`/`stream()` çevresine trace hook'ları; ince bir test-completion endpoint'i ile tetiklenir |
| Veri saklama | **TTL ile otomatik silme** | ClickHouse `events` tablosunda 30 günlük TTL (yapılandırılabilir) |
| Test stratejisi | **Gerçek ClickHouse'a karşı** (M5/M7 ile tutarlı) | Integration testleri docker ClickHouse container'ına yazar; provider mock'lanır |

---

## M1–M7'den Gelen Taban

| Dosya | M8'de Kullanımı |
|---|---|
| `app/core/redis.py` | Redis Stream (`XADD`/`XREAD`) için mevcut singleton pool |
| `app/core/config.py` | `clickhouse_host`, `clickhouse_port`, `clickhouse_db`, `clickhouse_user`, `clickhouse_password` |
| `app/api/deps.py` | `require_role`, `TenantContext` — trace'ler org-scoped |
| `app/core/responses.py` | `AppError`, `success()` |
| `app/services/providers/*` | İlk gerçek event kaynağı — `complete()`/`stream()` trace üretecek |

> **Not (ClickHouse port):** `clickhouse-connect` HTTP arabirimini (8123) kullanır. `config.py`'de `clickhouse_port=9000` (native) ayarlı. İmplementasyonda HTTP portu (8123) kullanılacak; gerekirse ayrı bir `clickhouse_http_port` eklenecek. Bu, ilk netleştirilecek teknik nokta.

---

## Tasarım Kararları

### 1. Üç Aşamalı Pipeline

```
Provider/Agent çağrısı
      │  TraceCollector.emit(event)
      ▼
Redis Stream  (key: trace:{org_id})        ← yazma noktası (hızlı, bloklamaz)
      │
      ├──► Stream Consumer (XREAD, batch)  ──► ClickHouse (kalıcı)
      └──► WebSocket Manager               ──► UI (canlı)
```

Yazan taraf (provider) sadece Redis'e `XADD` yapar — ClickHouse yazımı ve WebSocket iletimi **arka planda**, ayrı tüketici tarafından yapılır. Böylece LLM çağrısı trace yüzünden yavaşlamaz.

### 2. Stream Consumer Nerede Çalışır?

FastAPI `lifespan` içinde başlatılan bir **arka plan asyncio task**'ı. `XREAD BLOCK` ile sürekli okur, batch halinde ClickHouse'a yazar ve aktif WebSocket'lere iletir. Uygulama kapanınca temiz durur. (Ölçeklenince ayrı worker container'a taşınabilir — şimdilik gerek yok.)

### 3. ClickHouse Async Değil

`clickhouse-connect` senkron. M4'teki Resend deseninin aynısı: çağrılar `asyncio.to_thread` ile sarmalanır, event loop bloklanmaz.

### 4. Trace vs Event

- **trace** = bir çalıştırmanın tamamı (bir `trace_id`, bir org, başlangıç/bitiş, durum).
- **event** = o çalıştırma içindeki tek adım (LLM çağrısı, tool çağrısı, hata...).
- Bir trace'in birden çok event'i olur. İkisi de ClickHouse'da, `organization_id` ile izole.

### 5. Org İzolasyonu

Her event/trace `organization_id` taşır (auth-spec'teki "shared store + organization_id" deseni). Sorgu endpoint'leri ve WebSocket sadece kullanıcının aktif org'unun trace'lerini döndürür — yanlış org'un verisi sızmaz.

### 6. WebSocket Kimlik Doğrulama

WebSocket handshake'inde mevcut `access_token` cookie'si doğrulanır (HTTP endpoint'lerle aynı mantık). Bağlantı, kullanıcının aktif org'una abone olur; sadece o org'un event'leri iletilir.

### 7. Saklama (TTL)

ClickHouse `events` tablosunda `TTL created_at + INTERVAL 30 DAY`. Süre `.env`'den ayarlanabilir (`TRACE_RETENTION_DAYS`, varsayılan 30).

---

## Event Tipleri

```
agent_start / agent_end
llm_call_start / llm_call_end      ← M8'de M7 provider'larından üretilir
tool_call_start / tool_call_end
reasoning
hitl_requested
error
```

Normalize event yapısı (Redis Stream'e ve ClickHouse'a giden):

```json
{
  "trace_id": "uuid",
  "organization_id": "uuid",
  "type": "llm_call_end",
  "timestamp": "2026-06-17T18:00:00Z",
  "payload": { "model": "...", "tokens": 123, "latency_ms": 456, ... }
}
```

---

## ClickHouse Şeması (taslak)

```sql
CREATE TABLE traces (
    trace_id        UUID,
    organization_id UUID,
    name            String,
    status          String,           -- running | completed | error
    started_at      DateTime64(3),
    ended_at        Nullable(DateTime64(3)),
    created_at      DateTime64(3) DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (organization_id, started_at, trace_id);

CREATE TABLE events (
    event_id        UUID DEFAULT generateUUIDv4(),
    trace_id        UUID,
    organization_id UUID,
    type            String,
    payload         String,           -- JSON
    created_at      DateTime64(3) DEFAULT now64()
) ENGINE = MergeTree()
ORDER BY (organization_id, trace_id, created_at)
TTL toDateTime(created_at) + INTERVAL 30 DAY;
```

> ClickHouse şeması Alembic'le yönetilmez (o Postgres içindir). Ayrı bir başlatma adımı: `app/core/clickhouse.py` içinde `init_schema()` — lifespan startup'ta `CREATE TABLE IF NOT EXISTS` çalıştırır.

---

## Endpoint'ler

| Method | Path | Min Rol | Açıklama |
|---|---|---|---|
| POST | `/providers/{provider}/test-completion` | member | Gerçek bir completion çalıştırır, trace üretir (M8 doğrulama seam'i, M9 agent bunu kullanır) |
| GET | `/traces` | member | Org'un trace listesi (filtreli: status, tarih, limit) |
| GET | `/traces/{trace_id}` | member | Tek trace + event'leri (timeline) |
| WS | `/ws/traces` | member | Aktif org'un canlı event akışı |

---

## Yeni / Değişen Dosyalar

```
backend/app/
├── core/
│   └── clickhouse.py          ← YENİ: client + init_schema (to_thread sarmalı)
├── services/
│   ├── trace_collector.py     ← YENİ: emit() → Redis XADD
│   └── trace_consumer.py      ← YENİ: XREAD → ClickHouse + WebSocket
├── api/v1/
│   ├── traces.py              ← YENİ: GET /traces, GET /traces/{id}
│   └── providers.py           ← GÜNCELLEME: test-completion endpoint + trace hook
├── ws/
│   └── traces.py              ← YENİ: WebSocket manager + /ws/traces
├── schemas/
│   └── traces.py              ← YENİ
└── main.py                    ← GÜNCELLEME: lifespan'de consumer başlat, router + ws ekle

backend/tests/
├── unit/
│   └── test_trace_collector.py    ← event formatı, Redis XADD (fakeredis)
└── integration/
    └── test_trace_flow.py         ← test-completion (provider mock) → trace ClickHouse'a düştü mü → GET /traces
```

`config.py`'ye eklenecek: `clickhouse_http_port` (varsayılan 8123), `trace_retention_days` (varsayılan 30).

---

## Hata Kodları (Yeni)

| Code | HTTP | Açıklama |
|---|---|---|
| `TRACE_NOT_FOUND` | 404 | Trace yok ya da başka org'a ait |
| `TRACE_STORE_UNAVAILABLE` | 503 | ClickHouse erişilemiyor |

---

## Tamamlanma Kriterleri

- [ ] ClickHouse şeması startup'ta otomatik oluşuyor (`traces`, `events`)
- [ ] `TraceCollector.emit()` event'i Redis Stream'e yazıyor
- [ ] Consumer Redis'ten okuyup ClickHouse'a persist ediyor
- [ ] `POST /providers/{provider}/test-completion` (mock provider) → `llm_call_start`/`llm_call_end` trace'e düşüyor
- [ ] `GET /traces` ve `GET /traces/{id}` org-scoped sonuç dönüyor (yanlış org → 404)
- [ ] WebSocket bağlantısı aktif org'un event'lerini canlı iletiyor
- [ ] TTL tanımlı (30 gün)
- [ ] Tüm testler geçiyor (unit + integration, gerçek ClickHouse)

---

## Sonraki Adım (M9)

M9'daki Agent Engine, her adımında `TraceCollector.emit()` çağıracak ve `test-completion` seam'ini gerçek agent execution loop'una genişletecek.
