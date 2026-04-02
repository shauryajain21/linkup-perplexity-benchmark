"""
Run search results benchmark: Linkup (searchResults) vs Perplexity Search API.

Requires: LINKUP_API_KEY, PERPLEXITY_API_KEY in .env

Reads:  queries.json
Writes: search_results_raw.json
"""

import asyncio
import json
import os
import time

import aiohttp
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LINKUP_API_KEY = os.environ["LINKUP_API_KEY"]
PERPLEXITY_API_KEY = os.environ["PERPLEXITY_API_KEY"]

DIR = os.path.dirname(os.path.abspath(__file__))
CONCURRENCY = 3


async def fetch_linkup(session, query):
    start = time.perf_counter()
    try:
        async with session.post(
            "https://api.linkup.so/v1/search",
            json={"q": query[:2000], "depth": "standard", "outputType": "searchResults"},
            headers={"Authorization": f"Bearer {LINKUP_API_KEY}"},
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            data = await resp.json()
        results = data.get("results", [])
        return {"results": results, "num_results": len(results),
                "latency_s": round(time.perf_counter() - start, 3), "error": None}
    except Exception as e:
        return {"results": [], "num_results": 0,
                "latency_s": round(time.perf_counter() - start, 3), "error": str(e)}


async def fetch_perplexity(session, query):
    start = time.perf_counter()
    try:
        async with session.post(
            "https://api.perplexity.ai/search",
            json={"query": query[:2000], "max_results": 20},
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            data = await resp.json()
        if "error" in data:
            return {"results": [], "num_results": 0,
                    "latency_s": round(time.perf_counter() - start, 3), "error": json.dumps(data["error"])}
        raw = data.get("results", [])
        results = [{"name": r.get("title", ""), "url": r.get("url", ""), "content": r.get("snippet", "")} for r in raw]
        return {"results": results, "num_results": len(results),
                "latency_s": round(time.perf_counter() - start, 3), "error": None}
    except Exception as e:
        return {"results": [], "num_results": 0,
                "latency_s": round(time.perf_counter() - start, 3), "error": str(e)}


async def main():
    with open(os.path.join(DIR, "queries.json")) as f:
        queries = json.load(f)

    n = len(queries)
    print(f"Running {n} queries through Linkup searchResults + Perplexity Search API...\n")

    session = aiohttp.ClientSession()
    results = []

    for batch_start in range(0, n, CONCURRENCY):
        batch = queries[batch_start:batch_start + CONCURRENCY]
        tasks = [asyncio.gather(fetch_linkup(session, q["query"]), fetch_perplexity(session, q["query"])) for q in batch]
        batch_results = await asyncio.gather(*tasks)

        for q, (l, p) in zip(batch, batch_results):
            results.append({"query": q["query"], "org": q.get("org", ""), "linkup": l, "pplx": p})
            le = "OK" if not l["error"] else "ERR"
            pe = "OK" if not p["error"] else "ERR"
            print(f"  [{len(results)}/{n}] L:{le} {l['num_results']}res | P:{pe} {p['num_results']}res")

        await asyncio.sleep(0.5)

    await session.close()

    with open(os.path.join(DIR, "search_results_raw.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved {len(results)} results to search_results_raw.json")


if __name__ == "__main__":
    asyncio.run(main())
