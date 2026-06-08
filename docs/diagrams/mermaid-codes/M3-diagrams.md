# M3 Diyagramları — Auth Faz 1: Core

## 1. M3 Dosya Yapısı

```mermaid
graph LR
    ROOT["backend/app/"]

    ROOT --> CORE["core/"]
    ROOT --> SVC["services/"]
    ROOT --> API["api/"]
    ROOT --> SCH["schemas/"]
    ROOT --> MW["middleware/"]

    CORE --> RD["redis.py\nRedis bağlantısı"]
    CORE --> CFG["config.py\nM1'den — değişmez"]
    CORE --> DB["database.py\nM1'den — değişmez"]
    CORE --> RSP["responses.py\nAppError + VALIDATION_ERROR"]

    SVC --> JWT["jwt_service.py\nRS256 token üret/doğrula"]
    SVC --> PWD["password_service.py\nArgon2id hash/verify"]
    SVC --> TS["token_store.py\nRedis whitelist/blacklist"]
    SVC --> AC["auth_context.py\nresolve_user_from_token"]

    MW --> AM["auth.py\nAuthMiddleware"]

    API --> DEPS["deps.py\nget_current_user dependency"]
    API --> V1["v1/auth.py\nregister, login, logout, me"]

    SCH --> SAUTH["auth.py\nPydantic schemas"]

    style JWT fill:#4ade80,stroke:#166534,color:#000
    style PWD fill:#4ade80,stroke:#166534,color:#000
    style TS fill:#4ade80,stroke:#166534,color:#000
    style DEPS fill:#4ade80,stroke:#166534,color:#000
    style V1 fill:#4ade80,stroke:#166534,color:#000
    style SAUTH fill:#4ade80,stroke:#166534,color:#000
    style AC fill:#4ade80,stroke:#166534,color:#000
    style AM fill:#4ade80,stroke:#166534,color:#000
    style RD fill:#60a5fa,stroke:#1e40af,color:#000
```

---

## 2. Register Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant PWD as PasswordService
    participant JWT as JWTService
    participant DB as PostgreSQL
    participant Redis

    User->>UI: email + password + full_name
    UI->>API: POST /auth/register
    API->>Redis: rate limit kontrol (register:{ip}, 5/saat)
    alt Rate limit aşıldı
        API-->>UI: 429 RATE_LIMIT_EXCEEDED
    else OK
        API->>DB: SELECT WHERE email = ?
        alt Email kayıtlı
            API-->>UI: 409 EMAIL_ALREADY_EXISTS
        else Email yok
            API->>PWD: validate_password_strength()
            alt Şifre zayıf
                API-->>UI: 422 PASSWORD_TOO_WEAK
            else Şifre güçlü
                API->>PWD: hash_password() → Argon2id
                API->>DB: INSERT users (is_verified=false)
                API->>JWT: generate_secure_token() → raw_token
                API->>JWT: hash_token(raw_token) → token_hash
                API->>DB: INSERT email_verifications
                API->>Redis: auth:email_verify:{hash} → user_id (TTL 24h)
                Note over API: TODO M4 — email gönder
                API-->>UI: 201 {message, user_id}
            end
        end
    end
```

---

## 3. Login Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant PWD as PasswordService
    participant JWT as JWTService
    participant DB as PostgreSQL
    participant Redis

    User->>UI: email + password
    UI->>API: POST /auth/login
    API->>Redis: rate limit kontrol (login:{email}, 10/15dk)
    alt Rate limit aşıldı
        API-->>UI: 429 RATE_LIMIT_EXCEEDED
    else OK
        API->>DB: SELECT WHERE email = ?
        alt User yok VEYA şifre yanlış
            Note over API: Aynı hata — enumeration koruması
            API-->>UI: 401 INVALID_CREDENTIALS
        else Şifre doğru
            API->>PWD: verify_password()
            alt is_verified = false
                API-->>UI: 403 EMAIL_NOT_VERIFIED
            else is_active = false
                API-->>UI: 403 ACCOUNT_DISABLED
            else Her şey OK
                API->>DB: Kullanıcının org'larını getir
                API->>JWT: create_access_token(user_id, email, org_id=null, role=null)
                API->>JWT: create_refresh_token(user_id) → (raw, jti)
                API->>JWT: hash_token(raw) → token_hash
                API->>DB: INSERT refresh_tokens (token_hash, device_info, ip)
                API->>DB: UPDATE users SET last_login_at = now()
                API->>Redis: auth:refresh:{jti} → user_id (TTL 7gün)
                API-->>UI: 200 + set httpOnly cookies
                Note over UI: access_token cookie (15dk, path=/)<br/>refresh_token cookie (7gün, path=/auth/refresh)
            end
        end
    end
```

