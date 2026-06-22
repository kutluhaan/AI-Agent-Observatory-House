# Agent Performans Paneli

**Faz:** F5.1 · **Kalıcılık:** Canlı hesap — `TestCaseResult` kayıtlarından
(yeni tablo yok). Çıkış/giriş yapsan da panel orada; her zaman güncel.

Bir agent'ın **tüm test çalıştırmalarındaki** case sonuçlarını toplayıp birleşik
performansını gösterir. `compute_suite_stats`'ın agent eksenindeki karşılığı.

## Veri

Agent'a ait case sonuçları: `TestCaseResult` → `TestCase.agent_id == agent`
eşleşmesi, org'a göre filtreli. A/B (system_prompt_override) run'ları da sayılır —
case'in agent'ı aynıdır.

| Alan | Tanım |
|---|---|
| `pass_rate` | Geçen case / toplam case (case-düzeyi) |
| `avg_latency_ms` | Case'ler arası ortalama gecikme |
| `avg_cost_usd` | Case başına ortalama maliyet |
| `avg_judge_score` | LLM-judge ortalaması (output_quality dahil) |
| `total_tokens` | Toplam token |
| `runs_count` | Agent'ın göründüğü run sayısı |
| `trend[]` | **Run bazında** gruplu, eski → yeni: `{run_id, created_at, pass_rate, avg_latency_ms, cases}` |

## Endpoint

```
GET /agents/{agent_id}/stats        (member rolü)
→ { total_cases, passed_cases, pass_rate, avg_latency_ms, avg_cost_usd,
    total_tokens, avg_judge_score, runs_count, trend[] }
```

## UI

- Agents listesinde her kartta **📊 Performans** butonu →
  `/agents/{id}/performance`.
- Panel: KPI kartları (geçme oranı, cevap süresi, judge skoru, maliyet, token,
  çalıştırma) + **geçme oranı trendi** (run başına renkli çubuk; hover'da
  tarih/oran/case/gecikme). Veri yoksa boş-durum mesajı.

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Hesaplama (saf) | `backend/app/services/test_suite/agent_stats.py` → `compute_agent_stats` |
| Endpoint | `backend/app/api/v1/agents.py` → `get_agent_stats` |
| UI | `frontend/src/app/(app)/agents/[id]/performance/page.tsx` + Agents kartı |
| Tip | `frontend/src/lib/api.ts` → `AgentStats`, `AgentTrendPoint` |
| Test | `backend/tests/unit/test_agent_stats.py` |

F5 kademeli: **F5.1 agent paneli** (bu) → F5.2 org dashboard → F5.3 bilgi-etkisi
(RAG metrik trendi). Hepsi `compute_*_stats` saf fonksiyonlarını paylaşır.
