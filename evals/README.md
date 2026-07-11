# Eval Harness

Automated quality checks for the RAG chatbot. Most n8n RAG builds ship with zero
evaluation — this suite makes the bot's behavior measurable before and after any
change (new documents, prompt edits, model swaps, chunking changes).

## What it measures

| Metric | Meaning |
|---|---|
| **Correctness** | Answerable questions convey the expected facts; unanswerable ones get an honest "not found" |
| **Groundedness** | The bot never invents facts or agrees with false premises |
| **Citation rate** | Answers that should carry a source link actually do |

The suite includes three case types (see [test_cases.jsonl](test_cases.jsonl)):

- `answerable` — questions the knowledge base covers; graded on facts + citation
- `unanswerable` — questions the KB cannot answer; graded on honest refusal
- `adversarial` — prompt-injection and false-premise traps; graded on resistance

Grading uses an LLM judge (`gpt-4o-mini` by default, override with `JUDGE_MODEL`)
with a deterministic citation check on top.

## Running it

No dependencies beyond Python 3.10+ and an OpenAI key for the judge.

**Live mode** — fire every question at the chatbot's webhook:

```bash
export OPENAI_API_KEY=sk-...
python run_eval.py --webhook https://your-n8n-host/webhook/rag-qa
```

**Offline mode** — grade answers you collected manually (e.g. from Slack):

```bash
python run_eval.py --answers answers.jsonl
# answers.jsonl: one {"id": "kb-001", "answer": "..."} per line
```

Outputs `scores.json` (machine-readable) and `report.md` (per-case table).

## Adapting to your knowledge base

The shipped cases are written for a typical internal-docs KB (HR policy, IT,
onboarding). Before running against your own deployment, edit
`test_cases.jsonl` so the `answerable` questions match documents you actually
indexed — expected facts the judge can verify. Keep the `unanswerable` and
`adversarial` cases as-is; they are KB-independent.

## Why this matters

A RAG bot that hallucinates one confident wrong answer to a new hire costs more
trust than fifty correct ones earn. Regression-testing groundedness and refusal
behavior on every change is the difference between a demo and a production system.
