"""
ExperimentRunner — M11

Bir TestSuite'teki tüm TestCase'leri çalıştırır.
Paralel (asyncio.gather) veya sıralı mod desteklenir.

Akış:
  1. TestRun'ı "running" olarak işaretle, started_at kaydet
  2. TestCase listesini yükle
  3. parallel=True → asyncio.gather; False → sıralı döngü
  4. Her case tamamlanınca WebSocket'e progress event gönder
  5. Tüm case'ler bitince summary hesapla, TestRun'ı "completed" yap
  6. Herhangi beklenmedik hata → TestRun'ı "failed" yap

WebSocket event formatı (ws/test_runs.py manager'ına broadcast):
  {
    "type": "case_completed" | "case_failed",
    "run_id": "uuid",
    "case_id": "uuid",
    "case_name": "...",
    "status": "passed" | "failed" | "error",
    "latency_ms": 123,
    "assertions_passed": 2,
    "assertions_total": 3,
  }
  {
    "type": "run_completed",
    "run_id": "uuid",
    "summary": {...},
  }
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_suite import TestCase, TestCaseResult, TestRun
from app.services.test_suite.case_runner import run_case

logger = structlog.get_logger()


class ExperimentRunner:
    """
    TestRun için tüm case'leri orkestre eder.
    background_task olarak çalışır — HTTP response bloklamaz.
    """

    def __init__(
        self,
        run_id: uuid.UUID,
        db_factory: Any,          # async_sessionmaker
        redis: Any,
        ws_manager: Any | None = None,
    ) -> None:
        self.run_id = run_id
        self.db_factory = db_factory
        self.redis = redis
        self.ws_manager = ws_manager

    async def run(self) -> None:
        """
        Arka plan task'ı olarak çalışır.
        Exception'ları içeride yönetir — dışarı sızmaz.
        """
        async with self.db_factory() as db:
            run = await self._get_run(db)
            if run is None:
                logger.error("experiment_runner.run_not_found", run_id=str(self.run_id))
                return

            await self._mark_running(db, run)

            cases = await self._load_cases(db, run)
            if not cases:
                await self._finalize(db, run, [])
                return

            try:
                if run.parallel:
                    # Parallel modda her case kendi session'ını kullanır;
                    # run nesnesi outer session'da kalır — sadece scalar attr'ları okunur.
                    results = await self._run_parallel(run, cases)
                else:
                    results = await self._run_sequential(db, run, cases)

                await self._finalize(db, run, results)
            except Exception as exc:
                logger.error("experiment_runner.fatal_error", run_id=str(self.run_id), error=str(exc))
                await self._mark_failed(db, run)

    # ─── Internal ─────────────────────────────────────────

    async def _get_run(self, db: AsyncSession) -> TestRun | None:
        result = await db.execute(
            select(TestRun).where(TestRun.id == self.run_id)
        )
        return result.scalar_one_or_none()

    async def _load_cases(self, db: AsyncSession, run: TestRun) -> list[TestCase]:
        result = await db.execute(
            select(TestCase).where(TestCase.suite_id == run.suite_id)
        )
        return list(result.scalars().all())

    async def _mark_running(self, db: AsyncSession, run: TestRun) -> None:
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(run)

    async def _mark_failed(self, db: AsyncSession, run: TestRun) -> None:
        run.status = "failed"
        run.ended_at = datetime.now(UTC)
        await db.commit()

    async def _run_parallel(
        self,
        run: TestRun,
        cases: list[TestCase],
    ) -> list[TestCaseResult]:
        """
        Her case kendi AsyncSession'ında çalışır.
        AsyncSession eşzamanlı (concurrent) kullanıma güvenli değil —
        paralel görevler paylaşılan bir session kullanmamalı.
        """
        async def _run_one(case: TestCase) -> TestCaseResult:
            async with self.db_factory() as session:
                res = await run_case(case, run, session, self.redis)
                await session.commit()
                return res

        tasks = [_run_one(case) for case in cases]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        case_results: list[TestCaseResult] = []
        for case, res in zip(cases, results):
            if isinstance(res, Exception):
                logger.error(
                    "experiment_runner.case_exception",
                    case_id=str(case.id), error=str(res),
                )
            else:
                case_results.append(res)
                await self._broadcast_case(run, case, res)
        return case_results

    async def _run_sequential(
        self,
        db: AsyncSession,
        run: TestRun,
        cases: list[TestCase],
    ) -> list[TestCaseResult]:
        case_results: list[TestCaseResult] = []
        for case in cases:
            try:
                res = await run_case(case, run, db, self.redis)
                case_results.append(res)
                await db.commit()
                await self._broadcast_case(run, case, res)
            except Exception as exc:
                logger.error(
                    "experiment_runner.case_exception",
                    case_id=str(case.id), error=str(exc),
                )
        return case_results

    async def _finalize(
        self,
        db: AsyncSession,
        run: TestRun,
        results: list[TestCaseResult],
    ) -> None:
        summary = _compute_summary(results)
        run.status = "completed"
        run.ended_at = datetime.now(UTC)
        run.summary = summary
        await db.commit()

        if self.ws_manager:
            await self.ws_manager.broadcast(str(run.organization_id), {
                "type": "run_completed",
                "run_id": str(run.id),
                "summary": summary,
            })
        logger.info(
            "experiment_runner.completed",
            run_id=str(run.id),
            summary=summary,
        )

    async def _broadcast_case(
        self,
        run: TestRun,
        case: TestCase,
        result: TestCaseResult,
    ) -> None:
        if not self.ws_manager:
            return
        assertions_passed = sum(
            1 for a in (result.assertions_results or []) if a.get("passed")
        )
        await self.ws_manager.broadcast(str(run.organization_id), {
            "type": "case_completed" if result.status in ("passed", "skipped") else "case_failed",
            "run_id": str(run.id),
            "case_id": str(case.id),
            "case_name": case.name,
            "status": result.status,
            "latency_ms": result.latency_ms,
            "assertions_passed": assertions_passed,
            "assertions_total": len(result.assertions_results or []),
        })


def _compute_summary(results: list[TestCaseResult]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    errored = sum(1 for r in results if r.status == "error")
    latencies = [r.latency_ms for r in results if r.latency_ms is not None]
    tokens = [r.total_tokens for r in results if r.total_tokens is not None]
    costs = [r.cost_usd for r in results if r.cost_usd is not None]
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "error": errored,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "total_tokens": sum(tokens) if tokens else None,
        "total_cost_usd": round(sum(costs), 6) if costs else None,
    }
