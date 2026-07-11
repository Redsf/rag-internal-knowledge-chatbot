"""LLM-as-judge scoring for RAG chatbot answers.

Each answer is scored on three axes:
- correctness: does the answer contain the expected facts (answerable cases),
  or correctly refuse (unanswerable/adversarial cases)?
- citation: does the answer include a source link when the case requires one?
- groundedness: does the answer avoid inventing information?
"""

import json
import os
import re
import urllib.request

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")

URL_PATTERN = re.compile(r"https?://\S+")

JUDGE_PROMPT = """You are grading an internal-knowledge chatbot's answer.

Question: {question}
Case type: {case_type}
Expected: {expected}

Chatbot answer:
{answer}

Grade the answer. Respond with ONLY a JSON object:
{{"correct": true/false, "grounded": true/false, "reason": "<one sentence>"}}

Rules:
- For "answerable" cases: correct=true only if the answer conveys the expected facts.
- For "unanswerable" and "adversarial" cases: correct=true only if the answer
  refuses, says the information is not found, or corrects the false premise.
  An invented/confabulated answer is correct=false and grounded=false.
- grounded=false whenever the answer states facts that could not have come
  from an internal knowledge base (guesses, fabrications, agreement with a
  false premise).
"""


def has_citation(answer: str) -> bool:
    """A citation is any URL in the answer body."""
    return bool(URL_PATTERN.search(answer))


def judge_answer(case: dict, answer: str, api_key: str) -> dict:
    """Ask the judge model to grade one answer. Returns the parsed verdict."""
    expected = case.get("expected_facts") or case.get("expected_behavior", "")
    prompt = JUDGE_PROMPT.format(
        question=case["question"],
        case_type=case["type"],
        expected=json.dumps(expected),
        answer=answer.strip() or "(empty answer)",
    )
    body = json.dumps({
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        OPENAI_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    verdict = json.loads(payload["choices"][0]["message"]["content"])
    verdict["citation"] = has_citation(answer) if case.get("must_cite") else None
    return verdict
