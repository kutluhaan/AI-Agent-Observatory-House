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
| F7 | MCP server + custom agent HTTP invoke | ⏳ |
| F8 | Agent ekipleri (çok-agent işbirliği) | ⏳ |

## İçindekiler

### Test Suite
- [Tool Call doğruluğu](test-suite/tool-call-correctness.md) — `tool_correctness` assertion'ı
- [Excel export](test-suite/excel-export.md) — sonuçları `.xlsx` indir
- [Suite KPI'ları](test-suite/suite-kpis.md) — başarı oranı + cevap süresi performans paneli
- [Çıktı kalitesi](test-suite/output-quality.md) — bileşik `output_quality` judge'ı (F4.1)
- [A/B prompt deneyleri](test-suite/ab-prompt-experiments.md) — system prompt varyantlarını yan yana karşılaştır (F4.3)
- [Senaryo testleri](test-suite/scenario-runs.md) — çok-turlu görev + adım checkpoint'leri (F6)

### Ajan & Araçlar
- [Tool kategorileri](features/tool-categories.md) — file/web/finance/operation/self; kategori bazlı seçim
- [Custom model (OpenAI-uyumlu)](features/custom-model-provider.md) — self-hosted endpoint + Providers ayar sayfası
- [Agent performans paneli](features/agent-performance-panel.md) — agent başına birleşik test performansı (F5.1)
- [Org dashboard & bilgi-etkisi](features/org-dashboard.md) — org özeti + agent sıralaması + RAG trendi (F5.2/F5.3)

> Önceki fazların (A/B/C: trajectory, deterministik assertion'lar, maliyet,
> LLM-as-judge, tutarlılık, güvenlik) referansı için kodu inceleyin:
> `backend/app/services/test_suite/`.
