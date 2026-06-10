# Sprint Plan
## AI Agent Observatory

**Planlama Tarihi:** Mayıs 2026  
**Tempo:** Düzensiz, milestone bazlı  
**Strateji:** Her milestone bağımsız çalışır ve test edilebilir. Birini bitirmeden diğerine geçme.

---

## Genel Bakış

| Milestone | Konu | Tahmini Süre | Çıktı |
|---|---|---|---|
| M1 | Proje iskeleti + Docker | 3-5 saat | Her servis ayağa kalkar |
| M2 | DB şeması + migrations | 2-3 saat | Tablolar oluşur |
| M3 | Auth — Faz 1 (core) | 6-10 saat | Register/login/logout, JWT, `/me` — ✅ tamam |
| M4 | Auth — Faz 2 (session) | 3-5 saat | Refresh, switch-org, verify-email — ✅ tamam |
| M5 | Auth — Faz 3 (org + davet) | 6-8 saat | Org CRUD, davet sistemi çalışır |
| M6 | RBAC middleware | 3-4 saat | Tüm endpoint'ler role göre korunur |
| M7 | Provider Layer | 4-6 saat | OpenAI, Anthropic, Ollama çalışır |
| M8 | Trace Collector | 5-8 saat | Her event loglanır, UI'da görünür |
| M9 | Agent Engine | 8-12 saat | İlk agent çalışır, trace edilir |
| M10 | HITL Engine | 5-7 saat | Agent onay noktasında durur |
| M11 | Test Core | 8-12 saat | Test suite çalışır, metrikler toplanır |
| M12 | Personal Research Agent | 6-10 saat | İlk gerçek agent tamamlanır |
| M13 | Next.js UI — Auth | 5-8 saat | Login/register/org UI çalışır |
| M14 | Next.js UI — Chat + Trace | 8-12 saat | Agent chat + observability UI |
| M15 | Next.js UI — Testing | 6-10 saat | Test runner UI tamamlanır |

**Toplam tahmini:** 80-120 saat  
**Gerçekçi süre (düzensiz tempo):** 3-5 ay

---

## M1 — Proje İskeleti + Docker

**Hedef:** `docker-compose up` çalıştırınca her şey ayağa kalkar.

**Yapılacaklar:**
- [ ] Repo yapısı oluştur (`backend/`, `frontend/`, `docs/`)
- [ ] `backend/` için FastAPI proje iskeleti (`pyproject.toml`, `uv` ile)
- [ ] `frontend/` için Next.js 14 projesi (`app router`)
- [ ] `docker-compose.yml` — PostgreSQL, ClickHouse, Redis, backend, frontend
- [ ] Her servis için `Dockerfile`
- [x] `.env.example` dosyası
- [ ] Backend health check endpoint: `GET /health`
- [ ] Frontend'den backend'e bağlantı testi

**Klasör Yapısı:**
```
observatory/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   └── models/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── Dockerfile
│   └── package.json
├── docs/
│   ├── spec/
│   │   ├── auth-spec.md
│   │   └── sprint-plan.md
│   └── diagrams/
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.example
```

**Tamamlanma kriteri:** `docker-compose up` sonrası:
- `http://localhost:8000/health` → `{"status": "ok"}`
- `http://localhost:3000` → Next.js sayfası açılır
- PostgreSQL, ClickHouse, Redis bağlantıları sağlıklı

---

## M2 — DB Şeması + Migrations

**Hedef:** Tüm auth tabloları veritabanında oluşur.

**Tool:** Alembic (FastAPI için standart migration aracı)

**Yapılacaklar:**
- [x] Alembic kurulumu ve konfigürasyonu
- [x] SQLAlchemy model'leri yaz (8 tablo)
  - [x] `users`
  - [x] `organizations`
  - [x] `organization_members`
  - [x] `refresh_tokens`
  - [x] `email_verifications`
  - [x] `password_resets`
  - [x] `organization_invitations`
  - [x] `oauth_accounts` (Faz 4 için şimdiden)
