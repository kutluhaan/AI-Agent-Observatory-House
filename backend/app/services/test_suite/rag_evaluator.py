"""
RAG Evaluator — M11

RAGAS kütüphanesi mevcutsa gerçek metrikler hesaplar.
Kurulu değilse basit heuristik fallback kullanılır (test ortamında geçerli).

Döndürülen dict:
  {
    "faithfulness": float,          # 0-1: cevap context'e ne kadar bağlı
    "answer_relevancy": float,      # 0-1: cevap soruyu ne kadar yanıtlıyor
    "context_recall": float,        # 0-1: altın standart context ne kadar kapsandı
    "context_precision": float,     # 0-1: alınan context'in ne kadarı ilgili
    "precision_at_k": float,        # ilk K context'te doğru olanların oranı
    "recall_at_k": float,           # toplam doğruların kaçı K içinde
    "evaluator": "ragas" | "heuristic"
  }
"""
from __future__ import annotations

import math


async def evaluate_rag(
    question: str,
    answer: str,
    contexts: list[str],
    golden_contexts: list[str] | None = None,
    k: int | None = None,
) -> dict:
    """
    RAG kalite metrikleri hesaplar.

    Args:
        question: Kullanıcının sorusu.
        answer: Agent'ın yanıtı.
        contexts: Retrieval'dan gelen context chunk'ları.
        golden_contexts: Altın standart context'ler (TestCase.rag_context).
                         Verilirse recall/precision hesaplar.
        k: Precision@K ve Recall@K için K değeri (varsayılan: len(contexts)).
    """
    try:
        return await _ragas_evaluate(question, answer, contexts, golden_contexts, k)
    except ImportError:
        return _heuristic_evaluate(question, answer, contexts, golden_contexts, k)


async def _ragas_evaluate(
    question: str,
    answer: str,
    contexts: list[str],
    golden_contexts: list[str] | None,
    k: int | None,
) -> dict:
    """RAGAS kütüphanesiyle değerlendirme."""
    from ragas import evaluate as ragas_evaluate  # noqa: F401
    from ragas.metrics import (  # noqa: F401
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
    )
    from datasets import Dataset  # noqa: F401

    data = {
        "question": [question],
        "answer": [answer],
        "contexts": [contexts],
    }
    if golden_contexts:
        data["ground_truth"] = [" ".join(golden_contexts)]

    dataset = Dataset.from_dict(data)

    metrics = [faithfulness, answer_relevancy]
    if golden_contexts:
        metrics += [context_recall, context_precision]

    result = ragas_evaluate(dataset, metrics=metrics)
    scores = result.to_pandas().iloc[0].to_dict()

    k_eff = k or len(contexts)
    prec, rec = _precision_recall_at_k(contexts, golden_contexts or [], k_eff)

    return {
        "faithfulness": _safe_float(scores.get("faithfulness")),
        "answer_relevancy": _safe_float(scores.get("answer_relevancy")),
        "context_recall": _safe_float(scores.get("context_recall")),
        "context_precision": _safe_float(scores.get("context_precision")),
        "precision_at_k": prec,
        "recall_at_k": rec,
        "evaluator": "ragas",
    }


def _heuristic_evaluate(
    question: str,
    answer: str,
    contexts: list[str],
    golden_contexts: list[str] | None,
    k: int | None,
) -> dict:
    """
    RAGAS olmadan basit keyword-overlap tabanlı heuristik.
    Production'da değil, test ortamında kullanılır.
    """
    answer_lower = answer.lower()
    question_lower = question.lower()

    # Faithfulness: cevaptaki kelimelerin context'te geçme oranı
    answer_words = set(answer_lower.split())
    context_text = " ".join(c.lower() for c in contexts)
    context_words = set(context_text.split())
    faithfulness = (
        len(answer_words & context_words) / len(answer_words)
        if answer_words else 0.0
    )

    # Answer relevancy: soru kelimelerinin cevapta geçme oranı
    question_words = set(question_lower.split())
    answer_relevancy = (
        len(question_words & answer_words) / len(question_words)
        if question_words else 0.0
    )

    k_eff = k or len(contexts)
    prec, rec = _precision_recall_at_k(contexts, golden_contexts or [], k_eff)

    # Context recall/precision sadece golden mevcutsa
    context_recall = rec if golden_contexts else None
    context_precision = prec if golden_contexts else None

    return {
        "faithfulness": round(faithfulness, 4),
        "answer_relevancy": round(answer_relevancy, 4),
        "context_recall": context_recall,
        "context_precision": context_precision,
        "precision_at_k": prec,
        "recall_at_k": rec,
        "evaluator": "heuristic",
    }


def _precision_recall_at_k(
    retrieved: list[str],
    golden: list[str],
    k: int,
) -> tuple[float, float]:
    """Basit exact-match Precision@K ve Recall@K."""
    if not golden:
        return (0.0, 0.0)
    top_k = retrieved[:k]
    golden_set = set(golden)
    hits = sum(1 for c in top_k if c in golden_set)
    precision = hits / k if k else 0.0
    recall = hits / len(golden_set) if golden_set else 0.0
    return (round(precision, 4), round(recall, 4))


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else round(f, 4)
    except (TypeError, ValueError):
        return None
