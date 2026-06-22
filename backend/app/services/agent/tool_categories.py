"""
Tool kategorileri — F2

Tool'ları kullanıcıya kategoriler halinde sunar: file / web / self / finance /
operation. Kategori bilgisi merkezi bir haritada tutulur (her tool kaydını
değiştirmeden).

İç (internal) tool'lar: kayıtlı kalır (testler + iç kullanım için) ama agent
formunda / tool listesinde GÖSTERİLMEZ. Kullanıcı bunları seçemez.

file & skill tool'ları "auto-managed"dır:
  - file tool'ları "Dosya sistemi" anahtarıyla otomatik gelir,
  - skill tool'ları (list_skills/read_skill) skill tanımlanınca otomatik gelir.
İkisi de tek tek seçilmez; tool listesinde görünmez.
"""
from __future__ import annotations

from app.services.agent.registry import ToolRegistry
from app.services.agent.tools.files import FILE_TOOL_NAMES
from app.services.agent.tools.skills import SKILL_TOOL_NAMES

# Kullanıcıya gösterilmeyen tool'lar (gereksiz/yedekli — bkz. F2 kararı).
# Kayıtlı kalırlar; sadece UI'dan ve seçilebilir listeden gizlenirler.
INTERNAL_TOOLS: set[str] = {
    "echo",        # test yardımcısı
    "calculator",  # model zaten hesaplar
    "save_note",   # dosya sistemi bunu karşılıyor
    "get_notes",   # dosya sistemi bunu karşılıyor
    "summarize",   # model zaten özetler
    "call_agent",  # çok-agent (F8'e kadar gizli)
}

# Seçilebilir tool → kategori. file & skill tool'ları burada YOK (auto-managed).
CATEGORY_OF: dict[str, str] = {
    "web_search": "web",
    "read_url": "web",
    "think": "self",
    "write_todos": "self",
    "ask_user": "self",
    # G1: Gmail (kullanıcının bağladığı hesapla çalışır)
    "gmail_search": "email",
    "gmail_read": "email",
    "gmail_send": "email",
}

# Sıralı kategori kataloğu (UI gösterim sırası + etiketler)
CATEGORIES: list[dict] = [
    {"key": "file", "label": "Dosya", "note": "Dosya sistemiyle otomatik gelir",
     "managed_by_file_system": True, "coming_soon": False},
    {"key": "web", "label": "Web", "note": "İnternette arama ve sayfa okuma",
     "managed_by_file_system": False, "coming_soon": False},
    {"key": "self", "label": "Ajan araçları", "note": "Düşünme, görev listesi, kullanıcıya soru",
     "managed_by_file_system": False, "coming_soon": False},
    {"key": "email", "label": "E-posta (Gmail)", "note": "Bağlantılar'dan Gmail bağla; oku/ara/gönder",
     "managed_by_file_system": False, "coming_soon": False},
    {"key": "finance", "label": "Finans", "note": "Yakında",
     "managed_by_file_system": False, "coming_soon": True},
    {"key": "operation", "label": "Operasyon", "note": "Takvim, dökümanlar — yakında",
     "managed_by_file_system": False, "coming_soon": True},
]


def is_internal(name: str) -> bool:
    return name in INTERNAL_TOOLS


def category_of(name: str) -> str | None:
    """Bir tool'un kategorisini döner; iç tool ise None."""
    if name in INTERNAL_TOOLS:
        return None
    if name in FILE_TOOL_NAMES:
        return "file"
    return CATEGORY_OF.get(name)


def _brief(name: str) -> dict:
    try:
        h = ToolRegistry.get(name)
        return {"name": h.name, "description": h.description}
    except KeyError:
        return {"name": name, "description": ""}


def build_categories() -> list[dict]:
    """UI için kategorize edilmiş tool yapısı.

    Her kategori: {key, label, note, managed_by_file_system, coming_soon, tools}.
    web/self → seçilebilir tool'lar; file → file tool'ları (bilgi amaçlı, auto-managed);
    finance/operation → boş (coming_soon).
    """
    by_cat: dict[str, list[dict]] = {c["key"]: [] for c in CATEGORIES}

    for name in ToolRegistry.all_names():
        if name in INTERNAL_TOOLS or name in SKILL_TOOL_NAMES or name in FILE_TOOL_NAMES:
            continue
        cat = CATEGORY_OF.get(name)
        if cat is not None:
            by_cat[cat].append(_brief(name))

    # file kategorisi: sabit FILE_TOOL_NAMES sırasıyla (bilgi amaçlı)
    by_cat["file"] = [_brief(n) for n in FILE_TOOL_NAMES]

    out: list[dict] = []
    for c in CATEGORIES:
        tools = by_cat[c["key"]]
        if c["key"] not in ("file",):
            tools = sorted(tools, key=lambda t: t["name"])
        out.append({**c, "tools": tools})
    return out
