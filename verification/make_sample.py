"""Draw the stratified verification sample (seed fixed) and emit the human checklist.

  python verification/make_sample.py
Output: verification/sample_apps.json (which apps) + verification/sample.csv (one row per app x field).
Verdict columns are left BLANK on purpose: only the human fills them.
"""
import csv, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED, N = 1512, 28
FIELDS = ["auth_methods", "self_serve", "api_surface", "existing_mcp", "buildability"]


def load(pass_name):
    d = {}
    for p in sorted((ROOT / "results" / pass_name).glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        d[r["id"]] = r
    return d


def show(r, f):
    v = r.get(f)
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v


def main():
    p1, p2 = load("pass1"), load("pass2")
    pool = sorted(p2 or p1)
    cats = {}
    for r in (p2 or p1).values():
        cats.setdefault(r["category"], []).append(r["id"])
    rng = random.Random(SEED)
    chosen = []
    for c in sorted(cats):  # 2 per category first, guarantees all 10 categories
        chosen += rng.sample(sorted(cats[c]), 2)
    rest = [i for i in pool if i not in chosen]
    chosen += rng.sample(rest, N - len(chosen))
    chosen = sorted(chosen)
    (ROOT / "verification" / "sample_apps.json").write_text(json.dumps({"seed": SEED, "n": N, "ids": chosen}, indent=1))
    with open(ROOT / "verification" / "sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "app", "field", "pass1_answer", "pass2_answer", "evidence_urls_pass2",
                    "human_verdict(correct|wrong|partial)", "truth_per_docs", "human_source_url", "notes"])
        for i in chosen:
            a, b = p1.get(i, {}), p2.get(i, {})
            for fld in FIELDS:
                urls = " | ".join(e["url"] for e in b.get("evidence", []) if e.get("quote_verified"))
                w.writerow([i, (b or a)["app"], fld, show(a, fld) if a else "", show(b, fld) if b else "", urls, "", "", "", ""])
    print(f"sample of {len(chosen)} apps -> verification/sample.csv ({len(chosen)*len(FIELDS)} rows)")


if __name__ == "__main__":
    main()
