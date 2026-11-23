"""Pass 3: correcting verification loops. No LLM. Every change is grounded in fetched page text (or a domain-scoped search).

Designed from FAILURE TYPES seen in pass 2 (not per-app hacks):
  R1 auth    : keep a method only if its keyword appears in fetched text; if the list is empty, derive it from the text.
  R2 api type: decide REST/GraphQL from keyword counts in fetched text when the model said 'unclear'/disagrees.
  R3 mcp     : 'official' only if the MCP URL is on the vendor's own domain/GitHub org; re-search vendor domains for an official MCP page.
  R4 access  : self_serve from access/pricing language (approval/partner > trial > free plan); else keep the model's value.
  R5 verdict : buildability + blocker derived from the corrected fields (consistency loop, now corrective).
Usage: python -m agent.pass3 --all   (reads results/pass2, writes results/pass3)
"""
from __future__ import annotations
import argparse, asyncio, json, re
from urllib.parse import urlparse

import httpx

from . import cache, tools
from .run import ROOT, load_apps
from .schema import AppRecord, Evidence
from .verify import gather_sources

KW = {"oauth2": r"oauth", "api_key": r"api[ -]?key|access token|api token|secret key|personal access token|private integration|bearer token",
      "basic": r"basic auth|basic authentication|http basic", "jwt": r"\bjwt\b|json web token"}
GATED = r"(request|apply for|apply to get) (api |developer |marketing api )?access|(must|need to|have to) be approved|approved (developer|partner)|developer (application|registration) (form|review)|api access (is )?(restricted|by approval)|requires? (api )?approval|nothing about .{0,40} is self-serve"
TRIAL = r"free trial|\d+-day (free )?trial|trial (account|period)"
FREE = r"free plan|free tier|free forever|free account|sign up for free|free to (use|start|generate)|free developer"
PAID = r"paid (plan|subscription) (is )?required|requires? a paid|enterprise plan|available (on|for) (paid|enterprise)"
AGG = ("mcp.so", "mcpservers.org", "glama.ai", "pulsemcp.com", "mcpmarket.com", "smithery.ai", "mcpserverhub.com")


