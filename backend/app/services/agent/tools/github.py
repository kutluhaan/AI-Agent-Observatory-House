"""
GitHub tool'ları — GitHub kategorisi (loop it.9)

github_search    : repo / kod / issue arama
github_repo_info : repo özeti (yıldız, dil, açıklama, README parçası)
github_issues    : repo issue/PR listele veya tek issue/PR detayı
github_read_file : repo'dan dosya içeriği oku (path + branch)

Org'da yapılandırılmış (GithubConnection, PAT şifreli) token ile çalışır.
Tool'lar exception fırlatmaz — hatayı string döner.
"""
from __future__ import annotations

import base64

import httpx
from sqlalchemy import select

from app.core.encryption import decrypt_value
from app.models.github_connection import GithubConnection
from app.services.agent.registry import ToolContext, ToolRegistry

_API = "https://api.github.com"
_NO_CONN = "[github error: GitHub token yok — Bağlantılar (GitHub)'tan bir PAT ekle]"


async def _resolve_token(ctx: ToolContext) -> str | None:
    if ctx.db is None:
        return None
    row = (await ctx.db.execute(
        select(GithubConnection).where(
            GithubConnection.organization_id == ctx.org_id, GithubConnection.is_active.is_(True)
        ).order_by(GithubConnection.created_at.asc())
    )).scalars().first()
    return decrypt_value(row.encrypted_token) if row else None


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ObservatoryGithubBot/1.0",
    }


async def _gh(token: str, path: str, params: dict | None = None) -> tuple[int, object]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{_API}{path}", headers=_headers(token), params=params)
    try:
        return r.status_code, r.json()
    except Exception:  # noqa: BLE001
        return r.status_code, r.text


