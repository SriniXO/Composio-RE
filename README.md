# Composio-REP: research agent for "which apps can become agent toolkits?"

An evidence-first pipeline that researches 100 apps (auth, self-serve vs gated, API surface, MCP, buildability), verifies its own output with several loops, and publishes a static case-study page.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Composio (search + page extraction).** Install the CLI and log in once (no API key goes in this repo):
```bash
curl -fsSL https://composio.dev/install | sh          # Windows: irm https://raw.githubusercontent.com/ComposioHQ/composio/next/install.ps1 | iex
composio login
```
**LLM backend.** Default is local Ollama (`ollama pull llama3.2` and `ollama pull qwen2.5-coder:7b`).
To use Claude instead, copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, and export it; the backend switches automatically (`LLM_BACKEND` overrides).

```bash
python -m agent.run --pass 2 --app Notion      # one app
python -m agent.run --pass 1 --all             # baseline, all 100 (snippets only; the honest "before")
python -m agent.run --pass 2 --all             # verified pass
python -m agent.analyze --pass 2               # data/apps.json, apps.csv, stats.json
python verification/make_sample.py             # builds verification/sample.csv (verdict columns blank)
python verification/score.py                   # accuracy from the human verdicts
python site/build.py --repo <repo-url> --live <page-url>
```
Runs are resumable (existing `results/passN/<id>.json` are skipped; `--force` redoes), cached in `.cache/`, and logged in `logs/`.

## Cost and time (measured, this repo's real run)
- Pass 1: about 85 s/app on a 6 GB laptop GPU with llama3.2.
- Pass 2: about 2 min/app with qwen2.5-coder:7b, so roughly 3.5 h for 100 apps.
- Composio calls: about $0.004 each on the account that ran it.

## Layout
`agent/` pipeline · `data/` seed list + generated outputs · `results/pass1|pass2/` one JSON per app · `verification/` sample + scorer · `site/` static page · see `ARCHITECTURE.md`, `PLAN.md`, `HUMAN_INTERVENTIONS.md`.

## Limitations (read these)
- Small local models extract worse than frontier models. Code checks (verbatim quotes, schema, dead links) limit damage but cannot make a wrong-but-quoted claim right.
- Accuracy is measured on a 28-app hand-checked sample, so per-field figures carry wide margins; the page states the sample size.
- Search/extract via Composio's Tavily tools can miss gated or login-walled docs; those land on the "defeated us" list rather than being guessed.
- Composio toolkit-existence (`composio_status`) is not yet checked automatically and is `unverified` unless a human fills it.
