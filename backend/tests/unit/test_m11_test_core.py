"""
Unit Testler — M11 Test Core

Kapsam:
  - YAML Parser: geçerli/geçersiz YAML
  - Assertion Engine: her assertion tipi
  - RAG Evaluator: heuristic fallback (ragas olmadan)
  - AgentSandbox: history injection, tools_called tracking
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agent.base import AgentConfig, AgentResult
from app.services.test_suite.assertions import (
    AssertionResult,
    SandboxResult,
    evaluate,
    evaluate_all,
)
from app.services.test_suite.parser import ParseError, parse_yaml
from app.services.test_suite.rag_evaluator import _heuristic_evaluate


# ─── YAML Parser ──────────────────────────────────────────

def test_parse_valid_yaml():
    yaml = """
name: my-suite
description: "Test"
agent_id: "00000000-0000-0000-0000-000000000001"
cases:
  - name: basic
    input: "Merhaba"
    assertions:
      - type: response_contains
        value: "hello"
      - type: tool_called
        value: "echo"
"""
    suite = parse_yaml(yaml)
    assert suite.name == "my-suite"
    assert suite.description == "Test"
    assert str(suite.agent_id) == "00000000-0000-0000-0000-000000000001"
    assert len(suite.cases) == 1
    assert suite.cases[0].name == "basic"
    assert len(suite.cases[0].assertions) == 2
    assert suite.cases[0].assertions[0].type == "response_contains"


def test_parse_minimal_yaml():
    yaml = """
name: minimal
cases:
  - name: case1
    input: "hi"
"""
    suite = parse_yaml(yaml)
    assert suite.name == "minimal"
    assert suite.agent_id is None
    assert len(suite.cases[0].assertions) == 0


def test_parse_expected_output_shorthand():
    """expected_output → implicit response_contains assertion."""
    yaml = """
name: shorthand
cases:
  - name: c1
    input: "ping"
    expected_output: "pong"
"""
    suite = parse_yaml(yaml)
    assertions = suite.cases[0].assertions
    assert len(assertions) == 1
    assert assertions[0].type == "response_contains"
    assert assertions[0].value == "pong"


def test_parse_missing_name_raises():
    with pytest.raises(ParseError, match="name"):
        parse_yaml("cases:\n  - name: c1\n    input: x")


def test_parse_missing_cases_raises():
    with pytest.raises(ParseError, match="cases"):
        parse_yaml("name: s")


def test_parse_empty_cases_raises():
    with pytest.raises(ParseError, match="cases"):
        parse_yaml("name: s\ncases: []")


def test_parse_unknown_assertion_type_raises():
    yaml = """
name: s
cases:
  - name: c
    input: x
    assertions:
      - type: nonexistent_type
        value: foo
"""
    with pytest.raises(ParseError, match="nonexistent_type"):
        parse_yaml(yaml)


def test_parse_invalid_agent_uuid_raises():
    yaml = """
name: s
agent_id: "not-a-uuid"
cases:
  - name: c
    input: x
"""
    with pytest.raises(ParseError, match="UUID"):
        parse_yaml(yaml)


def test_parse_case_level_agent_id_overrides_suite():
    yaml = """
name: s
agent_id: "00000000-0000-0000-0000-000000000001"
cases:
  - name: c
    input: x
    agent_id: "00000000-0000-0000-0000-000000000002"
"""
    suite = parse_yaml(yaml)
    assert str(suite.cases[0].agent_id) == "00000000-0000-0000-0000-000000000002"


def test_parse_rag_context():
    yaml = """
name: s
cases:
  - name: c
    input: x
    rag_context:
      - "chunk 1"
      - "chunk 2"
