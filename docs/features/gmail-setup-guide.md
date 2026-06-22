# Gmail Entegrasyonu — Adım Adım Kurulum Kılavuzu

Bu kılavuz, bir agent'ın senin Gmail hesabınla **e-posta arayıp okuyabilmesi ve
gönderebilmesi** için gereken kurulumu **baştan sona** anlatır. Teknik mimari için
bkz. [gmail-integration.md](gmail-integration.md).

> ⏱️ Toplam süre ~10 dakika. En kritik 2 adım: **A4 (scope ekleme)** ve
> **A3 (test user)** — atlanırsa 403 hatası alırsın (bkz. Bölüm F).

---

## Ön koşullar
- Bir Google hesabı (bağlayacağın Gmail).
- Çalışan platform (docker stack ayakta).
- Erişim: [Google Cloud Console](https://console.cloud.google.com).

---

## BÖLÜM A — Google Cloud kurulumu

### A1. Proje seç/oluştur
Google Cloud Console üstündeki proje seçiciden bir proje seç (yoksa **New Project**).

### A2. Gmail API'yi etkinleştir
**APIs & Services → Library** → ara: **"Gmail API"** → **Enable**.
> Bu yapılmazsa scope'lar verilse bile API çağrıları başarısız olur.

### A3. OAuth consent screen + Test users
**APIs & Services → OAuth consent screen**:
1. **User type = External** (Audience), **Create/Save**.
2. Uygulama adı, destek e-postası gibi zorunlu alanları doldur.
3. **Publishing status = Testing** kalsın (yayına alma!).
4. **Audience** sekmesi → **Test users** → **+ Add users** → **bağlayacağın Gmail
   adresini birebir ekle** (ör. `kayguzel255@gmail.com`) → **Save**.
   > Eklemezsen bağlanırken **403 access_denied** alırsın. Test modunda yalnız bu
   > listedeki hesaplar erişebilir.

### A4. Data access — Gmail scope'larını ekle ⚠️ (en sık atlanan adım)
**APIs & Services → OAuth consent screen → Data access** → **Add or remove scopes**:
- Açılan panelde alttaki **"Manually add scopes"** kutusuna şunları (ayrı satır) yapıştır:
  ```
  https://www.googleapis.com/auth/gmail.readonly
  https://www.googleapis.com/auth/gmail.send
  ```
- **Add to table** → **Update** → **Save**.
> Bu adım atlanırsa Google sadece temel `email/openid` izinlerini verir; Gmail
> çağrıları **403 "insufficient authentication scopes"** döner.

### A5. OAuth Client ID oluştur (Web application)
**APIs & Services → Credentials → + Create credentials → OAuth client ID**:
- **Application type:** Web application
- **Name:** istediğin (ör. `email-authorization`) — sadece konsolda görünür.
- **Authorized JavaScript origins:** **BOŞ bırak** (sunucu-taraflı akış; buraya
  path yazarsan *"URIs must not contain a path"* hatası verir).
- **Authorized redirect URIs → + Add URI:**
  ```
  http://localhost:8000/connections/google/callback
  ```
  > `.env`'deki `GOOGLE_REDIRECT_URI` ile **birebir aynı** olmalı (port 8000 =
  > backend). Tek karakter farkı → *redirect_uri_mismatch*.
- **Create**.

### A6. Client ID + Secret'i kopyala
Açılan kutudan **Client ID** ve **Client Secret**'i kopyala (sonra Credentials
listesindeki kalem ikonundan da görebilirsin).

---

## BÖLÜM B — Platform yapılandırması

### B1. `.env` doldur
Repo kökündeki `.env`:
```bash
GOOGLE_CLIENT_ID=<A6'daki Client ID>
GOOGLE_CLIENT_SECRET=<A6'daki Client Secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/connections/google/callback   # dokunma
```

### B2. Backend'i yenile
```bash
docker compose -f docker-compose.dev.yml up -d --force-recreate backend
```
> `.env` container başlangıcında okunur; restart şart.

---

