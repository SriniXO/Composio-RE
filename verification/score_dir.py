"""Score any results dir on the audited sample using the fixed rules in score_small.py. usage: python verification/score_dir.py pass3"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
src = (ROOT/"verification"/"score_small.py").read_text(encoding="utf-8").split("ids = json.load")[0]
ns = {}; exec(src, {"__file__": str(ROOT/"verification"/"score_small.py"), **ns}, ns) if False else None
g = {"__file__": str(ROOT/"verification"/"score_small.py")}; exec(src, g)
d = sys.argv[1]; ids = json.load(open(ROOT/"verification"/"sample_apps.json"))["ids"]
W = {"correct":1,"partial":.5,"wrong":0}; tot = {}
for i in ids:
    if i == 84: continue
    r = ({"auth_methods":["oauth2","api_key","basic","bearer_token","jwt"],"self_serve":"yes","api_surface":{"type":"unclear"},"existing_mcp":{"exists":True,"official":True},"buildability":"ready_now"}
         if d == "constant" else json.load(open(ROOT/"results"/d/f"{i:03d}.json", encoding="utf-8")))
    for f, x in g["jaudge"](i, r).items():
        for k in (f, "ALL"):
            t = tot.setdefault(k, [0,0,0]); t[0]+=W[x]; t[1]+=(x=="correct"); t[2]+=1
out = {f: {"accuracy": round(a/n,3), "strict": round(s/n,3), "n": n} for f,(a,s,n) in tot.items()}
print(d, {f:(v["accuracy"],v["strict"]) for f,v in out.items()})
if len(sys.argv) > 2:
    acc = json.load(open(ROOT/"data"/"accuracy.json", encoding="utf-8")); acc.setdefault("rule_scored", {})[d] = out
    json.dump(acc, open(ROOT/"data"/"accuracy.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)
