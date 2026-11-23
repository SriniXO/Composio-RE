"""LLM extraction: sources (url+text) -> AppRecord. Quotes are verified in CODE against the source text."""
from __future__ import annotations
import asyncio, json, os, re, time
from anthropic import AsyncAnthropic

from . import cache
from .schema import AppRecord, Evidence

# Backend: "anthropic" if ANTHROPIC_API_KEY is set, else local "ollama" (override with LLM_BACKEND).
BACKEND = os.getenv("LLM_BACKEND") or ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
PASS1_MODEL = os.getenv("PASS1_MODEL") or ("claude-haiku-5-5" if BACKEND == "anthropic" else "llama3.2:latest")
PASS2_MODEL = os.getenv("PASS2_MODEL") or ("claude-sonnet-5-5" if BACKEND == "anthropic" else "qwen2.5-coder:7b")
SRC_CHARS = 9000 if BACKEND == "anthropic" else 3500  # keep local prompts inside a 16k context
_client: AsyncAnthropic | None = None
_OLLAMA_LOCK = asyncio.Lock()


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic()
    return _client


SYSTEM = """You research whether an app can become an AI-agent toolkit (Composio-style: auth + API tools, MCP server or agent skills).
Use ONLY the SOURCES provided. Never use memory. If sources don't support a field, use "unclear"/"unverified"/null and say so.
Every non-trivial claim (auth, self_serve, api_surface, existing_mcp, buildability) needs an evidence item whose quote_snippet is
copied VERBATIM (<25 words) from one source's text, with that source's url. Return ONLY a JSON object matching the schema fields:
one_line_description, website, auth_methods[], auth_notes, self_serve, gate_detail, api_surface{type,breadth,docs_quality,openapi_spec_url,rate_limits},
existing_mcp{exists,official,url}, buildability, main_blocker, blocker_detail, suggested_form, webhooks, pagination, sandbox_test_env,
sdk_languages[], api_access_pricing, time_to_first_call, outreach_needed, evidence[{url,quote_snippet,field_supported}], confidence, needs_human{flag,reason}.
Enums: auth_methods: oauth2|api_key|basic|bearer_token|jwt|other. self_serve: yes|trial|paid_required|admin_approval|partner_gated|contact_sales|unclear.
buildability: ready_now|ready_with_caveats|blocked|unverified. main_blocker: none|partner_approval|paid_plan|no_public_api|enterprise_only|review_process|tos_restriction|cli_only|other.
suggested_form: "MCP server"|"agent skills"|"CLI wrapper"|"not feasible"|"unverified". confidence: high|med|low.
Definitions: ready_now = self-serve creds + public API + no review; ready_with_caveats = works but needs paid plan/app review/trial; blocked = needs partnership, contact-sales, or no public API."""


def build_prompt(app: dict, sources: list[dict]) -> str:
    blocks = "\n\n".join(f"### SOURCE url={s['url']}\n{s['text'][:SRC_CHARS]}" for s in sources if s.get("text"))
    return f"APP: {app['app']} (category: {app['category']}, hint: {app['hint']})\n\nSOURCES:\n{blocks or '(none fetched)'}"


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


async def llm(model: str, system: str, user: str, run: str, max_tokens: int = 3000) -> str:
    k = cache.key("llm", BACKEND, model, system, user)
    if (hit := cache.get("llm", k)) is not None:
        return hit["text"]
    if BACKEND == "anthropic":
        r = await client().messages.create(model=model, max_tokens=max_tokens, system=system,
                                           messages=[{"role": "user", "content": user}])
        text, usage = r.content[0].text, {"in": r.usage.input_tokens, "out": r.usage.output_tokens}
    else:
        import httpx
        async with _OLLAMA_LOCK:  # one local generation at a time on a 6GB GPU
            async with httpx.AsyncClient(timeout=600) as c:
                r = await c.post(f"{OLLAMA_URL}/api/chat", json={
                    "model": model, "stream": False, "format": "json", "keep_alive": "10m",
                    "options": {"temperature": 0, "num_ctx": 16384, "num_predict": max_tokens},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                r.raise_for_status()
                j = r.json()
        text, usage = j["message"]["content"], {"in": j.get("prompt_eval_count"), "out": j.get("eval_count")}
    cache.put("llm", k, {"text": text})
    cache.log(run, {"llm": f"{BACKEND}:{model}", **usage})
    return text


async def extract(app: dict, sources: list[dict], model: str, run: str, pass_name: str) -> AppRecord:
    raw = await llm(model, SYSTEM, build_prompt(app, sources), run)
    try:
        data = _json(raw)
    except Exception:
        data = {}
    data.update(id=int(app["id"]), app=app["app"], category=app["category"], pass_name=pass_name)
    texts = {s["url"]: norm(s["text"]) for s in sources if s.get("text")}
    stamp = {s["url"]: s.get("fetched_at", time.strftime("%Y-%m-%dT%H:%M:%S")) for s in sources}
    ev = []
    for e in data.get("evidence", []) or []:
        try:
            url = e["url"]
            e["quote_verified"] = url in texts and norm(e.get("quote_snippet", "")) in texts[url]  # code check
            e["fetched_at"] = stamp.get(url, "")
            ev.append(Evidence(**e))
        except Exception:
            continue
    data["evidence"] = ev
    return salvage(app, data, pass_name)


def salvage(app: dict, data: dict, pass_name: str) -> AppRecord:
    """Validate; on failure drop only the invalid fields (logged), keep the rest. Dropped => default/unverified."""
    from pydantic import ValidationError
    dropped = []
    for _ in range(20):
        try:
            rec = AppRecord(**data)
            if dropped:
                rec.verification_log.append(f"schema-invalid fields dropped: {dropped}")  # logged, not a human flag
            return rec
        except ValidationError as err:
            for e in sorted(err.errors(), key=lambda e: [-x if isinstance(x, int) else 0 for x in e["loc"]]):
                loc = list(e["loc"])
                dropped.append(".".join(map(str, loc)))
                node = data
                try:
                    for part in loc[:-1]:
                        node = node[part]
                    if isinstance(node, list):
                        node.pop(loc[-1])
                    else:
                        node.pop(loc[-1], None)
                except Exception:
                    data.pop(loc[0], None)
    return AppRecord(id=int(app["id"]), app=app["app"], category=app["category"], pass_name=pass_name,
                     needs_human={"flag": True, "reason": "unsalvageable model output"})
