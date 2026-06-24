# Sprint Sonrası / Plan-Dışı Çalışmalar — Genel Bakış

Orijinal yol haritası **F1–F8** ile bitti. Bu doküman, ondan sonra (kullanıcı
istekleri + `/loop` oturumları) eklenen **her şeyi** tek yerde özetler. Her madde
tam entegredir (backend + DB/migration + UI + test + doküman).

> Migration aralığı: **0014 → 0028**. Test sayısı: **559 geçer**. Tool kataloğu: **10 kategori**.

---

## 1. Gmail & Google (kullanıcı OAuth)

| Özellik | Ne | Migration | Doküman |
|---|---|---|---|
| **G1 Gmail** | OAuth bağlama + `gmail_search/read/send` | 0021 | [gmail-integration](gmail-integration.md), [kurulum](gmail-setup-guide.md) |
| **Google Takvim & Drive (D/#13)** | `calendar_list_events/create_event`, `drive_search/read_file`; Gmail OAuth scope'larına `calendar.events`+`drive.readonly` eklendi | — | [google-workspace](google-workspace.md) |

## 2. Tool kataloğu genişlemesi (kategoriler)

Başlangıçta `file/web/self/finance(boş)/operation(boş)`. Eklenen/doldurulan kategoriler:

| Kategori | Tool'lar | Kaynak | Doküman |
|---|---|---|---|
| **email** | gmail_search/read/send | Google OAuth | [gmail](gmail-integration.md) |
| **finance** | get_crypto_price/ohlc, get_stock_quote/history, get_technical_indicators, get_market_news | CoinGecko + Yahoo + ECB (anahtarsız) | [finance-tools](finance-tools.md) |
| **operation** (Google) | calendar_list_events/create_event, drive_search/read_file | Google OAuth | [google-workspace](google-workspace.md) |
| **messaging** | send_notification (generic webhook) | org Bildirim Kanalı (şifreli) | [notifications](notifications.md) |
| **utility** | get_current_datetime, date_calculate, convert_units, convert_currency | anahtarsız | [utility-tools](utility-tools.md) |
| **database** | sql_query, sql_schema, sql_sample (SALT-OKUNUR) | org DB bağlantısı (şifreli) | [sql-tools](sql-tools.md) |
| **github** | github_search, github_repo_info, github_issues, github_read_file | org GitHub PAT (şifreli) | [github-tools](github-tools.md) |

**web (genişletildi, it.10):** mevcut `web` kategorisine **`read_urls`** (paralel çoklu-URL
okuma — enrichment) + **`read_pdf`** (PDF URL'inden metin, `pypdf`) eklendi.

**Tool ekleme reçetesi:** backend tool dosyası + `main.py` lifespan kaydı +
`tool_categories.py` (CATEGORY_OF + CATEGORIES) + frontend ikon (`agent-form.tsx`).

## 3. Agent ekipleri — genişletmeler

| Özellik | Ne | Migration | Doküman |
|---|---|---|---|
| **Ekip (F8)** | rollü çok-agent (coordinator/planner/researcher/worker/evaluator), delegasyon + paylaşılan pano | 0020 | [agent-teams](agent-teams.md) |
| **Çok-turlu sohbet (B3)** | `conversation_id` ile ekip-sohbeti; Coordinator önceki turları hatırlar; tek-agent layout'u (sidebar+bubble) | 0023 | [agent-teams](agent-teams.md) |
| **Bütçe & limitler** | `max_delegations`, `run_timeout_seconds`, `shared_instructions`; bütçe prompt'a DİNAMİK enjekte edilir | 0024 | [agent-teams](agent-teams.md) |
| **Gözlemlenebilirlik (C)** | üye tool çağrıları + delegasyon timeline'ı (WebSocket canlı) | — | [agent-teams](agent-teams.md) |
| **Trading & Piyasa Analiz Ekibi** | 5 ajan (teknik/haber/temel analist + risk + portföy), Bull/Bear gömülü, finans tool'larıyla — mevcut yapı içinde | — | [finance-tools](finance-tools.md) |

> Keşif: `TeamMember.role` serbest metin → çok-analistli ekiplerde benzersiz rol
> etiketi (technical/news/fundamental) ile rol-başına-1-ajan limiti kod değiştirmeden aşıldı.

## 4. Çekirdek platform özellikleri

| Özellik | Ne | Migration | Doküman |
|---|---|---|---|
| **Özel HTTP tool (B1)** | kullanıcı tanımlı org-bazlı HTTP tool'ları | 0022 | [custom-tools](custom-tools.md) |
| **Dataset'ten suite (B2)** | CSV/JSONL yükle → otomatik test case | — | [dataset-suites](../test-suite/dataset-suites.md) |
| **MCP Registry (D/#2)** | resmi MCP Registry'de ara + tek tıkla sunucu ekle | — | [mcp-integration](mcp-integration.md) |
| **Bildirim Kanalları** | org webhook (şifreli) + `/test` | 0025 | [notifications](notifications.md) |
| **Veritabanı bağlantıları** | org PostgreSQL DSN (şifreli) + salt-okunur sorgu | 0027 | [sql-tools](sql-tools.md) |
| **GitHub bağlantıları** | org GitHub PAT (şifreli) + repo/issue/kod okuma | 0028 | [github-tools](github-tools.md) |
| **Prompt versiyonlama** | agent config'i otomatik snapshot + rollback UI + trace'e prompt_version | 0026 | [prompt-versioning-plan](prompt-versioning-plan.md) |

## 5. Güvenlik desenleri (tutarlı)

- **Şifreleme:** tüm sırlar (provider key, OAuth token, custom-tool header, webhook URL,
  DB DSN) **Fernet** ile şifreli; API yanıtlarında **ham dönmez** (sadece `*_set: bool` / isim).
- **Salt-okunur SQL:** sorgu doğrulama + asyncpg **readonly transaction** + statement_timeout + satır limiti.
- **OAuth scope artışı:** Calendar/Drive eklenince kullanıcı **yeniden bağlanmalı** (Console Data Access + reconnect).
- **Rol bazlı erişim:** config yazma `admin`, listeleme/çalıştırma `member`.

## 6. Süreç notları

- **/loop** oturumu: her 10 dk'da sistemi oku → kategori/özellik ekle → kullanıcıya
  multi-select sorular → uygula → dokümante. 9 iterasyon (finance, trading, Google,
  messaging, prompt-versioning tasarım + kurulum, utility, SQL, GitHub).
- **Bug-hunt:** Explore alt-ajanları tekrar tekrar yanlış pozitif üretti (idempotent
  `tracer.end`, kasıtlı best-effort `except`, async `await db.delete` doğrudur). Kod tabanı
  defansif yazıldığından recurring bug-tarama kaldırıldı; doğrulanmış tek gerçek düzeltme:
  `test-suites/new` yerel `cn()` kopyası → `@/lib/utils` import.
- İlgili anılar: [[test-pollutes-dev-db]] (entegrasyon testleri dev DB'ye yazıyor).
