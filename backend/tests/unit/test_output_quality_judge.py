"""F4.1 — bileşik output_quality judge'ı birim testleri."""
from app.services.agent.base import AgentResult
from app.services.test_suite.assertions import SandboxResult
from app.services.test_suite.judge import _build_user_prompt
from app.services.test_suite.parser import JUDGE_TYPES, ParseError, parse_yaml

import pytest


def _sr():
    ar = AgentResult(content="answer", steps_taken=1, trace_id="t")
    return SandboxResult(agent_result=ar, latency_ms=10, tools_called=[], trajectory=[])


def test_output_quality_registered_as_judge_type():
    assert "output_quality" in JUDGE_TYPES


def test_output_quality_prompt_covers_four_dimensions():
    p = _build_user_prompt({"type": "output_quality"}, "do X", "the answer", _sr())
    for dim in ("Correctness", "Completeness", "Clarity", "Helpfulness"):
        assert dim in p
    assert "0.0-1.0" in p


def test_output_quality_accepted_in_yaml():
    yaml = """
name: s
agent_id: "11111111-1111-1111-1111-111111111111"
cases:
  - name: c1
    input: "x"
    judges:
      - type: output_quality
        threshold: 0.75
"""
    suite = parse_yaml(yaml)
    j = suite.cases[0].judges[0]
    assert j.type == "output_quality"
    assert j.threshold == 0.75


def test_unknown_judge_still_rejected():
    with pytest.raises(ParseError):
        parse_yaml(
            'name: s\nagent_id: "11111111-1111-1111-1111-111111111111"\n'
            'cases:\n  - name: c\n    input: x\n    judges:\n      - type: made_up\n'
        )
