"""Faz C — güvenlik assertion'ları + tutarlılık (repeat) parser testleri."""
import pytest

from app.services.agent.base import AgentResult
from app.services.test_suite.assertions import SandboxResult, evaluate
from app.services.test_suite.parser import ParseError, parse_yaml


def _sr(content):
    ar = AgentResult(content=content, steps_taken=1, trace_id="t")
    return SandboxResult(agent_result=ar, latency_ms=10, tools_called=[], trajectory=[])


def _ev(t, v, content):
    return evaluate(t, v, _sr(content)).passed


# ─── no_pii ───────────────────────────────────────────────

def test_no_pii_clean():
    assert _ev("no_pii", True, "The answer is 42 and the weather is sunny.") is True


def test_no_pii_detects_email():
    assert _ev("no_pii", True, "Contact me at john.doe@example.com please.") is False


def test_no_pii_detects_long_number():
    assert _ev("no_pii", True, "TC: 12345678901") is False
    assert _ev("no_pii", True, "card 4111 1111 1111 1111") is False
    # kısa sayı PII değil
    assert _ev("no_pii", True, "order 4567 shipped") is True


# ─── not_refused ──────────────────────────────────────────

def test_not_refused_normal_answer():
    assert _ev("not_refused", True, "Sure! Here is the information you asked for.") is True


def test_not_refused_detects_english_refusal():
    assert _ev("not_refused", True, "I'm sorry, I cannot help with that request.") is False
    assert _ev("not_refused", True, "I am unable to assist with this.") is False


def test_not_refused_detects_turkish_refusal():
    assert _ev("not_refused", True, "Üzgünüm, bu konuda yardımcı olamam.") is False


# ─── Parser: repeat + min_pass_rate ───────────────────────

_BASE = """
name: s
agent_id: "11111111-1111-1111-1111-111111111111"
cases:
  - name: c1
    input: "x"
"""


def test_default_repeat_is_one():
    suite = parse_yaml(_BASE)
    assert suite.cases[0].repeat == 1
    assert suite.cases[0].min_pass_rate == 1.0


def test_case_repeat_and_min_pass_rate():
    suite = parse_yaml(_BASE + "    repeat: 5\n    min_pass_rate: 0.8\n")
    assert suite.cases[0].repeat == 5
    assert suite.cases[0].min_pass_rate == 0.8


def test_suite_level_repeat_applies_and_case_overrides():
    yaml = """
name: s
agent_id: "11111111-1111-1111-1111-111111111111"
repeat: 3
cases:
  - name: a
    input: "x"
  - name: b
    input: "y"
    repeat: 10
"""
    suite = parse_yaml(yaml)
    assert suite.cases[0].repeat == 3      # suite default
    assert suite.cases[1].repeat == 10     # case override


def test_repeat_out_of_range_rejected():
    with pytest.raises(ParseError):
        parse_yaml(_BASE + "    repeat: 99\n")


def test_min_pass_rate_out_of_range_rejected():
    with pytest.raises(ParseError):
        parse_yaml(_BASE + "    min_pass_rate: 1.5\n")


def test_safety_judge_type_accepted():
    suite = parse_yaml(_BASE + "    judges:\n      - type: safety\n        threshold: 0.9\n")
    assert suite.cases[0].judges[0].type == "safety"
    assert suite.cases[0].judges[0].threshold == 0.9
