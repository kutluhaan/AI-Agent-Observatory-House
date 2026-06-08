# M2 — DB Şeması + Migrations

**Milestone hedefi:** Auth sisteminin ihtiyaç duyduğu tüm tablolar PostgreSQL'de oluşur.
`alembic upgrade head` komutu çalıştırıldığında 8 tablo, index'ler, CHECK constraint'ler ve `updated_at` trigger'ları hazır olur.

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
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── app/
│   └── models/
│       ├── __init__.py
│       ├── user.py
│       ├── organization.py
│       └── auth.py
└── tests/
    ├── unit/
    │   └── test_models.py
    └── integration/
        └── test_migrations.py
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

`users.email` için ayrı bir index yok — `UNIQUE` constraint yeterli (login lookup).

| Index                               | Tablo                    | Sorgu / Gerekçe                               |
| ----------------------------------- | ------------------------ | --------------------------------------------- |
| `idx_organizations_slug`            | organizations            | Switch-org, URL routing — `WHERE slug = ?`    |
| `idx_org_members_org_id`            | organization_members     | Org üye listesi — `WHERE organization_id = ?` |
| `idx_org_members_user_id`           | organization_members     | Kullanıcının org'ları — `WHERE user_id = ?`   |
| `idx_refresh_tokens_user_id`        | refresh_tokens           | Toplu revoke — `WHERE user_id = ?`            |
| `idx_refresh_tokens_token_hash`     | refresh_tokens           | Token lookup — `WHERE token_hash = ?`         |
| `idx_password_resets_token_hash`    | password_resets          | Reset token lookup                            |
| `idx_password_resets_user_id`       | password_resets          | Önceki token'ları geçersiz kılma              |
| `idx_invitations_token_hash`        | organization_invitations | Davet kabul akışı                             |
| `idx_invitations_email`             | organization_invitations | Pending davet kontrolü                        |
| `uq_org_invitation_pending_email`   | organization_invitations | Partial UNIQUE — sadece `status = 'pending'`  |


---

## Unique Constraint'ler


| Constraint                          | Tablo                | Gerekçe                                       |
| ----------------------------------- | -------------------- | --------------------------------------------- |
| `uq_users_email` (`email`)        | users                | Aynı email ile iki hesap açılamaz             |
| `uq_organizations_slug` (`slug`)  | organizations        | Her org URL'i benzersiz olmalı                |
| `uq_org_member`                     | organization_members | Aynı kullanıcı aynı org'da iki kez üye olamaz |
| `uq_oauth_provider_id`              | oauth_accounts       | Aynı provider hesabı iki kullanıcıya bağlanamaz |

Davet tekrarı `uq_org_invitation_pending_email` partial index ile engellenir (yukarıdaki index tablosuna bak).

---

## CHECK Constraint'ler


| Constraint             | Tablo                    | Kural                                                      |
| ---------------------- | ------------------------ | ---------------------------------------------------------- |
| `ck_org_member_role`   | organization_members     | `role IN ('owner', 'admin', 'member')`                     |
| `ck_invitation_role`   | organization_invitations | `role IN ('admin', 'member')`                              |
| `ck_invitation_status` | organization_invitations | `status IN ('pending', 'accepted', 'expired', 'cancelled')` |
| `ck_oauth_provider`    | oauth_accounts           | `provider IN ('google', 'github')`                         |


---

## updated_at Trigger'ları

`users`, `organizations` ve `oauth_accounts` tablolarında PostgreSQL trigger ile `updated_at` otomatik güncellenir:

- Fonksiyon: `set_updated_at()`
- Trigger adları: `tr_{table}_updated_at` (BEFORE UPDATE)

Modellerde `onupdate` kullanılmaz — tek mekanizma DB trigger'ıdır.

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
8 tablo + index'ler + CHECK'ler + updated_at trigger'ları oluşur
          ↓
