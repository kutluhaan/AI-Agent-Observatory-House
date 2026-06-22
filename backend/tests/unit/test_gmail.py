"""G1 — Google OAuth yardımcıları + Gmail tool birim testleri."""
import base64
import uuid

import pytest

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.tools.gmail import _extract_text, _header, register_gmail_tools
from app.services.connections import google_oauth


def test_gmail_scopes_min_privilege():
    assert "https://www.googleapis.com/auth/gmail.readonly" in google_oauth.GMAIL_SCOPES
    assert "https://www.googleapis.com/auth/gmail.send" in google_oauth.GMAIL_SCOPES


def test_build_authorize_url(monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "google_client_id", "cid-123")
    monkeypatch.setattr(google_oauth.settings, "google_redirect_uri", "http://x/cb")
    url = google_oauth.build_authorize_url("nonce-abc")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=cid-123" in url
    assert "access_type=offline" in url
    assert "state=nonce-abc" in url
    assert "gmail.send" in url


def test_extract_text_plain():
    data = base64.urlsafe_b64encode(b"hello body").decode()
    payload = {"mimeType": "text/plain", "body": {"data": data}}
    assert _extract_text(payload) == "hello body"


def test_extract_text_nested_parts():
    data = base64.urlsafe_b64encode(b"nested").decode()
    payload = {"mimeType": "multipart/alternative", "body": {}, "parts": [
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>x</p>").decode()}},
        {"mimeType": "text/plain", "body": {"data": data}},
    ]}
    assert _extract_text(payload) == "nested"


def test_header_lookup():
    headers = [{"name": "From", "value": "a@b.com"}, {"name": "Subject", "value": "Hi"}]
    assert _header(headers, "from") == "a@b.com"
    assert _header(headers, "subject") == "Hi"
    assert _header(headers, "Cc") == ""


@pytest.mark.asyncio
async def test_gmail_tool_graceful_without_connection():
    """user_id yoksa (bağlantı yok) → zarif hata, exception yok."""
    register_gmail_tools()
    ctx = ToolContext(org_id=uuid.uuid4(), trace_id="t", db=None, redis=None, user_id=None)
    for name in ("gmail_search", "gmail_read", "gmail_send"):
        handler = ToolRegistry.get(name).handler
        kwargs = {"gmail_search": {"query": "x"}, "gmail_read": {"message_id": "1"},
                  "gmail_send": {"to": "a@b.com", "subject": "s", "body": "b"}}[name]
        out = await handler(ctx, **kwargs)
        assert "no Google connection" in out
