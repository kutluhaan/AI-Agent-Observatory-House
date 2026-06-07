# M2 Diyagramları — DB Şeması + Migrations

## 1. ER Diyagramı (Tam)

```mermaid
erDiagram
    users {
        UUID id PK "gen_random_uuid()"
        VARCHAR_255 email UK "NOT NULL — login + davet lookup"
        VARCHAR_255 password_hash "NULL = OAuth kullanıcısı"
        BOOLEAN is_verified "DEFAULT false — login'de kontrol edilir"
        BOOLEAN is_active "DEFAULT true — false = soft delete"
        VARCHAR_255 full_name "NULL olabilir"
        VARCHAR_500 avatar_url "NULL = frontend initials gösterir"
        TIMESTAMPTZ last_login_at "NULL = hiç giriş yapılmadı"
        TIMESTAMPTZ created_at "DEFAULT now()"
        TIMESTAMPTZ updated_at "DEFAULT now()"
    }

    organizations {
        UUID id PK "gen_random_uuid()"
        VARCHAR_255 name "NOT NULL — benzersiz olmak zorunda değil"
        VARCHAR_100 slug UK "NOT NULL — URL-safe, değiştirilemez"
        VARCHAR_50 plan "DEFAULT free"
        BOOLEAN is_active "DEFAULT true"
        UUID created_by FK "REFERENCES users(id) RESTRICT"
        TIMESTAMPTZ created_at "DEFAULT now()"
        TIMESTAMPTZ updated_at "DEFAULT now()"
    }

    organization_members {
        UUID id PK "gen_random_uuid()"
        UUID organization_id FK "CASCADE DELETE"
        UUID user_id FK "CASCADE DELETE"
        VARCHAR_50 role "CHECK: owner|admin|member"
        TIMESTAMPTZ joined_at "DEFAULT now()"
    }

    refresh_tokens {
        UUID id PK "gen_random_uuid()"
        UUID user_id FK "CASCADE DELETE"
        VARCHAR_255 token_hash "SHA-256 — raw token saklanmaz"
        VARCHAR_500 device_info "User-Agent"
        INET ip_address "Faz 5 için"
        TIMESTAMPTZ expires_at "NOT NULL — 7 gün"
        BOOLEAN is_revoked "DEFAULT false"
        TIMESTAMPTZ revoked_at "NULL = henüz revoke edilmedi"
        TIMESTAMPTZ created_at "DEFAULT now()"
    }

    email_verifications {
        UUID id PK "gen_random_uuid()"
        UUID user_id FK "CASCADE DELETE"
        VARCHAR_255 token_hash "SHA-256"
        TIMESTAMPTZ expires_at "NOT NULL — 24 saat"
        TIMESTAMPTZ used_at "NULL = kullanılmadı"
        TIMESTAMPTZ created_at "DEFAULT now()"
    }

    password_resets {
        UUID id PK "gen_random_uuid()"
        UUID user_id FK "CASCADE DELETE"
        VARCHAR_255 token_hash "SHA-256"
        TIMESTAMPTZ expires_at "NOT NULL — 30 dakika"
        TIMESTAMPTZ used_at "NULL = kullanılmadı"
        TIMESTAMPTZ created_at "DEFAULT now()"
    }

    organization_invitations {
        UUID id PK "gen_random_uuid()"
        UUID organization_id FK "CASCADE DELETE"
        UUID invited_by FK "REFERENCES users(id) RESTRICT"
        VARCHAR_255 email "Davet edilen kişi"
        VARCHAR_50 role "CHECK: admin|member"
        VARCHAR_255 token_hash "SHA-256"
        VARCHAR_50 status "DEFAULT pending"
        TIMESTAMPTZ expires_at "NOT NULL — 7 gün"
        TIMESTAMPTZ accepted_at "NULL = kabul edilmedi"
        TIMESTAMPTZ created_at "DEFAULT now()"
    }

    oauth_accounts {
        UUID id PK "gen_random_uuid()"
        UUID user_id FK "CASCADE DELETE"
        VARCHAR_50 provider "CHECK: google|github"
        VARCHAR_255 provider_id "NOT NULL"
        TEXT access_token "AES-256 şifreli — Faz 4"
        TEXT refresh_token "AES-256 şifreli — Faz 4"
        TIMESTAMPTZ expires_at "NULL olabilir"
        TIMESTAMPTZ created_at "DEFAULT now()"
        TIMESTAMPTZ updated_at "DEFAULT now()"
    }

    users ||--o{ organization_members : "üye olur"
    users ||--o{ refresh_tokens : "token sahip olur"
    users ||--o{ email_verifications : "doğrulama alır"
    users ||--o{ password_resets : "reset token alır"
    users ||--o{ oauth_accounts : "OAuth bağlar (Faz 4)"
    users ||--o{ organization_invitations : "davet gönderir"
    users ||--o{ organizations : "oluşturur (created_by)"
    organizations ||--o{ organization_members : "üye içerir"
    organizations ||--o{ organization_invitations : "davet içerir"
```

---

## 2. Tablo Bağımlılık Grafiği (Migration Sırası)

