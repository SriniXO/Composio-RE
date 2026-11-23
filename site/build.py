"""Build site/index.html (static, no framework) + llms.txt + JSON-LD from data/*.json. Every number comes from data files.

  python -m agent.analyze --pass 2 && python site/build.py [--repo URL] [--live URL]
"""
import argparse, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def jload(p, default):
    f = ROOT / "data" / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


def pct(a, b):
    return f"{round(100 * a / b)}%" if b else "n/a"


def headlines(st, apps):
    n = st["n_apps"]
    out = []
    if st["auth_overall"]:
        top, c = st["auth_overall"][0]
        out.append(f"<b>{top}</b> is the most common auth method ({c} of {n} apps list it).")
    ss = dict(st["self_serve_overall"])
    out.append(f"<b>{ss.get('yes', 0)}</b> apps are self-serve today; <b>{ss.get('trial', 0)}</b> via trial; "
               f"<b>{ss.get('paid_required', 0) + ss.get('admin_approval', 0) + ss.get('partner_gated', 0) + ss.get('contact_sales', 0)}</b> are gated; "
               f"<b>{ss.get('unclear', 0)}</b> are unclear.")
    if st["blockers"]:
        b, c = st["blockers"][0]
        out.append(f"Most common blocker among non-ready apps: <b>{b.replace('_', ' ')}</b> ({c} apps).")
    out.append(f"<b>{len(st['easy_wins'])}</b> apps are <code>ready_now</code> (easy wins); <b>{len(st['needs_outreach'])}</b> need outreach.")
    out.append(f"Existing MCP found for <b>{st['existing_mcp_exists']}</b> apps; <b>{st['existing_mcp_unverified']}</b> unverified.")
    out.append(f"Only <b>{st['with_verified_evidence']}</b> of {n} records have at least one machine-verified evidence quote; "
               f"<b>{len(st['needs_human'])}</b> are flagged for a human.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="")
    ap.add_argument("--live", default="")
    a = ap.parse_args()
    apps, st, acc = jload("apps.json", []), jload("stats.json", {}), jload("accuracy.json", {})
    p1 = jload("stats_pass1.json", {})
    if not apps or not st:
        raise SystemExit("run `python -m agent.analyze --pass 2` first")
    payload = {"apps": apps, "stats": st, "accuracy": acc, "pass1": p1, "repo": a.repo, "live": a.live}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    heads = "".join(f"<li>{h}</li>" for h in headlines(st, apps))
    tpl = (SITE / "template.html").read_text(encoding="utf-8")
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "Agent-toolkit buildability of 100 apps",
          "description": "Auth, self-serve vs gated, API surface, MCP and buildability for 100 apps, with evidence URLs.",
          "url": a.live, "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": "apps.json"},
                                          {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": "apps.csv"}],
          "variableMeasured": ["auth_methods", "self_serve", "api_surface", "existing_mcp", "buildability", "main_blocker"]}
    html = (tpl.replace("{{DATA}}", blob).replace("{{HEADLINES}}", heads)
               .replace("{{JSONLD}}", json.dumps(ld).replace("</", "<\\/")).replace("{{REPO}}", a.repo or "#"))
    (SITE / "index.html").write_text(html, encoding="utf-8")
    for f in ("apps.json", "apps.csv"):
        if (ROOT / "data" / f).exists():
            shutil.copy(ROOT / "data" / f, SITE / f)
    llms = [f"# Agent-toolkit buildability research: {st['n_apps']} apps", "",
            f"Source: {a.live or '(live URL pending)'}  Repo: {a.repo or '(pending)'}",
            "Data: apps.json, apps.csv. Every field has evidence[] with url + quote; quote_verified=true means the quote was found verbatim in the fetched page.",
            "", "## Headline patterns"] + ["- " + h.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "") for h in headlines(st, apps)]
    (SITE / "llms.txt").write_text("\n".join(llms), encoding="utf-8")
    print("built site/index.html,", len(apps), "apps")


if __name__ == "__main__":
    main()
