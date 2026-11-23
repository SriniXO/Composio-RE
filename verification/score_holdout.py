"""Score runs on the 15 HELD-OUT apps (never used to design pass 3). Truths in holdout_truth.json were audited BEFORE viewing answers.
Same rules as score_small.py. None truth => not scored. Apps 88 and 91 had their pass-3 corrective searches fail (wallet exhausted): reported separately."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
T = json.load(open(ROOT/"verification"/"holdout_truth.json", encoding="utf-8"))
GATED = {"paid_required","admin_approval","partner_gated","contact_sales"}
SC = {"ready_now":0,"ready_with_caveats":1,"blocked":2}
W = {"correct":1,"partial":.5,"wrong":0}
CONST = {"auth_methods":["oauth2","api_key","basic","bearer_token","jwt"],"self_serve":"yes","api_surface":{"type":"unclear"},"existing_mcp":{"exists":True,"official":True},"buildability":"ready_now"}

def judge(t, r):
    o = {}
    s, tt = set(r["auth_methods"]), set(t["auth"]); ex, mi = len(s-tt), len(tt-s)
    o["auth_methods"] = "wrong" if (not s and tt) or ex >= 3 else "correct" if ex == 0 and mi == 0 else "partial"
    if t["ss"]:
        good, ok = t["ss"]; v = r["self_serve"]
        cor = (v in GATED) if good == "gated" else (v == "paid_required") if good == "paid" else (v == good)
        o["self_serve"] = "correct" if cor else "partial" if ((ok and v == ok) or (good == "paid" and v in GATED) or (good == "gated" and v in GATED)) else "wrong"
    if t["api"]:
        ty = r["api_surface"]["type"]
        o["api_surface"] = "correct" if ty == t["api"] else "partial" if t["api"] == "REST+GraphQL" and ty in ("REST","GraphQL") else "wrong"
    if t["mcp"]:
        m = r["existing_mcp"]; e, off = t["mcp"]
        o["existing_mcp"] = "partial" if m["exists"] is None else "correct" if (m["exists"] == e and m["official"] == off) else "wrong"
    if t["bu"]:
        d = abs(SC.get(r["buildability"], 9) - SC[t["bu"]])
        o["buildability"] = "correct" if d == 0 else "partial" if d == 1 else "wrong"
    return o

def run(d, ids):
    tot = {}
    for i in ids:
        r = CONST if d == "constant" else json.load(open(ROOT/"results"/d/f"{int(i):03d}.json", encoding="utf-8"))
        for f, x in judge(T[str(i)], r).items():
            for k in (f, "ALL"):
                a = tot.setdefault(k, [0,0,0]); a[0]+=W[x]; a[1]+=(x == "correct"); a[2]+=1
    return {f: {"accuracy": round(a/n,3), "strict": round(s/n,3), "n": n} for f,(a,s,n) in tot.items()}

all_ids = sorted(int(i) for i in T); degraded = {88, 91}; clean = [i for i in all_ids if i not in degraded]
out = {"n_apps": len(all_ids), "clean_apps": len(clean), "degraded_apps": sorted(degraded), "runs": {}}
for d in ("constant", "pass2", "pass3"):
    out["runs"][d] = {"all_15": run(d, all_ids), "clean_13": run(d, clean)}
acc = json.load(open(ROOT/"data"/"accuracy.json", encoding="utf-8")); acc["holdout"] = out
json.dump(acc, open(ROOT/"data"/"accuracy.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)
for scope in ("clean_13", "all_15"):
    print(scope)
    for d in ("constant","pass2","pass3"):
        print(f"  {d:9}", {f:(v["accuracy"], v["n"]) for f,v in out["runs"][d][scope].items()})
