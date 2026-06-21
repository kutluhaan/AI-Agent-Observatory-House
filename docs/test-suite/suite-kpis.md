# Suite KPI'ları — Başarı Oranı & Cevap Süresi

**Faz:** F1.3 · **Kalıcılık:** Tamamen DB tabanlı — `test_runs.summary` (JSONB)
kayıtlarından okunur. Yeni DB kolonu/migration gerekmez; kullanıcı çıkış/giriş
yapsa veya sonradan dönse de panel orada olur (anlık state değil).

## Endpoint

```
GET /test-suites/{suite_id}/stats        (member rolü)
```

Suite'in **tamamlanmış** (`status == "completed"` + `summary` dolu) run'larından
toplu KPI'lar + zaman serisi (trend) döner.

## KPI tanımları

| Alan | Tanım |
|---|---|
| `success_run_rate` | **Run-düzeyi başarı**: `pass_rate == 1.0` olan (tüm case'leri geçen) run oranı. Kullanıcının "successful run rate"i. |
| `avg_pass_rate` | **Case-düzeyi başarı**: run'ların `pass_rate` ortalaması. |
| `latest_pass_rate` | En yeni tamamlanmış run'ın geçme oranı. |
| `avg_latency_ms` | **Cevap verme süresi** KPI: run'ların `avg_latency_ms` ortalaması (ms). |
| `avg_cost_usd` | Run başına ortalama tahmini maliyet. |
| `avg_judge_score` | LLM-judge tanımlı run'larda ortalama judge skoru. |
| `completed_runs` / `total_runs` | Tamamlanan / toplam run sayısı. |
| `trend[]` | **Eski → yeni** sıralı nokta listesi: her run için `pass_rate`, `avg_latency_ms`, `total_cost_usd`, `total_tokens`, `avg_judge_score`. |

> Not: `avg_latency_ms` run özetindeki **case'ler arası ortalama**dır (p95
> değildir — p95 için case-düzeyi gecikmeler gerekir; o run detayında mevcut).

## Yanıt örneği

```json
{
  "total_runs": 12,
  "completed_runs": 10,
  "success_run_rate": 0.4,
  "avg_pass_rate": 0.78,
  "latest_pass_rate": 1.0,
  "avg_latency_ms": 1340,
  "avg_cost_usd": 0.0031,
  "avg_judge_score": 0.82,
  "trend": [
    { "run_id": "...", "created_at": "...", "pass_rate": 0.8, "avg_latency_ms": 1200,
      "total_cost_usd": 0.002, "total_tokens": 3400, "avg_judge_score": 0.85 }
  ]
}
```

## UI

Suite detay sayfasında (`/test-suites/{id}`) Runs listesinin üstünde **Performans
paneli**: 4 KPI kartı (başarılı run, ort. geçme oranı, ort. cevap süresi, ort.
maliyet) + **geçme oranı trendi** (run başına renkli çubuk: yeşil ≥99%, amber
≥60%, kırmızı <60%; hover'da tarih + oran + gecikme). Yalnızca en az 1 tamamlanmış
run varsa görünür.

## Entegrasyon noktaları

| Katman | Dosya |
|---|---|
| KPI hesaplama (saf) | `backend/app/services/test_suite/suite_stats.py` → `compute_suite_stats` |
| Endpoint | `backend/app/api/v1/test_suites.py` → `get_suite_stats` |
| UI panel | `frontend/src/app/(app)/test-suites/[id]/page.tsx` → `PerformancePanel` |
| Tip | `frontend/src/lib/api.ts` → `SuiteStats`, `SuiteTrendPoint` |
| Test | `backend/tests/unit/test_suite_stats.py` |

`compute_suite_stats` saf bir fonksiyondur; F5'teki org-geneli dashboard'da da
tekrar kullanılacaktır.
