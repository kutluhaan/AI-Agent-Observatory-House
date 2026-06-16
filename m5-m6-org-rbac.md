# M5 + M6 — Org Yönetimi, Davet Sistemi ve RBAC

**M5 Hedefi:** Org yönetimi ve link tabanlı davet sistemi çalışır.
**M6 Hedefi:** Tüm endpoint'ler role göre korunur, tek satırla yetki kontrolü yapılır.

M5 ve M6 birlikte implement edildi çünkü org endpoint'leri RBAC olmadan yarım kalır.

---

## M1–M4'ten Gelen Taban

| Dosya | Kullanımı |
|---|---|
| `app/models/organization.py` | `Organization`, `OrganizationMember` |
| `app/models/auth.py` | `OrganizationInvitation` |
| `app/api/deps.py` | `CurrentUser`, `get_current_user` |
| `app/core/email.py` | Davet emaili |
| `app/services/jwt_service.py` | Token üretimi |

---

## M5+M6'da Eklenen Dosyalar

```
backend/
└── app/
    ├── api/
    │   ├── deps.py                    ← GÜNCELLEME: TenantContext + RBAC eklendi
    │   └── v1/
    │       └── organizations.py       ← YENİ: tüm org + davet endpoint'leri
    └── schemas/
        └── organizations.py           ← YENİ: org Pydantic schema'ları
tests/
├── unit/
│   └── test_rbac.py                   ← YENİ: RBAC unit testleri
└── integration/
    └── test_org_endpoints.py          ← YENİ: org + davet integration testleri
```

---

## M6 — RBAC Permission Matrisi

Spec'ten birebir:

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
| Agent çalıştır | ✅ | ✅ | ✅ |
| HITL onay ver | ✅ | ✅ | ✅ |

Role hiyerarşisi: `owner > admin > member`

---

## M5 Endpoint'leri

| Method | Path | Min Rol |
|---|---|---|
| POST | `/organizations` | authenticated |
| GET | `/organizations/{org_id}` | member |
| PATCH | `/organizations/{org_id}` | admin |
| DELETE | `/organizations/{org_id}` | owner |
| GET | `/organizations/{org_id}/members` | member |
| PATCH | `/organizations/{org_id}/members/{user_id}` | owner |
| DELETE | `/organizations/{org_id}/members/{user_id}` | owner |
| POST | `/organizations/{org_id}/invitations` | owner |
| DELETE | `/organizations/{org_id}/invitations/{invitation_id}` | owner |
| POST | `/invitations/{token}/accept` | authenticated |

---

## Davet Sistemi Akışı

```
Owner → POST /organizations/{org_id}/invitations
             ↓
    DB'ye OrganizationInvitation kaydı (status=pending)
    Redis'e auth:invite:{hash} → invitation_id
    Email'e link: /invitations/{raw_token}/accept
             ↓
Davet edilen kişi linke tıklar
    Email kayıtlı → login sayfasına (token query param ile)
    Email kayıtsız → register sayfasına (token query param ile)
             ↓
POST /invitations/{token}/accept
    Email eşleşmesi kontrol
    OrganizationMember oluştur
    Invitation status=accepted
```

---

## Tamamlanma Kriterleri

- [ ] Org oluşturma → owner üyeliği otomatik eklenir
- [ ] Slug unique kontrolü çalışıyor
- [ ] Davet linki gönderiliyor
- [ ] Davet kabul → org'a üye oluyor
- [ ] Email mismatch → 403
- [ ] Owner dışı member davet gönderemiyor → 403
- [ ] Member admin endpoint'ine erişemiyor → 403
- [ ] Owner her endpoint'e erişebiliyor
- [ ] Tüm testler geçiyor
