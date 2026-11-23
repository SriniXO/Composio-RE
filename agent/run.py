"""Research runner.

  python -m agent.run --pass 1 --app Notion        # one app, baseline
  python -m agent.run --pass 1 --all               # all 100, baseline (snippets only; honest 'before')
  python -m agent.run --pass 2 --all               # verified pass (fetch docs + verification loops)
Resumable: skips apps with an existing results/pass<N>/<id>.json unless --force.
"""
from __future__ import annotations
import argparse, asyncio, csv, json, time
from pathlib import Path

import httpx

from . import cache, extract, tools
from .schema import AppRecord

ROOT = cache.ROOT


def load_apps() -> list[dict]:
    with open(ROOT / "data" / "apps_seed.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def host(h: str) -> str:
    return h.split(" ")[0].strip()


async def pass1(app: dict, client: httpx.AsyncClient, run: str) -> AppRecord:
    """Baseline: 3 searches, snippets only, cheap model. No page fetches. Not tuned."""
    qs = [f"{app['app']} API authentication OAuth API key developer docs",
          f"{app['app']} API access pricing free trial partner program",
          f"{app['app']} MCP server"]
    sources = []
    for q in qs:
        r = await tools.search(q, client, n=5)
        txt = "\n".join(f"{x['title']} - {x['snippet']}" for x in r["results"])
        for x in r["results"]:
            sources.append({"url": x["url"], "text": f"{x['title']}. {x['snippet']}"})
    return await extract.extract(app, sources, extract.PASS1_MODEL, run, "pass1")


async def one(app: dict, pass_no: int, client, sem, run: str, force: bool, retries: int = 2):
    out = ROOT / "results" / f"pass{pass_no}" / f"{int(app['id']):03d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force:
        return
    async with sem:
        for attempt in range(retries + 1):
            try:
                if pass_no == 1:
                    rec = await pass1(app, client, run)
                else:
                    from .verify import pass2
                    rec = await pass2(app, client, run)
                out.write_text(rec.model_dump_json(indent=2), encoding="utf-8")
                cache.log(run, {"app": app["app"], "ok": True, "attempt": attempt})
                print(f"[pass{pass_no}] {app['id']:>3} {app['app']}: {rec.buildability} / {rec.self_serve}")
                return
            except Exception as e:
                cache.log(run, {"app": app["app"], "error": repr(e)[:300], "attempt": attempt})
                await asyncio.sleep(2 ** attempt)
        print(f"[pass{pass_no}] {app['id']:>3} {app['app']}: FAILED after retries")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="pass_no", type=int, choices=[1, 2], required=True)
    ap.add_argument("--app", help="app name (case-insensitive) or id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--concurrency", type=int, default=6)
    a = ap.parse_args()
    apps = load_apps()
    if a.app:
        apps = [x for x in apps if a.app.lower() in (x["app"].lower(), x["id"])] or \
               [x for x in apps if a.app.lower() in x["app"].lower()]
    elif not a.all:
        ap.error("give --app or --all")
    run = f"pass{a.pass_no}-{time.strftime('%Y%m%d-%H%M%S')}"
    sem = asyncio.Semaphore(a.concurrency)
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(one(x, a.pass_no, client, sem, run, a.force) for x in apps))


if __name__ == "__main__":
    asyncio.run(main())
