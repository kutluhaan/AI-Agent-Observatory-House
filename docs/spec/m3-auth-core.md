# M3 — Auth Faz 1: Core

**Milestone hedefi:** Register, login, logout çalışır. Token sistemi kurulu.
Korumalı endpoint'e token olmadan istek → 401.

---

## M1 + M2'den Gelen Taban

| Dosya | M3'te Kullanımı |
|---|---|
| `app/core/database.py` | DB session — `get_db` dependency |
| `app/core/config.py` | JWT key'leri, token TTL'leri |
| `app/core/responses.py` | `success()`, `error()`, `AppError`, `RequestValidationError` handler |
| `app/models/user.py` | `User` modeli — register/login |
| `app/models/auth.py` | `RefreshToken`, `EmailVerification` |

---

## M3'te Eklenen / Güncellenen Dosyalar

```
backend/
└── app/
    ├── core/
    │   └── redis.py                  ← Redis bağlantısı (M1'de yoktu, M3'e taşındı)
    ├── middleware/
    │   ├── __init__.py               ← AuthMiddleware export
    │   └── auth.py                   ← cookie → token doğrula → request.state
    ├── services/
    │   ├── jwt_service.py            ← RS256 token üret/doğrula/hash
    │   ├── password_service.py       ← Argon2id hash/verify
    │   ├── token_store.py            ← Redis whitelist/blacklist/rate limit
    │   └── auth_context.py           ← resolve_user_from_token, CurrentUser
    ├── api/
    │   ├── deps.py                   ← get_current_user dependency
    │   └── v1/
    │       └── auth.py               ← register, login, logout, me
    └── schemas/
        └── auth.py                   ← Pydantic request/response schemas
```

---

## M1/M2'den Değişen Dosyalar

### `app/main.py`
- Redis bağlantısı lifespan'a eklenir
- `AuthMiddleware` kayıtlı
- Exception handler'lar: `RequestValidationError`, `AppError`, `Exception`
- Auth router: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`

### `app/core/responses.py`
- `request_validation_error_handler` — Pydantic 422 → `VALIDATION_ERROR` formatı

### `app/core/config.py`
- JWT key'leri — değişmez (`.env`'den okunur)

---

## Token Mimarisi

### Access Token (RS256, 15 dakika)
```json
{
  "sub": "user_uuid",
  "email": "user@example.com",
  "org_id": null,
  "org_slug": null,
  "role": null,
  "type": "access",
  "jti": "unique_token_id",
  "iat": 1748563200,
  "exp": 1748564100
}
```
M3'te yeni kayıt olan kullanıcının henüz org'u yok — `org_id`, `org_slug`, `role` hepsi `null`.

### Refresh Token (RS256, 7 gün)
```json
{
  "sub": "user_uuid",
  "type": "refresh",
  "jti": "unique_token_id",
  "iat": 1748563200,
  "exp": 1749168000
}
```

### Cookie Yapısı
| Cookie | Value | Flags | Path |
|---|---|---|---|
| `access_token` | RS256 JWT | httpOnly, secure, samesite=lax | / |
| `refresh_token` | RS256 JWT | httpOnly, secure, samesite=lax | /auth/refresh |

`refresh_token` cookie'si sadece `/auth/refresh` path'ine gönderilir — başka endpoint'ler görmez.

---

## Auth Katmanı

| Katman | Dosya | Görev |
|---|---|---|
| Middleware | `middleware/auth.py` | Cookie varsa token doğrula → `request.state.current_user` |
| Dependency | `api/deps.py` | Korumalı route'larda user zorunlu → yoksa 401 |
| Context | `services/auth_context.py` | Token → `CurrentUser` (tek kaynak, duplication yok) |

**Public path'ler (middleware token parse etmez):** `/health`, `/auth/register`, `/auth/login`, `/auth/logout`, `/docs`, `/redoc`, `/openapi.json`

---

## Redis Key Yapısı (M3 kapsamında)

```
auth:refresh:{jti}    → user_id    TTL: 7 gün
auth:blacklist:{jti}  → "1"        TTL: 15 dakika

# Rate limiting
ratelimit:login:{email}    → count  TTL: 900 (15 dakika)
ratelimit:register:{ip}    → count  TTL: 3600 (1 saat)
```

---

## RS256 Key Üretimi

M3 çalışmadan önce bir kez yapılır (`.env` kök dizinde):

```bash
# Private key üret
openssl genrsa -out private.pem 2048

# Public key türet
openssl rsa -in private.pem -pubout -out public.pem

# .env'e ekle (tek satır — \n ile)
JWT_PRIVATE_KEY="$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' private.pem)"
JWT_PUBLIC_KEY="$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' public.pem)"

# Güvenlik: key dosyalarını sil
rm private.pem public.pem
```

OpenSSL 3.x `BEGIN PRIVATE KEY` (PKCS#8) formatı da geçerlidir.

---

## Tamamlanma Kriterleri

### Implementasyon (kod)

- [x] `POST /auth/register` → 201, DB'de user kaydı oluştu
- [x] `POST /auth/login` → 200, access + refresh cookie set edildi
- [x] `POST /auth/logout` → 200, cookie'ler silindi, token blacklist'e alındı
- [x] `GET /health` → korumalı değil, hâlâ 200
- [x] `GET /auth/me` → auth-spec response; token yok → 401
- [x] `AuthMiddleware` + `get_current_user` + `auth_context`
- [x] Global hata formatı (`AppError` + Pydantic `VALIDATION_ERROR`)
- [x] RS256 key'ler `.env`'de (placeholder değil)

### Testler

- [x] Unit testler: jwt encode/decode roundtrip (`mock_settings`)
- [x] Unit testler: `auth_context`, `get_current_user`
- [x] Integration testler: register → login → logout → `/me` akışı (`tests/integration/test_auth_flow.py`, 5 test)

---

## M3 Doğrulama (repo kökünden)

Stack ayaktayken (`docker compose -f docker-compose.dev.yml up --build -d`):

```bash
# 1. M3 unit testleri (password, JWT roundtrip, token_store, auth_context, deps)
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/test_m3_services.py -v

# 2. Tüm unit testler
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/ -v

# 3. Auth integration testleri
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/test_auth_flow.py -v -m integration

# 4. Manuel auth smoke test
curl http://localhost:8000/health
curl http://localhost:8000/auth/me
# → 401 INVALID_TOKEN

# register → verify-email → login → cookie ile /me → 200
```

> Integration conftest'te `clear_rate_limits` autouse fixture — her test öncesi Redis `ratelimit:*` key'lerini temizler.

---

## Sonraki Adım (M4) — tamamlandı

M4 session management tamamlandı. Ayrıntılar: [m4-session-management.md](./m4-session-management.md)

> **Not:** `GET /auth/me` M3'te auth-spec formatında implement edildi. M4'te refresh/switch-org/verify-email eklendi; `/me` regression ile korunur.
