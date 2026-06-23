"""D/#2 — Resmi MCP Registry kaydı sadeleştirme mantığı."""
import pytest

from app.services.mcp.registry import _simplify

pytestmark = pytest.mark.unit


def test_streamable_http_remote_is_addable_and_detects_auth():
    entry = {
        "server": {
            "name": "ai.example/foo",
            "description": "desc",
            "version": "1.2.0",
            "repository": {"url": "https://github.com/x/foo"},
            "remotes": [{
                "type": "streamable-http",
                "url": "https://srv.example/mcp",
                "headers": [{"name": "Authorization", "isSecret": True, "isRequired": True}],
            }],
        }
    }
    s = _simplify(entry)
    assert s["addable"] is True
    assert s["remote_url"] == "https://srv.example/mcp"
    assert s["requires_auth"] is True
    assert s["repository_url"] == "https://github.com/x/foo"
    assert s["version"] == "1.2.0"


def test_non_http_remote_not_addable():
    s = _simplify({"server": {"name": "ns/bar", "remotes": [{"type": "sse", "url": "https://y"}]}})
    assert s["addable"] is False and s["remote_url"] is None


def test_packages_only_not_addable():
    # stdio/npm paketleri çalıştıramayız → eklenebilir değil
    s = _simplify({"server": {"name": "ns/baz", "packages": [{"identifier": "some-npm"}]}})
    assert s["addable"] is False and s["requires_auth"] is False


def test_http_remote_without_secret_header_no_auth():
    entry = {"server": {"name": "ns/q", "remotes": [{"type": "streamable-http", "url": "https://z/mcp", "headers": []}]}}
    s = _simplify(entry)
    assert s["addable"] is True and s["requires_auth"] is False