def toks(app: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", app.lower()) if len(t) >= 4 and t not in ("business", "connect", "commerce", "selling", "partner")]


def vendor_host(url: str, app: str) -> bool:
    u = urlparse(url if url.startswith("http") else "https://" + url)
    h, path = u.netloc.lower(), u.path.lower()
    if any(a in h for a in AGG):
        return False
    if h.endswith("github.com"):
        org = path.strip("/").split("/")[0]
        return any(t in org for t in toks(app))
    return any(t in h for t in toks(app))


def domains(app: dict) -> list[str]:
    h = app["hint"].split(" ")[0].split("/")[0]
    base = ".".join(h.split(".")[-2:])
    return list({base, *[t + ".com" for t in toks(app["app"])]})


def grab(sources, rx, maxw=22):
    for s in sources:
        m = re.search(rx, s.get("text", ""), re.I)
        if m:
            words = s["text"][max(0, m.start() - 80): m.end() + 120].split()
            q = " ".join(words[:maxw])
            return s["url"], q
    return None


def ev(rec, url, quote, field, srcs):
    txt = next((re.sub(r"\s+", " ", s["text"]).lower() for s in srcs if s["url"] == url), "")
    ok = re.sub(r"\s+", " ", quote).lower() in txt
    rec.evidence.append(Evidence(url=url, quote_snippet=quote, field_supported=field, fetched_at=next((s.get("fetched_at", "") for s in srcs if s["url"] == url), ""), quote_verified=ok))


async def pass3(app: dict, client: httpx.AsyncClient, run: str) -> AppRecord:
    rec = AppRecord(**json.loads((ROOT / "results" / "pass2" / f"{int(app['id']):03d}.json").read_text(encoding="utf-8")))
    rec.pass_name = "pass3"
    srcs = await gather_sources(app, client, run)
    doms = domains(app)
    for q in (f"{app['app']} API pricing plans access", f"{app['app']} API authentication"):  # domain-scoped re-research
        r = await tools.search(q, client, n=4, domains=doms)
        for x in r["results"]:
            if not any(s["url"] == x["url"] for s in srcs):
                srcs.append({"url": x["url"], "text": x["title"] + ". " + x["snippet"], "status": 200, "fetched_at": ""})
    blob = "\n".join(s.get("text", "") for s in srcs)
    log = rec.verification_log
    # R1 auth
    keep = [m for m in rec.auth_methods if m in KW and re.search(KW[m], blob, re.I)]
    derived = [m for m in ("oauth2", "api_key") if re.search(KW[m], blob, re.I)]
    new_auth = keep or derived
    if set(new_auth) != set(rec.auth_methods):
        log.append(f"pass3 R1 auth {rec.auth_methods} -> {new_auth}")
        rec.auth_methods = new_auth
    for m in rec.auth_methods:
        g = grab(srcs, KW[m])
        if g: ev(rec, g[0], g[1], f"auth:{m}", srcs)
    # R2 api type
    rest_n, gql_n = len(re.findall(r"\brest(?:ful)?\b", blob, re.I)), len(re.findall(r"graphql", blob, re.I))
    t = "GraphQL" if gql_n >= 3 and gql_n > rest_n else "REST" if rest_n >= 2 else rec.api_surface.type
    if t != rec.api_surface.type:
        log.append(f"pass3 R2 api type {rec.api_surface.type} -> {t} (rest={rest_n}, graphql={gql_n})")
        rec.api_surface.type = t
    # R3 mcp official
    m = rec.existing_mcp
    found = None
    r = await tools.search(f"{app['app']} MCP server", client, n=5, domains=doms)
    for x in r["results"]:
        if vendor_host(x["url"], app["app"]) and re.search(r"mcp", x["url"] + x["snippet"], re.I):
            found = x
            break
    if found:
        m.exists, m.official, m.url = True, True, found["url"]
        ev(rec, found["url"], " ".join(found["snippet"].split()[:22]), "existing_mcp:official", srcs + [{"url": found["url"], "text": found["snippet"]}])
        log.append(f"pass3 R3 official MCP found on vendor domain: {found['url']}")
    elif m.exists:
        if m.official or (m.url and not vendor_host(m.url, app["app"])):
            log.append(f"pass3 R3 MCP 'official' unsupported (no vendor-domain MCP found); set official=False url={m.url}")
        m.official = False
    # R4 self-serve
    old = rec.self_serve
    g_gate, g_trial, g_free, g_paid = (grab(srcs, x) for x in (GATED, TRIAL, FREE, PAID))
    if g_gate and not g_free: new, g = "admin_approval", g_gate
    elif g_gate and g_free:
        new, g = old, None
        log.append("pass3 R4 conflicting signals (approval language AND free plan): kept model value")
    elif g_paid and not g_free: new, g = "paid_required", g_paid
    elif g_free: new, g = "yes", g_free
    elif g_trial: new, g = "trial", g_trial
    else: new, g = old, None
    if new != old:
        log.append(f"pass3 R4 self_serve {old} -> {new}")
        rec.self_serve = new
    if g: ev(rec, g[0], g[1], f"self_serve:{rec.self_serve}", srcs)
    # R5 verdict from corrected fields
    ss = rec.self_serve
    if ss in ("admin_approval", "partner_gated", "contact_sales"): b, bl = "blocked", "review_process"
    elif ss in ("paid_required", "trial"): b, bl = "ready_with_caveats", "paid_plan"
    elif ss == "yes" and rec.auth_methods and rec.api_surface.type in ("REST", "GraphQL"): b, bl = "ready_now", "none"
    else: b, bl = rec.buildability, rec.main_blocker
    if (b, bl) != (rec.buildability, rec.main_blocker):
        log.append(f"pass3 R5 verdict {rec.buildability}/{rec.main_blocker} -> {b}/{bl}")
    rec.buildability, rec.main_blocker = b, bl
    return rec


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--app")
    ap.add_argument("--concurrency", type=int, default=6); a = ap.parse_args()
    apps = load_apps() if a.all else [x for x in load_apps() if a.app and a.app.lower() in x["app"].lower()]
    out = ROOT / "results" / "pass3"; out.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(a.concurrency)
    async with httpx.AsyncClient() as client:
        async def one(app):
            async with sem:
                try:
                    rec = await pass3(app, client, "pass3")
                    (out / f"{int(app['id']):03d}.json").write_text(rec.model_dump_json(indent=2), encoding="utf-8")
                    print(f"[pass3] {app['id']:>3} {app['app']}: {rec.buildability} / {rec.self_serve} / {rec.auth_methods}")
                except Exception as e:
                    print(f"[pass3] {app['id']} {app['app']} FAILED {e!r}")
        await asyncio.gather(*(one(x) for x in apps))

if __name__ == "__main__":
    asyncio.run(main())
