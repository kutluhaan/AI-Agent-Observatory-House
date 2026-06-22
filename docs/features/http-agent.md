# External Agent (HTTP invoke)

**Faz:** F7.1 · **Kalıcılık:** Agent satırında (`agents.endpoint_url` +
şifreli `endpoint_api_key`, migration `0018`).

Dış (self-hosted) bir agent'ı **OpenAI-uyumlu HTTP** endpoint üzerinden çağırır.
Endpoint kendi mantığını/araçlarını çalıştırır; platform input gönderir, çıktı
alır — ve bu agent'ı native agent gibi **test/trace/dashboard**'a dahil eder.

## F3 custom'dan farkı

| | F3 `custom` | F7.1 `http` |
|---|---|---|
| Kapsam | **Org** başına tek endpoint | **Agent** başına endpoint |
| Konfig | `.env CUSTOM_BASE_URL` / Providers UI | Agent formunda URL + key |
| Kullanım | LLM completion sağlayıcısı | Dış agent'ı çağırma |

## Yapılandırma (UI)

Agent oluştur/düzenle → **Provider = External agent (HTTP)**:
- **Endpoint URL**: OpenAI-uyumlu kök (ör. `http://my-agent:9000/v1`).
- **API anahtarı** (opsiyonel): Fernet ile şifreli saklanır; yanıtta asla ham
  dönmez (`has_endpoint_api_key: bool`).
- **Model**: serbest metin (endpoint'in beklediği ad).

## Teknik

- **Provider:** `get_provider_for_agent(db, agent)` — `provider=='http'` ise
  `OpenAIProvider(base_url=agent.endpoint_url, api_key=decrypt(...) or "not-needed")`.
  Diğer tüm provider'lar org/platform çözümlemesine (`get_provider`) düşer.
- **Çağrı yerleri** (hepsi agent ORM satırına sahip): `_build_runner` (chat/run),
  `case_runner` (test), `call_agent` (multi-agent tool).
- **Şema:** `provider='http'` → `endpoint_url` zorunlu (`CreateAgentRequest` model
  validator). `endpoint_api_key` write-only; `get_provider` doğrudan `http` ile
  çağrılırsa "per-agent" uyarısı verir. `http`, Providers (org) listesinde görünmez.

## ⚠️ Ağ

Docker backend endpoint'e ulaşabilmeli: aynı makinedeyse `host.docker.internal`,
LAN/uzak sunucuysa IP/hostname. Sunucu OpenAI API'yi `/v1` altında sunuyorsa URL'e
`/v1` ekle (bkz. [custom-model-provider.md](custom-model-provider.md)).

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Model | `agents.endpoint_url` + `endpoint_api_key` (migration `0018`, `http` CHECK) |
| Provider | `backend/app/services/providers/factory.py` → `get_provider_for_agent` |
| Şema | `backend/app/schemas/agents.py` (endpoint alanları + http validator) |
| API | `backend/app/api/v1/agents.py` (create/update → şifrele/sakla) |
| UI | `frontend/src/components/agent-form.tsx` (http endpoint alanları) |
| Test | `backend/tests/unit/test_provider_factory.py`, `tests/integration/test_agent_execution.py` |
