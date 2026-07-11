"""Run the eval suite against the RAG chatbot.

Two modes:
1. Live mode  — POST each question to the chatbot's webhook and grade the reply.
   python run_eval.py --webhook https://your-n8n/webhook/rag-qa
2. Offline mode — grade pre-collected answers (e.g. exported from Slack).
   python run_eval.py --answers answers.jsonl

answers.jsonl format: one {"id": "...", "answer": "..."} per line.

Requires OPENAI_API_KEY in the environment (for the judge model).
Outputs: scores.json and report.md in this directory.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from judge import judge_answer

EVAL_DIR = Path(__file__).parent


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ask_webhook(webhook_url: str, question: str) -> str:
    body = json.dumps({"question": question}).encode()
    req = urllib.request.Request(
        webhook_url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)
    # n8n Respond-to-Webhook nodes commonly wrap the text; accept both shapes.
    if isinstance(payload, dict):
        return payload.get("answer") or payload.get("output") or json.dumps(payload)
    return str(payload)


def collect_answers(cases: list[dict], args: argparse.Namespace) -> dict[str, str]:
    if args.answers:
        rows = load_jsonl(Path(args.answers))
        return {row["id"]: row["answer"] for row in rows}
    answers = {}
    for case in cases:
        print(f"  asking {case['id']} ...", file=sys.stderr)
        try:
            answers[case["id"]] = ask_webhook(args.webhook, case["question"])
        except Exception as exc:  # noqa: BLE001 - record the failure as the answer
            answers[case["id"]] = f"(request failed: {exc})"
    return answers


def summarize(results: list[dict]) -> dict:
    total = len(results)
    correct = sum(1 for r in results if r["verdict"]["correct"])
    grounded = sum(1 for r in results if r["verdict"]["grounded"])
    cited_cases = [r for r in results if r["verdict"]["citation"] is not None]
    cited = sum(1 for r in cited_cases if r["verdict"]["citation"])
    return {
        "total_cases": total,
        "correctness": round(correct / total, 3) if total else 0,
        "groundedness": round(grounded / total, 3) if total else 0,
        "citation_rate": round(cited / len(cited_cases), 3) if cited_cases else None,
    }


def write_report(results: list[dict], summary: dict) -> None:
    lines = [
        "# RAG Chatbot Eval Report",
        "",
        f"- **Cases:** {summary['total_cases']}",
        f"- **Correctness:** {summary['correctness']:.0%}",
        f"- **Groundedness:** {summary['groundedness']:.0%}",
    ]
    if summary["citation_rate"] is not None:
        lines.append(f"- **Citation rate:** {summary['citation_rate']:.0%}")
    lines += ["", "| Case | Type | Correct | Grounded | Cited | Note |", "|---|---|---|---|---|---|"]
    for r in results:
        v = r["verdict"]
        cited = "—" if v["citation"] is None else ("✅" if v["citation"] else "❌")
        lines.append(
            f"| {r['id']} | {r['type']} | {'✅' if v['correct'] else '❌'} "
            f"| {'✅' if v['grounded'] else '❌'} | {cited} | {v['reason']} |"
        )
    (EVAL_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--webhook", help="Chatbot webhook URL (live mode)")
    group.add_argument("--answers", help="Pre-collected answers JSONL (offline mode)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY is not set; the judge model needs it.")

    cases = load_jsonl(EVAL_DIR / "test_cases.jsonl")
    answers = collect_answers(cases, args)

    results = []
    for case in cases:
        answer = answers.get(case["id"])
        if answer is None:
            print(f"  skipping {case['id']}: no answer provided", file=sys.stderr)
            continue
        print(f"  judging {case['id']} ...", file=sys.stderr)
        verdict = judge_answer(case, answer, api_key)
        results.append({"id": case["id"], "type": case["type"], "answer": answer, "verdict": verdict})

    summary = summarize(results)
    (EVAL_DIR / "scores.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8"
    )
    write_report(results, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
