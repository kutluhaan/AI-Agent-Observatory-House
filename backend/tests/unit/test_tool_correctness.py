"""F1.1 — tool_correctness assertion birim testleri."""
from app.services.agent.base import AgentResult
from app.services.test_suite.assertions import SandboxResult, evaluate


def _sr(trajectory):
    ar = AgentResult(content="ok", steps_taken=1, trace_id="t")
    return SandboxResult(
        agent_result=ar, latency_ms=10,
        tools_called=[c["name"] for c in trajectory], trajectory=trajectory,
    )


def _traj():
    return [
        {"name": "web_search", "arguments": {"query": "burotime"}, "result": "r", "ok": True},
        {"name": "think", "arguments": {"thought": "..."}, "result": "r", "ok": True},
        {"name": "write_file", "arguments": {"path": "research/b.md", "content": "x"}, "result": "Wrote", "ok": True},
    ]


def _ev(value, traj):
    return evaluate("tool_correctness", value, _sr(traj))


def test_name_strictness_full_score():
    r = _ev({"expected": ["web_search", "write_file"]}, _traj())
    assert r.passed is True
    assert r.actual["score"] == 1.0


def test_name_strictness_partial():
    r = _ev({"expected": ["web_search", "read_file"], "threshold": 1.0}, _traj())
    assert r.passed is False
    assert r.actual["score"] == 0.5
    assert r.actual["missing"] == ["read_file"]


def test_partial_passes_with_lower_threshold():
    r = _ev({"expected": ["web_search", "read_file"], "threshold": 0.5}, _traj())
    assert r.passed is True


def test_args_strictness():
    ok = _ev({"expected": [{"name": "write_file", "args": {"path": "research/b.md"}}], "strictness": "args"}, _traj())
    assert ok.passed is True
    bad = _ev({"expected": [{"name": "write_file", "args": {"path": "other.md"}}], "strictness": "args"}, _traj())
    assert bad.passed is False


def test_order_strictness():
    ok = _ev({"expected": ["web_search", "write_file"], "strictness": "order"}, _traj())
    assert ok.passed is True
    # ters sıra → eşleşmez
    bad = _ev({"expected": ["write_file", "web_search"], "strictness": "order"}, _traj())
    assert bad.passed is False
    assert bad.actual["score"] == 0.5


def test_empty_expected_passes():
    r = _ev({"expected": []}, _traj())
    assert r.passed is True
