"""Score accuracy. Two SEPARATE sources, never mixed:
  ai_audit : verification/ai_audit.json  (independent audit by Claude reading official docs; NOT human)
  human    : verification/sample.csv     (verdict columns filled by the person; skipped while blank)
Verdicts: correct=1, partial=0.5, wrong=0, unverifiable=excluded.
Reports both 'accuracy' (partial=0.5) and 'strict' (only fully correct counts). Writes data/accuracy.json.
"""
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}


def tally(items):
    """items: iterable of (pass, field, verdict)"""
    acc = {p: defaultdict(lambda: {"sum": 0.0, "strict": 0, "n": 0}) for p in ("pass1", "pass2")}
    excluded = 0
    for p, f, v in items:
        v = (v or "").strip().lower()
        if v not in W:
            excluded += 1
            continue
        for key in (f, "ALL"):
            a = acc[p][key]
            a["sum"] += W[v]; a["strict"] += (v == "correct"); a["n"] += 1
    out = {p: {f: {"accuracy": round(a["sum"] / a["n"], 3), "strict": round(a["strict"] / a["n"], 3), "n": a["n"]}
               for f, a in d.items() if a["n"]} for p, d in acc.items()}
    return out, excluded


def main():
    res = {}
    # AI audit
    ai = json.loads((ROOT / "verification" / "ai_audit.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(ROOT / "verification" / "ai_audit.csv", encoding="utf-8")))
    items, wrong = [], []
    for r in rows:
        items += [("pass1", r["field"], r["ai_audit_pass1"]), ("pass2", r["field"], r["ai_audit_pass2"])]
        for p in ("pass1", "pass2"):
            if r[f"ai_audit_{p}"] == "wrong":
                wrong.append({"pass": p, "app": r["app"], "field": r["field"], "agent_said": r[f"{p}_answer"][:140],
                              "truth": r["ai_audit_truth"], "source": r["ai_audit_source"]})
    res["ai_audit"], res["ai_audit_unverifiable_excluded"] = tally(items)
    res["ai_audit_wrong_answers"] = wrong
    # Human
    hrows = list(csv.DictReader(open(ROOT / "verification" / "sample.csv", encoding="utf-8")))
    hitems = []
    for r in hrows:
        hitems += [("pass1", r["field"], r.get("human_verdict_pass1")), ("pass2", r["field"], r.get("human_verdict_pass2"))]
    res["human"], _ = tally(hitems)
    res["human_rows_filled"] = sum(1 for r in hrows if (r.get("human_verdict_pass1") or r.get("human_verdict_pass2") or "").strip())
    res["sample_apps"] = len({r["id"] for r in hrows})
    hr = ROOT / "verification" / "human_review.csv"
    if hr.exists():
        rr = [r for r in csv.DictReader(open(hr, encoding="utf-8")) if (r.get("YOUR_verdict(correct|wrong|partial)") or r.get("YOUR_verdict(correct|partial|wrong)") or "").strip().lower() in W]
        key = "YOUR_verdict(correct|partial|wrong)"
        done = [r for r in rr if r.get(key, "").strip().lower() in W]
        agree = sum(1 for r in done if r[key].strip().lower() == r["ai_audit_verdict_pass2"].strip().lower())
        res["human_review"] = {"n": len(done), "agree_with_audit": agree,
                               "pass2_accuracy_by_human": round(sum(W[r[key].strip().lower()] for r in done) / len(done), 3) if done else None}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "accuracy.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for p in ("pass1", "pass2"):
        print(p, {f: (v["accuracy"], v["strict"], v["n"]) for f, v in res["ai_audit"][p].items()})
    print("human rows filled:", res["human_rows_filled"], "| unverifiable excluded:", res["ai_audit_unverifiable_excluded"])


if __name__ == "__main__":
    main()
