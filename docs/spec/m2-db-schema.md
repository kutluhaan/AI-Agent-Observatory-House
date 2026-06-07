# M2 — DB Şeması + Migrations

**Milestone hedefi:** Auth sisteminin ihtiyaç duyduğu tüm tablolar PostgreSQL'de oluşur.
`alembic upgrade head` komutu çalıştırıldığında 8 tablo ve tüm index'ler hazır olur.

---

## M1'den Gelen Taban

M2, M1'in üzerine inşa edilir. M1'den gelen ve M2'de kullanılan bileşenler:


| M1 Dosyası             | M2'de Kullanımı                            |
| ---------------------- | ------------------------------------------ |
| `app/core/database.py` | `Base` class — tüm modeller buradan türer  |
| `app/core/config.py`   | `DATABASE_URL` — Alembic bu URL'i kullanır |
| `pyproject.toml`       | SQLAlchemy, asyncpg, alembic zaten tanımlı |


---

## M2'de Eklenen Dosyalar

```
backend/
├── alembic.ini                          ← Alembic config (root)
├── alembic/
│   ├── env.py                           ← Async migration runner
│   ├── script.py.mako                   ← Migration template
│   └── versions/
│       └── 0001_initial_schema.py       ← İlk migration
└── app/
    ├── models/
    │   ├── __init__.py                  ← Tüm modelleri export eder
    │   ├── user.py                      ← users tablosu
    │   ├── organization.py              ← organizations + organization_members
    │   └── auth.py                      ← refresh_tokens, email_verifications,
    │                                       password_resets, organization_invitations,
    │                                       oauth_accounts
    └── tests/
        ├── __init__.py
        └── unit/
            └── test_models.py           ← Model validasyon testleri
```

---

## M1'de Değişen Dosyalar

### `app/core/database.py` — Değişmez

M1'den gelen haliyle kullanılır. `Base` class zaten tanımlı.

### `app/main.py` — Küçük ekleme

Startup log'una DB bağlantı bilgisi eklenir. Tablo oluşturma yapılmaz — bu Alembic'in işi.

---

## 8 Tablo ve Aralarındaki İlişkiler

```
users (merkez tablo)
  ├── organization_members (users ←→ organizations)
  ├── refresh_tokens (token rotation)
  ├── email_verifications (kayıt doğrulama)
  ├── password_resets (şifre sıfırlama)
  └── oauth_accounts (Faz 4 — şimdiden hazır)

organizations
  ├── organization_members (users ←→ organizations)
  └── organization_invitations (davet sistemi)
```

### Cascade Davranışları


| İlişki                                      | Cascade            | Gerekçe                                            |
| ------------------------------------------- | ------------------ | -------------------------------------------------- |
| user → organization_members                 | DELETE CASCADE     | Kullanıcı silinince üyelikleri de silinir          |
| user → refresh_tokens                       | DELETE CASCADE     | Kullanıcı silinince token'ları da silinir          |
| user → email_verifications                  | DELETE CASCADE     | Kullanıcı silinince doğrulama kayıtları da silinir |
| user → password_resets                      | DELETE CASCADE     | Kullanıcı silinince reset kayıtları da silinir     |
| user → oauth_accounts                       | DELETE CASCADE     | Kullanıcı silinince OAuth bağlantıları da silinir  |
| organizations → organization_members        | DELETE CASCADE     | Org silinince üyelikler de silinir                 |
| organizations → organization_invitations    | DELETE CASCADE     | Org silinince davetler de silinir                  |
| organizations.created_by → users            | RESTRICT (default) | Org sahibi silinemez, önce org silinmeli           |
| organization_invitations.invited_by → users | RESTRICT (default) | Daveti gönderen silinemez                          |


---

## Index Stratejisi

Her index neden var, hangi sorgu için:


| Index                            | Tablo                    | Sorgu                                         |
| -------------------------------- | ------------------------ | --------------------------------------------- |
| `idx_users_email`                | users                    | Login, davet kontrolü — `WHERE email = ?`     |
| `idx_organizations_slug`         | organizations            | Switch-org, URL routing — `WHERE slug = ?`    |
| `idx_org_members_org_id`         | organization_members     | Org üye listesi — `WHERE organization_id = ?` |
| `idx_org_members_user_id`        | organization_members     | Kullanıcının org'ları — `WHERE user_id = ?`   |
| `idx_refresh_tokens_user_id`     | refresh_tokens           | Toplu revoke — `WHERE user_id = ?`            |
| `idx_refresh_tokens_token_hash`  | refresh_tokens           | Token lookup — `WHERE token_hash = ?`         |
| `idx_password_resets_token_hash` | password_resets          | Reset token lookup                            |
| `idx_password_resets_user_id`    | password_resets          | Önceki token'ları geçersiz kılma              |
| `idx_invitations_token_hash`     | organization_invitations | Davet kabul akışı                             |
| `idx_invitations_email`          | organization_invitations | Pending davet kontrolü                        |


---

## Unique Constraint'ler


| Constraint                          | Tablo                    | Gerekçe                                                  |
| ----------------------------------- | ------------------------ | -------------------------------------------------------- |
| `email` UNIQUE                      | users                    | Aynı email ile iki hesap açılamaz                        |
| `slug` UNIQUE                       | organizations            | Her org URL'i benzersiz olmalı                           |
| `(organization_id, user_id)` UNIQUE | organization_members     | Aynı kullanıcı aynı org'da iki kez üye olamaz            |
| `(organization_id, email)` UNIQUE   | organization_invitations | Aynı email'e aynı org'dan iki pending davet gönderilemez |
| `(provider, provider_id)` UNIQUE    | oauth_accounts           | Aynı Google hesabı iki kullanıcıya bağlanamaz            |


---

## Alembic Çalışma Prensibi

```
alembic upgrade head komutu çalıştırılır
          ↓
alembic.ini → DATABASE_URL okunur
          ↓
alembic_version tablosu kontrol edilir (yoksa oluşturulur)
          ↓
Hangi migration'ların uygulanmadığı tespit edilir
          ↓
versions/0001_initial_schema.py içindeki upgrade() çalışır
          ↓
8 tablo + index'ler oluşur
          ↓
alembic_version tablosuna "0001" yazılır
```

### Geri Alma

```bash
alembic downgrade -1    # Bir adım geri
alembic downgrade base  # Sıfırdan başa dön
```

---

## Tamamlanma Kriterleri

- `alembic upgrade head` hatasız çalışır
- 8 tablo PostgreSQL'de görünür
- Tüm index'ler oluşmuştur
- Tüm unique constraint'ler aktiftir
- `alembic downgrade -1` ardından `alembic upgrade head` tekrar çalışır
- Model unit testleri geçer

---

## Sonraki Adım

M2 tamamlandıktan sonra M3 (Auth Core) bu tabloları kullanmaya başlar:

- `users` → register/login
- `refresh_tokens` → token rotation
- `email_verifications` → email doğrulama
- `password_resets` → şifre sıfırlama

