# Tool Call Doğruluğu (`tool_correctness`)

**Faz:** F1.1 · **Tip:** Deterministik assertion (LLM gerektirmez, token harcamaz)

Agent'ın **doğru tool'ları doğru şekilde çağırıp çağırmadığını** tek bir 0–1
skoruna indirger. Sektördeki "Tool Correctness" metriğinin (DeepEval/LangSmith)
karşılığıdır: beklenen tool çağrılarını gerçek trajectory ile katmanlı
sıkılıkta (strictness) karşılaştırır.

## Neden ayrı bir metrik?

Mevcut `tool_called` / `tools_used` / `tool_sequence` ikili (geç/kal) sonuç verir.
`tool_correctness` ise **kısmi başarıyı** ölçer (ör. 3 beklenen tool'dan 2'si
doğru → 0.67) ve tek bir konfigüre edilebilir sıkılık seviyesinde değerlendirir.

## Sıkılık seviyeleri (`strictness`)

| Seviye | Eşleşme kuralı |
|---|---|
| `name` (varsayılan) | Sadece tool **adları** — sırasız, küme bazlı |
| `args` | Ad **+ argümanlar** (beklenen argümanlar alt-küme olarak eşleşmeli) |
| `order` | Adlar trajectory'de **bu sırayla** (ordered subsequence) geçmeli |

## Skor

`score = eşleşen beklenen tool sayısı / toplam beklenen tool sayısı`

- `order` seviyesinde: adlar sırayla ne kadar eşleştiyse o oran.
- **Geçer** (passed) ⇔ `score ≥ threshold` (varsayılan `1.0` = tam doğruluk).

## YAML kullanımı

```yaml
assertions:
  # Sadece adlar (sırasız)
  - type: tool_correctness
    value:
      expected: ["web_search", "write_file"]
      strictness: name          # opsiyonel, varsayılan "name"
      threshold: 1.0            # opsiyonel, varsayılan 1.0

  # Ad + argüman
  - type: tool_correctness
    value:
      expected:
        - { name: "write_file", args: { path: "research/burotime.md" } }
        - { name: "web_search" }
      strictness: args
      threshold: 0.8

  # Sıralı
  - type: tool_correctness
    value:
      expected: ["web_search", "write_file"]
      strictness: order
```

## Sonuç (UI / API)

Assertion sonucu olarak görünür:
```json
{
  "type": "tool_correctness",
  "passed": true,
  "expected": { "expected": ["web_search","write_file"], "strictness": "name", "threshold": 1.0 },
  "actual": { "score": 1.0, "matched": ["web_search","write_file"], "missing": [], "strictness": "name" },
  "message": "Tool doğruluğu: 100% (2/2)"
}
```

## Entegrasyon noktaları

| Katman | Dosya |
|---|---|
| Değerlendirme | `backend/app/services/test_suite/assertions.py` → `_tool_correctness` |
| Parser whitelist | `backend/app/services/test_suite/parser.py` → `SUPPORTED_ASSERTION_TYPES` |
| Test | `backend/tests/unit/test_tool_correctness.py` |
| UI | Mevcut assertion listesi (test-runs detayı) otomatik gösterir |

Trajectory (her adımın tool adı + argümanı + sonucu) Faz A'da yakalanır; bu
metrik onun üzerine kurulur.
