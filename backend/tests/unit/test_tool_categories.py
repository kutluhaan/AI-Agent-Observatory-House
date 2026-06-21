"""F2 — tool kategorileri birim testleri."""
from app.services.agent.tools.builtin import register_builtin_tools
from app.services.agent.tools.files import register_file_tools
from app.services.agent.tools.research import register_research_tools
from app.services.agent.tools.skills import register_skill_tools
from app.services.agent.tool_categories import (
    INTERNAL_TOOLS,
    build_categories,
    category_of,
)


def _setup():
    # Hepsi idempotent
    register_builtin_tools()
    register_research_tools()
    register_file_tools()
    register_skill_tools()


def test_category_of():
    _setup()
    assert category_of("web_search") == "web"
    assert category_of("read_url") == "web"
    assert category_of("think") == "self"
    assert category_of("write_file") == "file"
    assert category_of("echo") is None        # internal
    assert category_of("nonexistent") is None


def test_build_categories_order_and_labels():
    _setup()
    cats = build_categories()
    assert [c["key"] for c in cats] == ["file", "web", "self", "finance", "operation"]


def test_web_and_self_have_expected_tools():
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    web = {t["name"] for t in cats["web"]["tools"]}
    assert "web_search" in web and "read_url" in web
    self_ = {t["name"] for t in cats["self"]["tools"]}
    assert {"think", "write_todos", "ask_user"} <= self_


def test_internal_tools_hidden_everywhere():
    _setup()
    shown = {t["name"] for c in build_categories() for t in c["tools"]}
    assert shown.isdisjoint(INTERNAL_TOOLS)
    assert "echo" not in shown
    assert "calculator" not in shown
    assert "summarize" not in shown


def test_file_category_managed_and_lists_file_tools():
    _setup()
    file_cat = next(c for c in build_categories() if c["key"] == "file")
    assert file_cat["managed_by_file_system"] is True
    names = {t["name"] for t in file_cat["tools"]}
    assert "write_file" in names and "remove_folder" in names


def test_finance_operation_empty_and_coming_soon():
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    for key in ("finance", "operation"):
        assert cats[key]["tools"] == []
        assert cats[key]["coming_soon"] is True


def test_skill_tools_not_in_selectable_categories():
    _setup()
    shown = {t["name"] for c in build_categories() for t in c["tools"]}
    assert "list_skills" not in shown
    assert "read_skill" not in shown
