"""
Research Tools — M12 Personal Research Agent

web_search  : Tavily AI ile web araması (AsyncTavilyClient)
read_url    : URL'den temiz metin çeker (httpx + trafilatura)
summarize   : TF tabanlı extractive özetleme (sıfır ek LLM çağrısı)
save_note   : Araştırma notunu Redis'e kaydeder (trace-scoped, 24 sa TTL)
get_notes   : Oturumda kaydedilen tüm notları döner

Tasarım kararları:
  - web_search: search_depth="basic" → 1 kredi, hızlı; LLM'den topic+query alınır.
  - read_url: httpx async fetch + trafilatura extraction; Tavily extract fallback değil
    (ekstra kredi harcanmaması için). Başarısız extraksiyon → ham metin kırpılır.
  - summarize: Saf Python, TF-based; ek API çağrısı yok → sıfır gecikme eklenti.
  - save_note / get_notes: Redis HASH, key = research_notes:{org_id}:{trace_id}.
    Trace bitince notlar 24 saat daha yaşar.

Tüm tool'lar exception fırlatmaz — hatayı string olarak döner (AgentRunner uyumlu).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.services.agent.registry import ToolContext, ToolRegistry

logger = structlog.get_logger()

# ─── Notes Redis helpers ───────────────────────────────────

_NOTES_TTL = 86_400          # 24 saat
_READ_TIMEOUT = 15.0         # saniye
_MAX_HTML_BYTES = 2_000_000  # 2 MB — büyük sayfaları köreltmemek için cap
_MAX_PDF_BYTES = 10_000_000  # 10 MB — PDF indirme tavanı (read_pdf)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; ObservatoryResearchBot/1.0; "
    "+https://github.com/observatory)"
)


def _notes_key(ctx: ToolContext) -> str:
    return f"research_notes:{ctx.org_id}:{ctx.trace_id}"


# ─── Registration ─────────────────────────────────────────

def register_research_tools() -> None:
    """Idempotent — birden fazla çağrılabilir."""
    try:
        ToolRegistry.get("web_search")
        return  # zaten kayıtlı
    except KeyError:
        pass

    # ── web_search ────────────────────────────────────────

    @ToolRegistry.register(
        name="web_search",
        description=(
            "Searches the web for up-to-date information using Tavily AI. "
            "Returns a ranked list of results with title, URL and a snippet. "
            "Use multiple parallel calls for different angles of a research topic."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10). Default 5.",
                    "default": 5,
                },
                "topic": {
                    "type": "string",
                    "enum": ["general", "news"],
                    "description": "'news' for recent events, 'general' otherwise. Default 'general'.",
                    "default": "general",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year"],
                    "description": "Restrict results to this time window. Omit for no restriction.",
                },
            },
            "required": ["query"],
        },
    )
    async def web_search(
        ctx: ToolContext,
        query: str,
        max_results: int = 5,
        topic: str = "general",
        time_range: str | None = None,
    ) -> str:
        return await _web_search(ctx, query, max_results, topic, time_range)

    # ── read_url ──────────────────────────────────────────

    @ToolRegistry.register(
        name="read_url",
        description=(
            "Fetches a URL and returns the main text content (ads, nav and boilerplate removed). "
            "Use to read full articles after web_search gives you promising URLs. "
            "Returns up to max_chars characters of clean text."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch (must start with http:// or https://).",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return. Default 4000.",
                    "default": 4000,
                },
            },
            "required": ["url"],
        },
    )
    async def read_url(
        ctx: ToolContext,
        url: str,
        max_chars: int = 4000,
    ) -> str:
        return await _read_url(ctx, url, max_chars)

    # ── read_urls (paralel web enrichment) ────────────────

    @ToolRegistry.register(
        name="read_urls",
        description=(
            "Fetch MULTIPLE URLs in parallel and return each one's cleaned text (capped per URL). "
            "Use to enrich/compare several sources at once instead of many separate read_url calls."
        ),
        parameters={
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "URL list (max 8)."},
                "max_chars_each": {"type": "integer", "description": "Max chars per URL. Default 2000.", "default": 2000},
            },
            "required": ["urls"],
        },
    )
    async def read_urls(ctx: ToolContext, urls: list[str], max_chars_each: int = 2000) -> str:
        return await _read_urls(ctx, urls, max_chars_each)

    # ── read_pdf ──────────────────────────────────────────

    @ToolRegistry.register(
        name="read_pdf",
        description=(
            "Fetch a PDF from a URL and extract its text (first pages). Use for PDF reports, papers, datasheets."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "PDF URL (must start with http:// or https://)."},
                "max_chars": {"type": "integer", "description": "Max characters. Default 6000.", "default": 6000},
            },
            "required": ["url"],
        },
    )
    async def read_pdf(ctx: ToolContext, url: str, max_chars: int = 6000) -> str:
        return await _read_pdf(ctx, url, max_chars)

    # ── summarize ─────────────────────────────────────────

    @ToolRegistry.register(
        name="summarize",
        description=(
            "Extracts the most important sentences from a long text using keyword frequency scoring. "
            "Fast and free — no extra LLM call. Use on text returned by read_url before saving notes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to summarize.",
                },
                "focus": {
                    "type": "string",
                    "description": "Optional topic hint — sentences containing these words get boosted.",
                    "default": "",
                },
                "max_sentences": {
                    "type": "integer",
                    "description": "How many sentences to keep. Default 8.",
                    "default": 8,
                },
            },
            "required": ["text"],
        },
    )
    async def summarize(
        ctx: ToolContext,
        text: str,
        focus: str = "",
        max_sentences: int = 8,
    ) -> str:
        return _extractive_summarize(text, focus, max_sentences)

    # ── save_note ─────────────────────────────────────────

    @ToolRegistry.register(
        name="save_note",
        description=(
            "Saves a research note for this session. "
            "Use after gathering information on a subtopic. "
            "Notes are retrievable with get_notes and used to compile the final report."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the note (used as key — saves overwrite previous notes with same title).",
                },
                "content": {
                    "type": "string",
                    "description": "The note content.",
                },
            },
            "required": ["title", "content"],
        },
    )
    async def save_note(ctx: ToolContext, title: str, content: str) -> str:
        return await _save_note(ctx, title, content)

    # ── get_notes ─────────────────────────────────────────

    @ToolRegistry.register(
        name="get_notes",
        description=(
            "Returns all research notes saved in this session. "
            "Call this when you are ready to compile the final report."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )
    async def get_notes(ctx: ToolContext) -> str:
        return await _get_notes(ctx)


# ─── Implementations ──────────────────────────────────────

async def _web_search(
    ctx: ToolContext,
    query: str,
    max_results: int,
    topic: str,
    time_range: str | None,
) -> str:
    settings = get_settings()
    if not settings.tavily_api_key:
        return (
            "[web_search error: TAVILY_API_KEY not configured. "
            "Set it in .env to enable web search.]"
        )

    try:
        from tavily import AsyncTavilyClient  # type: ignore[import-untyped]
    except ImportError:
        return "[web_search error: tavily-python not installed. Run: pip install tavily-python]"

    max_results = max(1, min(10, max_results))

    try:
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "topic": topic,
            "search_depth": "basic",
        }
        if time_range:
            kwargs["time_range"] = time_range

        response = await client.search(**kwargs)
    except Exception as exc:
        logger.warning("web_search.error", query=query, error=str(exc))
        return f"[web_search error: {exc}]"

    results = response.get("results", [])
    if not results:
        return f"No results found for: {query}"

    lines: list[str] = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        url = r.get("url", "")
        snippet = (r.get("content") or "")[:300].replace("\n", " ").strip()
        lines.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")

    return "\n\n".join(lines)


async def _read_url(ctx: ToolContext, url: str, max_chars: int) -> str:
    # Basit URL validasyonu
    if not url.startswith(("http://", "https://")):
        return f"[read_url error: invalid URL '{url}' — must start with http:// or https://]"

    max_chars = max(500, min(20_000, max_chars))

    try:
        import trafilatura  # type: ignore[import-untyped]
    except ImportError:
        return "[read_url error: trafilatura not installed. Run: pip install trafilatura]"

    # httpx ile async fetch
    try:
        async with httpx.AsyncClient(
            timeout=_READ_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(url)
    except httpx.TimeoutException:
        return f"[read_url error: request timed out after {_READ_TIMEOUT}s — {url}]"
    except httpx.RequestError as exc:
        return f"[read_url error: network error — {exc}]"

    if resp.status_code >= 400:
        return f"[read_url error: HTTP {resp.status_code} — {url}]"

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        return f"[read_url error: unsupported content type '{content_type}' — {url}]"

    html = resp.text[:_MAX_HTML_BYTES]

    # trafilatura extraction (sync — fast enough for tool use)
    text = trafilatura.extract(
        html,
        url=url,
        favor_precision=True,
        include_comments=False,
        include_tables=False,
        include_links=False,
    )

    if not text or len(text.strip()) < 50:
        # Fallback: strip all HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return f"[read_url error: could not extract text from {url}]"

    # Cümle sınırında kes
    if len(text) > max_chars:
        cut = text[:max_chars]
        last_period = max(cut.rfind(". "), cut.rfind(".\n"))
        if last_period > max_chars // 2:
            cut = cut[: last_period + 1]
        text = cut + "\n[...truncated]"

    return f"Content from {url}:\n\n{text}"


async def _read_urls(ctx: ToolContext, urls: list[str], max_chars_each: int = 2000) -> str:
    """Birden çok URL'i paralel oku (read_url üstüne). En fazla 8 URL."""
    import asyncio
    clean = [u for u in (urls or []) if isinstance(u, str) and u.strip()][:8]
    if not clean:
        return "[read_urls error: geçerli URL yok]"
    cap = max(200, min(int(max_chars_each or 2000), 8000))
    results = await asyncio.gather(*[_read_url(ctx, u, cap) for u in clean], return_exceptions=True)
    parts = []
    for u, r in zip(clean, results):
        parts.append(f"### {u}\n{r if isinstance(r, str) else f'[error: {r}]'}")
    return "\n\n".join(parts)


