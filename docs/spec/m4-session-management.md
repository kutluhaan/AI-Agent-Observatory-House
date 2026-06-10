# M4 — Auth Faz 2: Session Management

**Milestone hedefi:** Token refresh, org geçişi, email doğrulama çalışır.
Email servisi (Resend) entegre edilir.

---

## M1–M3'ten Gelen Taban

| Dosya | M4'te Kullanımı |
|---|---|
| `app/core/redis.py` | Token store operations |
| `app/services/jwt_service.py` | Token üretimi ve doğrulama |
| `app/services/token_store.py` | Whitelist/blacklist/rate limit, `consume_refresh_token` |
| `app/api/deps.py` | `get_current_user` dependency |
| `app/middleware/auth.py` | `AuthMiddleware` — PUBLIC_PATHS güncellenir |
| `app/models/auth.py` | `RefreshToken`, `EmailVerification` |
| `app/models/organization.py` | `OrganizationMember` |

---

## M4'te Eklenen / Değişen Dosyalar

```
backend/
├── app/
│   ├── core/
│   │   └── email.py                  ← YENİ: Resend email servisi
│   ├── middleware/
│   │   └── auth.py                   ← GÜNCELLEME: PUBLIC_PATHS
│   ├── api/v1/
│   │   └── auth.py                   ← GÜNCELLEME: 4 endpoint + register email
│   ├── schemas/
│   │   └── auth.py                   ← GÜNCELLEME: M4 request modelleri
│   └── services/
│       └── token_store.py            ← GÜNCELLEME: consume_refresh_token, get_email_verify_user
└── tests/
    ├── unit/
    │   ├── test_m3_services.py       ← GÜNCELLEME: consume_refresh_token, email verify Redis
    │   └── test_m4_services.py       ← YENİ: resolve_active_org
    └── integration/
        ├── auth_helpers.py           ← YENİ: register_and_verify, org seed
        ├── test_auth_flow.py         ← GÜNCELLEME: verify-email akışı (M3 regression)
        └── test_m4_auth_flow.py      ← YENİ: refresh, switch-org, verify, resend
```

### `app/core/config.py` — Değişmez
`RESEND_API_KEY` ve `EMAIL_FROM` `.env` / `.env.example` üzerinden okunur.

---

## M4 Endpoint'leri

| Endpoint | Açıklama | Not |
|---|---|---|
| `POST /auth/refresh` | Token rotation — eski revoke, yeni üret | M4 — yeni |
| `GET /auth/me` | Kullanıcı bilgisi + org listesi | M3'ten — M4'te değişmez, regression ile doğrulanır |
| `POST /auth/switch-org` | Aktif org değiştir, yeni access token al | M4 — yeni |
| `POST /auth/verify-email` | Email doğrulama token'ı kontrol et | M4 — yeni |
| `POST /auth/resend-verification` | Yeni doğrulama emaili gönder | M4 — yeni |

---

## Middleware — PUBLIC_PATHS

M4 ile `app/middleware/auth.py` içindeki `PUBLIC_PATHS` set'ine eklenir:

| Path | Gerekçe |
|---|---|
| `/auth/refresh` | Sadece `refresh_token` cookie (path=`/auth/refresh`); access token gerekmez |
| `/auth/verify-email` | Body'deki token ile kimlik doğrulama |
| `/auth/resend-verification` | Giriş yapmadan çağrılabilir |

Korumalı kalır: `/auth/switch-org` (access token zorunlu).

M3'ten gelen public path'ler değişmez: `/health`, `/auth/register`, `/auth/login`, `/auth/logout`, `/docs`, `/redoc`, `/openapi.json`.

---

## Email Servisi

Resend kullanılır. `RESEND_API_KEY` `.env`'den okunur. SDK çağrısı `asyncio.to_thread` ile event loop'u bloklamaz.

M4'te gönderilen emailler:
- Email doğrulama linki (register sonrası ve `/auth/resend-verification`)

M4 kapsamı dışı (M5'te):
- Org davet emaili

---

## Token Rotation Detayı

`POST /auth/refresh` endpoint'i token rotation uygular:

1. Refresh token cookie'den okunur
2. RS256 ile decode edilir (`REFRESH_TOKEN_EXPIRED` / `INVALID_TOKEN`)
3. Rate limit kontrolü (`refresh`, user_id)
4. Redis whitelist'te (`auth:refresh:{jti}`) hızlı kontrol
5. DB: `RefreshToken` satırı `FOR UPDATE` ile kilitlenir — `is_revoked=false`, `expires_at` geçerli olmalı
6. DB'de `is_revoked=true`, yeni `RefreshToken` INSERT
7. `commit()`
8. Redis: `consume_refresh_token` (atomik GETDEL) — eski jti silinir
9. Redis: yeni jti whitelist'e yazılır
10. Yeni access + refresh cookie set edilir

Org context: mevcut `access_token` cookie'deki `org_id` hâlâ geçerli üyelikse korunur; değilse `joined_at` en eski aktif org'a düşülür.

---

## Tamamlanma Kriterleri

- [x] `POST /auth/refresh` → eski token geçersiz, yeni cookie set edildi
- [x] `GET /auth/me` → M3 davranışı korunuyor (regression)
- [x] `POST /auth/switch-org` → token'da yeni org_id ve role var
- [x] `POST /auth/verify-email` → is_verified=true yapıldı
- [x] `POST /auth/resend-verification` → yeni token üretildi, email gönderildi
- [x] `PUBLIC_PATHS` güncellendi
- [x] Unit testler (`test_m4_services.py`, `test_m3_services.py` token/email)
- [x] Integration testler (`test_m4_auth_flow.py`)
- [x] M3 testleri hâlâ geçiyor (`test_auth_flow.py` regression)

---

## M4 Doğrulama (repo kökünden)

Stack ayaktayken (`docker compose -f docker-compose.dev.yml up --build -d`):

```bash
# 1. M4 unit testleri
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/test_m4_services.py -v

# 2. Tüm unit testler (M3 + M4)
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/ -v

# 3. M4 auth integration testleri
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/test_m4_auth_flow.py -v -m integration

# 4. M3 auth integration (regression)
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/test_auth_flow.py -v -m integration

# 5. Manuel smoke test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/auth/refresh
# → 401 INVALID_TOKEN (cookie yok)

# register → verify-email → login → refresh → switch-org (org seed gerekir)
```

> Integration conftest'te `clear_rate_limits` autouse fixture — her test öncesi Redis `ratelimit:*` key'lerini temizler.

Ayrıntılı akış diyagramları: [M4-diagrams.md](../diagrams/mermaid-codes/M4-diagrams.md)

---

## Sonraki Adım (M5)

M5'te org yönetimi ve davet sistemi eklenecek:
- `POST /organizations`
- `GET /organizations/{org_id}`
- `POST /organizations/{org_id}/invitations`
- `POST /invitations/{token}/accept`
