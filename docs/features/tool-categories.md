# Tool Kategorileri

**Faz:** F2 · **Etki:** Backend (tool kataloğu + endpoint) + UI (agent formu)

Tool'lar artık kullanıcıya **kategoriler** halinde sunulur. Kategori bazlı tek tek
veya "tümünü seç" ile bir kategorideki tüm tool'lar agent'a verilebilir.

## Kategoriler

| Kategori | Tool'lar | Yönetim |
|---|---|---|
| **Dosya** (`file`) | write/read/modify/delete_file, list_files, make_directory, search_files, move_file, remove_folder | **Auto-managed** — "Dosya sistemi" anahtarıyla gelir; tek tek seçilmez |
| **Web** (`web`) | `web_search`, `read_url` | Tek tek seçilebilir |
| **Ajan araçları** (`self`) | `think`, `write_todos`, `ask_user` | Tek tek seçilebilir |
| **Finans** (`finance`) | — | Boş çerçeve (yakında: MCP / public API tool'ları) |
| **Operasyon** (`operation`) | — | Boş çerçeve (yakında: e-posta/dökümanlar, OAuth gerektirir) |

## İç (internal) tool'lar — gizli

Şu tool'lar **kayıtlı kalır** (testler + iç kullanım için çalışır) ama agent
formunda / `/agents/tools` listesinde **görünmez** ve kullanıcı seçemez:

`echo`, `calculator` (model zaten hesaplar), `save_note`/`get_notes` (dosya
sistemi karşılıyor), `summarize` (model zaten özetler), `call_agent` (çok-agent,
F8'e kadar gizli). Skill tool'ları (`list_skills`/`read_skill`) da auto-managed
(skill tanımlanınca gelir), listede görünmez.

> İç tool'lar SİLİNMEDİ — `tool_names`'e API üzerinden hâlâ eklenebilir (mevcut
> testler `echo` kullanır). Sadece kullanıcı arayüzünden gizlendiler.

## API

```
GET /agents/tools             # seçilebilir tool'lar (her birinde "category" alanı; internal/file/skill hariç)
GET /agents/tool-categories   # kategorize yapı (F2)
```

`tool-categories` yanıtı (her kategori):
```json
{
  "key": "web",
  "label": "Web",
  "note": "İnternette arama ve sayfa okuma",
  "managed_by_file_system": false,
  "coming_soon": false,
  "tools": [{ "name": "web_search", "description": "..." }, ...]
}
```

## UI (agent formu)

`AgentForm` artık kategorize bir araç seçici gösterir:
- **Dosya** kategorisi → "Dosya sistemi" checkbox'ı (açılınca 9 file tool otomatik;
  yıkıcı olanlar varsayılan HITL).
- **Web / Ajan** → başlık + **"Tümünü seç / kaldır"** + tool checkbox'ları + her
  seçili tool için "İnsan onayı (HITL)" alt-seçeneği.
- **Finans / Operasyon** → soluk "yakında" kartı (seçilemez).

## Entegrasyon noktaları

| Katman | Dosya |
|---|---|
| Kategori kataloğu | `backend/app/services/agent/tool_categories.py` |
| Endpoint'ler | `backend/app/api/v1/agents.py` → `list_available_tools`, `list_tool_categories` |
| UI | `frontend/src/components/agent-form.tsx` |
| Tip | `frontend/src/lib/api.ts` → `ToolCategory`, `AgentTool.category` |
| Test | `backend/tests/unit/test_tool_categories.py` |

## Yeni tool nasıl kategorize edilir?

`tool_categories.py` içindeki `CATEGORY_OF`'a `"tool_adı": "kategori"` ekle.
İç (gizli) yapmak için `INTERNAL_TOOLS`'a ekle. File tool'ları otomatik `file`
kategorisindedir (FILE_TOOL_NAMES).