alembic_version tablosuna "0001" yazılır
```

---

## Tamamlanma Kriterleri

- `alembic downgrade base` ardından `alembic upgrade head` hatasız çalışır
- Model unit testleri geçer
- Integration testleri geçer (8 tablo, alembic head, partial unique index)

---

## M2 Doğrulama (repo kökünden)

M2'nin sağlıklı olduğunu doğrulamak için **3 komut** yeterlidir. Her komut farklı bir katmanı test eder; hepsi geçerse milestone tamamlanmış kabul edilir.

Tüm komutlar **repository kökünden** çalıştırılır (`cd backend` gerekmez). Container içindeki çalışma dizini zaten `/app` (backend).

### Ön koşullar

1. **`.env` dosyası** repo kökünde mevcut olmalı (`docker-compose.dev.yml` bunu okur).
2. **Dev stack ayakta olmalı** — `exec` çalışan container gerektirir; stack kapalıysa komutlar başlamadan hata verir:

   ```bash
   docker compose -f docker-compose.dev.yml up --build -d
   ```

   İlk kurulumda veya `backend/pyproject.toml` dev bağımlılıkları değiştiyse `--build` şarttır (paketler image build sırasında kurulur; sadece `up -d` yetmez).

3. **`POSTGRES_PASSWORD`** URL-safe olmalı (`!`, `?`, `@` gibi karakterler `DATABASE_URL` içinde asyncpg bağlantı hatasına yol açabilir). Şifre değiştirdikten sonra Postgres volume eski şifreyle kalmışsa: `down -v` ardından tekrar `up --build -d`.

### Doğrulama komutları

| # | Komut | Ne doğrular |
|---|--------|-------------|
| 1 | Migration downgrade + upgrade | Alembic `0001` migration'ı ileri-geri uygulanabilir; tablolar, index'ler, CHECK'ler, trigger'lar oluşur |
| 2 | `pytest tests/unit/` | SQLAlchemy model metadata — tablo adları, unique/CHECK constraint'ler, partial index tanımı (DB bağlantısı gerekmez) |
| 3 | `pytest tests/integration/ -m integration` | Canlı PostgreSQL — 8 auth tablosu, `alembic_version = 0001`, partial unique index predicate |

#### 1. Migration ileri-geri döngüsü

Alembic'in `downgrade base` ve `upgrade head` ile şemayı sıfırlayıp yeniden kurabildiğini doğrular.

```bash
docker compose -f docker-compose.dev.yml exec backend sh -c "alembic downgrade base && alembic upgrade head"
```

**Beklenen:** Traceback yok. Son satırda `Running upgrade -> 0001, initial schema` görünür. Zaten base'deyse downgrade sessiz no-op olabilir.

#### 2. Model metadata (unit)

Modellerin spec ile uyumlu tanımlandığını doğrular; PostgreSQL'e bağlanmaz.

```bash
docker compose -f docker-compose.dev.yml exec backend pytest tests/unit/ -v
```

**Beklenen:** `51 passed` (veya güncel test sayısı kadar passed), `0 failed`.

#### 3. Canlı PostgreSQL şeması (integration)

Gerçek veritabanında migration sonucunu doğrular.

```bash
docker compose -f docker-compose.dev.yml exec backend pytest tests/integration/ -v -m integration
```

**Beklenen:** `4 passed` — tablolar mevcut, alembic head `0001`, `uq_org_invitation_pending_email` partial unique index aktif.

### Tek seferde geçti mi?

Üç komutun çıktısında hata / `FAILED` yoksa **M2 tamam**. Migration'ı yalnızca ilk kurulumda veya şema değişikliğinde uygulamak için:

```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

---

## Sonraki Adım

M2 tamamlandıktan sonra M3 (Auth Core) bu tabloları kullanmaya başlar — **M3 implementasyonu tamamlandı**. Ayrıntılar: [m3-auth-core.md](./m3-auth-core.md)

- `users` → register/login/`/me`
- `refresh_tokens` → login/logout (rotation M4)
- `email_verifications` → register (verify M4)
- `password_resets` → şifre sıfırlama (M4+)
