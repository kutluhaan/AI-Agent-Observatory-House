# M11 — Test Core

**Milestone hedefi:** YAML test suite'leri çalışır, assertion'lar değerlendirilir, RAG metrikleri hesaplanır, sonuçlar karşılaştırılabilir saklanır.

Bu doküman mevcut implementasyonu belgeler (kod tamam).

---

## Veri Modeli (migration 0005)

| Tablo | Açıklama |
|---|---|
| `test_suites` | YAML config (org-scoped), isim, açıklama |
| `test_cases` | Suite içindeki tek senaryo (input + assertion'lar) |
| `test_runs` | Bir suite çalıştırması (status: pending/running/completed/failed) |
| `test_case_results` | Her case'in sonucu (passed/failed, assertion detayları, latency, RAG metrikleri) |

---

## Bileşenler

```
app/services/test_suite/
├── parser.py             — YAML → TestSuite/TestCase (validasyon, INVALID_TEST_YAML)
├── assertions.py         — assertion engine
├── sandbox.py            — AgentSandbox: synthetic history inject ederek izole çalıştırma
├── case_runner.py        — TestCaseRunner: agent yükle → sandbox → assert → RAG
├── experiment_runner.py  — ExperimentRunner: tüm case'ler (paralel/sıralı), TestRun günceller
└── rag_evaluator.py      — RAGAS varsa gerçek metrik, yoksa heuristik fallback
app/api/v1/test_suites.py — suite CRUD + run + run listesi
app/ws/test_runs.py       — WS /ws/test-runs: canlı test progress
```

### Assertion Tipleri

| Tip | Kontrol |
|---|---|
| `response_contains` | LLM çıktısı metni içeriyor mu (case-insensitive) |
| `tool_called` | Verilen tool en az bir kez çağrıldı mı (trace'den) |
| `latency_under` | Toplam süre (ms) eşiğin altında mı |

### RAG Değerlendirme

`rag_context` verilen case'ler için: RAGAS kuruluysa `faithfulness` / `answer_relevancy`; değilse (test ortamı) basit heuristik fallback. Precision@K / Recall@K ve latency metrikleri de toplanır.

### Çalıştırma

`ExperimentRunner`: `TestRun`'ı `running` işaretler → case'leri `parallel=True` ise `asyncio.gather`, değilse sıralı çalıştırır → her case `TestCaseRunner` ile (agent DB'den yüklenir, provider hazırlanır, `AgentSandbox` üzerinden koşar) → sonuçlar `test_case_results`'a yazılır → `TestRun` `completed/failed` olur. İlerleme WebSocket'le iletilir.

---

## Endpoint'ler

| Method | Path | Min Rol | Açıklama |
|---|---|---|---|
| POST | `/test-suites` | admin | Suite oluştur (YAML validate edilir) |
| GET | `/test-suites` | member | Org'un suite'leri |
| GET | `/test-suites/{id}` | member | Suite detayı |
| PATCH | `/test-suites/{id}` | admin | Suite güncelle (YAML yeniden validate) |
| DELETE | `/test-suites/{id}` | admin | Suite sil |
| POST | `/test-suites/{id}/run` | member | Çalıştır (202) — background task, `parallel` opsiyonu |
| GET | `/test-suites/{id}/runs` | member | Suite'in run geçmişi |
| GET | `/test-runs/{id}` | member | Run detayı + case sonuçları |
| WS | `/ws/test-runs` | member | Canlı test progress akışı |

Tümü org-scoped (yanlış org → 404).

---

## Hata Kodları

| Code | HTTP | Açıklama |
|---|---|---|
| `INVALID_TEST_YAML` | 422 | YAML parse/şema hatası |
| `TEST_SUITE_NOT_FOUND` | 404 | Suite yok ya da başka org'a ait |
| `TEST_RUN_NOT_FOUND` | 404 | Run yok ya da başka org'a ait |

---

## Tamamlanma Kriterleri

- [x] YAML'dan yüklenen suite çalışıyor
- [x] Assertion engine (3 tip) doğru sonuç veriyor
- [x] Paralel ve sıralı çalıştırma
- [x] RAG metrikleri hesaplanıyor (RAGAS veya fallback)
- [x] Sonuçlar DB'de karşılaştırılabilir formatta
- [x] Real-time progress WebSocket
- [x] Unit + integration testler geçiyor

---

## Sonraki Adım

M12 Personal Research Agent: gerçek bir kullanım senaryosu, M9–M11 üzerine.
