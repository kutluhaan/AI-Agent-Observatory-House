"""
Assertion Engine — M11

Her assertion bir SandboxResult üzerinde değerlendirilir ve
AssertionResult döner.

Desteklenen tipler:
  response_contains  — LLM çıktısı belirtilen metni içeriyor mu (case-insensitive)
  tool_called        — verilen tool en az bir kez çağrıldı mı (trace'den)
  latency_under      — ms cinsinden toplam süre
  finish_reason_is   — "stop" | "tool_calls" | ...
  steps_under        — kaç adımda bitti
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.agent.base import AgentResult


@dataclass
class AssertionResult:
    type: str
    passed: bool
    expected: Any
    actual: Any
    message: str

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
        }


@dataclass
class SandboxResult:
    """AgentRunner çalıştırmasından çıkan zenginleştirilmiş sonuç."""
    agent_result: AgentResult
    latency_ms: int
    tools_called: list[str]   # çağrılan tool isimlerinin sıralı listesi


def evaluate(
    assertion_type: str,
    value: Any,
    result: SandboxResult,
) -> AssertionResult:
    """
    Tek bir assertion'ı değerlendirir.

    Args:
        assertion_type: YAML'daki type alanı.
        value: YAML'daki value alanı.
        result: Sandbox çalıştırmasının sonucu.

    Returns:
        AssertionResult — passed veya failed.
    """
    handlers = {
        "response_contains": _response_contains,
        "tool_called": _tool_called,
        "latency_under": _latency_under,
        "finish_reason_is": _finish_reason_is,
        "steps_under": _steps_under,
    }
    handler = handlers.get(assertion_type)
    if handler is None:
        return AssertionResult(
            type=assertion_type,
            passed=False,
            expected=value,
            actual=None,
            message=f"Bilinmeyen assertion tipi: '{assertion_type}'",
        )
    return handler(value, result)


def evaluate_all(
    assertions: list[dict],
    result: SandboxResult,
) -> list[AssertionResult]:
    """
    Tüm assertion'ları değerlendirir.

    Args:
        assertions: [{"type": "...", "value": ...}, ...]
        result: Sandbox sonucu.
    """
    return [evaluate(a["type"], a["value"], result) for a in assertions]


# ─── Handlers ─────────────────────────────────────────────

def _response_contains(value: str, result: SandboxResult) -> AssertionResult:
    actual = result.agent_result.content
    passed = value.lower() in actual.lower()
    return AssertionResult(
        type="response_contains",
        passed=passed,
        expected=value,
        actual=actual[:200] if len(actual) > 200 else actual,
        message="OK" if passed else f"Çıktı '{value}' içermiyor.",
    )


def _tool_called(value: str, result: SandboxResult) -> AssertionResult:
    actual = result.tools_called
    passed = value in actual
    return AssertionResult(
        type="tool_called",
        passed=passed,
        expected=value,
        actual=actual,
        message="OK" if passed else f"Tool '{value}' çağrılmadı. Çağrılanlar: {actual}",
    )


def _latency_under(value: int | float, result: SandboxResult) -> AssertionResult:
    actual = result.latency_ms
    passed = actual < int(value)
    return AssertionResult(
        type="latency_under",
        passed=passed,
        expected=int(value),
        actual=actual,
        message="OK" if passed else f"Gecikme {actual}ms — limit {int(value)}ms.",
    )


def _finish_reason_is(value: str, result: SandboxResult) -> AssertionResult:
    actual = result.agent_result.finish_reason
    passed = actual == value
    return AssertionResult(
        type="finish_reason_is",
        passed=passed,
        expected=value,
        actual=actual,
        message="OK" if passed else f"finish_reason='{actual}', beklenen='{value}'.",
    )


def _steps_under(value: int | float, result: SandboxResult) -> AssertionResult:
    actual = result.agent_result.steps_taken
    passed = actual < int(value)
    return AssertionResult(
        type="steps_under",
        passed=passed,
        expected=int(value),
        actual=actual,
        message="OK" if passed else f"{actual} adım atıldı — limit {int(value)}.",
    )