- [x] İlk migration (`0001_initial_schema.py`) — tablolar, index'ler, CHECK'ler, partial unique, `updated_at` trigger'ları
- [x] Unit + integration testleri
- [x] Doğrulama adımları: [m2-db-schema.md](./m2-db-schema.md#m2-doğrulama-repo-kökünden)

**Tamamlanma kriteri:**
- Migration downgrade/upgrade döngüsü hatasız çalışır
- Unit ve integration testleri geçer

**Doğrulama (repo kökünden, stack ayaktayken):**

```bash
docker compose -f docker-compose.dev.yml up --build -d

docker compose -f docker-compose.dev.yml exec backend sh -c "alembic downgrade base && alembic upgrade head"
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/ -v
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/ -v -m integration
```

Ayrıntılı açıklamalar: [m2-db-schema.md](./m2-db-schema.md#m2-doğrulama-repo-kökünden)

---

## M3 — Auth Faz 1: Core

**Hedef:** Register, login, logout çalışır. Token sistemi kurulu.

**Yapılacaklar:**

*Services:*
- [x] `JWTService` — RS256 key pair üret, token üret/doğrula
- [x] `PasswordService` — Argon2id hash/verify
- [x] `RedisTokenService` (`token_store.py`) — whitelist/blacklist yönetimi
- [x] `auth_context.py` — `resolve_user_from_token`, `CurrentUser`

*Endpoints:*
- [x] `POST /auth/register`
- [x] `POST /auth/login`
- [x] `POST /auth/logout`
- [x] `GET /auth/me` — auth-spec response (M3 kapanış kriteri; M4 overlap)

*Middleware:*
- [x] `AuthMiddleware` — cookie'den token al, doğrula, `request.state`'e ekle
- [x] `get_current_user` FastAPI dependency

*Diğer:*
- [x] RS256 private/public key üretimi ve `.env`'e ekleme
- [x] Pydantic request/response schema'ları
- [x] Global hata formatı (`AppError` + Pydantic `VALIDATION_ERROR`)

*Testler:*
- [x] JWT encode/decode unit testleri (`mock_settings`)
- [x] `auth_context` / `get_current_user` unit testleri
- [x] Integration: register → login → logout → `/me` (`tests/integration/test_auth_flow.py`)

**Tamamlanma kriteri:**
- Register → email doğrulama bekleniyor
- Login → access + refresh token cookie set ediliyor
- Logout → token'lar geçersiz kılınıyor
- Korumalı endpoint'e token olmadan istek → 401 (`GET /auth/me`)

**Doğrulama:** [m3-auth-core.md](./m3-auth-core.md#m3-doğrulama-repo-kökünden)

---

## M4 — Auth Faz 2: Session Management

**Hedef:** Token refresh, org geçişi, email doğrulama çalışır.

**Yapılacaklar:**
- [x] `POST /auth/refresh` — token rotation (`FOR UPDATE`, commit sonrası `consume_refresh_token`)
- [x] `POST /auth/switch-org` — yeni org için access token (403 `NOT_A_MEMBER`, 404 org yok)
- [x] `POST /auth/verify-email` — Redis fast-path + DB doğrulama
- [x] `POST /auth/resend-verification` — enumeration koruması (her zaman 200)
- [x] Email servisi entegrasyonu (Resend, `asyncio.to_thread`)

**Tamamlanma kriteri:**
- Refresh token rotation çalışıyor, eski token geçersiz
- Switch-org sonrası token'da yeni org_id ve role var
- Email doğrulama linki çalışıyor

**Doğrulama:** [m4-session-management.md](./m4-session-management.md#m4-doğrulama-repo-kökünden)

---

## M5 — Auth Faz 3: Organization + Davet

**Hedef:** Org yönetimi ve link tabanlı davet sistemi çalışır.

**Yapılacaklar:**
- [ ] `POST /organizations` — org oluştur
- [ ] `GET /organizations/{org_id}` — org bilgisi
- [ ] `GET /organizations/{org_id}/members` — üye listesi
- [ ] `POST /organizations/{org_id}/invitations` — davet gönder
- [ ] `POST /invitations/{token}/accept` — daveti kabul et
- [ ] `DELETE /organizations/{org_id}/members/{user_id}` — üye çıkar
- [ ] `PATCH /organizations/{org_id}/members/{user_id}` — rol değiştir
- [ ] Davet email'i template'i

**Edge case'ler:**
- [ ] Davet edilen email kayıtsızsa register'a yönlendir, token korunur
- [ ] Süresi dolmuş davet kontrolü
- [ ] Aynı email'e birden fazla pending davet engeli

**Tamamlanma kriteri:**
- Owner davet linki gönderebilir
- Davet linki tıklanınca kullanıcı org'a katılır
- Üye çıkarma ve rol değiştirme çalışır

---

## M6 — RBAC Middleware

**Hedef:** Tüm endpoint'ler role göre korunur, tek satırla yetki kontrolü yapılır.

**Yapılacaklar:**
- [ ] `TenantContext` dataclass
- [ ] `get_tenant_context` dependency — token'dan context çıkar
- [ ] `require_role(minimum_role)` dependency factory
- [ ] Tüm mevcut endpoint'lere RBAC uygula
- [ ] Permission matrisi testleri

**Kullanım örneği:**
```python
@router.delete("/projects/{id}")
async def delete_project(
    id: UUID,
    ctx: TenantContext = Depends(require_role("admin"))
):
    ...
```

**Tamamlanma kriteri:**
- Member admin endpoint'ine istek atarsa → 403
- Owner her endpoint'e erişebilir
- Yanlış org'a istek atılırsa → 403

---

## M7 — Provider Layer

**Hedef:** OpenAI, Anthropic, Ollama tek interface üzerinden çağrılabilir.

**Yapılacaklar:**
- [ ] `BaseLLMProvider` abstract class
- [ ] `OpenAIProvider` implementasyonu
- [ ] `AnthropicProvider` implementasyonu
- [ ] `OllamaProvider` implementasyonu (local IP üzerinden)
- [ ] Provider factory — config'e göre doğru provider döndürür
- [ ] Streaming desteği (SSE için async generator)
- [ ] Tool calling desteği
- [ ] Org bazlı API key yönetimi (DB'den şifreli okuma)
- [ ] Provider health check endpoint'i

**Tamamlanma kriteri:**
- Üç provider da aynı interface ile çağrılabiliyor
- Token streaming çalışıyor
- Tool calling çalışıyor
- Hatalı API key → anlamlı hata mesajı

---

## M8 — Trace Collector

**Hedef:** Her agent eventi otomatik loglanır, Redis Stream'e yazılır, ClickHouse'a persist edilir.

**Yapılacaklar:**
- [ ] ClickHouse şeması — trace ve event tabloları
- [ ] `TraceCollector` servisi
- [ ] Event tipleri tanımla:
  - `llm_call_start` / `llm_call_end`
  - `tool_call_start` / `tool_call_end`
  - `reasoning`
  - `agent_start` / `agent_end`
  - `hitl_requested`
  - `error`
- [ ] Redis Streams entegrasyonu — org bazlı stream key'leri
- [ ] Stream consumer — Redis'ten oku, ClickHouse'a yaz
- [ ] WebSocket manager — stream event'lerini UI'a ilet
- [ ] `GET /traces/{trace_id}` endpoint'i
- [ ] `GET /traces` — liste endpoint'i (filtreleme ile)

**Tamamlanma kriteri:**
- Manuel tetiklenen bir LLM call trace'e düşüyor
- WebSocket bağlantısıyla real-time event akıyor
- ClickHouse'da sorgulama çalışıyor

---

## M9 — Agent Engine

**Hedef:** Agent çalışır, her adım trace edilir, multi-agent desteği var.

**Yapılacaklar:**
- [ ] `BaseAgent` abstract class
- [ ] Tool registry sistemi
- [ ] Agent execution loop
- [ ] Reasoning adımı yönetimi
- [ ] Tool call → result → next step döngüsü
- [ ] Multi-agent orchestrator (basit)
- [ ] Agent konfigürasyon sistemi (DB'de saklanır)
- [ ] `POST /agents/{id}/run` endpoint'i
- [ ] SSE endpoint'i — token streaming
- [ ] Timeout ve max step koruması (sonsuz döngü önlemi)
- [ ] Trace Collector entegrasyonu — her adım otomatik loglanır

**Tamamlanma kriteri:**
- Basit tool'lu bir agent çalışıyor
- Her adım trace UI'da görünüyor
- Agent sonsuz döngüye giremez
- İki agent birbirini çağırabilir ve bu trace'de görünür

---

## M10 — HITL Engine

**Hedef:** Agent onay noktasında durur, kullanıcı UI'dan devam ettirir.

**Yapılacaklar:**
- [ ] `HITLEngine` servisi
- [ ] Redis queue entegrasyonu
- [ ] Agent'ta HITL decorator/marker
- [ ] `POST /hitl/{request_id}/approve` endpoint'i
- [ ] `POST /hitl/{request_id}/reject` endpoint'i
- [ ] `POST /hitl/{request_id}/modify` — input değiştirerek devam
- [ ] Timeout yönetimi (10 dakika, sonra auto-reject)
- [ ] WebSocket bildirimi — UI'a HITL bekleniyor mesajı

**Tamamlanma kriteri:**
- Agent HITL noktasına gelince duruyor
- UI bildirim alıyor
- Onay sonrası agent kaldığı yerden devam ediyor
- Timeout sonrası agent gracefully sonlanıyor

---

## M11 — Test Core

**Hedef:** Test suite çalışır, RAG değerlendirmesi yapılır, metrikler toplanır.

**Yapılacaklar:**
- [ ] `AgentSandbox` — synthetic history enjeksiyonu
- [ ] YAML test suite parser
- [ ] Assertion engine (tool_called, response_contains, latency_under)
- [ ] `ExperimentRunner` — paralel/sıralı çalıştırma
- [ ] RAG Evaluator:
  - [ ] RAGAS entegrasyonu (faithfulness, relevancy)
  - [ ] Precision@K, Recall@K hesaplama
  - [ ] Latency metrikleri
- [ ] Test sonuçları DB'ye kaydetme
- [ ] `POST /test-suites` — suite oluştur
- [ ] `POST /test-suites/{id}/run` — çalıştır
- [ ] `GET /test-runs/{id}` — sonuçlar
- [ ] WebSocket — real-time test progress

**Tamamlanma kriteri:**
- YAML'dan yüklenen test suite çalışıyor
- RAG metrikleri hesaplanıyor
- Sonuçlar karşılaştırılabilir formatta saklanıyor

---

## M12 — Personal Research Agent

**Hedef:** İlk gerçek kullanım senaryosu — araştırma yapan agent tamamlanır.

**Tool'lar:**
- [ ] `web_search` — Tavily veya SerpAPI entegrasyonu
- [ ] `read_url` — URL içeriği çekme
- [ ] `summarize` — uzun içeriği özetleme
- [ ] `save_note` — araştırma notlarını kaydetme

**Yapılacaklar:**
- [ ] Tool'ların implementasyonu
- [ ] Agent system prompt tasarımı
- [ ] Multi-step reasoning akışı
- [ ] Araştırma sonucu formatlama
- [ ] HITL entegrasyonu — kritik arama kararlarında onay
- [ ] Test suite yazımı

**Tamamlanma kriteri:**
- "Türkiye'deki AI startup ekosistemi" gibi bir soruya kapsamlı rapor üretebiliyor
- Her adım trace UI'da görünüyor
- Test suite geçiyor

---

## M13 — Next.js UI: Auth

**Hedef:** Login, register, org yönetimi UI'ı çalışır.

**Yapılacaklar:**
- [ ] Layout ve temel UI bileşenleri (Tailwind + shadcn/ui)
- [ ] Login sayfası
- [ ] Register sayfası
- [ ] Email doğrulama sayfası
- [ ] Org oluşturma sayfası
- [ ] Org seçici (birden fazla org varsa)
- [ ] Davet kabul sayfası
- [ ] Auth context — token yönetimi, otomatik refresh
- [ ] Protected route wrapper
- [ ] API client (fetch wrapper, hata yönetimi)

**Tamamlanma kriteri:**
- Kullanıcı kayıt olup giriş yapabiliyor
- Org oluşturup geçiş yapabiliyor
- Davet linkiyle org'a katılabiliyor
- Token expire olunca otomatik refresh oluyor

---

## M14 — Next.js UI: Chat + Trace

**Hedef:** Agent chat arayüzü ve observability dashboard çalışır.

**Yapılacaklar:**

*Chat UI:*
- [ ] Chat input + mesaj listesi
- [ ] Token streaming — kelime kelime yazılma efekti
- [ ] Tool call bileşeni — çalışırken spinner, bitince sonuç
- [ ] Reasoning tag görüntüleme
- [ ] HITL onay bileşeni — modal + approve/reject/modify
- [ ] Custom bileşenler — form, döküman viewer, resim, video

*Trace UI:*
- [ ] Trace listesi
- [ ] Trace detay sayfası — timeline görünümü
- [ ] Agent çağrı grafiği — multi-agent için
- [ ] Metrik kartları — latency, token kullanımı, maliyet
- [ ] Real-time WebSocket entegrasyonu

**Tamamlanma kriteri:**
- Agent chat gerçek zamanlı çalışıyor
- Tool call'lar UI'da adım adım görünüyor
- HITL onay akışı UI'dan tamamlanabiliyor
- Trace detayı incelenebiliyor

---

## M15 — Next.js UI: Testing

**Hedef:** Test runner UI tamamlanır, platform kullanılabilir hale gelir.

**Yapılacaklar:**
- [ ] Test suite oluşturma UI'ı (YAML editörü veya form)
- [ ] Test çalıştırma butonu + real-time progress
- [ ] Senaryo bazlı sonuç görünümü (passed/failed/running)
- [ ] RAG metrik dashboard'u
- [ ] Experiment karşılaştırma tablosu
- [ ] Test geçmişi

**Tamamlanma kriteri:**
- UI'dan test suite oluşturulup çalıştırılabiliyor
- Sonuçlar real-time takip edilebiliyor
- İki experiment yan yana karşılaştırılabiliyor

---
## Testing Stratejisi

### Araçlar

| Araç | Amaç |
|---|---|
| `pytest` | Backend unit + integration testleri |
| `pytest-asyncio` | Async FastAPI endpoint testleri |
| `httpx` | FastAPI test client (async) |
| `pytest-postgresql` | Test için izole PostgreSQL instance |
| `fakeredis` | Redis mock — gerçek Redis'e gerek yok |
| `respx` | HTTP mock — dış API çağrıları (LLM provider'lar) |
| `factory-boy` | Test fixture üretimi (user, org, token) |
| `Playwright` | E2E testleri (tarayıcı üzerinden tam akış) |

### Test Klasör Yapısı

```
backend/
└── tests/
    ├── unit/
    │   ├── test_m3_services.py       # JWT, password, token_store, auth_context, deps
    │   ├── test_m4_services.py       # resolve_active_org
    │   ├── test_models.py
    │   ├── test_rbac.py              # M6+
    │   ├── test_provider_layer.py    # M7+
    │   └── test_trace_collector.py   # M8+
    ├── integration/
    │   ├── conftest.py               # client, auth_user, clear_rate_limits
    │   ├── auth_helpers.py           # register_and_verify, org seed
    │   ├── test_auth_flow.py         # M3 regression
    │   ├── test_m4_auth_flow.py      # M4 session endpoints
    │   ├── test_migrations.py
    │   ├── test_org_endpoints.py     # M5+
    │   ├── test_invitation_flow.py   # M5+
    │   ├── test_agent_execution.py   # M9+
    │   ├── test_hitl_flow.py         # M10+
    │   └── test_test_runner.py       # M11+
    └── e2e/
        ├── test_register_login_flow.py
        ├── test_org_invite_flow.py
        ├── test_agent_chat_flow.py
        └── test_hitl_approval_flow.py

frontend/
└── tests/
    └── e2e/
        ├── auth.spec.ts
        ├── org.spec.ts
        └── chat.spec.ts
```

---

### Test Seviyeleri

#### Unit Testler
Her servis ve utility fonksiyon için. Dış bağımlılık yok — DB, Redis, LLM hepsi mock'lanır.

**Kapsam:**
- `JWTService` — token üretme, doğrulama, expire kontrolü, blacklist
- `PasswordService` — hash, verify, zayıf şifre reddi
- `RBACDependency` — her rol için her aksiyon doğru mu
- `ProviderLayer` — mock LLM response ile streaming, tool calling
- `TraceCollector` — event formatı, Redis yazımı
- `HITLEngine` — queue yönetimi, timeout mantığı

**Örnek:**
```python
async def test_access_token_contains_org_context():
    token = jwt_service.create_access_token(
        user_id=uuid4(), email="test@test.com",
        org_id=uuid4(), org_slug="my-org", role="admin"
    )
    payload = jwt_service.decode(token)
    assert payload["role"] == "admin"
    assert payload["org_slug"] == "my-org"

async def test_expired_token_raises():
    token = jwt_service.create_access_token(..., expires_in=-1)
    with pytest.raises(TokenExpiredError):
        jwt_service.decode(token)
```

---

#### Integration Testler
Gerçek DB (test instance) ve fakeredis kullanılır. LLM provider'lar mock'lanır.

**Kapsam:**
- Auth akışının tamamı (register → verify → login → refresh → logout)
- Org oluşturma ve üye yönetimi
- Davet akışı (gönder → kabul et → üye oldu)
- Switch-org sonrası token'da doğru org var mı
- RBAC — member admin endpoint'ine erişemez
- Agent çalıştırma → trace DB'ye yazıldı mı
- HITL — agent durdu, onay verildi, devam etti

**Örnek:**
```python
async def test_login_sets_correct_org_in_token(client, db):
    user = await UserFactory.create(db)
    org = await OrgFactory.create(db, owner=user)
    response = await client.post("/auth/login", json={
        "email": user.email, "password": "Test1234!"
    })
    assert response.status_code == 200
    payload = jwt_service.decode(response.cookies["access_token"])
    assert payload["org_id"] == str(org.id)
    assert payload["role"] == "owner"

async def test_member_cannot_delete_project(client, db):
    member_token = await create_token(role="member")
    response = await client.delete(
        "/projects/some-id",
        cookies={"access_token": member_token}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
```

---

#### E2E Testler
Playwright ile gerçek tarayıcıda tam kullanıcı akışları. Tüm Docker servisleri ayakta olmalı.

**Kapsam:**
- Kullanıcı kayıt olur, email doğrular, giriş yapar
- Org oluşturur, davet linki gönderir, başka kullanıcı kabul eder
- Agent çalıştırır, tool call'ları UI'da görür
- HITL noktasında onay verir, agent devam eder
- Test suite oluşturur, çalıştırır, sonuçları görür

**Örnek:**
```typescript
test("register → verify → login flow", async ({ page }) => {
  await page.goto("/register");
  await page.fill('[name="email"]', "test@example.com");
  await page.fill('[name="password"]', "Test1234!");
  await page.click('[type="submit"]');
  await expect(page).toHaveURL("/verify-email");
  const token = await getVerificationToken("test@example.com");
  await page.goto(`/verify-email?token=${token}`);
  await expect(page).toHaveURL("/dashboard");
});
```

---

### Test Ortamı Konfigürasyonu

```python
# backend/tests/conftest.py
@pytest.fixture(scope="session")
async def db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield get_test_session()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def redis():
    return fakeredis.aioredis.FakeRedis()

@pytest.fixture
async def client(db, redis):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
```

---

### Milestone Bazlı Test Kapsamı

| Milestone | Unit | Integration | E2E |
|---|---|---|---|
| M1 — Docker/iskelet | — | Health check | — |
| M2 — DB schema | Model validasyonları | Migration çalışıyor | — |
| M3 — Auth core | JWTService, PasswordService, auth_context, deps | Register/login/logout/`/me` (`test_auth_flow.py`) | [m3-auth-core.md](./m3-auth-core.md) |
| M4 — Session | `resolve_active_org`, `consume_refresh_token` | `test_m4_auth_flow.py`, `test_auth_flow.py` regression | [m4-session-management.md](./m4-session-management.md) |
| M5 — Org + davet | Davet token mantığı | Davet akışı baştan sona | — |
| M6 — RBAC | Her rol her aksiyon | Forbidden senaryoları | — |
| M7 — Provider | Mock LLM response | Streaming, tool call | — |
| M8 — Trace | Event formatı | Redis → ClickHouse yazımı | — |
| M9 — Agent | Execution loop, timeout | Agent çalıştır + trace | — |
| M10 — HITL | Queue, timeout | Onay/ret akışı | — |
| M11 — Test Core | Assertion engine | YAML suite çalıştır | — |
| M12 — Research Agent | Tool'lar | Tam araştırma akışı | — |
| M13 — UI Auth | — | — | Register/login/org E2E |
| M14 — UI Chat | — | — | Agent chat + HITL E2E |
| M15 — UI Testing | — | — | Test suite E2E |

---


## Genel Kurallar

**Her milestone için:**
1. Unit testleri yaz
2. `pytest tests/unit/` çalıştır — hepsi geçmeli
3. Integration testleri yaz
4. `pytest tests/integration/` çalıştır — hepsi geçmeli
5. Manuel tamamlanma kriterlerini kontrol et
6. Bir sonraki milestone'a geç

**Takılınca:**
- 30 dakika çözemedin → not al, devam et, sonra bak
- 2 saat çözemedin → scope küçült, minimal çalışan versiyonu bitir

**Koda başlamadan önce her milestone için:**
- Spec'i oku
- Tamamlanma kriterlerini gözden geçir
- Bağımlılıkları kontrol et (M3 bitmeden M4'e geçme)

---

## Bağımlılık Grafiği

```
M1 → M2 → M3 → M4 → M5 → M6
                              ↓
                    M7 → M8 → M9 → M10 → M11 → M12
                              ↓
                    M13 → M14 → M15
```

M6 tamamlanmadan M7'ye geçme.  
M9 tamamlanmadan M13'e geçebilirsin — frontend ve backend paralel yürütülebilir.

---

*Sprint planı değişken tempoyla 3-5 aylık çalışmayı kapsar. Her milestone bağımsız bir çalışan çıktı üretir.*
