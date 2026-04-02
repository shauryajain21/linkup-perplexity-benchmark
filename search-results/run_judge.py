"""
Run LLM-as-judge on search results: Linkup vs Perplexity, pairwise A/B comparison.

Requires: ANTHROPIC_API_KEY in .env

Reads:  search_results_raw.json
Writes: llm_judge_scores.json
"""

import asyncio
import json
import os
import random
import time

import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DIR = os.path.dirname(os.path.abspath(__file__))
client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-haiku-4-5-20251001"
CONCURRENCY = 15

WEIGHTS = {
    "relevance": 0.35,
    "source_quality": 0.25,
    "coverage": 0.20,
    "freshness": 0.10,
    "agent_usefulness": 0.10,
}

JUDGE_PROMPT = """You are an expert search quality evaluator for AI application use cases.

You will evaluate search results from two providers (A and B) for the same query. Your goal is to assess which provider's results are more useful for an AI agent that needs to answer questions or build software.

Rate each provider on these criteria (1–5 scale):

1. **Relevance** (weight: 35%) — Do the sources directly address the query?
   5 = Highly relevant, exactly on topic | 3 = Mixed | 1 = Off-topic

2. **Source Quality** (weight: 25%) — Are the sources authoritative and trustworthy?
   5 = Excellent (official docs, reputable sites) | 3 = Average | 1 = Low quality / spam

3. **Coverage** (weight: 20%) — Is the topic well covered with useful detail?
   5 = Comprehensive, multiple angles | 3 = Partial | 1 = Very thin

4. **Freshness** (weight: 10%) — For time-sensitive queries, are sources current?
   5 = Up-to-date (or evergreen) | 3 = Somewhat dated | 1 = Severely outdated

5. **AI Agent Usefulness** (weight: 10%) — How much would this help an AI agent?
   5 = Rich context, directly actionable | 3 = Some useful context | 1 = Not useful

Respond with ONLY valid JSON, no other text:
{
  "A": {"relevance": N, "source_quality": N, "coverage": N, "freshness": N, "agent_usefulness": N, "brief_note": "..."},
  "B": {"relevance": N, "source_quality": N, "coverage": N, "freshness": N, "agent_usefulness": N, "brief_note": "..."}
}"""


def weighted_score(r):
    return sum(r.get(c, 3) * w for c, w in WEIGHTS.items())


def format_results(results):
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results[:20]):
        name = r.get("name", r.get("title", ""))
        url = r.get("url", "")
        content = r.get("content", r.get("snippet", ""))[:300]
        lines.append(f"  {i+1}. [{name}]({url})\n     {content}")
    return "\n".join(lines)


async def judge_pair(sem, query, org, linkup_results, pplx_results):
    async with sem:
        providers = [("Linkup", linkup_results), ("Perplexity", pplx_results)]
        random.shuffle(providers)
        order = [p[0] for p in providers]

        user_msg = f"**Query** ({org}): {query[:400]}\n\n"
        for label, (name, results) in zip(["A", "B"], providers):
            user_msg += f"---\n**Provider {label}:**\n{format_results(results)}\n\n"

        for attempt in range(3):
            try:
                resp = await client.messages.create(
                    model=MODEL, max_tokens=600, system=JUDGE_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
                text = resp.content[0].text.strip()
                if text.startswith("```"):
                    text = text.split("```", 2)[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                if text.endswith("```"):
                    text = text[:-3].strip()
                ratings = json.loads(text)
                result = {provider: ratings[label] for label, provider in zip(["A", "B"], order)}
                return result
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    await asyncio.sleep(2)
        return None


async def main():
    with open(os.path.join(DIR, "search_results_raw.json")) as f:
        data = json.load(f)

    pairs = [(d["query"], d.get("org", ""), d["linkup"]["results"], d["pplx"]["results"])
             for d in data if not d["linkup"].get("error") and not d["pplx"].get("error")]

    n = len(pairs)
    print(f"Judging {n} query pairs...\n")

    random.seed(42)
    sem = asyncio.Semaphore(CONCURRENCY)

    tasks = [judge_pair(sem, q, o, lr, pr) for q, o, lr, pr in pairs]
    results = await asyncio.gather(*tasks)

    all_ratings = {}
    for (query, org, _, _), result in zip(pairs, results):
        if result:
            all_ratings[query] = {"org": org, "ratings": result}

    failed = sum(1 for r in results if r is None)
    print(f"\nJudged: {len(all_ratings)} | Failed: {failed}")

    # Summary
    lw = sum(1 for q in all_ratings if weighted_score(all_ratings[q]["ratings"]["Linkup"]) > weighted_score(all_ratings[q]["ratings"]["Perplexity"]))
    pw = sum(1 for q in all_ratings if weighted_score(all_ratings[q]["ratings"]["Perplexity"]) > weighted_score(all_ratings[q]["ratings"]["Linkup"]))
    d = len(all_ratings) - lw - pw
    print(f"\nLinkup wins: {lw} | Perplexity wins: {pw} | Ties: {d}")

    output = {"metadata": {"judge_model": MODEL, "total": len(all_ratings), "failed": failed}, "per_query": all_ratings}
    with open(os.path.join(DIR, "llm_judge_scores.json"), "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Saved to llm_judge_scores.json")


if __name__ == "__main__":
    asyncio.run(main())