"""
    suite = parse_yaml(yaml)
    assert suite.cases[0].rag_context == ["chunk 1", "chunk 2"]


# ─── Assertion Engine ─────────────────────────────────────

def _make_result(
    content: str = "hello world",
    finish_reason: str = "stop",
    steps_taken: int = 2,
    latency_ms: int = 500,
    tools_called: list[str] | None = None,
) -> SandboxResult:
    return SandboxResult(
        agent_result=AgentResult(
            content=content,
            steps_taken=steps_taken,
            trace_id="trace-1",
            finish_reason=finish_reason,
            total_usage={},
        ),
        latency_ms=latency_ms,
        tools_called=tools_called or [],
    )


def test_response_contains_pass():
    result = _make_result(content="Hello World!")
    ar = evaluate("response_contains", "hello", result)
    assert ar.passed is True


def test_response_contains_fail():
    result = _make_result(content="foo bar")
    ar = evaluate("response_contains", "hello", result)
    assert ar.passed is False
    assert "içermiyor" in ar.message


def test_tool_called_pass():
    result = _make_result(tools_called=["echo", "calc"])
    ar = evaluate("tool_called", "echo", result)
    assert ar.passed is True


def test_tool_called_fail():
    result = _make_result(tools_called=["calc"])
    ar = evaluate("tool_called", "echo", result)
    assert ar.passed is False


def test_latency_under_pass():
    result = _make_result(latency_ms=300)
    ar = evaluate("latency_under", 500, result)
    assert ar.passed is True


def test_latency_under_fail():
    result = _make_result(latency_ms=600)
    ar = evaluate("latency_under", 500, result)
    assert ar.passed is False


def test_finish_reason_is_pass():
    result = _make_result(finish_reason="stop")
    ar = evaluate("finish_reason_is", "stop", result)
    assert ar.passed is True


def test_finish_reason_is_fail():
    result = _make_result(finish_reason="tool_calls")
    ar = evaluate("finish_reason_is", "stop", result)
    assert ar.passed is False


def test_steps_under_pass():
    result = _make_result(steps_taken=2)
    ar = evaluate("steps_under", 5, result)
    assert ar.passed is True


def test_steps_under_fail():
    result = _make_result(steps_taken=6)
    ar = evaluate("steps_under", 5, result)
    assert ar.passed is False


def test_unknown_assertion_type():
    result = _make_result()
    ar = evaluate("nonexistent", "x", result)
    assert ar.passed is False
    assert "Bilinmeyen" in ar.message


def test_evaluate_all():
    result = _make_result(content="hello", tools_called=["echo"], latency_ms=200)
    assertions = [
        {"type": "response_contains", "value": "hello"},
        {"type": "tool_called", "value": "echo"},
        {"type": "latency_under", "value": 500},
    ]
    results = evaluate_all(assertions, result)
    assert len(results) == 3
    assert all(r.passed for r in results)


# ─── RAG Evaluator ────────────────────────────────────────

def test_heuristic_faithfulness():
    result = _heuristic_evaluate(
        question="What is AI?",
        answer="AI is artificial intelligence used in many applications.",
        contexts=["AI is artificial intelligence."],
        golden_contexts=None,
        k=None,
    )
    assert "faithfulness" in result
    assert result["evaluator"] == "heuristic"
    assert 0 <= result["faithfulness"] <= 1


def test_heuristic_precision_recall():
    result = _heuristic_evaluate(
        question="q",
        answer="a",
        contexts=["ctx1", "ctx2", "ctx3"],
        golden_contexts=["ctx1", "ctx3"],
        k=2,
    )
    # top 2: ctx1 (hit), ctx2 (miss) → precision=0.5, recall=0.5
    assert result["precision_at_k"] == 0.5
    assert result["recall_at_k"] == 0.5


def test_heuristic_no_golden_context():
    result = _heuristic_evaluate(
        question="q",
        answer="answer",
        contexts=["ctx"],
        golden_contexts=None,
        k=None,
    )
    assert result["context_recall"] is None
    assert result["context_precision"] is None
    assert result["precision_at_k"] == 0.0
    assert result["recall_at_k"] == 0.0