async def _read_pdf(ctx: ToolContext, url: str, max_chars: int = 6000) -> str:
    """PDF URL'inden metin çıkar (ilk sayfalar). pypdf ile."""
    if not url.startswith(("http://", "https://")):
        return "[read_pdf error: url http:// veya https:// ile başlamalı]"
    try:
        async with httpx.AsyncClient(timeout=_READ_TIMEOUT, follow_redirects=True,
                                     headers={"User-Agent": _USER_AGENT}) as client:
            r = await client.get(url)
            r.raise_for_status()
            content = r.content[:_MAX_PDF_BYTES]
    except Exception as exc:  # noqa: BLE001
        return f"[read_pdf error: indirilemedi: {exc}]"
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:50]).strip()
    except Exception as exc:  # noqa: BLE001
        return f"[read_pdf error: PDF işlenemedi: {exc}]"
    if not text:
        return "[read_pdf: metin çıkarılamadı (taranmış/görüntü PDF olabilir)]"
    return text[:min(max(500, int(max_chars or 6000)), 50_000)]


def _extractive_summarize(text: str, focus: str, max_sentences: int) -> str:
    """
    TF tabanlı extractive özetleme.

    Algoritma:
      1. Metni cümlelere böl.
      2. Kelime frekans tablosu oluştur (durdurma kelimeleri hariç).
      3. Her cümleyi ortalama kelime frekansıyla puanla.
      4. `focus` terimleri içeren cümleler 1.5x çarpanı alır.
      5. En yüksek puanlı max_sentences cümleyi orijinal sırayla döndür.
    """
    text = text.strip()
    if not text:
        return ""

    # Cümlelere böl (. ! ? sonrası boşluk veya satır sonu)
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 20]

    if len(sentences) <= max_sentences:
        return text

    # Kelime frekansları (3+ harf, stopwords hariç)
    _STOPWORDS = {
        "the", "and", "for", "are", "was", "were", "has", "have", "had",
        "but", "not", "this", "that", "with", "from", "they", "their",
        "its", "can", "will", "been", "also", "more", "than", "into",
        "bir", "ve", "ile", "bu", "da", "de", "için", "olan", "olan",
    }
    words_all = re.findall(r"\b[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}\b", text.lower())
    freq: Counter[str] = Counter(w for w in words_all if w not in _STOPWORDS)
    max_freq = max(freq.values()) if freq else 1

    # Normalise
    norm_freq = {w: f / max_freq for w, f in freq.items()}

    # Focus terimleri
    focus_terms = set(re.findall(r"\b[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}\b", focus.lower())) - _STOPWORDS

    def _score(sent: str) -> float:
        ws = re.findall(r"\b[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}\b", sent.lower())
        if not ws:
            return 0.0
        base = sum(norm_freq.get(w, 0) for w in ws) / len(ws)
        boost = 1.5 if focus_terms and focus_terms & set(ws) else 1.0
        return base * boost

    ranked = sorted(enumerate(sentences), key=lambda x: _score(x[1]), reverse=True)
    top_indices = sorted(i for i, _ in ranked[:max_sentences])
    return " ".join(sentences[i] for i in top_indices)


