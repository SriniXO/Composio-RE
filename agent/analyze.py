"""Compute every statistic shown on the site from results/<pass>/*.json. Nothing is hand-typed.

  python -m agent.analyze --pass 2
Writes data/apps.json, data/apps.csv, data/stats.json
"""
import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="p", default="pass2")
    a = ap.parse_args()
    d = ROOT / "results" / (a.p if a.p.startswith("pass") else f"pass{a.p}")
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]
    n = len(recs)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "apps.json").write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
    cols = ["id", "app", "category", "one_line_description", "auth_methods", "self_serve", "buildability",
            "main_blocker", "suggested_form", "existing_mcp_exists", "outreach_needed", "confidence", "needs_human", "evidence_urls"]
    with open(ROOT / "data" / "apps.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in recs:
            w.writerow([r["id"], r["app"], r["category"], r["one_line_description"], ";".join(r["auth_methods"]), r["self_serve"],
                        r["buildability"], r["main_blocker"], r["suggested_form"], r["existing_mcp"]["exists"], r["outreach_needed"],
                        r["confidence"], r["needs_human"]["flag"], ";".join(e["url"] for e in r["evidence"] if e["quote_verified"])])
    verified = lambda r: any(e["quote_verified"] for e in r["evidence"])
    cat = defaultdict(list)
    for r in recs:
        cat[r["category"]].append(r)
    auth_all = Counter(m for r in recs for m in r["auth_methods"])
    stats = {
        "source_pass": a.p, "n_apps": n,
        "auth_overall": auth_all.most_common(),
        "auth_by_category": {c: Counter(m for r in rs for m in r["auth_methods"]).most_common() for c, rs in cat.items()},
        "self_serve_overall": Counter(r["self_serve"] for r in recs).most_common(),
        "self_serve_by_category": {c: Counter(r["self_serve"] for r in rs).most_common() for c, rs in cat.items()},
        "buildability_overall": Counter(r["buildability"] for r in recs).most_common(),
        "buildability_by_category": {c: Counter(r["buildability"] for r in rs).most_common() for c, rs in cat.items()},
        "blockers": Counter(r["main_blocker"] for r in recs if r["buildability"] != "ready_now").most_common(),
        "easy_wins": [r["app"] for r in recs if r["buildability"] == "ready_now"],
        "needs_outreach": [r["app"] for r in recs if r["outreach_needed"] or r["main_blocker"] in ("partner_approval", "enterprise_only")],
        "existing_mcp_exists": sum(1 for r in recs if r["existing_mcp"]["exists"]),
        "existing_mcp_unverified": sum(1 for r in recs if r["existing_mcp"]["exists"] is None),
        "with_verified_evidence": sum(1 for r in recs if verified(r)),
        "needs_human": [r["app"] for r in recs if r["needs_human"]["flag"]],
        "confidence": Counter(r["confidence"] for r in recs).most_common(),
        "defeated": [r["app"] for r in recs if not verified(r)],
    }
    (ROOT / "data" / "stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{n} records from {d.name}; verified-evidence apps: {stats['with_verified_evidence']}; ready_now: {len(stats['easy_wins'])}")


if __name__ == "__main__":
    main()
