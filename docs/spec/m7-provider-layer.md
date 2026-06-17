# M7 — Provider Layer

**Milestone hedefi:** OpenAI, Anthropic, Ollama tek interface üzerinden çağrılabilir.
Token streaming ve tool calling her üç provider için çalışır.

---

## M1–M6'dan Gelen Taban

| Dosya | M7'de Kullanımı |
|---|---|
| `app/core/database.py` | Yeni `provider_credentials` tablosu için Base |
| `app/api/deps.py` | `require_role`, `TenantContext` — provider key yönetimi org-scoped |
| `app/core/responses.py` | `AppError`, `success()` — provider hataları |
| `app/core/config.py` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL` (.env'den, fallback) |

---

## Tasarım Kararları

### 1. API Key Yönetimi — İki Katmanlı

Sprint planı "org bazlı API key yönetimi (DB'den şifreli okuma)" diyor. İki kaynak var:

1. **Platform-level fallback** — `.env`'deki key'ler (geliştirme/demo için)
2. **Org-level override** — org kendi key'ini girerse DB'den şifreli okunur, öncelik bu

Org'un kendi key'i yoksa platform key'ine düşülür. Hiçbiri yoksa `PROVIDER_NOT_CONFIGURED` hatası.

### 2. Yeni Tablo: `provider_credentials`

auth-spec'te bu tablo tanımlı değildi çünkü o spec sadece auth sistemini kapsıyordu. M7 kapsamında yeni bir tablo ekliyoruz:

```sql
CREATE TABLE provider_credentials (
    id              UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider        VARCHAR(50) NOT NULL,  -- openai | anthropic | ollama
    encrypted_key   TEXT,                   -- AES-256 şifreli, ollama için NULL olabilir
    base_url        VARCHAR(500),           -- ollama için zorunlu, diğerleri NULL
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(organization_id, provider)
);
```

Şifreleme: `cryptography.fernet` ile AES-256. Key `APP_SECRET_KEY`'den türetilir — auth-spec'teki OAuth token şifreleme kararıyla tutarlı (Faz 4'te `oauth_accounts.access_token` için de aynı yöntem planlanmıştı).

### 3. Tek Interface — `BaseLLMProvider`

Tüm provider'lar şu metotları implement eder:
- `complete()` — non-streaming tek cevap
- `stream()` — async generator, SSE için
- `supports_tools` property

### 4. Streaming Format

SSE event formatı tüm provider'larda aynı normalize edilmiş şekle çevrilir:
```json
{"type": "token", "content": "..."}
{"type": "tool_call", "name": "...", "arguments": {...}}
{"type": "done", "finish_reason": "stop"}
{"type": "error", "message": "..."}
```

Bu normalizasyon önemli — M9'daki Agent Engine hangi provider kullanıldığını bilmeden aynı kodu çalıştırabilecek.

---

## M7'de Eklenen Dosyalar

```
backend/
└── app/
    ├── models/
    │   └── provider.py                    ← YENİ: ProviderCredential modeli
    ├── core/
    │   └── encryption.py                  ← YENİ: Fernet şifreleme yardımcıları
    ├── services/
    │   └── providers/
    │       ├── __init__.py
    │       ├── base.py                    ← YENİ: BaseLLMProvider, normalize tipler
    │       ├── openai_provider.py         ← YENİ
    │       ├── anthropic_provider.py      ← YENİ
    │       ├── ollama_provider.py         ← YENİ
    │       └── factory.py                 ← YENİ: get_provider(org_id, provider_name)
    ├── api/
    │   └── v1/
    │       └── providers.py               ← YENİ: provider credential CRUD + health check
    └── schemas/
        └── providers.py                   ← YENİ
alembic/versions/
    └── 0002_provider_credentials.py       ← YENİ migration
tests/
├── unit/
│   ├── test_encryption.py
│   └── test_provider_factory.py
└── integration/
    └── test_provider_endpoints.py
```

---

## Provider Endpoint'leri

| Method | Path | Min Rol | Açıklama |
|---|---|---|---|
| POST | `/providers` | admin | Org'a provider key ekle/güncelle |
| GET | `/providers` | member | Org'un yapılandırılı provider'larını listele (key'ler maskeli) |
| DELETE | `/providers/{provider}` | admin | Provider credential sil |
| GET | `/providers/{provider}/health` | member | Provider'a test çağrısı yap |

---

## Hata Kodları (Yeni)

| Code | HTTP | Açıklama |
|---|---|---|
| `PROVIDER_NOT_CONFIGURED` | 404 | Org için bu provider yapılandırılmamış, platform fallback da yok |
| `PROVIDER_NOT_SUPPORTED` | 422 | Geçersiz provider adı |
| `PROVIDER_AUTH_FAILED` | 401 | API key geçersiz (provider'dan 401 geldi) |
| `PROVIDER_RATE_LIMITED` | 429 | Provider rate limit'e çarptı |
| `PROVIDER_REQUEST_FAILED` | 502 | Provider'dan beklenmeyen hata |

---

## Tamamlanma Kriterleri

- [ ] `BaseLLMProvider` üç provider tarafından da implement edildi
- [ ] `complete()` her üç provider'da çalışıyor (mock ile test edildi)
- [ ] `stream()` async generator olarak token'ları normalize formatta veriyor
- [ ] Tool calling her üç provider'da destekleniyor
- [ ] Org key'i DB'den şifreli okunup kullanılabiliyor
- [ ] Org key'i yoksa platform fallback devreye giriyor
- [ ] Hiçbiri yoksa `PROVIDER_NOT_CONFIGURED` dönüyor
- [ ] Health check endpoint'i gerçek/mock çağrı yapıp sonucu dönüyor
- [ ] Tüm testler geçiyor (unit + integration)

---

## Sonraki Adım (M8)

M8'de bu provider çağrıları her LLM call'ında otomatik event üretecek:
`llm_call_start`, `llm_call_end` — Trace Collector bu event'leri yakalayacak.
