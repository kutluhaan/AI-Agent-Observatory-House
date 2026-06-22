# Senaryo Tabanlı Testler (Çok-adımlı)

**Faz:** F6 · **Kalıcılık:** `test_cases.steps` + `test_case_results.steps_results`
(migration `0017`). Senaryolar suite YAML'ında tanımlı, sonuçlar DB'de kalıcı.

Tek girdi + tek değerlendirme yerine, agent'ı **çok-turlu** bir görevde sınar:
sıralı adımlar, her adımda **kontrol noktaları (checkpoint)**. Agent konuşma
bağlamını adımlar boyunca korur.

## Tanım (suite YAML)

Bir case ya **tekil** (`input` + `assertions`) ya da **senaryo** (`steps`):

```yaml
cases:
  - name: ucus-rezervasyonu
    steps:
      - input: "Paris'e uçuş bul"
        assertions:
          - type: response_contains
            value: "Paris"
          - type: tools_used
            value: ["web_search"]
      - input: "En ucuzunu seç ve rezerve et"      # önceki turu hatırlar
        assertions:
          - type: tool_called_with_args
            value: { name: "book_flight", args: { } }
      - input: "Onay numarasını ver"
        assertions:
          - type: response_not_contains
            value: "error"
```

- `steps` varsa üst `input` opsiyoneldir (temsilci = ilk adımın input'u).
- Her adımın `assertions`'ı o turun çıktısına uygulanır (mevcut tüm assertion
  tipleri geçerli).

## Çalışma davranışı

- **Çok-turlu:** her adım, önceki turların (kullanıcı + asistan) konuşma
  geçmişiyle çalışır (sandbox'ın `history` desteği). Agent'ın kalıcı durumu
  (dosyalar/bilgi) DB'de zaten korunur.
- **Devam et, hepsini raporla:** bir adım/checkpoint kalsa da sonraki adımlar
  çalışır. Case **TÜM adımlar geçerse** `passed`, aksi halde `failed`.
- Toplam latency/token/maliyet adımlar üzerinden toplanır; temsilci çıktı = son
  adımın çıktısı.

## Sonuç

`steps_results`: `[{step, input, output, passed, latency_ms, assertions_results}]`
(hata olursa `error`). UI'da (run detayı) her adım açılır: input ▸ çıktı +
adım-adım checkpoint'ler. Üstte "Senaryo · geçen/toplam adım".

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Parser | `backend/app/services/test_suite/parser.py` → `ParsedStep`, `_parse_steps`, `_parse_assertion_list` |
| Şema | `test_cases.steps` + `test_case_results.steps_results` (migration `0017`) |
| Runner | `backend/app/services/test_suite/case_runner.py` → `_run_scenario` |
| Store | `backend/app/api/v1/test_suites.py` (create/update → `steps`) |
| UI | `frontend/src/app/(app)/test-runs/[id]/page.tsx` → `StepView` |
| Tip | `frontend/src/lib/api.ts` → `StepResult` |
| Test | `backend/tests/unit/test_scenario_parser.py`, `test_scenario_runner.py`, `tests/integration/test_test_runner.py` |
