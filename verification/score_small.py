"""Score results/pass2-small against the SAME audit truths, using fixed rules (no new research).
Rules: auth: empty=wrong, >=3 extras=wrong, 1-2 extras or missing=partial, exact=correct. self_serve: accepted/partial sets.
api type: exact=correct, unclear=wrong. mcp: exists+official must match truth. buildability: scale ready_now<caveats<blocked, 1 step=partial, 2=wrong."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
O, A_, B_ = "ready_now", "ready_with_caveats", "blocked"
AUTH = {4:{"oauth2","api_key"},8:{"oauth2","api_key"},11:{"oauth2","api_key","basic"},17:{"api_key"},20:{"api_key","basic"},23:{"oauth2"},26:{"api_key","oauth2","basic"},33:{"oauth2"},34:{"oauth2","api_key"},40:{"api_key"},42:{"api_key"},45:{"bearer_token"},48:{"oauth2","api_key"},49:{"oauth2"},51:{"basic"},52:{"api_key"},53:{"api_key"},65:{"api_key","oauth2","jwt"},69:{"api_key","oauth2"},73:{"oauth2","api_key"},76:{"api_key","oauth2"},79:{"api_key","oauth2"},81:{"api_key","basic","bearer_token","oauth2"},87:{"oauth2"},93:{"api_key","oauth2"},98:set(),100:{"oauth2","api_key"}}
SS = {4:("yes","trial"),8:("yes","trial"),11:("trial","yes"),17:("trial","yes"),20:("gated",""),23:("yes","trial"),26:("yes",""),33:("gated",""),34:("trial","yes"),40:("trial","yes"),42:("yes",""),45:("yes",""),48:("yes",""),49:("gated",""),51:("trial","yes"),52:("trial","yes"),53:("paid",""),65:("yes",""),69:("trial","yes"),73:("yes",""),76:("yes",""),79:("trial","yes"),81:("yes",""),87:("yes",""),93:("yes",""),98:("yes",""),100:("yes","trial")}
GATED = {"paid_required","admin_approval","partner_gated","contact_sales"}
API = {i:"REST" for i in AUTH}; API.update({17:"GraphQL",73:"GraphQL",76:"GraphQL",45:"REST+GraphQL",98:"none"})
MCP = {i:(True,True) for i in AUTH}; MCP.update({20:(True,False),26:(True,False),33:(True,False),40:(True,False),45:(True,False),48:(True,False),49:(True,None),98:(True,False)})
BU = {4:O,8:O,11:A_,17:O,20:B_,23:A_,26:O,33:B_,34:A_,40:A_,42:A_,45:A_,48:O,49:B_,51:O,52:O,53:A_,65:O,69:A_,73:O,76:O,79:A_,81:O,87:O,93:O,98:A_,100:O}
SC = {O:0,A_:1,B_:2}
def jaudge(i, r):
    out = {}
    s, t = set(r["auth_methods"]), AUTH[i]
    ex, mi = len(s - t), len(t - s)
    out["auth_methods"] = "wrong" if not s and t or ex >= 3 else "correct" if ex == 0 and mi == 0 else "partial"
    if not t and not s: out["auth_methods"] = "correct"
    v = r["self_serve"]; good, ok = SS[i]
    isg = v in GATED
    cor = isg if good == "gated" else (v == "paid_required") if good == "paid" else (v == good)
    out["self_serve"] = "correct" if cor else "partial" if ((v == ok and ok) or (good == "paid" and isg)) else "wrong"
    ty = r["api_surface"]["type"]; tr = API[i]
    out["api_surface"] = "correct" if ty == tr else "partial" if tr == "REST+GraphQL" and ty in ("REST","GraphQL") else "wrong"
    m = r["existing_mcp"]; te, to = MCP[i]
    if m["exists"] is None: out["existing_mcp"] = "partial"
    else: out["existing_mcp"] = "correct" if (m["exists"] == te and (to is None or m["official"] == to)) else "wrong"
    d = abs(SC.get(r["buildability"], 9) - SC[BU[i]])
    out["buildability"] = "correct" if d == 0 else "partial" if d == 1 else "wrong"
    return out
ids = json.load(open(ROOT/"verification"/"sample_apps.json"))["ids"]
res, W = {}, {"correct":1,"partial":.5,"wrong":0}
tot = {f:[0,0,0] for f in ["auth_methods","self_serve","api_surface","existing_mcp","buildability","ALL"]}
for i in ids:
    if i == 84: continue
    r = json.load(open(ROOT/"results"/"pass2-small"/f"{i:03d}.json", encoding="utf-8"))
    v = jaudge(i, r); res[str(i)] = v
    for f, x in v.items():
        for k in (f, "ALL"): tot[k][0]+=W[x]; tot[k][1]+=(x=="correct"); tot[k][2]+=1
out = {f:{"accuracy":round(a/n,3),"strict":round(s/n,3),"n":n} for f,(a,s,n) in tot.items()}
(ROOT/"verification"/"ai_audit_small.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
acc = json.load(open(ROOT/"data"/"accuracy.json", encoding="utf-8")); acc["ai_audit_small"] = {"pass2_small": out}
(ROOT/"data"/"accuracy.json").write_text(json.dumps(acc, indent=1, ensure_ascii=False), encoding="utf-8")
print({f:(v["accuracy"],v["strict"]) for f,v in out.items()})
