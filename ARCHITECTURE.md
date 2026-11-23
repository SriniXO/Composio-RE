# Architecture: why each piece exists

**Fixed schema (pydantic).** Forces every app into the same fields and enums so results can be compared and counted. Unknown is a legal value (`unclear`/`unverified`/`null`); guessing is not.

**Evidence-first extraction.** The model may only use fetched text, and must copy each supporting quote verbatim. *Code*, not the model, checks that the quote is a substring of the page (`quote_verified`). Reason: small models paraphrase and invent; a substring check is cheap and cannot be argued with.

**Two passes, kept separate.** Pass 1 is a deliberately light baseline (3 searches, snippets only, llama3.2). It is never tuned; it is the "before". Pass 2 fetches real pages (stronger model) and runs the loops below. Reason: accuracy gains are only believable against an untouched baseline.

**Pass 2 loops.**
- a. Verifier re-reads the cited page and confirms the quote supports the field.
- b. Cross-source: auth and self-serve claims need 2 distinct verified pages, else confidence drops.
- c. Rules: schema validation, dead-link detection, contradictions (e.g. `ready_now` with a blocker).
- d. Fallbacks for pages plain fetch can't read: Composio `TAVILY_EXTRACT`, then Playwright.
- e. Anything low-confidence, conflicting or unevidenced is flagged `needs_human`.

**Schema salvage.** If a model breaks an enum, only that field is dropped and logged, and the record is flagged. Reason: discarding a whole record hid real signal in the first run, and the drop count is itself a quality metric.

**Cache + resumability + logs.** Every search, fetch and LLM call is cached by content key; failures are never cached (an early bug cached empty searches). Reason: a 3+ hour run must survive crashes and be re-runnable deterministically.

**Composio usage.** The logged-in CLI executes `TAVILY_SEARCH` and `TAVILY_EXTRACT`. Reason: it removes the need for a separate search API key and is the intended way to give agents tools. The SDK path was not used because the CLI route was the one verified end to end.

**Local Ollama LLM.** Chosen because no Anthropic key was available. The backend is swappable by env var. Trade-off: slower and less accurate; the verification loops exist precisely to bound that.

**Human verification.** The human fills the verdict columns of `verification/sample.csv`; the scorer reads only those. Reason: accuracy must be measured against ground truth the agent did not produce.

**Static page.** One HTML file generated from `data/*.json` (no hand-typed numbers), with the data embedded, plus `apps.json`/`apps.csv`/`llms.txt`/JSON-LD for agents.
