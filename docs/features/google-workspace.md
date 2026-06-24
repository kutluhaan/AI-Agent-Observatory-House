# Google Takvim & Drive Tool'ları

**Küme:** D/#13 · **Kategori:** `operation` ("Takvim & Drive (Google)") · **Kalıcılık:** kod
(tool kaydı) + Gmail OAuth altyapısı (`ServiceConnection`).

Gmail (G1) ile **aynı altyapı**: kullanıcının bağladığı Google hesabı + otomatik token
yenileme. 4 tool, `backend/app/services/agent/tools/google_workspace.py`:

| Tool | Ne yapar | Google API |
|------|----------|-----------|
| `calendar_list_events` | Yaklaşan takvim etkinliklerini listele (zaman/başlık/konum) | Calendar v3 `events` |
| `calendar_create_event` | Etkinlik oluştur (summary + RFC3339 start/end) | Calendar v3 `events` (POST) |
| `drive_search` | Drive'da dosya ara (ad + tam metin) | Drive v3 `files` |
| `drive_read_file` | Dosya metnini oku (Google Docs → text export) | Drive v3 `files/export` veya `alt=media` |

## ⚠️ Yeni izinler — yeniden bağlanma gerekir

Bu tool'lar **yeni OAuth scope'ları** ister (`google_oauth.GMAIL_SCOPES`'a eklendi):
- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/drive.readonly`

**Mevcut Google bağlantıları bu izinlere sahip değil.** Kullanıcı:
1. **Google Cloud Console** → OAuth consent screen → **Data Access** → bu iki scope'u ekle
   (testing modunda doğrulama gerekmez, ≤100 kullanıcı).
2. Uygulamada **Bağlantılar → Google'ı KOPAR → yeniden bağla** (yeni izin ekranını onayla).

İzin yoksa tool'lar net bir uyarı döner: *"yetersiz izin — Bağlantılar'dan Google'ı kopar ve yeniden bağla"*.

## Entegrasyon

| | Yer |
|---|---|
| Tool'lar | `app/services/agent/tools/google_workspace.py` (`register_google_tools`) |
| Scope'lar | `app/services/connections/google_oauth.py` (`GMAIL_SCOPES`) |
| Kayıt | `app/main.py` lifespan (gmail'in yanında) |
| Kategori | `tool_categories.py` (`operation`, artık `coming_soon=False`) |
| UI ikon | `frontend/src/components/agent-form.tsx` (`CalendarClock`) |
| Test | `backend/tests/unit/test_google_workspace.py` |

Not: `calendar_create_event` bir **yazma** işlemidir ama gmail_send gibi varsayılan
HITL'siz akar; istenirse agent'ın `hitl_tool_names`'ine eklenebilir.
