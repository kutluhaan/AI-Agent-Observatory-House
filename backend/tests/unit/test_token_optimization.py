"""Token optimizasyonu birim testleri — tool sonucu kırpma + history bütçesi."""
from types import SimpleNamespace

from app.api.v1.conversations import (
    _HISTORY_CHAR_BUDGET,
    _HISTORY_MAX_MESSAGES,
    _select_history,
)
from app.services.agent.runner import MAX_TOOL_RESULT_CHARS, _truncate_for_context


# ─── Tool sonucu kırpma ───────────────────────────────────

def test_short_result_unchanged():
    text = "small result"
    assert _truncate_for_context(text) == text


def test_long_result_truncated_with_marker():
    text = "x" * (MAX_TOOL_RESULT_CHARS + 5000)
    out = _truncate_for_context(text)
    assert len(out) < len(text)
    assert out.startswith("x" * 100)
    assert "truncated" in out
    assert "5000 characters" in out


def test_none_result_safe():
    assert _truncate_for_context(None) == ""


# ─── History bütçesi ──────────────────────────────────────

def _msg(role, content):
    return SimpleNamespace(role=role, content=content)


def test_history_skips_empty_content():
    existing = [_msg("user", "hi"), _msg("assistant", ""), _msg("user", "again")]
    out = _select_history(existing)
    assert [m.content for m in out] == ["hi", "again"]


def test_history_chronological_order_preserved():
    existing = [_msg("user", "1"), _msg("assistant", "2"), _msg("user", "3")]
    out = _select_history(existing)
    assert [m.content for m in out] == ["1", "2", "3"]


def test_history_respects_char_budget_keeping_most_recent():
    # Her biri bütçenin yarısından büyük 3 mesaj → sadece en yenisi sığar
    big = "a" * (_HISTORY_CHAR_BUDGET // 2 + 1000)
    existing = [_msg("user", big + "_old"), _msg("assistant", big + "_mid"), _msg("user", big + "_new")]
    out = _select_history(existing)
    assert len(out) == 1
    assert out[0].content.endswith("_new")


def test_history_respects_message_cap():
    existing = [_msg("user", "m") for _ in range(_HISTORY_MAX_MESSAGES + 20)]
    out = _select_history(existing)
    assert len(out) == _HISTORY_MAX_MESSAGES
