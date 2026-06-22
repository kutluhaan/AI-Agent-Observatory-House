# A/B Prompt Deneyleri

**Faz:** F4.3 · **Kalıcılık:** Her varyant bir `TestRun` (DB'de); deney
`experiment_id` ile gruplanır. Çıkış/giriş yapsan da deneyler suite sayfasında durur.

Aynı suite'i, **aynı agent**'ın farklı **system prompt** varyantlarıyla yan yana
çalıştırıp karşılaştırır. "Hangi prompt daha iyi?" sorusunu ölçümle yanıtlar.

## Model

- Run başlatırken **2–5 varyant** girilir: her biri `{label, system_prompt}`.
- Her varyant = ortak `experiment_id` taşıyan bir `TestRun`; `system_prompt_override`
  o run'da agent'ın prompt'unu **geçici** ezer (agent kalıcı olarak değişmez).
- Varyantlar bağımsız çalışır; tamamlandıkça karşılaştırma tablosu dolar.

## Akış

```
POST /test-suites/{id}/experiments
  body: { parallel?: bool, variants: [{label, system_prompt}, …] }  (2–5, label benzersiz)
  → 202 { experiment_id, status, variants:[{run_id, variant_label, status, summary, system_prompt_override}] }

GET  /test-suites/{id}/experiments              → deney listesi (yeni → eski)
GET  /test-suites/{id}/experiments/{exp_id}     → tek deney (yan yana karşılaştırma)
```

`status`: tüm varyantlar `completed`/`failed` olunca `completed`, aksi halde `running`.

## Override nasıl uygulanır

`case_runner.run_case` agent config'i kurarken:
```python
system_prompt = run.system_prompt_override or agent_row.system_prompt
```
Yani override yalnızca o run'ın çalıştırılmasını etkiler; DB'deki agent dokunulmaz.

## UI

- **Suite detay → "A/B test"** butonu: varyant satırları (ad + system prompt),
  ekle/kaldır, **"A/B çalıştır"**.
- Karşılaştırma sayfası (`/test-suites/{id}/experiments/{exp_id}`): satır = metrik
  (geçme oranı, geçen/toplam, cevap süresi, judge skoru, maliyet, token),
  sütun = varyant. Her metrikte **en iyi** varyant yeşil vurgulanır. `running`
  iken 3 sn'de bir otomatik yenilenir. Altta her varyantın system prompt'u +
  run detay linki.
- Geçmiş deneyler suite sayfasında **"A/B Deneyleri"** listesinde (kalıcı).
- Varyant run'ları normal **Runs** listesinde de `variant_label` rozetiyle görünür.

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Şema | `test_runs.experiment_id` + `variant_label` + `system_prompt_override` (migration `0016`) |
| Override | `backend/app/services/test_suite/case_runner.py` |
| Endpoint | `backend/app/api/v1/test_suites.py` → `run_experiment`, `list_experiments`, `get_experiment` |
| Request/Response | `backend/app/schemas/test_suites.py` → `RunExperimentRequest`, `ExperimentResponse` |
| UI — başlat + liste | `frontend/src/app/(app)/test-suites/[id]/page.tsx` |
| UI — karşılaştırma | `frontend/src/app/(app)/test-suites/[id]/experiments/[experimentId]/page.tsx` |
| Test | `backend/tests/integration/test_test_runner.py` (A/B bölümü) |
