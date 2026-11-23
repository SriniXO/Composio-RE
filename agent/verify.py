"""Pass 2: fetch real docs, extract with a stronger model, then run verification loops a-e."""
from __future__ import annotations
import json, re
from urllib.parse import urlparse

import httpx

from . import extract, tools
from .schema import AppRecord

VERIFIER_SYS = ("You verify evidence. Given a PAGE TEXT, a QUOTE and a FIELD claim, answer JSON "
                '{"supports": true|false, "reason": "<short>"}. supports=true only if the page text clearly supports the claim.')

PAGE_HINTS = ["", "/docs", "/api", "/pricing"]


def domain(u: str) -> str:
    h = urlparse(u if u.startswith("http") else "https://" + u).netloc.lower()
    return ".".join(h.split(".")[-2:])


async def gather_sources(app: dict, client, run: str) -> list[dict]:
    """Discover + fetch: hint docs page, auth/getting-started, pricing, MCP, GitHub."""
    h = extract_host = app["hint"].split(" ")[0]
    urls = [h]
    for q in [f"{app['app']} API authentication getting started docs",
              f"{app['app']} API pricing plans access developer program",
              f"{app['app']} MCP server official github"]:
        r = await tools.search(q, client, n=4)
        urls += [x["url"] for x in r["results"][:3]]
    seen, sources = set(), []
    for u in urls:
        if u in seen or not u:
            continue
        seen.add(u)
        sources.append(await tools.fetch(u, client))
    return sources


async def pass2(app: dict, client: httpx.AsyncClient, run: str) -> AppRecord:
    sources = await gather_sources(app, client, run)
    log: list[str] = []

    # (d) browser fallback for pages that came back empty / JS shells
    for i, s in enumerate(sources):
        if s["status"] in (0, 200) and len(s["text"]) < 500:
            for fallback in (tools.extract_page, tools.browser_fetch):  # Composio Tavily Extract, then real browser
                b = await fallback(s["url"])
                if len(b["text"]) > max(len(s["text"]), 500):
                    sources[i] = b
                    log.append(f"{b['via']} fallback used for {s['url']}")
                    break

    rec = await extract.extract(app, sources, extract.PASS2_MODEL, run, "pass2")
    by_url = {s["url"]: s for s in sources}

    # (a) evidence check: quote must be in text (code) AND verifier LLM must agree it supports the field
    for e in rec.evidence:
        page = by_url.get(e.url, {}).get("text", "")
        if not e.quote_verified:
            log.append(f"dropped-quote-not-in-page: {e.field_supported} {e.url}")
            continue
        raw = await extract.llm(extract.PASS2_MODEL, VERIFIER_SYS,
                                f"FIELD: {e.field_supported}\nQUOTE: {e.quote_snippet}\nPAGE TEXT:\n{page[:8000]}", run, 300)
        try:
            ok = bool(extract._json(raw).get("supports"))
        except Exception:
            ok = False
        if not ok:
            e.quote_verified = False
            log.append(f"verifier-rejected: {e.field_supported} {e.url}")
    good = [e for e in rec.evidence if e.quote_verified]
    rec.evidence = rec.evidence  # keep all, flagged, for transparency

    # (b) cross-source: auth + self_serve need >=2 distinct domains OR >=2 distinct pages of verified evidence
    for field in ("auth", "self_serve"):
        sup = [e for e in good if field in e.field_supported.lower().replace(" ", "_") or
               (field == "auth" and "auth" in e.field_supported.lower())]
        pages = {e.url for e in sup}
        if len(pages) < 2:
            log.append(f"cross-source-missing: {field} backed by {len(pages)} verified page(s)")
            rec.confidence = "low" if not pages else "med"
            if not pages:
                rec.needs_human.flag = True
                rec.needs_human.reason += f"{field} has no verified evidence; "

    # (c) rule checks
    dead = [s["url"] for s in sources if s["status"] >= 400 or s["status"] == 0]
    if rec.self_serve == "yes" and rec.main_blocker in ("partner_approval", "enterprise_only"):
        log.append("contradiction: self_serve=yes but blocker is partner/enterprise")
        rec.needs_human.flag = True
        rec.needs_human.reason += "contradictory self_serve vs blocker; "
    if rec.buildability == "ready_now" and rec.main_blocker not in ("none",):
        log.append("contradiction: ready_now but blocker set")
        rec.needs_human.flag = True
        rec.needs_human.reason += "ready_now with blocker; "
    if rec.buildability == "blocked" and rec.main_blocker == "none":
        rec.needs_human.flag = True
        rec.needs_human.reason += "blocked without blocker; "
    log.append(f"dead_or_unreachable_sources: {dead}")

    # (e) escalation
    if rec.confidence == "low" or len(good) == 0:
        rec.needs_human.flag = True
        rec.needs_human.reason += "low confidence or no verified evidence; "
    rec.verification_log = log
    return rec
