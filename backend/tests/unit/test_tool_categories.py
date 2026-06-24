"""F2 — tool kategorileri birim testleri."""
from app.services.agent.tools.builtin import register_builtin_tools
from app.services.agent.tools.files import register_file_tools
from app.services.agent.tools.finance import register_finance_tools
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
    register_finance_tools()
    from app.services.agent.tools.google_workspace import register_google_tools
    register_google_tools()
    from app.services.agent.tools.notify import register_notify_tools
    register_notify_tools()
    from app.services.agent.tools.utility import register_utility_tools
    register_utility_tools()
    from app.services.agent.tools.sql import register_sql_tools
    register_sql_tools()
    from app.services.agent.tools.github import register_github_tools
    register_github_tools()


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
    assert [c["key"] for c in cats] == ["file", "web", "self", "email", "finance", "operation", "messaging", "utility", "database", "github"]


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


def test_operation_has_google_tools_and_active():
    """D/#13: operation kategorisi artık Google Takvim/Drive ile dolu + aktif."""
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    assert cats["operation"]["coming_soon"] is False
    names = {t["name"] for t in cats["operation"]["tools"]}
    assert {"calendar_list_events", "calendar_create_event", "drive_search", "drive_read_file"} <= names
    assert category_of("drive_search") == "operation"


def test_finance_has_tools_and_active():
    """D/#2: finance kategorisi artık dolu + aktif."""
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    assert cats["finance"]["coming_soon"] is False
    names = {t["name"] for t in cats["finance"]["tools"]}
    assert {"get_crypto_price", "get_stock_quote", "get_technical_indicators", "get_market_news"} <= names
    assert category_of("get_crypto_price") == "finance"


def test_messaging_category_has_notify():
    """loop it.4: messaging kategorisi send_notification ile dolu + aktif."""
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    assert cats["messaging"]["coming_soon"] is False
    names = {t["name"] for t in cats["messaging"]["tools"]}
    assert "send_notification" in names
    assert category_of("send_notification") == "messaging"


def test_utility_category_has_tools():
    """loop it.7: utility kategorisi zaman/çevrim tool'larıyla dolu."""
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    names = {t["name"] for t in cats["utility"]["tools"]}
    assert {"get_current_datetime", "date_calculate", "convert_units", "convert_currency"} <= names
    assert category_of("convert_units") == "utility"


def test_database_category_has_sql_tools():
    """loop it.8: database kategorisi SQL tool'larıyla dolu."""
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    names = {t["name"] for t in cats["database"]["tools"]}
    assert {"sql_query", "sql_schema", "sql_sample"} <= names
    assert category_of("sql_query") == "database"


def test_github_category_has_tools():
    """loop it.9: github kategorisi 4 tool ile dolu."""
    _setup()
    cats = {c["key"]: c for c in build_categories()}
    names = {t["name"] for t in cats["github"]["tools"]}
    assert {"github_search", "github_repo_info", "github_issues", "github_read_file"} <= names
    assert category_of("github_search") == "github"


def test_skill_tools_not_in_selectable_categories():
    _setup()
    shown = {t["name"] for c in build_categories() for t in c["tools"]}
    assert "list_skills" not in shown
    assert "read_skill" not in shown
