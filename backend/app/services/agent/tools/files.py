"""
Dosya sistemi tool'ları (Faz 3).

Agent'ın izole sanal FS'inde çalışır (ctx.agent_id'ye scope'lu). file_system_enabled
agent'lara runner tarafından OTOMATİK eklenir — kullanıcı tek tek seçmez. Bu yüzden
GET /agents/tools listesinde de gösterilmezler (FILE_TOOL_NAMES ile hariç tutulur).
"""
from __future__ import annotations

from app.services.agent import file_store
from app.services.agent.registry import ToolContext, ToolRegistry

FILE_TOOL_NAMES = [
    "write_file",
    "read_file",
    "modify_file",
    "delete_file",
    "list_files",
    "make_directory",
    "search_files",
    "move_file",
    "remove_folder",
]

# Veri kaybına yol açabilen (okuma dışı) tool'lar — varsayılan olarak kullanıcı onayı (HITL) ister
DESTRUCTIVE_FILE_TOOLS = ["delete_file", "modify_file", "remove_folder"]


def _no_fs() -> str:
    return "[error: this agent has no file system]"


def register_file_tools() -> None:
    """Idempotent — birden fazla çağrılabilir."""
    try:
        ToolRegistry.get("write_file")
        return
    except KeyError:
        pass

    @ToolRegistry.register(
        name="write_file",
        description="Create or overwrite a file in your file system with the given text content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, e.g. 'notes/research.md'."},
                "content": {"type": "string", "description": "Full file content."},
            },
            "required": ["path", "content"],
        },
    )
    async def write_file(ctx: ToolContext, path: str, content: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.write_file(ctx.agent_id, ctx.org_id, path, content)

    @ToolRegistry.register(
        name="read_file",
        description="Read and return the full text content of a file in your file system.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path to read."}},
            "required": ["path"],
        },
    )
    async def read_file(ctx: ToolContext, path: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.read_file(ctx.agent_id, path)

    @ToolRegistry.register(
        name="modify_file",
        description=(
            "Edit a file by replacing an exact piece of text with new text. "
            "The old_string must appear exactly in the file."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit."},
                "old_string": {"type": "string", "description": "Exact text to replace."},
                "new_string": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_string", "new_string"],
        },
    )
    async def modify_file(ctx: ToolContext, path: str, old_string: str, new_string: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.modify_file(ctx.agent_id, path, old_string, new_string)

    @ToolRegistry.register(
        name="delete_file",
        description="Delete a file (or an empty directory) from your file system.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to delete."}},
            "required": ["path"],
        },
    )
    async def delete_file(ctx: ToolContext, path: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.delete_file(ctx.agent_id, path)

    @ToolRegistry.register(
        name="list_files",
        description="List files and directories in your file system, optionally under a path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional directory to list under."},
            },
            "required": [],
        },
    )
    async def list_files(ctx: ToolContext, path: str | None = None) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.list_files(ctx.agent_id, path)

    @ToolRegistry.register(
        name="make_directory",
        description="Create a new (empty) directory in your file system to organize files.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path to create."}},
            "required": ["path"],
        },
    )
    async def make_directory(ctx: ToolContext, path: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.make_directory(ctx.agent_id, ctx.org_id, path)

    @ToolRegistry.register(
        name="search_files",
        description=(
            "Search your file system for a term — matches file names and file contents. "
            "Use this to find files instead of listing everything when you have many files."
        ),
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search term."}},
            "required": ["query"],
        },
    )
    async def search_files(ctx: ToolContext, query: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.search_files(ctx.agent_id, query)

    @ToolRegistry.register(
        name="move_file",
        description="Move or rename a file or directory within your file system.",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Current path."},
                "destination": {"type": "string", "description": "New path."},
            },
            "required": ["source", "destination"],
        },
    )
    async def move_file(ctx: ToolContext, source: str, destination: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.move_file(ctx.agent_id, source, destination)

    @ToolRegistry.register(
        name="remove_folder",
        description=(
            "Delete a folder and EVERYTHING inside it (all sub-folders and files), recursively. "
            "Destructive — only use when you intend to remove the whole directory tree."
        ),
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Folder path to remove."}},
            "required": ["path"],
        },
    )
    async def remove_folder(ctx: ToolContext, path: str) -> str:
        if ctx.agent_id is None:
            return _no_fs()
        return await file_store.remove_folder(ctx.agent_id, path)
