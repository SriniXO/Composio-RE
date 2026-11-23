# PLAN

## Goal
Research 100 apps for agent-toolkit buildability with an evidence-first agent, verify it honestly, publish one static HTML case study + repo.

## Hard rules
- No claim without an evidence URL that the pipeline fetched. Quote snippets must be substrings of fetched text (checked in code, not by the LLM). Otherwise the field is `unverified`.
- Pass 1 is a deliberately light baseline and is never tuned. It is the honest "before".
- Verdict columns in `verification/sample.csv` are filled by the human only. Accuracy is computed from them.
- Every number on the site comes from `agent/analyze.py` output (`data/stats.json`). No hand-typed stats.

## Architecture (Python 3.11+)
```
data/apps_seed.csv ──► agent/run.py ──► results/pass1/<id>.json   (baseline)
                          │
                          └─► agent/pass2.py ──► results/pass2/<id>.json  (verified)
                                  a. evidence check (quote in fetched text + verifier LLM re-read)
                                  b. cross-source (auth & self_serve need 2 independent domains/sources)
                                  c. rules (schema, dead links, contradictions)
                                  d. browser fallback (Playwright) for JS pages
                                  e. escalate -> needs_human + HUMAN_INTERVENTIONS.md
verification/make_sample.py ─► verification/sample.csv ─► (human verdicts) ─► verification/score.py ─► data/accuracy.json
agent/analyze.py ─► data/stats.json + data/apps.json/csv ─► site/build.py ─► site/index.html
```
Modules: `agent/tools.py` (search, fetch, browser), `agent/extract.py` (LLM -> schema), `agent/verify.py` (loops a-e),
`agent/schema.py` (pydantic), `agent/cache.py` (disk cache keyed by URL hash), `agent/run.py` (async, concurrency, resume, logs/).

## Tooling choices
- LLM: Anthropic SDK. Pass 1 = claude-haiku-5-5 over search snippets only. Pass 2 = claude-sonnet-5-5 over fetched pages; verifier = separate call.
- Search: Composio search tool via Composio SDK when `COMPOSIO_API_KEY` is set (also used for GitHub MCP-registry lookup + Composio-toolkit-exists check); falls back to plain HTTP search so the repo runs without it. The README states exactly which path was used in the real run.
- Fetch: httpx + text extraction; Playwright fallback for JS-rendered pages.
- Resumability: skip an app if `results/<pass>/<id>.json` exists unless `--force`. Every HTTP/LLM call is cached on disk and logged to `logs/`.

## Schema
As specified in the brief (fixed; see `agent/schema.py`). Enums enforced by pydantic; unknown => `unclear`/`unverified`.

## Verification protocol
1. Stratified sample of 28 apps, seed=1512 published: >=2 per category, every auth type represented.
2. `sample.csv`: per app x field (auth, self_serve, api_surface, mcp, buildability) rows with pass1 answer, pass2 answer, evidence links, blank `human_verdict` (correct/wrong/partial) + `notes`.
3. `score.py` computes per-field accuracy for pass1, pass2, and post-human-fix (final), plus a wrong-answers table (said / truth / why / which loop fixed it).
4. Apps unresolved after all loops go on the "defeated us" list.
Caveat reported on the page: the human checks only 28 of 100, so figures are sample estimates with a stated margin.

## Page outline (single static `site/index.html`, no build step to view)
1 Headline patterns + stat tiles · 2 Easy-wins vs needs-outreach matrix · 3 Filterable table w/ expandable evidence ·
4 Agent architecture + Composio usage + human interventions · 5 Proof: runnable trigger + repo · 6 Verification (accuracy chart, hits/misses, defeated) ·
7 Machine-readable: apps.json/csv, llms.txt, Dataset JSON-LD. Light/dark, responsive, accessible.

## Tasks
- [x] ASSIGNMENT.md, seed CSV
- [ ] Scaffold repo, schema, tools, cache
- [ ] Pass 1 extractor + runner; run on 100 (needs API key)
- [ ] Pass 2 verify loops; run on 100
- [ ] Sample + checklist (human fills verdicts)
- [ ] Scoring, analysis, charts
- [ ] Site + machine-readable files
- [ ] README, ARCHITECTURE.md, HUMAN_INTERVENTIONS.md
- [ ] Deploy + small logical commits

## Blockers needing the user
- `ANTHROPIC_API_KEY` (extraction/verification) and ideally `COMPOSIO_API_KEY` (search/tools). Neither is set in this environment.
- GitHub repo creation/push + Pages enable (no `gh` CLI installed; `GITHUB_TOKEN` is set).
- Human verdicts on `verification/sample.csv`.
