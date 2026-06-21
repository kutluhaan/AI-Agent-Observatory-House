# Test Sonuçları — Excel Export

**Faz:** F1.2 · **Bağımlılık:** `openpyxl>=3.1` (pyproject.toml)

Bir test run'ının tüm sonuçlarını tek bir **`.xlsx`** çalışma kitabı olarak indirir.

## Endpoint

```
GET /test-runs/{run_id}/export.xlsx       (member rolü)
```

`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
ve `Content-Disposition: attachment; filename="test-run-XXXXXXXX.xlsx"` döner.

## Çalışma kitabı içeriği

| Sayfa | İçerik |
|---|---|
| **Özet** | Run bilgisi + toplu metrikler (toplam/geçen/kalan, geçme oranı, ort. gecikme, toplam token, tahmini maliyet, ort. judge skoru) |
| **Case Sonuçları** | Case başına satır: durum, assertion (geçen/toplam), judge ort., adım, token, maliyet, gecikme, tutarlılık, trace, kısa çıktı |
| **Assertion'lar** | Her case'in her assertion'ı: tip, geçti/kaldı, beklenen, gerçek, mesaj |
| **Judge'lar** | Her LLM-judge sonucu: metrik, skor, geçti, eşik, gerekçe |

Geçen/kalan/hata satırları renklendirilir (yeşil/kırmızı/amber), başlıklar
sabitlenir (freeze panes), kolon genişlikleri otomatik ayarlanır.

## UI

Test-run detay sayfasında (run tamamlanıp sonuç varsa) sağ üstte **"Excel'e aktar"**
butonu. Buton, endpoint'i `credentials: include` ile fetch eder, blob'u indirir.

## Entegrasyon noktaları

| Katman | Dosya |
|---|---|
| Workbook üretimi | `backend/app/services/test_suite/excel_export.py` → `build_workbook` |
| Endpoint | `backend/app/api/v1/test_suites.py` → `export_test_run_xlsx` |
| Bağımlılık | `backend/pyproject.toml` → `openpyxl>=3.1.0` |
| UI | `frontend/src/app/(app)/test-runs/[id]/page.tsx` → `downloadXlsx` |
| Test | `backend/tests/unit/test_excel_export.py` |

## Notlar

- Export salt-okunurdur; mevcut `TestCaseResult` verisinden üretilir, DB'ye yazmaz.
- Yeni image build'lerinde `openpyxl` otomatik kurulur (pyproject.toml). Çalışan
  container'a tek seferlik `uv pip install --system openpyxl` ile de eklenebilir.
