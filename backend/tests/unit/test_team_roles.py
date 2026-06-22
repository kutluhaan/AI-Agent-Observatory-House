"""F8 — ekip rolleri + roster birim testleri."""
from types import SimpleNamespace

from app.services.team.executor import build_roster_text
from app.services.team.roles import (
    COORDINATOR,
    DEFAULT_ROLE_PROMPTS,
    TEAM_ROLES,
    default_role_prompt,
)


def test_coordinator_in_roles():
    assert COORDINATOR == "coordinator"
    assert "coordinator" in TEAM_ROLES
    assert len(TEAM_ROLES) == 5


def test_default_prompts_exist_for_all_roles():
    for r in TEAM_ROLES:
        assert default_role_prompt(r)
        assert r in DEFAULT_ROLE_PROMPTS


def test_roster_marks_you_and_lists_others():
    members = [
        SimpleNamespace(role="coordinator", agent=SimpleNamespace(name="Lead")),
        SimpleNamespace(role="researcher", agent=SimpleNamespace(name="Rex")),
    ]
    text = build_roster_text(members, me_role="researcher")
    assert "Rex" in text and "(you)" in text
    assert "Lead" in text
    # "you" yalnız researcher satırında
    you_line = [ln for ln in text.splitlines() if "(you)" in ln][0]
    assert "Rex" in you_line
