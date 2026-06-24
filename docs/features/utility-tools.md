# Zaman & Yardımcı Tool'ları (Utility kategorisi)

**Küme:** loop it.7 · **Kategori:** `utility` · **Kalıcılık:** kod (tool kaydı).
Anahtarsız, sıfır-config. `backend/app/services/agent/tools/utility.py`.

| Tool | Ne yapar | Kaynak |
|------|----------|--------|
| `get_current_datetime` | Şu anki tarih/saat (IANA timezone destekli) — agent'ın "bugün ne / saat kaç" sorununu çözer | sistem saati + zoneinfo |
| `date_calculate` | İki tarih arası fark (gün/saat) + tarih aritmetiği (X gün/hafta/saat sonrası/öncesi) | saf hesap |
| `convert_units` | Birim çevrimi: uzunluk, ağırlık, veri boyutu, sıcaklık | saf hesap |
| `convert_currency` | Döviz çevrimi güncel kurla | **Frankfurter/ECB** (`api.frankfurter.dev/v1`, anahtarsız) |

- Tüm tool'lar exception fırlatmaz; hatayı string döner.
- `get_current_datetime`: timezone bulunamazsa (tzdata yoksa) UTC'ye düşer + uyarır.
- `convert_currency`: 3-harf kod (USD/EUR/TRY/GBP…); aynı kod → ağ çağrısı yapmaz. Trading ekibine de yarar.
- Not: Frankfurter `.app`→`.dev/v1`'e taşındı (301); `follow_redirects=True` + yeni URL.

## Entegrasyon

| | Yer |
|---|---|
| Tool'lar | `app/services/agent/tools/utility.py` (`register_utility_tools`) |
| Kayıt | `app/main.py` lifespan + `tests/integration/conftest.py` |
| Kategori | `tool_categories.py` (`utility`) |
| UI ikon | `agent-form.tsx` (`Clock`) |
| Test | `tests/unit/test_utility.py` (çevrim + tarih matematiği) |
