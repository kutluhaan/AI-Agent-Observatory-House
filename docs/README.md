# Observatory — Özellik Dokümantasyonu

Bu klasör, platforma eklenen özelliklerin **kalıcı (persistent)** dokümantasyonunu
içerir. Her özellik: backend + DB + UI + test entegrasyonuyla birlikte burada
belgelenir.

## Yol haritası (kolaydan zora)

| Faz | Kapsam | Durum |
|---|---|---|
| F1 | Ölçüm & export temelleri (Tool Call doğruluğu, Excel export, başarı oranı, cevap süresi) | ✅ |
| F2 | Tool kategorileri (file/web/finance/operation/self) | ✅ |
| F3 | Self-hosted / OpenAI-uyumlu custom model | ✅ |
| F4 | Test derinliği (prompt override + A/B, çıktı kalitesi, KPI tablosu) | ✅ |
| F5 | Dashboard & rapor & bilgi-etkisi gözlemi | ✅ |
| F6 | Senaryo tabanlı çalıştırma (çok-adımlı + kontrol noktaları) | ✅ |
| F7 | MCP server + custom agent HTTP invoke | ✅ |
| F8 | Agent ekipleri (çok-agent işbirliği) | ✅ |
| G1 | Gmail entegrasyonu (kullanıcı OAuth: ara/oku/gönder) | ✅ |

> **Sprint sonrası / plan-dışı** eklenen her şey (Gmail, A/B/C/D kümeleri, `/loop`
> oturumları: finance/utility/SQL/messaging kategorileri, trading ekibi, MCP registry,
> prompt versiyonlama, Google Takvim/Drive…) tek yerde: **[Genel bakış](features/post-sprint-overview.md)**.

## İçindekiler

### Test Suite
- [Tool Call doğruluğu](test-suite/tool-call-correctness.md) — `tool_correctness` assertion'ı
- [Excel export](test-suite/excel-export.md) — sonuçları `.xlsx` indir
- [Suite KPI'ları](test-suite/suite-kpis.md) — başarı oranı + cevap süresi performans paneli
- [Çıktı kalitesi](test-suite/output-quality.md) — bileşik `output_quality` judge'ı (F4.1)
- [A/B prompt deneyleri](test-suite/ab-prompt-experiments.md) — system prompt varyantlarını yan yana karşılaştır (F4.3)
- [Senaryo testleri](test-suite/scenario-runs.md) — çok-turlu görev + adım checkpoint'leri (F6)
- [Dataset'ten suite](test-suite/dataset-suites.md) — CSV/JSONL yükle, otomatik case (B2/#5)

### Ajan & Araçlar
- [Tool kategorileri](features/tool-categories.md) — file/web/finance/operation/self; kategori bazlı seçim
- [Custom model (OpenAI-uyumlu)](features/custom-model-provider.md) — self-hosted endpoint + Providers ayar sayfası
- [External agent (HTTP invoke)](features/http-agent.md) — dış agent'ı OpenAI-uyumlu HTTP ile çağır (F7.1)
- [MCP server entegrasyonu](features/mcp-integration.md) — dış MCP tool'larını agent'a bağla (F7.2)
- [Agent ekipleri](features/agent-teams.md) — rollü çok-agent işbirliği (delegasyon + paylaşılan pano) (F8)
- [Gmail entegrasyonu](features/gmail-integration.md) — kullanıcı OAuth + gmail ara/oku/gönder tool'ları (G1)
- [Gmail kurulum kılavuzu](features/gmail-setup-guide.md) — adım adım Google Cloud + bağlama + sorun giderme (G1)
- [Özel HTTP tool'ları](features/custom-tools.md) — kullanıcı tanımlı, org-bazlı HTTP tool'ları (B1/#1)
- [Agent performans paneli](features/agent-performance-panel.md) — agent başına birleşik test performansı (F5.1)
- [Org dashboard & bilgi-etkisi](features/org-dashboard.md) — org özeti + agent sıralaması + RAG trendi (F5.2/F5.3)

### Plan-dışı / Loop ile eklenenler
- [Genel bakış (sprint sonrası)](features/post-sprint-overview.md) — **hepsinin özeti + migration/dok haritası**
- [Finans tool'ları](features/finance-tools.md) — kripto/hisse fiyat+geçmiş, teknik indikatör, piyasa haberi + Trading ekibi
- [Google Takvim & Drive](features/google-workspace.md) — calendar/drive tool'ları (D/#13)
- [Mesajlaşma & Bildirim](features/notifications.md) — şifreli webhook kanalı + `send_notification`
- [Zaman & Yardımcı](features/utility-tools.md) — datetime, tarih matematiği, birim & döviz çevrimi
- [Veritabanı & SQL](features/sql-tools.md) — şifreli PostgreSQL bağlantısı + salt-okunur sorgu
- [Prompt versiyonlama](features/prompt-versioning-plan.md) — otomatik snapshot + rollback + trace bağı

> Önceki fazların (A/B/C: trajectory, deterministik assertion'lar, maliyet,
> LLM-as-judge, tutarlılık, güvenlik) referansı için kodu inceleyin:
> `backend/app/services/test_suite/`.
