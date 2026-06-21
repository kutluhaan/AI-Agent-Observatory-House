# Çıktı Kalitesi (`output_quality`)

**Faz:** F4.1 · **Tip:** LLM-as-judge (opsiyonel, token harcar)

Agent çıktısının **genel kalitesini** tek bir 0–1 skoruna indirger. Bileşik bir
metrik: dört boyutu birlikte tartar.

| Boyut | Ne ölçer |
|---|---|
| Correctness | Olgusal doğruluk; hata/halüsinasyon yok |
| Completeness | İsteğin tamamını karşılıyor mu |
| Clarity | Yapılandırılmış, okunabilir, net |
| Helpfulness | Kullanıcı için gerçekten faydalı/uygulanabilir |

Tek dengeli skor üretir; herhangi bir boyuttaki ciddi başarısızlık skoru düşürür.
Mevcut `task_completion` (hedefe ulaştı mı) ve `rubric` (özel kriter)
judge'larından farkı: **genel kaliteyi** tek metrikte özetler.

## YAML kullanımı

```yaml
judges:
  - type: output_quality
    threshold: 0.75       # opsiyonel, varsayılan 0.7
```

Geçer ⇔ `skor ≥ threshold`. Diğer judge'lar gibi `avg_judge_score`'a ve suite
performans paneline katkı verir.

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Prompt | `backend/app/services/test_suite/judge.py` → `_build_user_prompt` (`output_quality`) |
| Whitelist | `backend/app/services/test_suite/parser.py` → `JUDGE_TYPES` |
| UI etiketi | `frontend/src/app/(app)/test-runs/[id]/page.tsx` → `JUDGE_LABELS` |
| Test | `backend/tests/unit/test_output_quality_judge.py` |

Judge altyapısının tamamı (skorlama, eşik, hata-non-blocking) Faz B'de kuruldu;
bu yalnızca yeni bir judge tipi ekler.