## BÖLÜM C — Hesabı bağla
1. Uygulamada üst nav → **Bağlantılar**.
2. **Gmail** kartında **"Google ile bağlan"**.
3. Google hesabını seç (test user olarak eklediğin).
4. "Google doğrulamadı" uyarısı çıkarsa (test modunda normal):
   **Gelişmiş / Advanced → "<uygulama adı>'na git (güvenli değil)"**.
5. İzin ekranında **"E-postalarını oku"** ve **"E-posta gönder"** dahil **tüm
   izinleri ver** (kutuların işaretli olduğundan emin ol).
6. Geri dönünce **"Gmail bağlandı ✓"** + bağlı e-postan görünür.

---

## BÖLÜM D — Gmail ajanı oluştur
1. **Agents → Yeni agent**.
2. **Provider:** Google Gemini · **Model:** `gemini-2.5-flash` (veya `pro`).
3. **Araçlar → E-posta (Gmail)** akordiyonu → `gmail_search`, `gmail_read`,
   `gmail_send` (üçünü seç). Güvenlik için `gmail_send` yanındaki **HITL onayı**'nı işaretle.
4. **System prompt** (örnek):
   ```
   Sen kullanıcının Gmail asistanısın: e-posta ara, oku, özetle ve onay alarak gönder.
   - gmail_search(query): Gmail söz dizimi (is:unread, from:, newer_than:7d, subject:"...").
   - gmail_read(id): tam içerik. Özetlerken gönderen+konu+tarih belirt.
   - gmail_send(to,subject,body): ASLA onaysız gönderme — önce taslağı göster, "Göndereyim mi?" diye sor.
   Türkçe, net konuş. Bilgi uydurma.
   ```

---

## BÖLÜM E — Kullanım örnekleri
- *"Bugün gelen son maillerimi özetle."* → `gmail_search("newer_than:1d")` + read
- *"Patronumdan gelen okunmamış mailler var mı?"* → `from:... is:unread`
- *"Ali'ye toplantıyı onayladığımı yazan bir taslak hazırla."* → taslak → onay → `gmail_send`

Gmail arama operatörleri: `from: to: subject: is:unread is:important has:attachment
newer_than:7d older_than:1m label:inbox`.

---

## BÖLÜM F — Sorun giderme

| Hata | Sebep | Çözüm |
|---|---|---|
| **403 access_denied** ("doğrulama tamamlanmadı") | Hesap **Test users**'da değil | A3: bağladığın maili Test users'a ekle |
| **403 insufficient authentication scopes** | Token'da Gmail izni yok (Data access eksik) | A4: scope'ları ekle → **Bağlantıyı kes** → yeniden bağlan |
| **redirect_uri_mismatch** | Redirect URI uyuşmuyor | A5 ve `.env` birebir aynı: `http://localhost:8000/connections/google/callback` |
| **"URIs must not contain a path"** | Redirect URI'yi **JavaScript origins**'e yazdın | A5: redirect URI **Authorized redirect URIs**'e gider; JS origins boş |
| **"no Google connection — connect Gmail..."** (tool çıktısı) | O kullanıcının bağlantısı yok | Bölüm C ile bağlan |
| Bağlandı ama izinler eksik | Consent'te kutular işaretsiz / Data access eksik | Bağlantıyı kes, A4'ü kontrol et, yeniden bağlanıp tüm izinleri ver |

> İzin teşhisi: kayıtlı token'ın scope'ları `service_connections.scopes` alanında
> tutulur; `gmail.readonly` görünmüyorsa A4 eksiktir.

---

## BÖLÜM G — Güvenlik & limitler
- **Token'lar Fernet ile şifreli** saklanır (`service_connections`), yanıtta ham dönmez.
- **Testing modu:** ≤100 test kullanıcısı, Google doğrulaması/CASA **gerekmez** —
  geliştirme/kendi kullanımın için yeterli.
- **Public'e açmak** istersen Gmail restricted scope için **Google CASA Tier 2**
  güvenlik denetimi (yıllık, ücretli) gerekir.
- **En az yetki:** sadece `gmail.readonly` + `gmail.send` istenir.
- Gönderimde **HITL onayı** + sistem prompt kuralı ile çift güvenlik önerilir.
