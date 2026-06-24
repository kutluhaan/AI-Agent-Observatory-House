# Prompt Versiyonlama — ✅ KURULDU (it.6)

Kullanıcıyla it.5'te kararlaştırıldı, it.6'da uygulandı (migration `0026`, 541 test).

**Dosyalar:** `app/models/agent_prompt_version.py` · `app/services/agent/prompt_versions.py`
(`snapshot_agent`, `config_dict`) · `app/api/v1/agents.py` (create→v1, update→snapshot,
`GET /agents/{id}/prompt-versions`, `POST .../{version}/restore`) · `agents.prompt_version`
sütunu · Tracer `metadata={"prompt_version": …}` (agent_start payload'ına yazılır) ·
UI: agent düzenle → **Geçmiş sürümler** paneli (liste + Geri yükle) ·
test: `tests/integration/test_prompt_versions.py`.

**Caveat:** Bu özellikten ÖNCE oluşturulmuş agent'ların v1 satırı yok (lazy) — ilk
düzenlemede sürüm geçmişi başlar. Yeni agent'lar v1 ile gelir.

---
## Orijinal plan (referans)

## Kararlar (kullanıcı seçimi)

| Konu | Karar |
|------|-------|
| **Snapshot tetiği** | **Otomatik** — agent her güncellendiğinde eski config sürüm olur |
| **Kapsam** | **Tüm agent config** — system_prompt + provider + model + temperature + max_tokens + tool_names + hitl_tool_names |
| **Trace bağlantısı** | **Evet** — her run hangi sürümle koştuğunu trace'e yazsın |
| **Rollback** | Bir sürümü "geri yükle" → o config agent'a uygulanır (bu da yeni snapshot üretir) |

## Uygulama planı

1. **Migration** `0026`: `agent_prompt_versions` tablosu
   - `id, agent_id (FK), version (int, agent içinde artan), system_prompt, provider, model,
     temperature, max_tokens, tool_names (JSONB), hitl_tool_names (JSONB), note (str|None),
     created_by (FK user|None), created_at`
   - + `agents.prompt_version (int, default 1)` = aktif sürüm numarası.
2. **Model** `app/models/agent_prompt_version.py` (`AgentPromptVersion`) + `__init__` + test_models.
3. **Snapshot mantığı** — `PATCH /agents/{id}` (update_agent): config alanlarından biri değişiyorsa,
   DEĞİŞİKLİKTEN ÖNCE mevcut config'i bir `AgentPromptVersion` olarak yaz, `agents.prompt_version++`.
   (Yardımcı: `snapshot_agent(db, agent, note)`.)
4. **Trace linkage** — run başlatılırken agent.prompt_version'ı trace payload'ına ekle
   (tracer event meta'sına `prompt_version`). Olay analizi + A/B temeli.
5. **Endpoint'ler**:
   - `GET /agents/{id}/prompt-versions` — sürüm listesi (yeni→eski).
   - `POST /agents/{id}/prompt-versions/{version}/restore` — o sürümü aktif yap.
6. **UI** — agent düzenle sayfasında **"Geçmiş sürümler"** paneli: liste (sürüm no + tarih + not)
   + **Geri yükle** butonu + (opsiyonel) iki sürüm arası diff.
7. **Test**: snapshot otomatik oluşuyor mu, restore config'i doğru yüklüyor mu, version artıyor mu.

## Notlar

- Bug-hunt recurring işi **KALDIRILDI** (4 iterasyon 0 gerçek bug — kod zaten defansif).
  Recurring odak artık: tool kataloğu + ekipler + özellik geliştirme + internet keşfi.
- İlgili keşif: **Trace → Test-case** köprüsü (canlı trace'i tek tıkla test-case yap) — ileride değerlendirilecek.
