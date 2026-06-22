# Gmail Entegrasyonu (kullanıcı OAuth)

**Faz:** G1 · **Kalıcılık:** `service_connections` (migration `0021`) — token'lar
**Fernet ile şifreli**, (user, org, provider) bazlı. Kullanıcı çıkış/giriş yapsa da
bağlantı durur.

Kullanıcı kendi Gmail hesabını **OAuth 2.0** ile bağlar; agent'lar onun adına
**email arar / okur / gönderir**. Native akış (dış bağımlılık yok), mevcut
Fernet + multi-tenant desenini kullanır.

## Kurulum (Google Cloud — kullanıcı yapar)

1. Google Cloud Console → **OAuth client (Web app)**.
2. Consent screen: **External + Testing**; test kullanıcısı = kendi mailin
   (testing modunda ≤100 kullanıcı → CASA/doğrulama gerekmez).
3. Scope: `gmail.readonly` + `gmail.send` (en az yetki).
4. Redirect URI: `http://localhost:8000/connections/google/callback`.
5. `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` →
   backend'i yeniden başlat (`up -d --force-recreate backend`).

## Akış

```
POST /connections/google/authorize   → {authorize_url}  (state Redis'te, 10dk TTL)
   frontend window.location = authorize_url → Google consent
GET  /connections/google/callback?code&state → kodu token'a çevir, email al,
   Fernet ile şifreli sakla → frontend'e /connections?google=connected
GET  /connections                    → bağlı hesaplar (token sızdırılmaz)
DELETE /connections/google           → Google'da revoke + kaydı sil
```

- **Refresh:** `get_valid_access_token` token süresi dolmuşsa `refresh_token` ile
  yeniler ve kalıcı günceller (`access_type=offline` + `prompt=consent`).
- **Güvenlik:** state Redis'ten doğrulanır (CSRF), cookie'ye güvenilmez; token'lar
  asla ham dönmez.

## Tool'lar

`gmail_search` · `gmail_read` · `gmail_send` — **E-posta (Gmail)** kategorisinde.
Çalışma anında `ToolContext.user_id` + `org_id` ile kullanıcının bağlantısını bulur
(Gmail REST API). Bağlantı yoksa zarif hata: *"connect Gmail under Bağlantılar"*.

- Agent formunda **E-posta (Gmail)** akordiyonundan seçilir (veri-güdümlü;
  otomatik görünür).
- `user_id` `ToolContext`'e eklendi; `_build_runner` chat/run akışında set eder.

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Model | `app/models/connection.py` (`ServiceConnection`, migration `0021`) |
| OAuth | `app/services/connections/google_oauth.py` + `store.py` (refresh) |
| API | `app/api/v1/connections.py` (authorize/callback/list/delete) |
| Config | `app/core/config.py` (`google_client_id/secret/redirect_uri`) + `.env` |
| Tool'lar | `app/services/agent/tools/gmail.py` + `tool_categories.py` (email) |
| Bağlam | `ToolContext.user_id` (registry) + `_build_runner` |
| UI | `frontend/src/app/(app)/connections/page.tsx` + nav |
| Test | `backend/tests/unit/test_gmail.py`, `tests/integration/test_connections.py` |

## Sonraki (opsiyonel)
Public'e açılınca Gmail restricted scope için **Google CASA Tier 2** denetimi
(yıllık) gerekir. Test modunda gerek yok. Drive/Calendar aynı desenle eklenebilir.