async def _save_note(ctx: ToolContext, title: str, content: str) -> str:
    if not title.strip():
        return "[save_note error: title cannot be empty]"
    if not content.strip():
        return "[save_note error: content cannot be empty]"
    try:
        key = _notes_key(ctx)
        await ctx.redis.hset(key, title, content)
        await ctx.redis.expire(key, _NOTES_TTL)
        return f"Note saved: '{title}'"
    except Exception as exc:
        logger.warning("save_note.error", title=title, error=str(exc))
        return f"[save_note error: {exc}]"


async def _get_notes(ctx: ToolContext) -> str:
    try:
        key = _notes_key(ctx)
        raw: dict[bytes | str, bytes | str] = await ctx.redis.hgetall(key)
    except Exception as exc:
        logger.warning("get_notes.error", error=str(exc))
        return f"[get_notes error: {exc}]"

    if not raw:
        return "No notes saved yet."

    parts: list[str] = []
    for title_b, content_b in raw.items():
        title = title_b.decode() if isinstance(title_b, bytes) else title_b
        content = content_b.decode() if isinstance(content_b, bytes) else content_b
        parts.append(f"### {title}\n{content}")

    return "\n\n---\n\n".join(parts)


# ─── Recommended system prompt for the research agent ─────

RESEARCH_AGENT_SYSTEM_PROMPT = """\
You are a thorough research assistant. When given a research topic, follow this workflow:

**Phase 1 — Discovery (parallel searches)**
Call web_search with 2-3 different queries simultaneously to cover multiple angles.

**Phase 2 — Deep reading**
For the most relevant URLs from search results, call read_url (up to 3-4 URLs in parallel).
Use summarize on any content longer than 2000 characters before saving.

**Phase 3 — Note taking**
Save key findings with save_note. Use descriptive titles like "Market size data", "Key players", "Recent developments".

**Phase 4 — Synthesis**
Call get_notes to retrieve all findings, then write a comprehensive, structured report with:
- Executive Summary
- Key Findings (subsections per angle)
- Sources (URLs cited)
- Gaps / Limitations

Rules:
- Always cite URLs when mentioning facts.
- Do NOT hallucinate — only state what you found.
- Use parallel tool calls whenever possible for speed.
- If a URL fails, skip it and move on.
"""
