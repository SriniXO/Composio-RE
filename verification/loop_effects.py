"""What did the pass-2 verification loops actually do? Computed from results/ + the AI audit. Writes data/loop_effects.json."""
import csv, json, re
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
W = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}

def load(p): return {json.loads(f.read_text(encoding="utf-8"))["id"]: json.loads(f.read_text(encoding="utf-8")) for f in sorted((ROOT/"results"/p).glob("*.json"))}
p1, p2 = load("pass1"), load("pass2")
def qrate(rs):
    ev = [e for r in rs.values() for e in r["evidence"]]
    return {"quotes": len(ev), "verified": sum(e["quote_verified"] for e in ev), "apps_with_verified_evidence": sum(any(e["quote_verified"] for e in r["evidence"]) for r in rs.values())}
log = Counter()
for r in p2.values():
    for l in r["verification_log"]:
        for k in ("dropped-quote-not-in-page", "verifier-rejected", "cross-source-missing", "fallback used", "contradiction", "schema-invalid"):
            if k in l: log[k] += 1
fall = Counter(re.search(r"(composio:TAVILY_EXTRACT|playwright)", l).group(1) for r in p2.values() for l in r["verification_log"] if "fallback used" in l and re.search(r"(composio:TAVILY_EXTRACT|playwright)", l))
rows = list(csv.DictReader(open(ROOT/"verification"/"ai_audit.csv", encoding="utf-8")))
def acc(sel):
    v = [W[r["ai_audit_pass2"]] for r in sel if r["ai_audit_pass2"] in W]
    return {"accuracy": round(sum(v)/len(v), 3) if v else None, "n": len(v)}
hv = lambda r: any(e["quote_verified"] for e in p2[int(r["id"])]["evidence"])
fl = lambda r: p2[int(r["id"])]["needs_human"]["flag"]
out = {"pass1": qrate(p1), "pass2": qrate(p2), "pass2_log_events": dict(log), "pass2_fallbacks_used": dict(fall),
       "pass2_accuracy_by_evidence": {"has_verified_evidence": acc([r for r in rows if hv(r)]), "no_verified_evidence": acc([r for r in rows if not hv(r)])},
       "pass2_accuracy_by_flag": {"flagged_needs_human": acc([r for r in rows if fl(r)]), "not_flagged": acc([r for r in rows if not fl(r)])}}
(ROOT/"data"/"loop_effects.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
