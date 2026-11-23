"""Search + fetch + browser tools.

search(): Composio TAVILY_SEARCH via the logged-in Composio CLI (no API key needed after `composio login`). "via" is stored per result.
fetch():  httpx + HTML->text. Returns status so dead links can be detected.
browser_fetch(): Playwright fallback for JS-rendered pages (pass 2 only).
"""
from __future__ import annotations
import asyncio, json, os, re, subprocess, time
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import httpx
from bs4 import BeautifulSoup

from . import cache

UA = "Mozilla/5.0 (compatible; ToolkitResearchBot/0.1; take-home research)"
MAX_CHARS = 40_000


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        t.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n\s*\n+", "\n", text)
    return re.sub(r"[ \t]+", " ", text).strip()


async def fetch(url: str, client: httpx.AsyncClient) -> dict:
    if not url.startswith("http"):
        url = "https://" + url
    k = cache.key("fetch", url)
    if (hit := cache.get("fetch", k)) is not None:
        return hit
    out = {"url": url, "status": 0, "text": "", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "via": "httpx"}
    try:
        r = await client.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=25)
        out["status"] = r.status_code
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ("html" in ctype or "text" in ctype or "json" in ctype):
            out["text"] = (html_to_text(r.text) if "html" in ctype else r.text)[:MAX_CHARS]
    except Exception as e:  # network error is a result, not a crash
        out["error"] = repr(e)[:200]
    cache.put("fetch", k, out)
    return out


async def browser_fetch(url: str) -> dict:
    """Render JS pages. Requires `playwright install chromium`."""
    k = cache.key("browser", url)
    if (hit := cache.get("browser", k)) is not None:
        return hit
    out = {"url": url, "status": 0, "text": "", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "via": "playwright"}
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(user_agent=UA)
            resp = await pg.goto(url if url.startswith("http") else "https://" + url, wait_until="networkidle", timeout=45000)
            out["status"] = resp.status if resp else 0
            out["text"] = html_to_text(await pg.content())[:MAX_CHARS]
            await b.close()
    except Exception as e:
        out["error"] = repr(e)[:200]
    cache.put("browser", k, out)
    return out


def _composio_bin() -> str | None:
    import shutil
    return shutil.which("composio") or next((str(p) for p in [Path.home() / ".composio" / "composio.exe", Path.home() / ".composio" / "composio"] if p.exists()), None)


def composio_execute(slug: str, args: dict) -> dict:
    """Run a Composio tool through the logged-in Composio CLI (verified path). Raises on failure."""
    exe = _composio_bin()
    if not exe:
        raise RuntimeError("composio CLI not found")
    p = subprocess.run([exe, "execute", slug, "-d", json.dumps(args)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    out = json.loads(p.stdout[p.stdout.index("{"):])
    if not out.get("successful"):
        raise RuntimeError(str(out.get("error"))[:200])
    return out["data"]


async def search(query: str, client: httpx.AsyncClient, n: int = 6, domains: list[str] | None = None) -> dict:
    k = cache.key("search", query, ",".join(domains or []))
    if (hit := cache.get("search", k)) is not None:
        return hit
    results, via = [], "none"
    try:
        args = {"query": query, "max_results": n, "search_depth": "basic"}
        if domains:
            args["include_domains"] = domains
        data = await asyncio.to_thread(composio_execute, "TAVILY_SEARCH", args)
        results = [{"title": i.get("title", ""), "url": i.get("url", ""), "snippet": i.get("content", "")} for i in data.get("results", [])]
        via = "composio:TAVILY_SEARCH"
    except Exception as e:
        cache.log("tools", {"composio_search_failed": repr(e)[:200], "query": query})
    out = {"query": query, "via": via, "results": results}
    if results:  # never cache a failure
        cache.put("search", k, out)
    return out


async def extract_page(url: str) -> dict:
    """JS-rendered / bot-protected pages: Composio TAVILY_EXTRACT (cheaper than a local browser)."""
    k = cache.key("extract", url)
    if (hit := cache.get("extract", k)) is not None:
        return hit
    out = {"url": url, "status": 0, "text": "", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "via": "composio:TAVILY_EXTRACT"}
    try:
        data = await asyncio.to_thread(composio_execute, "TAVILY_EXTRACT", {"urls": [url if url.startswith("http") else "https://" + url]})
        r = (data.get("results") or [{}])[0]
        out["text"] = (r.get("raw_content") or "")[:MAX_CHARS]
        out["status"] = 200 if out["text"] else 0
    except Exception as e:
        out["error"] = repr(e)[:200]
    if out["text"]:
        cache.put("extract", k, out)
    return out
