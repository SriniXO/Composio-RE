"""Independent audit helper: official-source searches for one app. Prints compact evidence for me to read.
usage: python verification/audit_fetch.py "App Name" domain1 [domain2 ...]"""
import asyncio, sys, httpx
from agent import tools

async def main(app, domains):
    qs = [(f"{app} API authentication OAuth API key", domains),
          (f"{app} API access pricing free trial sign up developer", domains),
          (f"{app} official MCP server", None)]
    async with httpx.AsyncClient() as c:
        for q, d in qs:
            r = await tools.search(q, c, n=3, domains=d)
            print(f"## {q} [{'|'.join(d) if d else 'any'}]")
            for x in r["results"]:
                print(f"- {x['url']}\n  {x['snippet'][:300].replace(chr(10),' ')}")
asyncio.run(main(sys.argv[1], sys.argv[2:]))
