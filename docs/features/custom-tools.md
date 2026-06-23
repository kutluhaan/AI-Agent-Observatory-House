# Kullanıcı Tanımlı HTTP Tool'ları

**Faz:** B1 (#1) · **Kalıcılık:** `custom_tools` (org bazlı, migration `0022`).
Header'lar **Fernet ile şifreli**; yanıtta yalnız anahtar adları döner, değerler gizli.

Kullanıcı kendi HTTP endpoint'ini bir **tool** olarak tanımlar; agent oluştururken
seçer. Org genelinde paylaşılır. Kod çalıştırma yok — güvenli, sadece HTTP.

## Tanım

| Alan | Açıklama |
|---|---|
| `name` | LLM'e görünen tool adı (`[a-zA-Z0-9_-]`, yerleşik/ayrılmış adlarla çakışamaz) |
| `description` | LLM'in ne zaman çağıracağını anlaması için |
| `method` | GET / POST / PUT / PATCH / DELETE |
| `url` | `{param}` placeholder içerebilir (argümanlardan doldurulur) |
| `headers` | Statik header'lar (JSON) — Fernet şifreli (auth anahtarları için) |
| `parameters` | **JSON Schema** (object) — LLM bu alanları doldurur |
| `timeout_seconds` | 1–120 |

## Çalışma

`call_custom_tool`: argümanları işler →
- URL'deki `{param}` placeholder'lar argümanlardan doldurulur,
- kalan argümanlar **GET/DELETE** → query string, **POST/PUT/PATCH** → JSON gövde,
- statik header'lar (çözülmüş) eklenir,
- yanıt metni döner (4000 karaktere kırpılır); HTTP ≥400 ise `[custom tool HTTP {kod}]`.

Runner entegrasyonu MCP ile aynı desende: agent'ın `custom_tool_ids`'i
`resolve_agent_custom_tools` ile çözülür → `AgentRunner(http_tools=...)` →
`_http_definitions()` LLM'e tool olarak sunar → `_execute_tool` adıyla yakalar →
`call_custom_tool`. Chat/run + test + ekip yollarının hepsinde aktif.

## API

```
POST   /custom-tools            — oluştur (admin)
GET    /custom-tools            — listele (member; header değerleri gizli)
PATCH  /custom-tools/{id}       — güncelle (admin)
DELETE /custom-tools/{id}       — sil (admin)
POST   /custom-tools/{id}/test  — örnek argümanlarla GERÇEKTEN çağır (deneme)
```

Agent: `custom_tool_ids: ["uuid", ...]` (create/update). UI'da agent formunda
**Özel araçlar** bölümünden checkbox ile seçilir.

## UI
- **Özel Araçlar** sayfası (üst nav): tool ekle (ad/metot/URL/header JSON/parametre
  JSON Schema), listele, **Test et** (örnek argüman → canlı sonuç), sil.
- Agent formunda seçim; seçilen tool'lar o agent'a verilir.

## Güvenlik
- Header değerleri Fernet ile şifreli, yanıtta dönmez (`header_names` sadece anahtarlar).
- Ad çakışma koruması (yerleşik tool'ları gölgeleyemez).
- Yalnız admin oluşturur/değiştirir; member listeler/test eder.

## Entegrasyon noktaları
| | Dosya |
|---|---|
| Model | `app/models/custom_tool.py` + `agents.custom_tool_ids` (migration `0022`) |
| Çalıştırıcı | `app/services/agent/custom_tools.py` (`call_custom_tool`, `resolve_agent_custom_tools`) |
| Runner | `app/services/agent/runner.py` (`http_tools`, `_http_definitions`, routing) |
| API | `app/api/v1/custom_tools.py` |
| UI | `frontend/src/app/(app)/custom-tools/page.tsx` + agent formu + nav |
| Test | `backend/tests/unit/test_custom_tools.py`, `tests/integration/test_custom_tools.py` |