---

## 4. Logout Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant JWT as JWTService
    participant DB as PostgreSQL
    participant Redis

    User->>UI: Çıkış yap
    UI->>API: POST /auth/logout
    Note over UI,API: Her iki cookie otomatik gönderilir
    opt access_token cookie varsa
        API->>JWT: decode_access_token() → payload
        API->>Redis: auth:blacklist:{jti} → "1" (TTL 15dk)
    end
    opt refresh_token cookie varsa
        API->>JWT: decode_refresh_token() → payload
        API->>JWT: hash_token(raw) → token_hash
        API->>Redis: auth:refresh:{jti} sil
        API->>DB: UPDATE refresh_tokens SET is_revoked=true
    end
    API-->>UI: 200 + cookies cleared
    UI-->>User: Login sayfasına yönlendir
```

---

## 5. Protected Endpoint Akışı (get_current_user)

```mermaid
sequenceDiagram
    participant UI as Next.js UI
    participant API as FastAPI
    participant DEPS as deps.py
    participant JWT as JWTService
    participant Redis

    UI->>API: GET /protected (access_token cookie)
    API->>DEPS: get_current_user() dependency
    DEPS->>DEPS: Cookie'den access_token al
    alt Token yok
        DEPS-->>API: 401 INVALID_TOKEN
        API-->>UI: 401
    else Token var
        DEPS->>JWT: decode_access_token()
        alt Token geçersiz/expire
            DEPS-->>API: 401
        else Token geçerli
            DEPS->>Redis: auth:blacklist:{jti} var mı?
            alt Blacklist'te var
                DEPS-->>API: 401 INVALID_TOKEN
            else Blacklist'te yok
                DEPS-->>API: CurrentUser {user_id, email, jti}
                API->>API: Endpoint handler çalışır
                API-->>UI: 200 + data
            end
        end
    end
```

---

## 6. RS256 Token Akışı

```mermaid
graph LR
    subgraph Üretim["Token Üretimi (login)"]
        PK["Private Key\n(.env'den)"] -->|sign| AT["Access Token\nRS256 JWT"]
        PK -->|sign| RT["Refresh Token\nRS256 JWT"]
    end

    subgraph Doğrulama["Token Doğrulama (her request)"]
        AT2["Access Token\n(cookie'den)"] -->|verify| PUBK["Public Key\n(.env'den)"]
        PUBK -->|valid/invalid| RESULT["Payload veya Hata"]
    end

    subgraph Redis["Redis Kontrolleri"]
        RESULT -->|jti| BL["auth:blacklist:{jti}\nblacklist kontrolü"]
        RT2["Refresh Token\n(cookie'den)"] -->|jti| WL["auth:refresh:{jti}\nwhitelist kontrolü"]
    end
```

---

## 7. Servis Katmanı Mimarisi

```mermaid
graph TD
    subgraph API["API Layer (api/v1/auth.py)"]
        REG["POST /auth/register"]
        LGN["POST /auth/login"]
        LGT["POST /auth/logout"]
    end

    subgraph Services["Service Layer"]
        JWT["jwt_service.py\ncreate_access_token()\ncreate_refresh_token()\ndecode_access_token()\nhash_token()\ngenerate_secure_token()"]
        PWD["password_service.py\nhash_password()\nverify_password()\nvalidate_password_strength()"]
        TS["token_store.py\nstore_refresh_token()\nblacklist_access_token()\ncheck_rate_limit()\nis_access_token_blacklisted()"]
    end

    subgraph Deps["Dependency Layer (api/deps.py)"]
        GCU["get_current_user()\naccess_token cookie\n→ blacklist kontrol\n→ CurrentUser"]
    end

    subgraph Infra["Infrastructure Layer"]
        PG["PostgreSQL\nusers, refresh_tokens\nemail_verifications"]
        RD["Redis\nwhitelist, blacklist\nrate limiting"]
    end

    REG --> PWD
    REG --> JWT
    REG --> TS
    LGN --> PWD
    LGN --> JWT
    LGN --> TS
    LGT --> JWT
    LGT --> TS
    GCU --> JWT
    GCU --> TS

    JWT --> RD
    TS --> RD
    REG --> PG
    LGN --> PG
    LGT --> PG
```
