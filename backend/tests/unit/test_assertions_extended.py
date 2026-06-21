"""Faz A — yeni deterministik assertion'lar + maliyet tahmini birim testleri."""
from app.services.agent.base import AgentResult
from app.services.pricing import estimate_cost
from app.services.test_suite.assertions import SandboxResult, evaluate


def _sr(content="hello world", trajectory=None, usage=None, cost=None, finish="stop", steps=2):
    traj = trajectory or []
    ar = AgentResult(content=content, steps_taken=steps, trace_id="t", finish_reason=finish, total_usage=usage or {})
    return SandboxResult(
        agent_result=ar,
        latency_ms=100,
        tools_called=[c["name"] for c in traj],
        trajectory=traj,
        cost_usd=cost,
    )


def _ev(t, v, sr):
    return evaluate(t, v, sr).passed


# ─── Çıktı assertion'ları ─────────────────────────────────

def test_response_not_contains():
    sr = _sr("the answer is 42")
    assert _ev("response_not_contains", "error", sr) is True
    assert _ev("response_not_contains", "answer", sr) is False


def test_response_equals_trim_case_insensitive():
    sr = _sr("  Hello World  ")
    assert _ev("response_equals", "hello world", sr) is True
    assert _ev("response_equals", "hello", sr) is False


def test_response_regex():
    sr = _sr("order #12345 shipped")
    assert _ev("response_regex", r"#\d+", sr) is True
    assert _ev("response_regex", r"^\d+$", sr) is False
    # geçersiz regex → fail, çökme yok
    assert _ev("response_regex", r"[unclosed", sr) is False


# ─── Trajectory / tool assertion'ları ─────────────────────

def _traj():
    return [
        {"name": "web_search", "arguments": {"query": "burotime"}, "result": "results...", "ok": True},
        {"name": "write_file", "arguments": {"path": "a.md", "content": "x"}, "result": "Wrote 'a.md'.", "ok": True},
        {"name": "delete_file", "arguments": {"path": "b.md"}, "result": "[delete_file error: not found]", "ok": False},
    ]


def test_tool_called_with_args():
    sr = _sr(trajectory=_traj())
    assert _ev("tool_called_with_args", {"name": "web_search", "args": {"query": "burotime"}}, sr) is True
    assert _ev("tool_called_with_args", {"name": "web_search", "args": {"query": "other"}}, sr) is False
    assert _ev("tool_called_with_args", {"name": "write_file", "args": {"path": "a.md"}}, sr) is True


def test_tool_sequence_ordered_subsequence():
    sr = _sr(trajectory=_traj())
    assert _ev("tool_sequence", ["web_search", "write_file"], sr) is True
    assert _ev("tool_sequence", ["web_search", "delete_file"], sr) is True
    assert _ev("tool_sequence", ["write_file", "web_search"], sr) is False  # ters sıra


def test_tools_used_set():
    sr = _sr(trajectory=_traj())
    assert _ev("tools_used", ["web_search", "write_file"], sr) is True
    assert _ev("tools_used", ["web_search", "read_file"], sr) is False


def test_no_tool_errors():
    ok_traj = [{"name": "web_search", "arguments": {}, "result": "ok", "ok": True}]
    assert _ev("no_tool_errors", True, _sr(trajectory=ok_traj)) is True
    assert _ev("no_tool_errors", True, _sr(trajectory=_traj())) is False  # delete_file errored


# ─── Operasyonel ──────────────────────────────────────────

def test_tokens_under():
    sr = _sr(usage={"prompt_tokens": 1000, "completion_tokens": 500})
    assert _ev("tokens_under", 2000, sr) is True
    assert _ev("tokens_under", 1000, sr) is False


def test_cost_under():
    assert _ev("cost_under", 0.01, _sr(cost=0.005)) is True
    assert _ev("cost_under", 0.001, _sr(cost=0.005)) is False
    # maliyet None → fail
    assert _ev("cost_under", 0.01, _sr(cost=None)) is False


# ─── Maliyet tahmini ──────────────────────────────────────

def test_estimate_cost_gemini():
    cost = estimate_cost("gemini", "gemini-2.5-flash", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    assert cost == round(0.30 + 2.50, 6)  # 1M in + 1M out


def test_estimate_cost_ollama_free():
    assert estimate_cost("ollama", "qwen3:4b", {"prompt_tokens": 5000, "completion_tokens": 5000}) == 0.0


def test_estimate_cost_none_when_no_usage():
    assert estimate_cost("gemini", "gemini-2.5-flash", None) is None
    assert estimate_cost("gemini", "gemini-2.5-flash", {"prompt_tokens": 0, "completion_tokens": 0}) is None