def register_github_tools() -> None:
    if "github_search" in ToolRegistry.all_names():
        return

    @ToolRegistry.register(
        "github_search",
        "Search GitHub. kind='repositories' (default), 'code', or 'issues'. Returns top matches.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "GitHub search query, e.g. 'fastapi stars:>1000'."},
            "kind": {"type": "string", "enum": ["repositories", "code", "issues"], "description": "Search type."},
        }, "required": ["query"]},
    )
    async def github_search(ctx: ToolContext, query: str, kind: str = "repositories") -> str:
        token = await _resolve_token(ctx)
        if not token:
            return _NO_CONN
        if kind not in ("repositories", "code", "issues"):
            kind = "repositories"
        status, data = await _gh(token, f"/search/{kind}", {"q": query, "per_page": 5})
        if status != 200 or not isinstance(data, dict):
            return f"[github error: search failed ({status}) {str(data)[:160]}]"
        items = data.get("items", [])
        if not items:
            return "Eşleşme yok."
        out = []
        for it in items:
            if kind == "repositories":
                out.append(f"- {it['full_name']} ⭐{it.get('stargazers_count', 0)} · {it.get('description') or ''}")
            elif kind == "issues":
                out.append(f"- #{it.get('number')} [{it.get('state')}] {it.get('title')} ({it.get('html_url')})")
            else:
                out.append(f"- {it.get('repository', {}).get('full_name', '')}: {it.get('path')}")
        return "\n".join(out)

    @ToolRegistry.register(
        "github_repo_info",
        "Get summary info for a GitHub repository (owner/name): description, stars, language, README excerpt.",
        {"type": "object", "properties": {
            "repo": {"type": "string", "description": "Repository as 'owner/name', e.g. 'tiangolo/fastapi'."},
        }, "required": ["repo"]},
    )
    async def github_repo_info(ctx: ToolContext, repo: str) -> str:
        token = await _resolve_token(ctx)
        if not token:
            return _NO_CONN
        if "/" not in repo:
            return "[github error: repo 'owner/name' biçiminde olmalı]"
        status, data = await _gh(token, f"/repos/{repo}")
        if status != 200 or not isinstance(data, dict):
            return f"[github error: repo failed ({status}) {str(data)[:160]}]"
        info = (f"{data['full_name']} ⭐{data.get('stargazers_count', 0)} · fork {data.get('forks_count', 0)} · "
                f"dil: {data.get('language')} · açık issue: {data.get('open_issues_count', 0)}\n"
                f"{data.get('description') or ''}\nGüncelleme: {data.get('updated_at', '')[:10]} · {data.get('html_url')}")
        rs, rd = await _gh(token, f"/repos/{repo}/readme")
        if rs == 200 and isinstance(rd, dict) and rd.get("content"):
            try:
                readme = base64.b64decode(rd["content"]).decode("utf-8", "replace")
                info += f"\n\n— README (ilk 800) —\n{readme[:800]}"
            except Exception:  # noqa: BLE001
                pass
        return info

    @ToolRegistry.register(
        "github_issues",
        "List a repo's issues/PRs, or get one by number. repo='owner/name'. state='open'|'closed'|'all'.",
        {"type": "object", "properties": {
            "repo": {"type": "string", "description": "Repository 'owner/name'."},
            "number": {"type": "integer", "description": "Issue/PR number for detail (optional)."},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Filter for listing. Default 'open'."},
        }, "required": ["repo"]},
    )
    async def github_issues(ctx: ToolContext, repo: str, number: int | None = None, state: str = "open") -> str:
        token = await _resolve_token(ctx)
        if not token:
            return _NO_CONN
        if "/" not in repo:
            return "[github error: repo 'owner/name' biçiminde olmalı]"
        if number is not None:
            status, d = await _gh(token, f"/repos/{repo}/issues/{number}")
            if status != 200 or not isinstance(d, dict):
                return f"[github error: issue failed ({status}) {str(d)[:160]}]"
            kind = "PR" if d.get("pull_request") else "Issue"
            return (f"{kind} #{d['number']} [{d['state']}] {d['title']}\n"
                    f"yazar: {d.get('user', {}).get('login')} · {d.get('html_url')}\n\n{(d.get('body') or '')[:1500]}")
        st = state if state in ("open", "closed", "all") else "open"
        status, items = await _gh(token, f"/repos/{repo}/issues", {"state": st, "per_page": 10})
        if status != 200 or not isinstance(items, list):
            return f"[github error: issues failed ({status}) {str(items)[:160]}]"
        if not items:
            return "Issue yok."
        return "\n".join(
            f"- #{it['number']} [{it['state']}] {it['title']}"
            f"{' (PR)' if it.get('pull_request') else ''}" for it in items
        )

    @ToolRegistry.register(
        "github_read_file",
        "Read a file's content from a GitHub repo. repo='owner/name', path='src/main.py', ref=branch/tag (optional).",
        {"type": "object", "properties": {
            "repo": {"type": "string", "description": "Repository 'owner/name'."},
            "path": {"type": "string", "description": "File path in the repo."},
            "ref": {"type": "string", "description": "Branch/tag/commit (optional; default branch)."},
            "max_chars": {"type": "integer", "description": "Max characters (default 6000)."},
        }, "required": ["repo", "path"]},
    )
    async def github_read_file(ctx: ToolContext, repo: str, path: str, ref: str | None = None, max_chars: int = 6000) -> str:
        token = await _resolve_token(ctx)
        if not token:
            return _NO_CONN
        if "/" not in repo:
            return "[github error: repo 'owner/name' biçiminde olmalı]"
        params = {"ref": ref} if ref else None
        status, d = await _gh(token, f"/repos/{repo}/contents/{path.lstrip('/')}", params)
        if status != 200 or not isinstance(d, dict):
            return f"[github error: file failed ({status}) {str(d)[:160]}]"
        if d.get("encoding") != "base64" or not d.get("content"):
            return f"[github error: '{path}' okunabilir bir metin dosyası değil (belki dizin)]"
        try:
            text = base64.b64decode(d["content"]).decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            return f"[github error: decode failed: {exc}]"
        n = min(max(500, int(max_chars or 6000)), 50_000)  # üst limit: context'i şişirme
        return f"# {repo}/{path}\n\n{text[:n]}"
