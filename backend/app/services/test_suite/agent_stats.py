"""
Agent performans istatistikleri — F5.1

Bir agent'ın TÜM test çalıştırmalarındaki case sonuçlarından (TestCaseResult)
toplu performans + run-bazlı trend üretir. Saf fonksiyon, canlı hesaplanır
(yeni tablo yok). compute_suite_stats'ın agent eksenindeki karşılığıdır.

Girdi satırları TestCaseResult benzeri olmalı:
  .run_id .status .latency_ms .cost_usd .total_tokens .judge_results .created_at
"""
from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


# F5.3 — bilgi-etkisi: RAG metrikleri (rag_context'li case'lerde dolu)
RAG_KEYS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]


def _compute_rag(rows: list[Any]) -> dict | None:
    """RAG metrikli case sonuçlarından ortalamalar + run-bazlı trend.

    Bilgi (knowledge/RAG) tabanlı case'lerin çıktı kalitesine etkisini gözlemler.
    Hiç RAG verisi yoksa None döner.
    """
    rag_rows = [r for r in rows if getattr(r, "rag_metrics", None)]
    if not rag_rows:
        return None

    averages = {}
    for k in RAG_KEYS:
        vals = [float(r.rag_metrics[k]) for r in rag_rows if r.rag_metrics.get(k) is not None]
        averages[k] = _mean(vals)

    # Run bazında trend (eski → yeni): her metriğin o run'daki ortalaması
    by_run: dict[Any, list[Any]] = {}
    for r in rag_rows:
        by_run.setdefault(r.run_id, []).append(r)
    trend = []
    for run_id, group in by_run.items():
        point = {"run_id": str(run_id), "created_at": min(x.created_at for x in group).isoformat()}
        for k in RAG_KEYS:
            vals = [float(x.rag_metrics[k]) for x in group if x.rag_metrics.get(k) is not None]
            point[k] = _mean(vals)
        trend.append(point)
    trend.sort(key=lambda t: t["created_at"])

    return {**averages, "cases_with_rag": len(rag_rows), "trend": trend}


def compute_agent_stats(rows: list[Any]) -> dict:
    total = len(rows)
    passed = sum(1 for r in rows if r.status == "passed")
    latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
    costs = [float(r.cost_usd) for r in rows if r.cost_usd is not None]
    tokens = [r.total_tokens for r in rows if r.total_tokens is not None]
    judge_scores = [
        float(j["score"])
        for r in rows
        for j in (r.judge_results or [])
        if j.get("score") is not None
    ]

    # Run bazında grupla → trend noktaları
    by_run: dict[Any, list[Any]] = {}
    for r in rows:
        by_run.setdefault(r.run_id, []).append(r)

    trend = []
    for run_id, group in by_run.items():
        g_total = len(group)
        g_passed = sum(1 for x in group if x.status == "passed")
        g_lat = [x.latency_ms for x in group if x.latency_ms is not None]
        created = min(x.created_at for x in group)
        trend.append({
            "run_id": str(run_id),
            "created_at": created.isoformat(),
            "pass_rate": round(g_passed / g_total, 4) if g_total else 0.0,
            "avg_latency_ms": round(sum(g_lat) / len(g_lat)) if g_lat else None,
            "cases": g_total,
        })
    trend.sort(key=lambda t: t["created_at"])

    return {
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": round(passed / total, 4) if total else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "avg_cost_usd": _mean(costs),
        "total_tokens": sum(tokens) if tokens else None,
        "avg_judge_score": _mean(judge_scores),
        "runs_count": len(by_run),
        "trend": trend,
        "rag": _compute_rag(rows),
    }
