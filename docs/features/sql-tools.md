# Veritabanı & SQL Tool'ları (Database kategorisi)

**Küme:** loop it.8 · **Kategori:** `database` · **Kalıcılık:** `db_connections`
tablosu (migration `0027`).

Org-bazlı **PostgreSQL bağlantısı**: DSN (`postgresql://user:pass@host/db`) **Fernet
ile şifreli** saklanır; agent'lar **SALT-OKUNUR** sorgular için kullanır.

| Tool | Ne yapar |
|------|----------|
| `sql_query` | Verilen tek **SELECT/WITH** ifadesini salt-okunur çalıştırır (≤50 satır) |
| `sql_schema` | public şemadaki tabloları + sütun/tiplerini listeler (keşif) |
| `sql_sample` | Bir tablodan örnek satırlar (`SELECT * … LIMIT n`) |

## Güvenlik (katmanlı)

1. **Sorgu doğrulama:** yalnız tek bir `SELECT`/`WITH` ifadesi (';' ile çoklu ifade reddedilir,
   yazma anahtar kelimeleri reddedilir).
2. **DB seviyesi:** sorgu `asyncpg` **readonly transaction** içinde çalışır → INSERT/UPDATE/DELETE
   DDL DB tarafından reddedilir (uygulama hatası olsa bile yazma imkânsız).
3. **statement_timeout = 8sn** + **satır limiti (≤50)** → kaçak/ağır sorgu engellenir.
4. `sql_sample` tablo adı identifier regex'iyle doğrulanır (enjeksiyon yok).
5. DSN şifreli; API'de ham dönmez (`DbConnResponse`'ta `dsn` yok).

## Entegrasyon

| | Yer |
|---|---|
| Model | `app/models/db_connection.py` + migration `0027` |
| Tool'lar | `app/services/agent/tools/sql.py` (`_run_readonly`, 3 tool) |
| API | `app/api/v1/db_connections.py` (CRUD + `/test` → canlı `SELECT 1`) |
| Kategori | `tool_categories.py` (`database`) |
| UI | `frontend/src/app/(app)/db-connections/page.tsx` + nav (Veritabanları) + agent-form ikon (Database) |
| Test | `tests/unit/test_sql.py` (doğrulama), `tests/integration/test_db_connections.py` (canlı CRUD+test) |

Motor: şimdilik **PostgreSQL** (asyncpg — yeni bağımlılık yok). İleride MySQL (aiomysql) eklenebilir.
