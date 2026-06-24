# Mesajlaşma & Bildirim (Bildirim Kanalları)

**Küme:** loop it.4 · **Kategori:** `messaging` · **Kalıcılık:** `notification_channels`
tablosu (migration `0025`).

Org-bazlı **bildirim kanalı**: bir generic **webhook URL**'i (Slack/Discord/Teams
"incoming webhook"larıyla uyumlu) **Fernet ile şifreli** saklanır; agent'lar
`send_notification` tool'uyla buraya mesaj/uyarı gönderir. Trading ekibi uyarıları,
test sonuçları, özetler için ideal.

## Akış

1. **Bildirim Kanalları** sayfasından bir webhook ekle (ad + URL). URL şifreli saklanır,
   API'de **asla ham dönmez** (`ChannelResponse`'ta `url` yok). **Test** butonuyla doğrula.
2. Agent oluştururken **Mesajlaşma & Bildirim** kategorisinden `send_notification`'ı seç.
3. Agent çağırır: `send_notification(message, channel?)` — `channel` verilmezse varsayılan
   (en eski) kanal kullanılır. Gövdede hem `text` (Slack) hem `content` (Discord) gönderilir.

## Güvenlik

- URL **Fernet** ile şifreli (`encrypted_url`); yanıtlarda dönmez (custom-tool/connection deseni).
- Kanal yönetimi **admin**; listeleme/test **member**.

## Entegrasyon

| | Yer |
|---|---|
| Model | `app/models/notification.py` (`NotificationChannel`) + migration `0025` |
| Tool | `app/services/agent/tools/notify.py` (`send_notification`, `send_webhook`) |
| API | `app/api/v1/notification_channels.py` (CRUD + `/test`) |
| Kategori | `tool_categories.py` (`messaging`) |
| UI | `frontend/src/app/(app)/notification-channels/page.tsx` + nav (Bildirimler) + agent-form ikon (Bell) |
| Test | `tests/integration/test_notification_channels.py`, `tests/unit/test_tool_categories.py` |

İleride: Slack/Discord/Telegram'a özel biçimli (embed/bloklar) tool'lar + kanal başına tip.
