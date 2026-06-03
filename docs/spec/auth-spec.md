# Auth System Specification
## AI Agent Observatory — Multi-Tenant Platform

**Version:** 1.6  
**Status:** Draft  
**Last Updated:** May 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Decisions](#2-architecture-decisions)
3. [Data Models & DB Schema](#3-data-models--db-schema) — 8 tablo (password_resets dahil)
4. [RBAC — Roles & Permissions](#4-rbac--roles--permissions)
5. [API Contract](#5-api-contract) — tüm auth, org, member, invitation endpoint'leri
6. [Token Strategy](#6-token-strategy)
7. [Error Handling Strategy](#7-error-handling-strategy)
8. [Google OAuth Spec (Faz 4)](#8-google-oauth-spec-faz-4)
9. [Invitation System](#9-invitation-system)
10. [Security Constraints](#10-security-constraints) — rate limiting dahil
11. [Testing Stratejisi](#11-testing-stratejisi) — genişletilmiş senaryolar
12. [Out of Scope](#12-out-of-scope)

---

## 1. System Overview

AI Agent Observatory, AI agent'larını test etmek, gözlemlemek ve orkestre etmek için tasarlanmış multi-tenant bir platformdur. Auth sistemi aşağıdaki prensipleri karşılamalıdır:

- Her kullanıcı birden fazla organizasyona üye olabilir
- Her organizasyon tamamen izole — veriler arası sızıntı olmamalı
- Rol bazlı erişim kontrolü (RBAC) her endpoint'te uygulanmalı
- Token yönetimi güvenli, rotation destekli olmalı
- Davet sistemi link tabanlı çalışmalı
- Google OAuth Faz 4'te eklenecek, altyapı buna hazır olmalı

---

## 2. Architecture Decisions

| Karar | Seçim | Gerekçe |
|---|---|---|
| Password hashing | Argon2id | Bcrypt'ten daha modern, memory-hard |
| JWT algoritması | RS256 | Asymmetric key, daha güvenli |
| Access token süresi | 15 dakika | Kısa ömür = düşük risk |
| Refresh token süresi | 7 gün | UX ve güvenlik dengesi |
| Token storage | httpOnly cookie | XSS'e karşı localStorage'dan güvenli |
| Session store | Redis | Hızlı blacklist/whitelist kontrolü |
| DB izolasyon | Shared DB + organization_id | Başlangıç için pratik, sonra migrate edilebilir |
| RBAC mekanizması | FastAPI Dependency | Test edilebilir, tutarlı |
| Hata dili | Sadece İngilizce | Uluslararası kullanım hedefi |
| Org context yönetimi | Token içinde (org_id, role, org_slug) | DB round-trip yok, performans kazanımı |
| Rol değişikliği yansıma süresi | Max 15 dakika | Kabul edilebilir trade-off olarak bilinçli seçildi |

---

## 3. Data Models & DB Schema

### 3.1 users

Platformdaki her kullanıcının temel kimlik tablosu. Auth akışının merkezinde yer alır.

```sql
CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Kullanıcının benzersiz kimliği. JWT'nin "sub" claim'inde kullanılır.
    -- UUID kullanımı; sequential ID'lerin tahmin edilebilirliğinden kaçınır.

    email             VARCHAR(255) UNIQUE NOT NULL,
    -- Login identifier. Davet sisteminde hedef adres olarak da kullanılır.
    -- UNIQUE constraint: aynı email ile iki hesap açılamaz.

    password_hash     VARCHAR(255),
    -- Argon2id ile hashlenmiş şifre. NULL olabilir:
    -- Google OAuth ile kayıt olan kullanıcılar şifre kullanmaz (Faz 4).
    -- NULL kontrolü ile login akışında hangi auth yöntemi kullanılacağı belirlenir.

    is_verified       BOOLEAN DEFAULT FALSE,
    -- Email doğrulama tamamlanana kadar FALSE.
    -- Login sırasında kontrol edilir; FALSE ise EMAIL_NOT_VERIFIED hatası döner.
    -- Doğrulanmamış kullanıcılar platforma erişemez.

    is_active         BOOLEAN DEFAULT TRUE,
    -- Soft delete mekanizması. FALSE yapılınca kullanıcı login yapamaz.
    -- Kullanıcı kaydı fiziksel olarak silinmez; audit trail korunur.
    -- Login sırasında kontrol edilir; FALSE ise ACCOUNT_DISABLED hatası döner.

    full_name         VARCHAR(255),
    -- Görüntüleme adı. UI'da profil, üye listesi ve bildirimler için kullanılır.
    -- NULL olabilir; OAuth kullanıcılarında provider'dan otomatik doldurulur.

    avatar_url        VARCHAR(500),
    -- Profil fotoğrafı URL'i. OAuth'ta provider'dan alınır, manuel de girilebilir.
    -- UI'da avatar bileşeninde kullanılır; NULL ise fallback initial gösterilir.

    last_login_at     TIMESTAMP WITH TIME ZONE,
    -- Her başarılı login'de güncellenir.
    -- Güvenlik auditing ve inaktif hesap tespiti için kullanılır.

    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Hesap oluşturma zamanı. Değiştirilemez.

    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    -- Her UPDATE'te tetiklenen trigger ile güncellenir.
    -- Profil değişikliklerini izlemek için kullanılır.
);

CREATE INDEX idx_users_email ON users(email);
-- Login ve davet akışında email'e göre lookup yapılır. Bu index olmadan full table scan gerekir.
```

---

### 3.2 organizations

Multi-tenant yapının temel birimi. Her tenant bir organization'dır.

```sql
CREATE TABLE organizations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Tenant'ın benzersiz kimliği. JWT access token'ın "org_id" claim'inde tutulur.
    -- Tüm tenant-specific sorgularda WHERE org_id = ? filtresi bu değeri kullanır.

    name         VARCHAR(255) NOT NULL,
    -- Görüntüleme adı. UI'da org seçici, header ve ayarlar sayfasında gösterilir.
    -- Benzersiz olması zorunlu değil — farklı org'lar aynı ismi kullanabilir.

    slug         VARCHAR(100) UNIQUE NOT NULL,
    -- URL-safe benzersiz tanımlayıcı. Yalnızca lowercase harf, rakam ve tire içerebilir.
    -- JWT "org_slug" claim'inde tutulur; frontend routing'de kullanılır: /org/{slug}/dashboard
    -- Bir kez oluşturulunca değiştirilmemeli — tüm URL'ler ve token'lar bu değere bağlı.

    plan         VARCHAR(50) DEFAULT 'free',
    -- Abonelik planı: free | pro | enterprise.
    -- İleride feature flag sistemiyle entegre olacak.
    -- Şu an sadece kayıt altına alınıyor, henüz business logic'te kullanılmıyor.

    is_active    BOOLEAN DEFAULT TRUE,
    -- Org deaktif edilince tüm üyelerin erişimi kesilir.
    -- Tenant Middleware'de kontrol edilir; FALSE ise ORG_DEACTIVATED (403) döner.

    created_by   UUID NOT NULL REFERENCES users(id),
    -- Org'u oluşturan kullanıcı. Otomatik olarak owner rolüyle organization_members'a eklenir.
    -- Kullanıcı silinse dahi kayıt tutmak için ON DELETE RESTRICT (varsayılan) uygulanır.

    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
-- Switch-org ve URL routing'de slug'a göre lookup için kullanılır.
```

---

### 3.3 organization_members

Kullanıcı ile organizasyon arasındaki many-to-many ilişki ve rol bilgisi.
Bir kullanıcı birden fazla org'a farklı rollerle üye olabilir.

```sql
CREATE TABLE organization_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    -- Üyeliğin ait olduğu org. Org silinirse tüm üyelikler de silinir (CASCADE).
    -- Her sorguda WHERE organization_id = ? ile tenant izolasyonu sağlanır.

    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Üye olan kullanıcı. Kullanıcı silinirse üyelikleri de silinir (CASCADE).
    -- /auth/me endpoint'inde kullanıcının tüm org'larını getirmek için JOIN'de kullanılır.

    role            VARCHAR(50) NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    -- Kullanıcının bu org içindeki rolü.
    -- JWT access token'ın "role" claim'ine yazılır; switch-org'da bu tablodan okunur.
    -- CHECK constraint: geçersiz rol değeri DB seviyesinde engellenir.

    joined_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Üyeliğin başladığı zaman. Davet kabul edildiğinde veya org oluşturulduğunda set edilir.
    -- Üye listesi UI'ında ve audit amaçlı kullanılır.

    UNIQUE(organization_id, user_id)
    -- Bir kullanıcı aynı org'da yalnızca bir kez üye olabilir.
    -- Aynı kullanıcıyı iki kez davet etmeye çalışmak ALREADY_MEMBER hatasına yol açar.
);

CREATE INDEX idx_org_members_org_id ON organization_members(organization_id);
-- Org üye listesi getirilirken (GET /organizations/{id}/members) kullanılır.

CREATE INDEX idx_org_members_user_id ON organization_members(user_id);
-- /auth/me endpoint'inde kullanıcının tüm org üyeliklerini getirmek için kullanılır.
```

---

### 3.4 refresh_tokens

Uzun ömürlü refresh token'ların persistent kaydı. Token rotation ve revocation için kullanılır.

```sql
CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Token'ın sahibi. Kullanıcı silinince tüm refresh token'ları da silinir.
    -- "Tüm cihazlardan çıkış yap" özelliğinde WHERE user_id = ? ile toplu revoke yapılır.

    token_hash      VARCHAR(255) NOT NULL,
    -- Refresh token'ın SHA-256 hash'i. Düz token hiçbir zaman DB'ye yazılmaz.
    -- Cookie'den gelen raw token hash'lenip bu değerle karşılaştırılır.
    -- Hash saklanması: DB sızıntısında token'ların kullanılmasını engeller.

    device_info     VARCHAR(500),
    -- İsteği yapan client'ın User-Agent string'i.
    -- Oturum listesi UI'ında "Chrome — MacOS" gibi görüntülemek için kullanılır (Faz 2).
    -- Şu an kayıt altına alınıyor, aktif kullanımda değil.

    ip_address      INET,
    -- Token oluşturulduğundaki client IP adresi.
    -- Güvenlik auditing ve şüpheli aktivite tespiti için kullanılır (Faz 5).
    -- Şu an kayıt altına alınıyor, aktif kullanımda değil.

    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Token'ın geçerlilik süresi: oluşturulma zamanı + 7 gün.
    -- /auth/refresh endpoint'inde bu alan kontrol edilir; geçmişse REFRESH_TOKEN_EXPIRED döner.

    is_revoked      BOOLEAN DEFAULT FALSE,
    -- Token rotation veya logout sırasında TRUE yapılır.
    -- TRUE ise REFRESH_TOKEN_REVOKED hatası döner — token çalınmış olsa dahi kullanılamaz.

    revoked_at      TIMESTAMP WITH TIME ZONE,
    -- Revocation zamanı. is_revoked = TRUE yapılırken set edilir.
    -- Audit ve güvenlik analizi için kullanılır.

    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    -- Token'ın ilk oluşturulma zamanı. Login veya token rotation'da set edilir.
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
-- Kullanıcıya ait tüm token'ları getirmek için (toplu revoke, oturum listesi).

CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
-- /auth/refresh endpoint'inde hash'e göre token lookup için. Her refresh isteğinde kullanılır.
```

---

### 3.5 email_verifications

Kayıt sonrası email doğrulama token'larının yönetimi.

```sql
CREATE TABLE email_verifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Doğrulaması beklenen kullanıcı.
    -- Token kullanıldığında bu user'ın is_verified alanı TRUE yapılır.

    token_hash  VARCHAR(255) NOT NULL,
    -- Email'e gönderilen raw token'ın SHA-256 hash'i.
    -- /auth/verify-email endpoint'inde gelen token hash'lenip bu değerle karşılaştırılır.
    -- Ham token asla DB'de saklanmaz.

    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Token geçerlilik süresi: oluşturulma zamanı + 24 saat.
    -- Süresi geçmiş token kullanılırsa EMAIL_VERIFICATION_EXPIRED hatası döner.
    -- Kullanıcı resend-verification ile yeni token talep edebilir.

    used_at     TIMESTAMP WITH TIME ZONE,
    -- Token başarıyla kullanıldığında set edilir.
    -- NULL ise henüz kullanılmamış; NULL değilse token zaten tüketilmiştir.
    -- Aynı token'ın iki kez kullanılması bu alan ile engellenir.

    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    -- Token oluşturma zamanı. Resend durumunda yeni kayıt oluşturulur.
);
```

---

### 3.6 organization_invitations

Link tabanlı org davet sisteminin kalıcı kaydı.

```sql
CREATE TABLE organization_invitations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    -- Davet edilen org. Org silinirse davetler de silinir.
    -- Kabul akışında kullanıcı hangi org'a ekleneceğini bu field belirler.

    invited_by      UUID NOT NULL REFERENCES users(id),
    -- Daveti gönderen kullanıcı (owner). Audit ve UI'da "X kişisi davet etti" için kullanılır.
    -- ON DELETE RESTRICT (varsayılan): daveti gönderen kullanıcı silinirse
    -- önce davetler iptal edilmelidir.

    email           VARCHAR(255) NOT NULL,
    -- Davet edilen kişinin email adresi.
    -- Kabul akışında giriş yapan kullanıcının email'i ile karşılaştırılır (EMAIL_MISMATCH kontrolü).
    -- Kayıtsız kullanıcılar bu email ile kayıt olmaya yönlendirilir.

    role            VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'member')),
    -- Davet kabul edildiğinde kullanıcıya atanacak rol.
    -- Owner rolüyle davet gönderilemez (CANNOT_INVITE_OWNER).

    token_hash      VARCHAR(255) NOT NULL,
    -- Email'e gönderilen davet linkteki raw token'ın SHA-256 hash'i.
    -- /invitations/{token}/accept endpoint'inde gelen token hash'lenip bu değerle eşleştirilir.

    status          VARCHAR(50) DEFAULT 'pending'
                    CHECK (status IN ('pending', 'accepted', 'expired', 'cancelled')),
    -- Davet durumu:
    -- pending:   Gönderildi, henüz kabul edilmedi.
    -- accepted:  Kullanıcı daveti kabul etti, org'a eklendi.
    -- expired:   expires_at geçti, token artık geçersiz.
    -- cancelled: Owner daveti iptal etti (ileride eklenecek).

    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Davet geçerlilik süresi: oluşturulma zamanı + 7 gün.
    -- Süre dolduktan sonra kabul girişimi INVITATION_EXPIRED hatası döner.

    accepted_at     TIMESTAMP WITH TIME ZONE,
    -- Davet kabul edildiğinde set edilir. Audit ve UI için kullanılır.
    -- NULL ise henüz kabul edilmemiş demektir.

    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(organization_id, email)
    -- Aynı org'a aynı email'e birden fazla pending davet gönderilemez.
    -- INVITATION_ALREADY_PENDING hatasının DB seviyesindeki güvencesi.
    -- Not: accepted/expired davetler bu constraint'i tetiklemez çünkü
    -- yeni davet farklı bir row olarak eklenir.
);

CREATE INDEX idx_invitations_token_hash ON organization_invitations(token_hash);
-- /invitations/{token}/accept endpoint'inde token lookup için. Her kabul isteğinde kullanılır.

CREATE INDEX idx_invitations_email ON organization_invitations(email);
-- Belirli bir email'e ait bekleyen davetleri kontrol etmek için kullanılır.
```

---

### 3.7 oauth_accounts (Faz 4 için — şimdi oluştur, sonra kullan)

Google OAuth entegrasyonu için kullanıcı-provider bağlantı tablosu.
Faz 4'te aktif kullanıma girecek; altyapı şimdiden hazır tutulur.

```sql
CREATE TABLE oauth_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Bu OAuth hesabının bağlı olduğu platform kullanıcısı.
    -- Bir kullanıcı birden fazla provider'a bağlanabilir (Google + GitHub).

    provider        VARCHAR(50) NOT NULL CHECK (provider IN ('google', 'github')),
    -- OAuth provider adı. Faz 4'te önce Google, sonra GitHub eklenecek.
    -- CHECK constraint: desteklenmeyen provider'lar DB seviyesinde engellenir.

    provider_id     VARCHAR(255) NOT NULL,
    -- Provider'ın bu kullanıcıya atadığı benzersiz ID (Google sub, GitHub id).
    -- OAuth callback'inde gelen ID ile mevcut hesap eşleştirmesi bu field ile yapılır.
    -- Aynı Google hesabı iki farklı platform kullanıcısına bağlanamaz (UNIQUE constraint).

    access_token    TEXT,
    -- Provider'dan alınan access token. AES-256 ile şifreli tutulur.
    -- Provider API'larına istek yapmak için kullanılır (Faz 4'te gerekirse).

    refresh_token   TEXT,
    -- Provider'dan alınan refresh token. AES-256 ile şifreli tutulur.
    -- Access token expire olduğunda yenilemek için kullanılır.

    expires_at      TIMESTAMP WITH TIME ZONE,
    -- Provider access token'ının geçerlilik süresi.
    -- Bu zamandan sonra refresh_token ile yenileme yapılması gerekir.

    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- updated_at: token refresh edildiğinde güncellenir.

    UNIQUE(provider, provider_id)
    -- Aynı provider hesabı iki farklı platform kullanıcısına bağlanamaz.
    -- Örneğin aynı Google hesabı hem alice@x.com hem bob@x.com'a bağlanamaz.
);
```

---

---

### 3.8 password_resets

Şifre sıfırlama token'larının yönetimi. `email_verifications` ile aynı prensipte çalışır ama daha kısa TTL ve ek güvenlik önlemleri içerir.

```sql
CREATE TABLE password_resets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Şifresi sıfırlanacak kullanıcı.
    -- Token kullanıldığında bu user'ın password_hash alanı güncellenir.
    -- Şifre sıfırlama başarılı olunca tüm refresh_tokens revoke edilir.

    token_hash  VARCHAR(255) NOT NULL,
    -- Email'e gönderilen raw token'ın SHA-256 hash'i.
    -- /auth/reset-password endpoint'inde gelen token hash'lenip bu değerle karşılaştırılır.
    -- Ham token asla DB'de saklanmaz — DB sızıntısında token kullanılamaz.

    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Token geçerlilik süresi: oluşturulma zamanı + 30 dakika (industry standard).
    -- Kısa TTL: şifre sıfırlama token'ları email verification'dan daha hassas.
    -- Süresi dolmuş token: PASSWORD_RESET_TOKEN_EXPIRED hatası döner.

    used_at     TIMESTAMP WITH TIME ZONE,
    -- Token başarıyla kullanıldığında set edilir.
    -- NULL ise henüz kullanılmamış; NULL değilse token tüketilmiş → PASSWORD_RESET_TOKEN_USED.
    -- Single-use enforcement: aynı token iki kez kullanılamaz.

    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    -- Her forgot-password isteğinde yeni kayıt oluşturulur.
    -- Eski kullanılmamış token'lar geçersiz kılınır (aşağıya bak).
);

CREATE INDEX idx_password_resets_token_hash ON password_resets(token_hash);
-- /auth/reset-password endpoint'inde token lookup için. Her reset isteğinde kullanılır.

CREATE INDEX idx_password_resets_user_id ON password_resets(user_id);
-- Kullanıcıya ait önceki token'ları geçersiz kılmak için kullanılır.
```

**Kritik davranış — önceki token'ların invalidation'ı:**
Kullanıcı birden fazla kez "şifremi unuttum" derse her seferinde yeni token üretilir ve önceki token'lar `used_at = NOW()` yapılarak tüketilmiş sayılır. Böylece yalnızca en son gönderilen link çalışır.

**Şifre sıfırlama sonrası session invalidation:**
Şifre başarıyla sıfırlandıktan sonra kullanıcının tüm cihazlarındaki tüm refresh token'ları revoke edilir (`refresh_tokens` tablosunda `is_revoked = TRUE`). Güvenlik gerekçesi: şifreyi ele geçiren kişi aktif oturumları kullanamamalı.



## 4. RBAC — Roles & Permissions

### 4.1 Rol Tanımları

| Rol | Tanım |
|---|---|
| `owner` | Organizasyonu oluşturan kişi. Tüm yetkiler dahil org silme ve ownership transfer |
| `admin` | Üye yönetimi hariç her şeyi yapabilir |
| `member` | Kaynakları okuyabilir ve agent çalıştırabilir, oluşturamaz/silemez |

### 4.2 Permission Matrisi

| Aksiyon | Owner | Admin | Member |
|---|---|---|---|
| Org ayarlarını görüntüle | ✅ | ✅ | ✅ |
| Org ayarlarını güncelle | ✅ | ✅ | ❌ |
| Org'u sil | ✅ | ❌ | ❌ |
| Üye davet et | ✅ | ❌ | ❌ |
| Üye rolünü değiştir | ✅ | ❌ | ❌ |
| Üyeyi çıkar | ✅ | ❌ | ❌ |
| Proje oluştur/sil | ✅ | ✅ | ❌ |
| Proje görüntüle | ✅ | ✅ | ✅ |
| Agent oluştur/sil | ✅ | ✅ | ❌ |
| Agent çalıştır | ✅ | ✅ | ✅ |
| Test suite oluştur/sil | ✅ | ✅ | ❌ |
| Test çalıştır | ✅ | ✅ | ✅ |
| Trace görüntüle | ✅ | ✅ | ✅ |
| HITL onay ver | ✅ | ✅ | ✅ |
| API key yönet | ✅ | ✅ | ❌ |

### 4.3 FastAPI RBAC Dependency

```python
# Kullanım örneği
@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    ctx: TenantContext = Depends(require_role("admin"))
    #                            ^ owner da dahil, minimum "admin" gerekli
):
    ...

# TenantContext yapısı
@dataclass
class TenantContext:
    user_id: UUID
    email: str
    org_id: Optional[UUID]         # None ise kullanıcının aktif org'u yok
    org_slug: Optional[str]        # None ise org yok — JWT'den direkt okunur, DB round-trip yok
    role: Optional[Literal["owner", "admin", "member"]]  # None ise org context yok
```

---

## 5. API Contract

### 5.1 Global Request/Response Formatı

**Başarılı Response:**
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "uuid"
  }
}
```

**Hatalı Response:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "The email or password you entered is incorrect.",
    "details": {}
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

---

### 5.2 Auth Endpoints

#### POST /auth/register
**Request:**
```json
{
  "email": "user@example.com",
  "password": "min8chars",
  "full_name": "John Doe"
}
```

**Validations:**
- email: valid format, max 255 chars
- password: min 8 chars, en az 1 büyük harf, 1 rakam
- full_name: min 2, max 255 chars

**Response 201:**
```json
{
  "success": true,
  "data": {
    "message": "Registration successful. Please verify your email.",
    "user_id": "uuid"
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `EMAIL_ALREADY_EXISTS` | 409 | Email kayıtlı |
| `INVALID_EMAIL_FORMAT` | 422 | Geçersiz email |
| `PASSWORD_TOO_WEAK` | 422 | Şifre kurallara uymuyor |

---

#### POST /auth/login
**Request:**
```json
{
  "email": "user@example.com",
  "password": "mypassword"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_verified": true
    },
    "organizations": [
      {
        "id": "uuid",
        "name": "My Company",
        "slug": "my-company",
        "role": "owner"
      }
    ]
  }
}
```

**Cookies Set:**
- `access_token`: httpOnly, secure, samesite=lax, 15 dakika
- `refresh_token`: httpOnly, secure, samesite=lax, 7 gün, path=/auth/refresh

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | Email veya şifre hatalı |
| `EMAIL_NOT_VERIFIED` | 403 | Email doğrulanmamış |
| `ACCOUNT_DISABLED` | 403 | Hesap deaktif |

---

#### POST /auth/logout
**Request:** Cookie'ler otomatik gönderilir, body gerekmez.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "message": "Logged out successfully."
  }
}
```
Cookies cleared. Access token blacklist'e alınır, refresh token revoke edilir.

---

#### POST /auth/refresh
**Request:** Sadece `refresh_token` cookie gönderilir (path=/auth/refresh).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "message": "Token refreshed."
  }
}
```
Yeni `access_token` ve `refresh_token` cookie set edilir. Token rotation uygulanır.

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `REFRESH_TOKEN_EXPIRED` | 401 | Refresh token süresi dolmuş |
| `REFRESH_TOKEN_REVOKED` | 401 | Token revoke edilmiş |
| `INVALID_TOKEN` | 401 | Token geçersiz |

---

#### GET /auth/me
**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_verified": true,
    "avatar_url": null,
    "organizations": [
      {
        "id": "uuid",
        "name": "My Company",
        "slug": "my-company",
        "role": "owner"
      }
    ]
  }
}
```

---

#### POST /auth/switch-org
**Auth:** Giriş yapmış herhangi bir kullanıcı

**Request:**
```json
{
  "org_id": "uuid"
}
```

**Akış:**
1. Mevcut access token doğrulanır
2. Kullanıcının hedef orgaya üye olup olmadığı DBden kontrol edilir
3. O orgdaki rolü çekilir
4. Yeni access token üretilir — yeni `org_id`, `org_slug`, `role` ile
5. Refresh token değişmez
6. Yeni access token cookie olarak set edilir

**Response 200:**
```json
{
  "success": true,
  "data": {
    "organization": {
      "id": "uuid",
      "name": "My Company",
      "slug": "my-company"
    },
    "role": "admin"
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `NOT_A_MEMBER` | 403 | Kullanıcı bu orga üye değil |
| `ORGANIZATION_NOT_FOUND` | 404 | Org bulunamadı |

---

#### POST /auth/forgot-password
**Auth:** Gerekmez — giriş yapmamış kullanıcı da kullanabilir.
**Rate limit:** 5 istek / 30 dakika / kullanıcı başına (email bazında)

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Akış:**
1. Email DB'de aranır
2. Kullanıcı bulunursa: 32 byte cryptographically secure random token üretilir
3. Önceki kullanılmamış token'lar geçersiz kılınır (`used_at = NOW()`)
4. Yeni token hash'lenerek `password_resets` tablosuna yazılır (TTL: 30 dakika)
5. Email'e reset linki gönderilir: `https://app.domain.com/reset-password?token={raw_token}`
6. Her durumda aynı response döner (email enumeration koruması)

**Response 200:** (kullanıcı bulunsun ya da bulunmasın)
```json
{
  "success": true,
  "data": {
    "message": "If this email exists, a password reset link has been sent."
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `RATE_LIMIT_EXCEEDED` | 429 | Çok fazla reset isteği |

---

#### POST /auth/reset-password
**Auth:** Gerekmez — token kimliği doğrular.
**Rate limit:** 10 istek / saat / IP başına (brute force koruması)

**Request:**
```json
{
  "token": "raw_reset_token",
  "new_password": "NewSecurePass1!"
}
```

**Validations:**
- new_password: min 8 chars, en az 1 büyük harf, 1 rakam

**Akış:**
1. Token SHA-256 ile hash'lenir, `password_resets` tablosunda aranır
2. Token bulunamazsa → `PASSWORD_RESET_TOKEN_INVALID`
3. `used_at` NULL değilse → `PASSWORD_RESET_TOKEN_USED`
4. `expires_at` geçmişse → `PASSWORD_RESET_TOKEN_EXPIRED`
5. Tüm kontroller geçerse yeni şifre Argon2id ile hash'lenir
6. `users` tablosunda `password_hash` güncellenir
7. `password_resets` tablosunda `used_at = NOW()` yapılır
8. Kullanıcının **tüm** `refresh_tokens` kayıtları revoke edilir
9. Redis'teki tüm `auth:refresh:{jti}` key'leri silinir
10. Response döner — kullanıcı yeniden login olmak zorunda kalır

**Response 200:**
```json
{
  "success": true,
  "data": {
    "message": "Password reset successful. Please log in with your new password."
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `PASSWORD_RESET_TOKEN_INVALID` | 400 | Token bulunamadı |
| `PASSWORD_RESET_TOKEN_EXPIRED` | 410 | Token süresi dolmuş (30 dakika) |
| `PASSWORD_RESET_TOKEN_USED` | 409 | Token daha önce kullanılmış |
| `PASSWORD_TOO_WEAK` | 422 | Yeni şifre kurallara uymuyor |

---

#### POST /auth/verify-email
**Request:**
```json
{
  "token": "raw_verification_token"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "message": "Email verified successfully."
  }
}
```

---

#### POST /auth/resend-verification
**Request:**
```json
{
  "email": "user@example.com"
}
```

**Akış:**
1. Email DB'de aranır
2. Kullanıcı bulunursa ve `is_verified = false` ise:
3. Önceki kullanılmamış verification token'ları geçersiz kılınır (`used_at = NOW()`)
4. Yeni token üretilir, DB'ye yazılır (TTL: 24 saat), Redis'e eklenir
5. Email gönderilir
6. Her durumda aynı response döner (email enumeration koruması)

**Response 200:** Her zaman 200 döner (email enumeration'ı önlemek için)
```json
{
  "success": true,
  "data": {
    "message": "If this email exists, a verification link has been sent."
  }
}
```

---

### 5.3 Organization Endpoints

#### POST /organizations
**Minimum rol:** Authenticated (herhangi bir giriş yapmış kullanıcı)

**Request:**
```json
{
  "name": "My Company",
  "slug": "my-company"
}
```

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "My Company",
    "slug": "my-company",
    "role": "owner",
    "created_at": "2026-05-30T00:00:00Z"
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `SLUG_ALREADY_EXISTS` | 409 | Slug kullanımda |
| `INVALID_SLUG_FORMAT` | 422 | Slug sadece lowercase, rakam, tire içerebilir |

---

#### GET /organizations/{org_id}
**Minimum rol:** member

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "My Company",
    "slug": "my-company",
    "plan": "free",
    "member_count": 5,
    "created_at": "2026-05-30T00:00:00Z"
  }
}
```

---

#### GET /organizations/{org_id}/members
**Minimum rol:** member

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "user_id": "uuid",
      "email": "user@example.com",
      "full_name": "John Doe",
      "role": "owner",
      "joined_at": "2026-05-30T00:00:00Z"
    }
  ]
}
```

---


#### PATCH /organizations/{org_id}
**Minimum rol:** admin

Güncellenebilir alanlar: `name`. `slug` ve `id` değiştirilemez.

**Request:**
```json
{
  "name": "New Company Name"
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "New Company Name",
    "slug": "my-company",
    "plan": "free",
    "updated_at": "2026-05-31T00:00:00Z"
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `ORGANIZATION_NOT_FOUND` | 404 | Org bulunamadı |
| `INSUFFICIENT_PERMISSIONS` | 403 | Admin veya owner değil |

---

#### DELETE /organizations/{org_id}
**Minimum rol:** owner

Hard delete — tüm ilişkili veriler (üyeler, projeler, agent'lar, trace'ler) silinir. Geri alınamaz.

**Response 204:** Body yok.

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `ORGANIZATION_NOT_FOUND` | 404 | Org bulunamadı |
| `INSUFFICIENT_PERMISSIONS` | 403 | Sadece owner silebilir |

**Silme sonrası davranış:**
- Tüm üyelerin bu org'a ait access token'ları geçersiz kılınmaz (15 dakika içinde expire olur)
- Tenant Middleware bir sonraki istekte org'u bulamayınca `ORGANIZATION_NOT_FOUND` döner
- Kullanıcılar başka org'larına geçiş yapabilir veya yeni org oluşturabilir

---

#### DELETE /organizations/{org_id}/invitations/{invitation_id}
**Minimum rol:** owner

Bekleyen daveti iptal eder. Sadece `pending` durumdaki davetler iptal edilebilir.

**Response 204:** Body yok.

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `INVITATION_NOT_FOUND` | 404 | Davet bulunamadı |
| `INVITATION_NOT_CANCELLABLE` | 409 | Davet pending değil (zaten kabul edilmiş veya expired) |

---


### 5.4 Member Management Endpoints

#### PATCH /organizations/{org_id}/members/{user_id}
**Minimum rol:** owner

Bir üyenin rolünü değiştirir. Owner kendi rolünü değiştiremez.

**Request:**
```json
{
  "role": "admin"
}
```

**Validations:**
- role: `admin` veya `member` — `owner` rolüne yükseltilemez
- Kullanıcı kendi rolünü değiştiremez

**Response 200:**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "role": "admin",
    "updated_at": "2026-05-31T00:00:00Z"
  }
}
```

**Not:** Rol değişikliği kullanıcının mevcut access token'ına max 15 dakika içinde yansır (token rotation trade-off).

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `NOT_A_MEMBER` | 404 | Kullanıcı bu org'un üyesi değil |
| `CANNOT_CHANGE_OWNER_ROLE` | 422 | Owner rolü değiştirilemez |
| `CANNOT_CHANGE_OWN_ROLE` | 422 | Kendi rolünü değiştiremezsin |
| `INSUFFICIENT_PERMISSIONS` | 403 | Sadece owner yapabilir |

---

#### DELETE /organizations/{org_id}/members/{user_id}
**Minimum rol:** owner

Bir üyeyi org'dan çıkarır. Owner kendini çıkaramaz.

**Response 204:** Body yok.

**Çıkarma sonrası davranış:**
- Kullanıcının mevcut access token'ı max 15 dakika daha geçerli kalır (trade-off)
- Bir sonraki `/auth/refresh` isteğinde org üyeliği kontrol edilir, `NOT_A_MEMBER` döner
- Kullanıcı başka org'larına geçiş yapabilir veya yeni org oluşturabilir

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `NOT_A_MEMBER` | 404 | Kullanıcı bu org'un üyesi değil |
| `CANNOT_REMOVE_OWNER` | 422 | Owner kendini çıkaramaz |
| `INSUFFICIENT_PERMISSIONS` | 403 | Sadece owner yapabilir |

---

### 5.5 Invitation Endpoints

#### POST /organizations/{org_id}/invitations
**Minimum rol:** owner

**Request:**
```json
{
  "email": "newmember@example.com",
  "role": "member"
}
```

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "newmember@example.com",
    "role": "member",
    "expires_at": "2026-06-06T00:00:00Z"
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `ALREADY_MEMBER` | 409 | Kullanıcı zaten üye |
| `INVITATION_ALREADY_PENDING` | 409 | Bu email'e bekleyen davet var |
| `CANNOT_INVITE_OWNER` | 422 | Owner rolüyle davet edilemez |

---

#### POST /invitations/{token}/accept
**Auth:** Token'ı olan herkes (giriş yapmış olmak zorunlu)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "organization": {
      "id": "uuid",
      "name": "My Company",
      "slug": "my-company"
    },
    "role": "member"
  }
}
```

**Error Codes:**
| Code | HTTP | Açıklama |
|---|---|---|
| `INVITATION_EXPIRED` | 410 | Davet süresi dolmuş |
| `INVITATION_ALREADY_USED` | 409 | Davet kullanılmış |
| `EMAIL_MISMATCH` | 403 | Giriş yapan email ile davet edilen email farklı |

---

## 6. Token Strategy

### 6.1 Access Token Payload (RS256)

**Org'u olan kullanıcı:**
```json
{
  "sub": "user_uuid",
  "email": "user@example.com",
  "org_id": "org_uuid",
  "org_slug": "my-company",
  "role": "owner",
  "type": "access",
  "jti": "unique_token_id",
  "iat": 1748563200,
  "exp": 1748564100
}
```

**Org'u olmayan kullanıcı:**
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

**Not:** `org_id`, `org_slug` ve `role` her zaman JSON'da bulunur — org yoksa `null` gönderilir, field atlanmaz. Frontend null kontrolü yaparak org oluşturma sayfasını gösterir veya gizler. Her request'te DB'ye gidilmez — performans kazanımı sağlanır. Trade-off: rol değişikliği token expire olana kadar (max 15 dakika) yansımaz. Bu kabul edilebilir bir trade-off olarak bilinçli seçilmiştir.

**Org geçişi:** Kullanıcı birden fazla org'a üye olabilir. Aktif org token'da tutulur. Org değiştirmek için `/auth/switch-org` endpoint'i kullanılır — yeni org için yeni access token üretilir, refresh token değişmez.

### 6.2 Refresh Token Payload (RS256)

```json
{
  "sub": "user_uuid",
  "type": "refresh",
  "jti": "unique_token_id",
  "iat": 1748563200,
  "exp": 1749168000
}
```

### 6.3 Redis Key Yapısı

```
# Refresh token whitelist
auth:refresh:{jti} → user_id               TTL: 7 gün

# Access token blacklist (logout sonrası)
auth:blacklist:{jti} → "1"                 TTL: 15 dakika

# Email verification token
auth:email_verify:{token_hash} → user_id   TTL: 24 saat

# Invitation token
auth:invite:{token_hash} → invitation_id   TTL: 7 gün

# Password reset token
auth:pwd_reset:{token_hash} → user_id      TTL: 30 dakika

# Rate limiting (sliding window)
ratelimit:login:{email} → count            TTL: 900 (15 dakika)
ratelimit:register:{ip} → count            TTL: 3600 (1 saat)
ratelimit:forgot_password:{email} → count  TTL: 1800 (30 dakika)
ratelimit:reset_password:{ip} → count      TTL: 3600 (1 saat)
ratelimit:resend_verify:{email} → count    TTL: 3600 (1 saat)
ratelimit:refresh:{user_id} → count        TTL: 60 (1 dakika)
ratelimit:switch_org:{user_id} → count     TTL: 60 (1 dakika)
ratelimit:general:{user_id} → count        TTL: 60 (1 dakika)
```

### 6.4 Token Rotation Akışı

1. Client `/auth/refresh` endpoint'ini çağırır
2. Refresh token doğrulanır, Redis'te varlığı kontrol edilir
3. Eski refresh token Redis'ten silinir, DB'de `is_revoked=true` yapılır
4. Yeni access token ve refresh token üretilir
5. Yeni refresh token Redis'e yazılır, DB'ye kaydedilir
6. Her iki token da cookie olarak set edilir

---

## 7. Error Handling Strategy

### 7.1 HTTP Status Code Kullanımı

| Status | Kullanım |
|---|---|
| 200 | Başarılı GET, PUT, PATCH |
| 201 | Başarılı POST (kaynak oluşturuldu) |
| 204 | Başarılı DELETE (body yok) |
| 400 | Bad request (genel) |
| 401 | Unauthenticated (token yok veya geçersiz) |
| 403 | Unauthorized (token var ama yetki yok) |
| 404 | Kaynak bulunamadı |
| 409 | Conflict (unique constraint ihlali) |
| 410 | Gone (süresi dolmuş kaynak — invitation) |
| 422 | Validation hatası |
| 429 | Rate limit aşıldı |
| 500 | Internal server error |

### 7.2 Tam Error Code Listesi

```
# Auth
INVALID_CREDENTIALS
EMAIL_ALREADY_EXISTS
EMAIL_NOT_VERIFIED
ACCOUNT_DISABLED
INVALID_TOKEN
REFRESH_TOKEN_EXPIRED
REFRESH_TOKEN_REVOKED
INVALID_EMAIL_FORMAT
PASSWORD_TOO_WEAK
EMAIL_VERIFICATION_EXPIRED

# Password Reset
PASSWORD_RESET_TOKEN_INVALID
PASSWORD_RESET_TOKEN_EXPIRED
PASSWORD_RESET_TOKEN_USED

# Organization
ORGANIZATION_NOT_FOUND
SLUG_ALREADY_EXISTS
INVALID_SLUG_FORMAT
NOT_A_MEMBER
INSUFFICIENT_PERMISSIONS
ORG_DEACTIVATED
CANNOT_CHANGE_OWNER_ROLE
CANNOT_CHANGE_OWN_ROLE
CANNOT_REMOVE_OWNER

# Invitation
INVITATION_NOT_FOUND
INVITATION_EXPIRED
INVITATION_ALREADY_USED
INVITATION_ALREADY_PENDING
INVITATION_NOT_CANCELLABLE
ALREADY_MEMBER
EMAIL_MISMATCH
CANNOT_INVITE_OWNER

# General
VALIDATION_ERROR
INTERNAL_SERVER_ERROR
RATE_LIMIT_EXCEEDED
```

### 7.3 Validation Error Formatı

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": {
      "fields": [
        {
          "field": "email",
          "message": "Invalid email format."
        },
        {
          "field": "password",
          "message": "Password must be at least 8 characters."
        }
      ]
    }
  }
}
```

### 7.4 Güvenlik Önlemleri

- Login endpoint'inde hatalı email ve hatalı şifre için **aynı hata mesajı** döner (`INVALID_CREDENTIALS`) — kullanıcı enumeration önlenir
- Resend verification endpoint'i her zaman 200 döner — email enumeration önlenir
- Stack trace hiçbir zaman response'a eklenmez
- 500 hatalarında sadece generic mesaj döner, detay server log'larına yazılır

---

## 8. Google OAuth Spec (Faz 4)

Şu an implementasyon yapılmayacak. Ama altyapı hazır tutulacak:

- `oauth_accounts` tablosu şimdiden oluşturulacak
- `password_hash` NULL olabilir (OAuth kullanıcıları için)
- Auth flow'unda `provider` field'ı genişletilebilir yapıda

**Faz 4'te eklenecek endpoint'ler:**
```
GET  /auth/google              → Google OAuth redirect
GET  /auth/google/callback     → Google callback handler
```

---

## 9. Invitation System

### Akış

1. Owner `/organizations/{org_id}/invitations` endpoint'ini çağırır
2. Backend unique token üretir (32 byte random, URL-safe base64)
3. Token hash'i DB'ye ve Redis'e yazılır (TTL: 7 gün)
4. Davet email'i gönderilir: `https://app.domain.com/invitations/{raw_token}/accept`
5. Davet alan kişi linke tıklar
6. Eğer giriş yapmamışsa login/register sayfasına yönlendirilir, token query param olarak korunur
7. Giriş sonrası `/invitations/{token}/accept` endpoint'i çağrılır
8. Email eşleşmesi kontrol edilir
9. Üyelik oluşturulur, token geçersiz kılınır

### Edge Cases

| Durum | Davranış |
|---|---|
| Davet edilen email zaten kayıtlı | Direkt login'e yönlendir |
| Davet edilen email kayıtsız | Register'a yönlendir, token korunur |
| Token süresi dolmuş | `INVITATION_EXPIRED` hatası, owner'dan yeni davet istenmesi önerilir |
| Aynı email'e tekrar davet | `INVITATION_ALREADY_PENDING` hatası |
| Kullanıcı zaten üye | `ALREADY_MEMBER` hatası |

---

## 10. Security Constraints

| Kural | Detay |
|---|---|
| Argon2id parametreleri | time_cost=2, memory_cost=65536, parallelism=2 |
| JWT signing key | RS256, 2048-bit RSA key pair |
| Private key storage | Environment variable, asla kod içinde değil |
| Cookie flags | httpOnly=true, secure=true, samesite=lax |
| Refresh token cookie path | Sadece `/auth/refresh` — başka endpoint'lere gönderilmez |
| Token hash storage | DB'de düz token değil SHA-256 hash'i tutulur |
| OAuth token storage | DB'de AES-256 ile şifreli tutulur (Faz 4) |
| HTTPS | Production'da zorunlu, development'ta opsiyonel |

### Rate Limiting

Rate limiting kullanıcı bazında (`JWT sub`) uygulanır. Giriş yapmamış istekler için email veya IP bazında uygulanır. Redis'te sliding window algoritması kullanılır.

| Endpoint | Limit | Pencere | Baz |
|---|---|---|---|
| `POST /auth/login` | 10 istek | 15 dakika | email |
| `POST /auth/register` | 5 istek | saat | IP |
| `POST /auth/forgot-password` | 5 istek | 30 dakika | email |
| `POST /auth/reset-password` | 10 istek | saat | IP |
| `POST /auth/resend-verification` | 3 istek | saat | email |
| `POST /auth/refresh` | 30 istek | dakika | user_id |
| `POST /auth/switch-org` | 20 istek | dakika | user_id |
| Diğer korumalı endpoint'ler | 100 istek | dakika | user_id |

**Rate limit aşılınca:**
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "details": {
      "retry_after_seconds": 60
    }
  }
}
```

**Redis key yapısı:**
```
ratelimit:{endpoint_key}:{identifier} → istek sayısı   TTL: pencere süresi
# Örnek:
ratelimit:login:user@example.com → 3                   TTL: 900 (15 dakika)
ratelimit:refresh:user_uuid → 12                       TTL: 60 (1 dakika)
```

---


## 11. Testing Stratejisi

### Araçlar

| Araç | Amaç |
|---|---|
| `pytest` | Backend unit + integration testleri |
| `pytest-asyncio` | Async FastAPI endpoint testleri |
| `httpx` | FastAPI test client (async) |
| `pytest-postgresql` | Test için izole PostgreSQL instance |
| `fakeredis` | Redis mock — gerçek Redis'e gerek yok |
| `respx` | HTTP mock — LLM provider HTTP çağrıları |
| `factory-boy` | Test fixture üretimi (user, org, token) |
| `Playwright` | E2E testleri — tarayıcı üzerinden tam akış |

---

### Test Seviyeleri

#### Unit Testler
Her servis ve utility fonksiyon için. Dış bağımlılık yok — DB, Redis, LLM hepsi mock'lanır.

**Auth için kapsam:**
- `JWTService` — token üretme, doğrulama, expire, blacklist, org context
- `PasswordService` — hash, verify, zayıf şifre reddi
- `RBACDependency` — her rol için her aksiyon doğru mu
- Token rotation mantığı — eski token geçersiz kılındı mı
- Switch-org — yeni token'da doğru org_id ve role var mı

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

async def test_member_role_below_admin_threshold():
    result = rbac.check_permission(role="member", required="admin")
    assert result is False
```

---

#### Integration Testler
Gerçek DB (test instance) ve fakeredis kullanılır. LLM provider'lar mock'lanır. Endpoint'ler HTTP üzerinden test edilir.

**Auth için kapsam:**
- Register → verify → login → refresh → logout tam akışı
- Login sonrası token'da doğru org_id, role, org_slug var mı
- Org'u olmayan kullanıcı login olunca token'da org_id null gelir, korumalı endpoint'lere erişebilir
- Switch-org sonrası yeni token doğru org'u içeriyor mu
- Switch-org — kullanıcı üye olmadığı org'a geçiş yapamazdı (403)
- Refresh token rotation — eski token geçersiz, yeni token çalışıyor
- Süresi dolmuş access token → otomatik /auth/refresh → devam (kullanıcı fark etmez)
- Davet akışı — gönder → kabul et → üye oldu
- Davet linki — giriş yapmadan tıkla → login sayfasına yönlendir → token korunarak kabul
- RBAC — member admin endpoint'ine 403 alıyor
- Email enumeration koruması — resend-verification her zaman 200
- Email enumeration koruması — forgot-password her zaman 200
- Password reset akışı — forgot → reset linki → yeni şifre → tüm oturumlar kapanır
- Süresi dolmuş reset token kullanımı → 410
- Aynı reset token iki kez kullanımı → 409
- Birden fazla cihazda oturum — refresh token'lar bağımsız çalışıyor
- Şifre sıfırlandıktan sonra eski refresh token'lar geçersiz (tüm cihazlar)
- Rate limit — login endpoint'i 10 istekten sonra 429 döner
- Org silme (hard delete) — üyelerin sonraki isteği ORGANIZATION_NOT_FOUND verir
- Invitation iptal — cancelled davet kabul edilemiyor

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
    token = await create_token(role="member")
    response = await client.delete(
        "/projects/some-id",
        cookies={"access_token": token}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

async def test_refresh_token_rotation(client, db):
    old_refresh = await get_refresh_token(client)
    await client.post("/auth/refresh")
    # Eski token artık çalışmamalı
    response = await client.post("/auth/refresh",
        cookies={"refresh_token": old_refresh})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"
```

---

#### E2E Testler
Playwright ile gerçek tarayıcıda tam kullanıcı akışları. Tüm Docker servisleri ayakta olmalı.

**Auth için kapsam:**
- Kullanıcı kayıt olur, email doğrular, giriş yapar
- Org olmadan giriş yapan kullanıcı platforma erişebilir, org oluşturabilir
- Org oluşturur, davet linki gönderir, başka kullanıcı kabul eder
- Davet linki giriş yapmadan tıklanır → login → token korunur → org'a katılır
- Birden fazla org'a üye olan kullanıcı org'lar arası geçiş yapar
- Token expire olunca otomatik refresh gerçekleşir, kullanıcı fark etmez
- Kullanıcı şifresini sıfırlar → tüm cihazlarda oturum kapanır → yeniden login gerekir
- Org silinir → üyelerin bir sonraki isteği hata verir, başka org'a geçiş yapılabilir

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

test("invite flow — owner invites member", async ({ page }) => {
  await loginAs(page, "owner@example.com");
  await page.goto("/settings/members");
  await page.fill('[name="invite-email"]', "newmember@example.com");
  await page.click("text=Send Invite");
  await expect(page.locator(".toast")).toContainText("Invitation sent");
  // Başka tarayıcı context'iyle davet linkini kabul et
  const inviteToken = await getInvitationToken("newmember@example.com");
  const newContext = await browser.newContext();
  const newPage = await newContext.newPage();
  await loginAs(newPage, "newmember@example.com");
  await newPage.goto(`/invitations/${inviteToken}/accept`);
  await expect(newPage).toHaveURL("/dashboard");
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

### Test Yazma Kuralları

- Her yeni fonksiyon için en az 1 happy path + 1 edge case testi
- Hata durumları (401, 403, 404, 409, 410) mutlaka test edilmeli
- Test isimleri ne test ettiğini açıkça söylemeli: `test_member_cannot_delete_project`
- Her test bağımsız çalışmalı — sıra önemli olmamalı
- Auth hata mesajları email enumeration'a yol açmamalı — test edilmeli

---

## 12. Out of Scope

Aşağıdakiler bu spec'te kapsanmamaktadır. İleride ayrı spec'ler oluşturulacak:

- 2FA / TOTP (Faz 5)
- API key yönetimi (Faz 6)
- Audit logging
- Session listesi / cihaz yönetimi (Faz 2)
- GitHub OAuth
- Organization plan yönetimi / billing

---

*Bu spec sprint planlaması ve kod yazımı için temel referans dokümandır. Değişiklikler versiyon numarası güncellenerek yapılır.*
