# M4 Diyagramları — Session Management

## 1. Token Refresh + Rotation Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant JWT as JWTService
    participant Redis
    participant DB as PostgreSQL

    Note over User,UI: Access token süresi doldu, UI 401 aldı
    UI->>API: POST /auth/refresh
    Note over UI,API: Sadece refresh_token cookie gönderilir (path=/auth/refresh)

    alt refresh_token cookie yok
        API-->>UI: 401 INVALID_TOKEN
    else Token var
        API->>JWT: decode_refresh_token()
        alt Decode başarısız veya type!=refresh
            API-->>UI: 401 INVALID_TOKEN
        else Decode başarılı
            API->>Redis: rate limit kontrol (refresh:{user_id}, 30/dk)
            API->>Redis: auth:refresh:{jti} var mı?
            alt Redis'te yok
                API-->>UI: 401 REFRESH_TOKEN_REVOKED
            else Redis'te var
                API->>DB: User getir, is_active kontrol
                API->>DB: RefreshToken FOR UPDATE (hash, is_revoked=false, expires_at)
                alt DB satırı yok veya revoke/expired
                    API-->>UI: 401 REFRESH_TOKEN_REVOKED
                else Geçerli
                    Note over API: Org context — access_token org'u koru (geçerliyse)
                    API->>DB: is_revoked=true, INSERT yeni RefreshToken
                    API->>JWT: create_access_token + create_refresh_token
                    API->>DB: COMMIT
                    API->>Redis: consume_refresh_token (GETDEL old_jti)
                    API->>Redis: auth:refresh:{new_jti} → user_id
                    API-->>UI: 200 + yeni httpOnly cookies
                    Note over UI: Kullanıcı hiçbir şey fark etmez
                end
            end
        end
    end
```

---

## 2. GET /auth/me Akışı

```mermaid
sequenceDiagram
    participant UI as Next.js UI
    participant API as FastAPI
    participant DEPS as get_current_user
    participant DB as PostgreSQL

    UI->>API: GET /auth/me (access_token cookie)
    API->>DEPS: get_current_user()
    DEPS-->>API: CurrentUser {user_id, email, jti}
    API->>DB: SELECT User WHERE id = user_id
    API->>DB: SELECT OrganizationMember WHERE user_id = ?
    Note over DB: selectinload(organization) ile JOIN
    DB-->>API: User + memberships + organizations
    API-->>UI: 200 {id, email, full_name, is_verified, avatar_url, organizations[]}
```

---

## 3. Switch-Org Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant DEPS as get_current_user
    participant JWT as JWTService
    participant DB as PostgreSQL
    participant Redis

    User->>UI: Org seçici'den başka org'a tıklar
    UI->>API: POST /auth/switch-org {org_id}
    API->>DEPS: get_current_user()
    DEPS-->>API: CurrentUser
    API->>Redis: rate limit (switch_org:{user_id}, 20/dk)
    API->>DB: SELECT Organization WHERE id=?
    alt Org yok
        API-->>UI: 404 ORGANIZATION_NOT_FOUND
    else Org var
        API->>DB: SELECT OrganizationMember WHERE user_id=? AND org_id=?
        alt Üye değil
            API-->>UI: 403 NOT_A_MEMBER
        else Org aktif değil
            API-->>UI: 403 ORG_DEACTIVATED
        else Üye ve aktif
            API->>JWT: create_access_token(org_id, org_slug, role)
            Note over API: Refresh token DEĞİŞMEZ
            API-->>UI: 200 + yeni access_token cookie
            UI-->>User: Yeni org context'inde dashboard
        end
    end
```

---

## 4. Email Verification Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant JWT as JWTService
    participant DB as PostgreSQL
    participant Redis

    Note over User: Register sonrası email'e link geldi
    User->>UI: Email'deki linke tıklar (?token=abc123)
    UI->>API: POST /auth/verify-email {token}
    API->>JWT: hash_token(token) → token_hash
    API->>Redis: auth:email_verify:{hash} var mı?
    alt Redis'te yok
        API-->>UI: 410 EMAIL_VERIFICATION_EXPIRED
    else Redis'te var
        API->>DB: SELECT EmailVerification WHERE token_hash=? AND used_at IS NULL
        alt DB'de yok, expired veya user_id uyuşmaz
            API-->>UI: 410 EMAIL_VERIFICATION_EXPIRED
        else Geçerli
            API->>DB: UPDATE EmailVerification SET used_at=now()
            API->>DB: UPDATE User SET is_verified=true
            API->>Redis: auth:email_verify:{hash} sil
            API-->>UI: 200 "Email verified successfully."
            UI-->>User: Login sayfasına yönlendir
        end
    end
```

---

## 5. Resend Verification Akışı

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js UI
    participant API as FastAPI
    participant JWT as JWTService
    participant DB as PostgreSQL
    participant Redis
    participant Mail as Resend

    User->>UI: "Email doğrulama linkini yeniden gönder"
    UI->>API: POST /auth/resend-verification {email}
    API->>Redis: rate limit (resend_verify:{email}, 3/saat)
    Note over API: Her durumda aynı response — enumeration koruması
    opt User varsa AND is_verified=false AND is_active=true
        API->>DB: UPDATE EmailVerification SET used_at=now() WHERE user_id=? AND used_at IS NULL
        API->>JWT: generate_secure_token() → raw
        API->>JWT: hash_token(raw) → hash
        API->>DB: INSERT EmailVerification (hash, expires_at=+24h)
        API->>Redis: auth:email_verify:{hash} → user_id (TTL 24h)
        API->>Mail: send verification email (raw token)
    end
    API-->>UI: 200 "If this email exists, a verification link has been sent."
```

---

## 6. M4 Dosya Yapısı

```mermaid
graph LR
    ROOT["backend/"]

    ROOT --> APP["app/"]
    ROOT --> TESTS["tests/"]

    APP --> CORE["core/email.py\nYENİ"]
    APP --> AUTH["api/v1/auth.py\nM3 + M4 endpoint'leri"]
    APP --> MW["middleware/auth.py\nPUBLIC_PATHS"]
    APP --> TS["services/token_store.py\nconsume_refresh_token"]

    TESTS --> TU["unit/test_m4_services.py\nresolve_active_org"]
    TESTS --> TI["integration/test_m4_auth_flow.py\nM4 akışları"]
    TESTS --> TH["integration/auth_helpers.py\npaylaşılan fixture'lar"]

    style CORE fill:#4ade80,stroke:#166534,color:#000
    style TU fill:#4ade80,stroke:#166534,color:#000
    style TI fill:#4ade80,stroke:#166534,color:#000
    style AUTH fill:#60a5fa,stroke:#1e40af,color:#000
```
