"""Score accuracy from the HUMAN verdicts in verification/sample.csv. Writes data/accuracy.json.

Verdict values: correct | wrong | partial (partial counts 0.5). Rows with no verdict are excluded and counted as 'unchecked'.
Pass 1 and pass 2 answers are judged by the human in the same row via the optional columns
`human_verdict_pass1` / `human_verdict_pass2`; if only `human_verdict(...)` is present it is applied to pass 2.
"""
import csv, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}


def main():
    rows = list(csv.DictReader(open(ROOT / "verification" / "sample.csv", encoding="utf-8")))
    acc = {p: defaultdict(lambda: [0.0, 0]) for p in ("pass1", "pass2")}
    unchecked, wrong = 0, []
    for r in rows:
        v2 = (r.get("human_verdict_pass2") or r.get("human_verdict(correct|wrong|partial)") or "").strip().lower()
        v1 = (r.get("human_verdict_pass1") or "").strip().lower()
        if v2 not in W and v1 not in W:
            unchecked += 1
            continue
        for p, v in (("pass1", v1), ("pass2", v2)):
            if v in W:
                acc[p][r["field"]][0] += W[v]
                acc[p][r["field"]][1] += 1
                acc[p]["ALL"][0] += W[v]
                acc[p]["ALL"][1] += 1
                if v == "wrong":
                    wrong.append({"pass": p, "app": r["app"], "field": r["field"], "agent_said": r[f"{p}_answer"],
                                  "truth": r["truth_per_docs"], "source": r["human_source_url"], "notes": r["notes"]})
    out = {p: {f: {"accuracy": round(a / n, 3), "n": n} for f, (a, n) in d.items() if n} for p, d in acc.items()}
    out["unchecked_rows"] = unchecked
    out["wrong_answers"] = wrong
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "accuracy.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "wrong_answers"}, indent=1))


if __name__ == "__main__":
    main()
