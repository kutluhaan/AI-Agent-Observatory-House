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
            API-->>UI: 401 INVALID_TOKEN / REFRESH_TOKEN_EXPIRED
        else Decode başarılı
            API->>Redis: rate limit kontrol (refresh:{user_id}, 30/dk)
            API->>Redis: auth:refresh:{jti} var mı?
            alt Redis'te yok
                API-->>UI: 401 REFRESH_TOKEN_REVOKED
            else Redis'te var
                API->>DB: RefreshToken WHERE token_hash AND is_revoked=false
                API->>DB: User getir, is_active kontrol
                Note over API: Org context — mevcut access_token org'u koru (geçerliyse)
                Note over API: TOKEN ROTATION BAŞLIYOR
                API->>Redis: auth:refresh:{old_jti} sil
                API->>DB: RefreshToken is_revoked=true, revoked_at=now
                API->>JWT: create_access_token(user, org)
                API->>JWT: create_refresh_token(user) → (raw, new_jti)
                API->>DB: INSERT RefreshToken (new hash)
                API->>Redis: auth:refresh:{new_jti} → user_id
                API-->>UI: 200 + yeni httpOnly cookies
                Note over UI: Kullanıcı hiçbir şey fark etmez
            end
        end
    end
```

---

## 2. GET /auth/me Akışı (M3 — regression)

```mermaid
sequenceDiagram
    participant UI as Next.js UI
    participant API as FastAPI
    participant MW as AuthMiddleware
    participant DEPS as get_current_user
    participant DB as PostgreSQL

    UI->>API: GET /auth/me (access_token cookie)
    API->>MW: cookie → resolve_user_from_token
    MW-->>API: request.state.current_user
    API->>DEPS: get_current_user()
    DEPS-->>API: CurrentUser {user_id, email, org_id, role, jti}
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
    API->>DB: SELECT Organization WHERE id = org_id
    alt Org bulunamadı
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
    API->>DB: SELECT EmailVerification WHERE token_hash=? AND used_at IS NULL
    alt Token bulunamadı veya kullanılmış veya expires_at geçmiş
        API-->>UI: 410 EMAIL_VERIFICATION_EXPIRED
    else Geçerli
        API->>DB: UPDATE EmailVerification SET used_at=now()
        API->>DB: UPDATE User SET is_verified=true
        API->>Redis: auth:email_verify:{hash} sil
        API-->>UI: 200 "Email verified successfully."
        UI-->>User: Login sayfasına yönlendir
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
    ROOT["backend/app/"]

    ROOT --> CORE["core/"]
    ROOT --> SVC["services/"]
    ROOT --> API["api/v1/"]
    ROOT --> MW["middleware/"]
    ROOT --> TESTS["tests/"]

    CORE --> EMAIL["email.py\nResend entegrasyonu\nYENİ"]
    CORE --> CFG["config.py\nM1 — değişmez"]

    SVC --> TS["token_store.py\nM3 — opsiyonel güncelleme"]

    API --> AUTH["auth.py\nM3 + M4 endpoint'leri\n+refresh\n+switch-org\n+verify-email\n+resend-verification"]

    MW --> AM["auth.py\nPUBLIC_PATHS güncelleme"]

    TESTS --> TU["unit/test_m4_services.py\nYENİ"]
    TESTS --> TI["integration/test_m4_auth_flow.py\nYENİ"]

    style EMAIL fill:#4ade80,stroke:#166534,color:#000
    style TU fill:#4ade80,stroke:#166534,color:#000
    style TI fill:#4ade80,stroke:#166534,color:#000
    style AUTH fill:#60a5fa,stroke:#1e40af,color:#000
    style AM fill:#60a5fa,stroke:#1e40af,color:#000
```
