"""
Run sourced answer benchmark: Linkup (sourcedAnswer) vs Perplexity Sonar & Sonar Pro.

Requires: LINKUP_API_KEY, PERPLEXITY_API_KEY in .env

Reads:  queries.json
Writes: results.json
"""

import asyncio
import json
import os
import sys
import time

import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LINKUP_API_KEY = os.environ["LINKUP_API_KEY"]
PERPLEXITY_API_KEY = os.environ["PERPLEXITY_API_KEY"]

DIR = os.path.dirname(os.path.abspath(__file__))
CONCURRENCY = 3


async def query_linkup(session, query):
    start = time.monotonic()
    try:
        async with session.post(
            "https://api.linkup.so/v1/search",
            json={"q": query[:2000], "depth": "standard", "outputType": "sourcedAnswer"},
            headers={"Authorization": f"Bearer {LINKUP_API_KEY}"},
            timeout=aiohttp.ClientTimeout(total=90),
        ) as resp:
            data = await resp.json()
        return {"answer": data.get("answer", ""), "duration_s": round(time.monotonic() - start, 2), "error": None}
    except Exception as e:
        return {"answer": "", "duration_s": round(time.monotonic() - start, 2), "error": str(e)}


async def query_perplexity(client, model, query):
    for attempt in range(3):
        start = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant. Search the web and answer the user's question."},
                    {"role": "user", "content": query[:2000]},
                ],
            )
            raw = response.model_dump()
            usage = raw.get("usage", {})
            cost_info = usage.get("cost", {})
            return {
                "answer": response.choices[0].message.content or "",
                "duration_s": round(time.monotonic() - start, 2),
                "cost": cost_info.get("total_cost", 0),
                "error": None,
            }
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            return {"answer": "", "duration_s": round(time.monotonic() - start, 2), "cost": 0, "error": str(e)}


def simple_grade(expected, predicted):
    if not predicted or not expected:
        return None
    if expected.lower().strip() in predicted.lower().strip():
        return "A"
    exp_words = set(expected.lower().split())
    pred_words = set(predicted.lower().split())
    overlap = exp_words & pred_words
    if len(overlap) >= len(exp_words) * 0.8:
        return "B"
    if len(overlap) >= len(exp_words) * 0.5:
        return "C"
    return "F"


async def main():
    with open(os.path.join(DIR, "queries.json")) as f:
        queries = json.load(f)

    n = len(queries)
    print(f"Running {n} queries through Linkup, Sonar, and Sonar Pro...\n")

    pplx_client = AsyncOpenAI(api_key=PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")
    session = aiohttp.ClientSession()

    results = []
    for i, q in enumerate(queries):
        query = q["query"]
        expected = q.get("expected_answer")

        l, s, sp = await asyncio.gather(
            query_linkup(session, query),
            query_perplexity(pplx_client, "sonar", query),
            query_perplexity(pplx_client, "sonar-pro", query),
        )

        row = {
            "query": query[:300],
            "category": q.get("category", ""),
            "expected_answer": expected,
            "linkup_answer": l["answer"][:1000],
            "linkup_duration": l["duration_s"],
            "linkup_cost": 0.0058,
            "linkup_error": l["error"],
            "sonar_answer": s["answer"][:1000],
            "sonar_duration": s["duration_s"],
            "sonar_cost": s.get("cost", 0),
            "sonar_error": s["error"],
            "sonar_pro_answer": sp["answer"][:1000],
            "sonar_pro_duration": sp["duration_s"],
            "sonar_pro_cost": sp.get("cost", 0),
            "sonar_pro_error": sp["error"],
        }

        if expected:
            row["linkup_grade"] = simple_grade(expected, l["answer"])
            row["sonar_grade"] = simple_grade(expected, s["answer"])
            row["sonar_pro_grade"] = simple_grade(expected, sp["answer"])

        results.append(row)
        print(f"[{i+1}/{n}] {query[:60]}...")
        await asyncio.sleep(1.5)

    await pplx_client.close()
    await session.close()

    with open(os.path.join(DIR, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} results to results.json")


if __name__ == "__main__":
    asyncio.run(main())
