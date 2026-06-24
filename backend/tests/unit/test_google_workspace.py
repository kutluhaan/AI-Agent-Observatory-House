"""D/#13 — Google Takvim & Drive tool'ları: kayıt + scope'lar."""
import pytest

from app.services.agent.registry import ToolRegistry
from app.services.agent.tools.google_workspace import register_google_tools
from app.services.connections import google_oauth

pytestmark = pytest.mark.unit


def test_google_tools_registered():
    register_google_tools()
    for name in ("calendar_list_events", "calendar_create_event", "drive_search", "drive_read_file"):
        assert ToolRegistry.get(name) is not None


def test_calendar_and_drive_scopes_present():
    s = google_oauth.GMAIL_SCOPES
    assert "https://www.googleapis.com/auth/calendar.events" in s
    assert "https://www.googleapis.com/auth/drive.readonly" in s
    # Gmail scope'ları hâlâ duruyor (geriye uyumluluk)
    assert "https://www.googleapis.com/auth/gmail.send" in s


def test_create_event_requires_params():
    h = ToolRegistry.get("calendar_create_event")
    req = h.parameters["required"]
    assert set(req) == {"summary", "start", "end"}
