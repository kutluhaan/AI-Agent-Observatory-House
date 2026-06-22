"""F6 — _run_scenario birim testleri (sahte sandbox + sahte db)."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent.base import AgentResult
from app.services.test_suite.assertions import SandboxResult
from app.services.test_suite.case_runner import _run_scenario


class _FakeSandbox:
    """Önceden tanımlı çıktıları sırayla döndürür; history çağrılarını kaydeder."""
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[tuple[str, list]] = []

    async def run(self, user_input: str, history=None) -> SandboxResult:
        self.calls.append((user_input, list(history or [])))
        out = self.outputs.pop(0)
        ar = AgentResult(content=out, steps_taken=1, trace_id="t", total_usage={"in": 1, "out": 1})
        return SandboxResult(agent_result=ar, latency_ms=10, tools_called=[], trajectory=[], cost_usd=0.001)


def _case(steps):
    return SimpleNamespace(id=uuid.uuid4(), steps=steps)


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_scenario_all_steps_pass():
    case = _case([
        {"input": "Paris bul", "assertions": [{"type": "response_contains", "value": "Paris"}]},
        {"input": "onayla", "assertions": [{"type": "response_contains", "value": "tamam"}]},
    ])
    sandbox = _FakeSandbox(["Paris uçuşları", "tamam onaylandı"])
    run = SimpleNamespace(id=uuid.uuid4())

    result = await _run_scenario(_db(), run, case, sandbox)

    assert result.status == "passed"
    assert len(result.steps_results) == 2
    assert all(s["passed"] for s in result.steps_results)


@pytest.mark.asyncio
async def test_scenario_continues_after_failed_step():
    """'Devam et, hepsini raporla': 1. adım kalsa da 2. adım çalışır."""
    case = _case([
        {"input": "a", "assertions": [{"type": "response_contains", "value": "YOK"}]},  # kalır
        {"input": "b", "assertions": [{"type": "response_contains", "value": "iki"}]},   # geçer
    ])
    sandbox = _FakeSandbox(["bir", "iki"])
    run = SimpleNamespace(id=uuid.uuid4())

    result = await _run_scenario(_db(), run, case, sandbox)

    assert result.status == "failed"  # bir adım kaldı → case failed
    assert len(result.steps_results) == 2  # ama ikisi de çalıştı
    assert result.steps_results[0]["passed"] is False
    assert result.steps_results[1]["passed"] is True


@pytest.mark.asyncio
async def test_scenario_accumulates_conversation_history():
    case = _case([
        {"input": "ilk soru", "assertions": []},
        {"input": "ikinci soru", "assertions": []},
    ])
    sandbox = _FakeSandbox(["ilk yanıt", "ikinci yanıt"])
    run = SimpleNamespace(id=uuid.uuid4())

    await _run_scenario(_db(), run, case, sandbox)

    # 1. çağrıda history boş; 2. çağrıda önceki tur (user+assistant) inject edilmiş
    assert sandbox.calls[0][1] == []
    assert sandbox.calls[1][1] == [
        {"role": "user", "content": "ilk soru"},
        {"role": "assistant", "content": "ilk yanıt"},
    ]
