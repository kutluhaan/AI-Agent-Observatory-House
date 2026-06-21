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

import re
from dataclasses import dataclass, field
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
    # Adım-adım trajectory: [{name, arguments, result, ok}] — sıralı tool çağrıları
    trajectory: list[dict] = field(default_factory=list)
    cost_usd: float | None = None

    @property
    def total_tokens(self) -> int:
        u = self.agent_result.total_usage
        return sum(u.values()) if u else 0


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
        "response_not_contains": _response_not_contains,
        "response_equals": _response_equals,
        "response_regex": _response_regex,
        "tool_called": _tool_called,
        "tool_called_with_args": _tool_called_with_args,
        "tool_sequence": _tool_sequence,
        "tools_used": _tools_used,
        "no_tool_errors": _no_tool_errors,
        "latency_under": _latency_under,
        "finish_reason_is": _finish_reason_is,
        "steps_under": _steps_under,
        "tokens_under": _tokens_under,
        "cost_under": _cost_under,
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


def _response_not_contains(value: str, result: SandboxResult) -> AssertionResult:
    actual = result.agent_result.content or ""
    passed = str(value).lower() not in actual.lower()
    return AssertionResult(
        type="response_not_contains",
        passed=passed,
        expected=value,
        actual=actual[:200],
        message="OK" if passed else f"Çıktı yasaklı metni '{value}' içeriyor.",
    )


def _response_equals(value: str, result: SandboxResult) -> AssertionResult:
    actual = (result.agent_result.content or "").strip()
    passed = actual.lower() == str(value).strip().lower()
    return AssertionResult(
        type="response_equals",
        passed=passed,
        expected=value,
        actual=actual[:200],
        message="OK" if passed else "Çıktı beklenen metne tam eşit değil.",
    )


def _response_regex(value: str, result: SandboxResult) -> AssertionResult:
    actual = result.agent_result.content or ""
    try:
        passed = re.search(str(value), actual, re.IGNORECASE | re.MULTILINE) is not None
        msg = "OK" if passed else f"Çıktı '/{value}/' desenine uymuyor."
    except re.error as exc:
        passed = False
        msg = f"Geçersiz regex: {exc}"
    return AssertionResult(
        type="response_regex",
        passed=passed,
        expected=value,
        actual=actual[:200],
        message=msg,
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


def _tool_called_with_args(value: Any, result: SandboxResult) -> AssertionResult:
    """value: {"name": "...", "args": {...}} — bu isimde, argümanları verilen
    alt-kümeyi içeren bir tool çağrısı var mı."""
    name = (value or {}).get("name") if isinstance(value, dict) else None
    want_args = (value or {}).get("args", {}) if isinstance(value, dict) else {}
    matches = []
    for call in result.trajectory:
        if call.get("name") != name:
            continue
        call_args = call.get("arguments") or {}
        if all(str(call_args.get(k)) == str(v) for k, v in want_args.items()):
            matches.append(call)
    passed = len(matches) > 0
    return AssertionResult(
        type="tool_called_with_args",
        passed=passed,
        expected=value,
        actual=[{"name": c["name"], "arguments": c.get("arguments")} for c in result.trajectory if c.get("name") == name],
        message="OK" if passed else f"'{name}' beklenen argümanlarla çağrılmadı.",
    )


def _tool_sequence(value: Any, result: SandboxResult) -> AssertionResult:
    """value: [name1, name2, ...] — bu isimler trajectory'de bu SIRAYLA
    (aralarında başka çağrılar olabilir) geçiyor mu (ordered subsequence)."""
    want = list(value) if isinstance(value, list) else []
    seq = [c.get("name") for c in result.trajectory]
    i = 0
    for name in seq:
        if i < len(want) and name == want[i]:
            i += 1
    passed = i == len(want)
    return AssertionResult(
        type="tool_sequence",
        passed=passed,
        expected=want,
        actual=seq,
        message="OK" if passed else f"Beklenen tool sırası bulunamadı. Gerçek: {seq}",
    )


def _tools_used(value: Any, result: SandboxResult) -> AssertionResult:
    """value: [name1, name2] — bu tool'ların HEPSİ en az bir kez kullanıldı mı."""
    want = set(value) if isinstance(value, list) else set()
    used = set(result.tools_called)
    missing = want - used
    passed = len(missing) == 0
    return AssertionResult(
        type="tools_used",
        passed=passed,
        expected=sorted(want),
        actual=sorted(used),
        message="OK" if passed else f"Eksik tool'lar: {sorted(missing)}",
    )


def _no_tool_errors(value: Any, result: SandboxResult) -> AssertionResult:
    """value: true — hiçbir tool çağrısı hata döndürmedi mi."""
    failed = [c["name"] for c in result.trajectory if not c.get("ok", True)]
    passed = len(failed) == 0
    return AssertionResult(
        type="no_tool_errors",
        passed=passed,
        expected=True,
        actual={"failed_tools": failed},
        message="OK" if passed else f"Hata döndüren tool'lar: {failed}",
    )


def _tokens_under(value: int | float, result: SandboxResult) -> AssertionResult:
    actual = result.total_tokens
    passed = actual < int(value)
    return AssertionResult(
        type="tokens_under",
        passed=passed,
        expected=int(value),
        actual=actual,
        message="OK" if passed else f"{actual} token harcandı — limit {int(value)}.",
    )


def _cost_under(value: int | float, result: SandboxResult) -> AssertionResult:
    actual = result.cost_usd
    if actual is None:
        return AssertionResult(
            type="cost_under", passed=False, expected=float(value), actual=None,
            message="Maliyet hesaplanamadı (token bilgisi yok).",
        )
    passed = actual < float(value)
    return AssertionResult(
        type="cost_under",
        passed=passed,
        expected=float(value),
        actual=round(actual, 6),
        message="OK" if passed else f"Maliyet ${actual:.6f} — limit ${float(value):.6f}.",
    )