```mermaid
graph TD
    U["users\n(bağımsız — ilk oluşur)"]
    O["organizations\n(created_by → users)"]
    OM["organization_members\n(organization_id → organizations\nuser_id → users)"]
    RT["refresh_tokens\n(user_id → users)"]
    EV["email_verifications\n(user_id → users)"]
    PR["password_resets\n(user_id → users)"]
    OI["organization_invitations\n(organization_id → organizations\ninvited_by → users)"]
    OA["oauth_accounts\n(user_id → users)"]

    U --> O
    U --> RT
    U --> EV
    U --> PR
    U --> OA
    O --> OM
    U --> OM
    O --> OI
    U --> OI

    style U fill:#4ade80,stroke:#166534,color:#000
    style O fill:#60a5fa,stroke:#1e40af,color:#000
    style OM fill:#f472b6,stroke:#9d174d,color:#000
```

---

## 3. Index ve Constraint Haritası

```mermaid
graph LR
    subgraph users_indexes["users — index'ler"]
        UI1["idx_users_email\n(email)\nLogin + davet lookup"]
    end

    subgraph org_indexes["organizations — index'ler"]
        OI1["idx_organizations_slug\n(slug)\nSwitch-org + routing"]
    end

    subgraph om_indexes["organization_members — index'ler"]
        OMI1["idx_org_members_org_id\n(organization_id)\nÜye listesi"]
        OMI2["idx_org_members_user_id\n(user_id)\nKullanıcının org'ları"]
        OMI3["UNIQUE(org_id, user_id)\nTekrar üye engeli"]
    end

    subgraph rt_indexes["refresh_tokens — index'ler"]
        RTI1["idx_refresh_tokens_user_id\n(user_id)\nToplu revoke"]
        RTI2["idx_refresh_tokens_token_hash\n(token_hash)\nToken lookup"]
    end

    subgraph pr_indexes["password_resets — index'ler"]
        PRI1["idx_password_resets_token_hash\n(token_hash)\nReset lookup"]
        PRI2["idx_password_resets_user_id\n(user_id)\nÖnceki token geçersiz kılma"]
    end

    subgraph inv_indexes["organization_invitations — index'ler"]
        II1["idx_invitations_token_hash\n(token_hash)\nDavet kabul akışı"]
        II2["idx_invitations_email\n(email)\nPending davet kontrolü"]
        II3["UNIQUE(org_id, email)\nTekrar davet engeli"]
    end
```

---

## 4. Alembic Migration Akışı

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as alembic CLI
    participant ENV as alembic/env.py
    participant PG as PostgreSQL

    Dev->>CLI: alembic upgrade head
    CLI->>ENV: env.py'yi çalıştır
    ENV->>ENV: DATABASE_URL oku (os.getenv)
    ENV->>PG: Async engine oluştur
    PG-->>ENV: Bağlantı hazır
    ENV->>PG: alembic_version tablosu var mı?
    alt İlk kez çalışıyor
        PG-->>ENV: Tablo yok
        ENV->>PG: alembic_version tablosu oluştur
    else Daha önce çalışmış
        PG-->>ENV: Mevcut versiyon: X
    end
    ENV->>CLI: Uygulanacak migration'ları belirle
    CLI->>PG: 0001_initial_schema.py → upgrade() çalıştır
    PG->>PG: 8 tablo oluştur
    PG->>PG: 10 index oluştur
    PG->>PG: Unique constraint'leri ekle
    PG->>PG: alembic_version = "0001" güncelle
    CLI-->>Dev: Done — 1 migration applied
```

---

## 5. SQLAlchemy Model Hiyerarşisi

```mermaid
graph TD
    BASE["Base\n(app.core.database)\nDeclarativeBase"]

    USER["User\n(app.models.user)"]
    ORG["Organization\n(app.models.organization)"]
    ORGM["OrganizationMember\n(app.models.organization)"]
    RT["RefreshToken\n(app.models.auth)"]
    EV["EmailVerification\n(app.models.auth)"]
    PR["PasswordReset\n(app.models.auth)"]
    OI["OrganizationInvitation\n(app.models.auth)"]
    OA["OAuthAccount\n(app.models.auth)"]

    INIT["app/models/__init__.py\nexports all models\n(Alembic için şart)"]

    BASE --> USER
    BASE --> ORG
    BASE --> ORGM
    BASE --> RT
    BASE --> EV
    BASE --> PR
    BASE --> OI
    BASE --> OA

    USER --> INIT
    ORG --> INIT
    ORGM --> INIT
    RT --> INIT
    EV --> INIT
    PR --> INIT
    OI --> INIT
    OA --> INIT

    style BASE fill:#f59e0b,stroke:#92400e,color:#000
    style INIT fill:#6366f1,stroke:#3730a3,color:#fff
```

---

## 6. M2 Dosya Yapısı

```mermaid
graph LR
    ROOT["backend/"]

    ROOT --> AI["alembic.ini\nDB URL config"]
    ROOT --> AL["alembic/"]
    ROOT --> APP["app/"]

    AL --> ENV["env.py\nAsync migration runner"]
    AL --> MAKO["script.py.mako\nMigration template"]
    AL --> VER["versions/"]
    VER --> V001["0001_initial_schema.py\nupgrade() + downgrade()"]

    APP --> MODELS["models/"]
    APP --> TESTS["tests/"]

    MODELS --> MINIT["__init__.py\nExports all 8 models"]
    MODELS --> MUSER["user.py\nUser model"]
    MODELS --> MORG["organization.py\nOrg + Member models"]
    MODELS --> MAUTH["auth.py\n5 auth models"]

    TESTS --> TINIT["__init__.py"]
    TESTS --> TUNIT["unit/"]
    TUNIT --> TMODELS["test_models.py\nModel validasyon testleri"]

    style ROOT fill:#1e293b,stroke:#475569,color:#fff
    style V001 fill:#4ade80,stroke:#166534,color:#000
```
