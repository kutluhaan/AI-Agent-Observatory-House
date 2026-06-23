# Org Dashboard & Bilgi-Etkisi

**Faz:** F5.2 (org dashboard) + F5.3 (bilgi-etkisi / RAG trendi)
**Kalıcılık:** Canlı hesap — mevcut `TestRun.summary` + `TestCaseResult` kayıtlarından
(yeni tablo yok). `compute_suite_stats` + `compute_agent_stats` saf fonksiyonları
tekrar kullanılır.

## F5.2 — Org Dashboard

Org'un tüm test aktivitesinin üst-düzey özeti. Giriş sonrası ana sayfada (`/dashboard`).

```
GET /dashboard        (member rolü)
→ {
    counts: { agents, suites, total_runs, completed_runs },
    success_run_rate, avg_pass_rate, avg_latency_ms, avg_cost_usd, avg_judge_score,
    trend[],                 # org genelindeki run trendi
    agents_evaluated,
    leaderboard: [{ agent_id, name, pass_rate, avg_judge_score, avg_latency_ms, total_cases }]
  }
```

- **Lider tablosu:** her agent'ın case sonuçları `compute_agent_stats` ile özetlenir,
  `pass_rate` (sonra judge skoru) ile sıralanır. Veri olmayan agent atlanır.
- **UI (C4 ile güncellendi):** "bir org, agent ve ekipleri kadar iyidir" →
  dashboard **agent + ekip odaklı**. Org metrikleri tek **kompakt şeride** indi;
  altında **Agent sıralaması** + **Ekip sıralaması** yan yana (satıra tıkla →
  agent performans paneli / ekip detayı). Yanıt `team_leaderboard` + `counts.teams`
  + `teams_evaluated` içerir (her ekip için `compute_team_stats`).

## F5.3 — Bilgi-etkisi (RAG metrik trendi)

Bilgi (knowledge/RAG) tabanlı case'lerin çıktı kalitesine etkisini gözlemler.
`rag_context` tanımlı case'lerde RAG değerlendiricisi şu metrikleri üretir
(zaten mevcut altyapı): **faithfulness, answer_relevancy, context_recall,
context_precision**.

- `compute_agent_stats` çıktısına `rag` anahtarı eklendi: dört metriğin ortalaması
  + `cases_with_rag` + **run-bazlı trend** (eski → yeni). RAG'li case yoksa `null`.
- **UI:** Agent performans panelinde (`/agents/{id}/performance`) yalnızca RAG verisi
  varsa **"Bilgi etkisi (RAG)"** bölümü: 4 metrik kartı + faithfulness trendi.

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Org özeti (saf) | `backend/app/services/test_suite/org_dashboard.py` → `compute_org_dashboard` |
| RAG agregasyon | `backend/app/services/test_suite/agent_stats.py` → `_compute_rag` |
| Endpoint | `backend/app/api/v1/dashboard.py` → `GET /dashboard` (main.py'de mount) |
| UI — dashboard | `frontend/src/app/(app)/dashboard/page.tsx` + nav |
| UI — RAG | `frontend/src/app/(app)/agents/[id]/performance/page.tsx` |
| Tip | `frontend/src/lib/api.ts` → `OrgDashboard`, `AgentRagStats` |
| Test | `backend/tests/unit/test_org_dashboard.py`, `test_agent_stats.py` |

Tüm F5 (run-rapor zaten run detayında · F5.1 agent paneli · F5.2 org dashboard ·
F5.3 bilgi-etkisi) tamamlandı.
