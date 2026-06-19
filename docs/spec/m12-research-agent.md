# M12 — Personal Research Agent

**Milestone hedefi:** İlk gerçek kullanım senaryosu — araştırma yapan agent. Web arar, sayfa okur, özetler, not alır ve kapsamlı bir rapor üretir.

Bu doküman mevcut implementasyonu belgeler (kod tamam).

---

## Tasarım Kararları

| Karar | Seçim | Gerekçe |
|---|---|---|
| Web arama | Tavily AI (`AsyncTavilyClient`, `search_depth="basic"`) | 1 kredi/arama, hızlı, LLM dostu sonuç |
| URL okuma | `httpx` async fetch + `trafilatura` extraction | Reklam/nav temizlenir; Tavily extract'a düşmez (kredi tasarrufu) |
| Özetleme | **LLM'siz** TF-tabanlı extractive | Sıfır ek API çağrısı / gecikme / maliyet |
| Not saklama | Redis HASH, `research_notes:{org_id}:{trace_id}`, 24sa TTL | Trace-scoped, oturum sonrası kısa süre yaşar |
| Hata davranışı | Tool'lar exception fırlatmaz, string hata döner | `AgentRunner` sözleşmesi |

M12 yeni bir engine eklemez — M9 agent engine'in üzerine **tool seti** olarak oturur. Tool'lar startup'ta `register_research_tools()` ile kaydedilir; herhangi bir agent `tool_names`'e ekleyerek kullanır.

---

## Tool'lar

```
app/services/agent/tools/research.py
```

| Tool | Parametreler | İşlev |
|---|---|---|
| `web_search` | query, max_results(1-10), topic(general/news), time_range | Tavily ile arama; sıralı sonuç listesi (title, URL, snippet) |
| `read_url` | url, max_chars | Sayfa metnini temiz çeker; cümle sınırında keser |
| `summarize` | text, focus, max_sentences | TF skorlu extractive özet; `focus` terimleri 1.5x boost |
| `save_note` | title, content | Notu Redis'e kaydeder (aynı title üzerine yazar) |
| `get_notes` | — | Oturumdaki tüm notları döner (rapor derleme için) |

Önerilen 4 fazlı sistem prompt'u (`RESEARCH_AGENT_SYSTEM_PROMPT`): **Keşif** (paralel `web_search`) → **Derin okuma** (`read_url` + `summarize`) → **Not alma** (`save_note`) → **Sentez** (`get_notes` + yapılandırılmış rapor).

---

## Konfigürasyon

`.env`:
```
TAVILY_API_KEY=        # https://tavily.com — web_search için gerekli
```
Bağımlılıklar (`pyproject.toml`): `tavily-python`, `trafilatura`.

`web_search` anahtar yoksa veya kütüphane kuruluysa anlamlı bir string hata döner (agent'ı çökertmez). Diğer tool'lar anahtar gerektirmez.

---

## Tamamlanma Kriterleri

- [x] Dört+bir tool implement edildi (`web_search`, `read_url`, `summarize`, `save_note`, `get_notes`)
- [x] Multi-step reasoning akışı (sistem prompt + ReAct loop)
- [x] Her adım trace'e düşüyor (M8 entegrasyonu — M9 üzerinden otomatik)
- [x] Kritik aramalarda HITL eklenebiliyor (`hitl_tool_names` ile, ör. `web_search`)
- [x] Unit testler geçiyor (mock Tavily/httpx)

---

## Sonraki Adım

M13–M15: Next.js UI — auth, chat/trace görünümü, test runner. Backend artık UI'ı besleyecek tüm API'lere sahip.
