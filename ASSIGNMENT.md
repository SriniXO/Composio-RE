# Composio AI Product Ops Intern: take-home spec (verbatim summary of the brief)

Budget 6-8 hours; submit < 8 hrs after receiving. Result + clarity of presentation matter, not hours.

## Context
Composio turns apps into tools AI agents can call. Before building a toolkit we research each app: auth, self-serve vs
partner-gated, API surface, MCP/skills feasibility. This assignment is a small real version of that at 100 apps.

## Task: for each of the 100 apps capture
- Category + one-line description
- Auth method(s): OAuth2 / API key / Basic / token / other
- Self-serve vs gated (free/trial vs paid plan, admin approval, partnership, contact-sales)
- API surface: public REST/GraphQL, breadth, existing MCP
- Buildability verdict (agent toolkit today?) + main blocker
- Evidence URL behind every answer; "and more.."

Then:
1. **Find the patterns** (cluster; dominant auth; self-serve vs gated by category; most common blocker; easy wins vs outreach). Insight over table.
2. **Do it with an agent** (script/pipeline). Composio SDK/MCP usage is in the spirit of the role. Say what it does and where a human was needed.
3. **Verify accuracy**: sample, hand-check against real docs, report right/wrong; build verification loops (agent, browser-use, human); show accuracy moving from first pass to higher pass. Accuracy matters most.

## Deliverable
One self-explanatory HTML page / case study understandable in ~2 min: findings table/matrix, patterns up top, the agent (+ where human needed),
proof (live link or runnable trigger), verification (sample, hits AND misses). Make it consumable by agents and humans.

## Constraints
Use AI freely but be able to explain everything. Admit wrong answers / defeated apps on the page. No paid accounts needed; gated-with-evidence is a valid finding.

## Submit
Live link to deployed page + source repo link with README on running the agent.

## The 100 apps
See `data/apps_seed.csv` (id, app, category, hint), 10 categories x 10 apps:
CRM and Sales (1-10), Support and Helpdesk (11-20), Communications and Messaging (21-30), Marketing/Ads/Email/Social (31-40),
Ecommerce (41-50), Data/SEO/Scraping (51-60), Developer/Infra/Data platforms (61-70), Productivity and PM (71-80),
Finance and Fintech (81-90), AI/Research/Media-native (91-100).
