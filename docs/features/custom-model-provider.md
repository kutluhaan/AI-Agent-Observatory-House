# Self-hosted / Custom Model (OpenAI-uyumlu)

**Faz:** F3 · **Kalıcılık:** Org bazında DB'de (`provider_credentials`).
Çıkış/giriş yapsan da yapılandırma kalır.

Kendi sunucunda çalıştırdığın bir modeli (ör. **gpt-oss-20b**) provider olmadan,
yalnızca **OpenAI-uyumlu** bir HTTP endpoint üzerinden agent modeli olarak kullan.

## Karar

- **OpenAI-uyumlu zorunlu** — endpoint, OpenAI Chat Completions API şemasını
  desteklemeli (`/v1/chat/completions`). vLLM, TGI (OpenAI modu), llama.cpp
  server, LM Studio, Ollama'nın OpenAI uyumlu ucu vb. uyumludur.
- **Org başına tek custom endpoint** — `provider_credentials` (org+provider
  benzersiz) yeniden kullanılır. Model adı agent başına serbest metindir.

## Yapılandırma

base_url iki yerden okunur — **çözümleme sırası: org credential (Providers UI) >
`.env`**. Tercih edilen: **`.env`**.

### 1) `.env` (önerilen)

Repo kökündeki `.env`:
```bash
CUSTOM_BASE_URL=http://host.docker.internal:8000/v1   # OpenAI-uyumlu kök
CUSTOM_API_KEY=                                        # endpoint istemiyorsa boş
```
`.env` değişikliği için backend container'ı **yeniden oluştur** (env_file
container başlangıcında okunur):
```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate backend
```

### 2) Providers sayfası (UI, alternatif)

Üst nav'daki **Sağlayıcılar** → **Custom** kartı: base_url + opsiyonel API key +
**Test et** (`/v1/models`'a hafif çağrı). Org-bazlı saklanır; `.env`'i ezer.

### Agent

Agent oluştururken **Provider = Custom** seç, **Model**'i serbest metin yaz
(ör. `gpt-oss-20b`). Form, `.env`/Providers yönlendirmesini gösterir.

## ⚠️ Ağ erişilebilirliği (infra)

Backend Docker container'ı endpoint'e **container ağından** ulaşabilmeli:
- Endpoint **başka bir sunucuda / LAN'de / public** ise → IP veya hostname ver
  (`http://10.0.0.5:8000/v1`).
- Endpoint **kendi makinende localhost**'ta ise → container `localhost`'a
  ulaşamaz; **`http://host.docker.internal:PORT/v1`** kullan (Docker Desktop'ta
  çalışır).

## Teknik

| Katman | Davranış |
|---|---|
| Provider | `OpenAIProvider(api_key, base_url)` — OpenAI SDK `base_url` override (aynı complete/stream/health_check) |
| Factory | `get_provider` → `custom`: `provider_credentials.base_url` zorunlu, key opsiyonel; yoksa `PROVIDER_NOT_CONFIGURED` |
| DB | İki CHECK constraint'e `'custom'` (migration 0014): `ck_provider_name`, `ck_agents_provider` |
| Health | `/providers/custom/health` → endpoint'in `/v1/models`'ı |

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Provider | `backend/app/services/providers/openai_provider.py` (`base_url`) |
| Factory | `backend/app/services/providers/factory.py` (`custom` dalı: org cred > env) |
| Env config | `backend/app/core/config.py` (`custom_base_url`, `custom_api_key`) + kök `.env` (`CUSTOM_BASE_URL`, `CUSTOM_API_KEY`) |
| API | `backend/app/api/v1/providers.py` (base_url custom için opsiyonel-key) |
| Şema | `backend/app/schemas/providers.py` (`custom` kabul) |
| Migration | `backend/alembic/versions/0014_custom_provider.py` |
| UI — sağlayıcılar | `frontend/src/app/(app)/providers/page.tsx` (+ TopBar ⚙ link) |
| UI — agent formu | `frontend/src/components/agent-form.tsx` (custom → serbest metin model) |
| Test | `backend/tests/integration/test_provider_endpoints.py` (custom akışı) |

## Notlar

- Custom, OpenAI sağlayıcısının istemcisini kullanır; tool-calling desteği
  endpoint'in OpenAI tool-calling uyumuna bağlıdır (gpt-oss tool-calling destekler).
- İlk kez bir **Providers ayar sayfası** eklendi; diğer sağlayıcıların (OpenAI/
  Anthropic/Gemini/Ollama) org-bazlı anahtarları da artık UI'dan girilebilir.
