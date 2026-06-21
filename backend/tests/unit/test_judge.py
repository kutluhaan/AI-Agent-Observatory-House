"""Faz B — LLM-as-judge: parser judges + judge motoru birim testleri."""
import pytest

from app.services.agent.base import AgentResult
from app.services.providers.base import CompletionResult
from app.services.test_suite.assertions import SandboxResult
from app.services.test_suite.judge import _parse_score, evaluate_judges
from app.services.test_suite.parser import ParseError, parse_yaml


# ─── Parser: judges ───────────────────────────────────────

_BASE = """
name: s
agent_id: "11111111-1111-1111-1111-111111111111"
cases:
  - name: c1
    input: "do X"
    expected_output: "the answer"
"""


def test_parse_case_level_judges():
    yaml = _BASE + """    judges:
      - type: task_completion
      - type: rubric
        criteria: "must cite a source"
        threshold: 0.8
"""
    suite = parse_yaml(yaml)
    judges = suite.cases[0].judges
    assert [j.type for j in judges] == ["task_completion", "rubric"]
    assert judges[1].threshold == 0.8
    assert judges[1].criteria == "must cite a source"


def test_answer_correctness_falls_back_to_expected_output():
    yaml = _BASE + """    judges:
      - type: answer_correctness
"""
    suite = parse_yaml(yaml)
    assert suite.cases[0].judges[0].expected == "the answer"


def test_suite_level_judges_apply_to_all_cases():
    yaml = """
name: s
agent_id: "11111111-1111-1111-1111-111111111111"
judges:
  - type: task_completion
cases:
  - name: c1
    input: "x"
    judges:
      - type: step_efficiency
"""
    suite = parse_yaml(yaml)
    assert [j.type for j in suite.cases[0].judges] == ["task_completion", "step_efficiency"]


def test_invalid_judge_type_rejected():
    with pytest.raises(ParseError):
        parse_yaml(_BASE + "    judges:\n      - type: nonsense\n")


def test_rubric_without_criteria_rejected():
    with pytest.raises(ParseError):
        parse_yaml(_BASE + "    judges:\n      - type: rubric\n")


def test_threshold_out_of_range_rejected():
    with pytest.raises(ParseError):
        parse_yaml(_BASE + "    judges:\n      - type: task_completion\n        threshold: 2\n")


# ─── _parse_score sağlamlığı ──────────────────────────────

def test_parse_score_plain_json():
    s, r = _parse_score('{"score": 0.9, "rationale": "good"}')
    assert s == 0.9 and r == "good"


def test_parse_score_with_markdown_noise():
    s, r = _parse_score('Here:\n```json\n{"score": 0.4, "rationale": "partial"}\n```')
    assert s == 0.4 and r == "partial"


def test_parse_score_clamped():
    s, _ = _parse_score('{"score": 1.7, "rationale": "x"}')
    assert s == 1.0


# ─── evaluate_judges (sahte provider) ─────────────────────

class _FakeProvider:
    def __init__(self, content="", raise_exc=False):
        self._content = content
        self._raise = raise_exc

    async def complete(self, messages, model, **kwargs):
        if self._raise:
            raise RuntimeError("provider down")
        return CompletionResult(content=self._content, finish_reason="stop")


def _sr():
    ar = AgentResult(content="42 is the answer", steps_taken=1, trace_id="t")
    return SandboxResult(agent_result=ar, latency_ms=10, tools_called=[], trajectory=[])


@pytest.mark.asyncio
async def test_evaluate_judges_pass_and_fail():
    judges = [{"type": "task_completion", "threshold": 0.7}]
    high = await evaluate_judges(judges, "q", "a", _sr(), _FakeProvider('{"score":0.9,"rationale":"ok"}'), "m")
    assert high[0]["passed"] is True and high[0]["score"] == 0.9
    low = await evaluate_judges(judges, "q", "a", _sr(), _FakeProvider('{"score":0.3,"rationale":"no"}'), "m")
    assert low[0]["passed"] is False


@pytest.mark.asyncio
async def test_evaluate_judges_error_is_non_blocking():
    judges = [{"type": "task_completion", "threshold": 0.7}]
    res = await evaluate_judges(judges, "q", "a", _sr(), _FakeProvider(raise_exc=True), "m")
    assert res[0]["passed"] is None
    assert res[0]["score"] is None
    assert "error" in res[0]
