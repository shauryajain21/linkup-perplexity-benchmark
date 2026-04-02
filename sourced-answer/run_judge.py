"""
Run LLM-as-judge on sourced answer results using Claude Opus.

Requires: ANTHROPIC_API_KEY in .env

Reads:  results.json
Writes: llm_judge_scores.csv
"""

import asyncio
import csv
import json
import os
import sys
import time

import anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DIR = os.path.dirname(os.path.abspath(__file__))
client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-opus-4-6"
CONCURRENCY = 3

JUDGE_PROMPT = """You are an expert evaluator of AI search engine responses. Given a user query and an AI-generated answer, rate the answer on the following criteria:

1. **Relevance** (1-5): Does the answer address the query directly?
   5 = Directly addresses the query | 3 = Partially relevant | 1 = Off-topic

2. **Accuracy** (1-5): Is the information factually correct and trustworthy?
   5 = Verifiably correct | 3 = Mostly correct with minor issues | 1 = Contains significant errors or hallucinations

3. **Completeness** (1-5): Does the answer cover the key aspects of the query?
   5 = Comprehensive coverage | 3 = Covers some aspects | 1 = Missing critical information

4. **Usefulness** (1-5): Would this answer be practically helpful to the user?
   5 = Immediately actionable | 3 = Somewhat helpful | 1 = Not useful

Provide an overall score (1-5) as a holistic assessment, weighted most heavily toward accuracy and relevance.

Return ONLY valid JSON:
{"relevance": N, "accuracy": N, "completeness": N, "usefulness": N, "overall": N, "brief_note": "one sentence"}"""


async def judge_single(sem, query, answer):
    if not answer or len(answer.strip()) < 20:
        return {"relevance": 0, "accuracy": 0, "completeness": 0, "usefulness": 0,
                "overall": 0, "brief_note": "empty/no answer"}
    async with sem:
        try:
            resp = await client.messages.create(
                model=MODEL, max_tokens=250, system=JUDGE_PROMPT, temperature=0,
                messages=[{"role": "user", "content": f"**Query:** {query[:500]}\n\n**Answer:** {answer[:1500]}"}],
            )
            text = resp.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            return json.loads(text)
        except Exception as e:
            return {"overall": 0, "error": str(e)}


async def main():
    with open(os.path.join(DIR, "results.json")) as f:
        results = json.load(f)

    # Only judge production queries (those without expected_answer)
    production = [(i, r) for i, r in enumerate(results)
                  if not r.get("expected_answer") and not r.get("sonar_error") and not r.get("sonar_pro_error")]

    n = len(production)
    print(f"Judging {n} production queries x 3 providers = {n*3} evaluations\n")

    sem = asyncio.Semaphore(CONCURRENCY)
    judge_results = []

    for idx, (i, r) in enumerate(production):
        query = r["query"]

        l, s, sp = await asyncio.gather(
            judge_single(sem, query, r.get("linkup_answer", "")),
            judge_single(sem, query, r.get("sonar_answer", "")),
            judge_single(sem, query, r.get("sonar_pro_answer", "")),
        )

        judge_results.append({
            "query_num": i + 1,
            "category": r.get("category", ""),
            "query_short": query[:60],
            "linkup_score": l.get("overall", 0),
            "sonar_score": s.get("overall", 0),
            "sonar_pro_score": sp.get("overall", 0),
            "winner": "Linkup" if l.get("overall", 0) > max(s.get("overall", 0), sp.get("overall", 0))
                      else ("Sonar Pro" if sp.get("overall", 0) > s.get("overall", 0) else "Sonar")
                      if max(s.get("overall", 0), sp.get("overall", 0)) > l.get("overall", 0)
                      else "Tie",
            "notes": l.get("brief_note", ""),
        })

        lo, so, spo = l.get("overall", 0), s.get("overall", 0), sp.get("overall", 0)
        print(f"[{idx+1}/{n}] L:{lo} S:{so} SP:{spo} | {query[:50]}...")

    with open(os.path.join(DIR, "llm_judge_scores.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=judge_results[0].keys())
        w.writeheader()
        w.writerows(judge_results)

    # Summary
    vn = len(judge_results)
    la = sum(r["linkup_score"] for r in judge_results) / vn
    sa = sum(r["sonar_score"] for r in judge_results) / vn
    spa = sum(r["sonar_pro_score"] for r in judge_results) / vn
    print(f"\nLinkup: {la:.2f}/5 | Sonar: {sa:.2f}/5 | Sonar Pro: {spa:.2f}/5")
    print(f"Saved {vn} scores to llm_judge_scores.csv")


if __name__ == "__main__":
    asyncio.run(main())
