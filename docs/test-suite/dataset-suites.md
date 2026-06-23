# Dataset'ten Test Suite (CSV/JSONL)

**Faz:** B2 (#5) · YAML yazmadan, **veri-odaklı** test oluşturma.

Bir CSV/JSONL dataset yükle; her satır bir test case'e dönüşür. Mevcut test-suite
altyapısını aynen kullanır (suite + case + run + rapor).

## Format

**CSV** (başlık satırı zorunlu, `input` sütunu şart, `expected` opsiyonel):
```csv
input,expected
İstanbul hava durumu nedir?,derece
Notion nedir?,not
```

**JSONL** (her satır bir JSON nesnesi):
```jsonl
{"input": "İstanbul hava durumu?", "expected": "derece"}
{"input": "Notion nedir?"}
```

- `input` zorunlu, `expected` opsiyonel.
- En fazla **500 satır**.

## Eşleşme (assertion)
Her satırda `expected` doluysa, seçtiğin tipte bir assertion eklenir:
| Seçim | Assertion | Anlamı |
|---|---|---|
| İçerir | `response_contains` | çıktı bu metni içeriyor (varsayılan) |
| Eşittir | `response_equals` | çıktı tam eşit |
| Regex | `response_regex` | çıktı kalıba uyuyor |

`expected` boşsa case yalnızca **çalışır** (assertion yok) — çıktıyı bir judge
(ör. `output_quality`) ile değerlendirmek için uygundur.

## Akış
```
POST /test-suites/from-dataset
  body: { name, description?, agent_id, format: "csv"|"jsonl", content, assertion: "contains"|"equals"|"regex" }
  → 201 { ...suite, cases_created }
```
- `parse_dataset` içeriği satırlara çevirir → `build_suite_yaml` geçerli bir suite
  YAML'ı üretir → mevcut `parse_yaml` + case-oluşturma akışıyla saklanır.
- `config_yaml` doldurulduğu için suite sonradan **YAML editöründen düzenlenebilir**.

## UI
**Yeni test suite** sayfasında **mod seçimi: YAML | Dataset**. Dataset modunda:
agent seç + format + eşleşme tipi + içeriği yapıştır → **Suite oluştur**.

## Entegrasyon noktaları
| | Dosya |
|---|---|
| Parser/üretici | `backend/app/services/test_suite/dataset.py` (`parse_dataset`, `build_suite_yaml`) |
| Endpoint | `backend/app/api/v1/test_suites.py` → `create_suite_from_dataset` |
| Şema | `backend/app/schemas/test_suites.py` → `CreateSuiteFromDatasetRequest` |
| UI | `frontend/src/app/(app)/test-suites/new/page.tsx` (mod toggle) |
| Test | `backend/tests/unit/test_dataset.py`, `tests/integration/test_test_runner.py` |
