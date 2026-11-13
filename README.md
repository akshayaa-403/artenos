# Ask the CRM

> **Public, synthetic data. This reproduces methods I used at a previous job (Artenos Network); it is not that company's system, data or results.** Every company, person and deal in it is invented.

Three things a sales team needs from an LLM, each one measured:

1. **Ask the CRM.** A sales question in plain English becomes SQL, runs read-only, and comes back as an answer with the query and the rows behind it. Five prompt versions are scored on a fixed question set, so each change shows what it was worth. When the data can't answer, it says so.
2. **The Monday summary, with every number checked.** The week's figures come from SQL. The model writes the sentences. A checker finds every number in the text and looks it up in the figures; anything it can't find is flagged, and the live version asks for one rewrite.
3. **Running it for real.** A Next.js front end over a FastAPI backend, deployable to Vercel, that traces every request (latency, tokens, cost, failures, thumbs up or down) and caps what a visitor can spend.

Results: [RESULTS.md](RESULTS.md) (regenerate with `python -m evals.report`).

## How the measuring works

**Question set** ([evals/questions.py](evals/questions.py), published as [evals/questions.json](evals/questions.json)). There are 155 questions. 133 have a gold SQL query, and 22 (14%) ask for things the data doesn't hold (satisfaction scores, quotas, forecasts), where the right move is to decline. A seeded, stratified split puts a third in **test**. It was fixed before any prompt ran, and prompts are only ever changed while looking at **dev**.

**Scoring** ([core/score.py](core/score.py)). Execution match: the model's query and the gold query are both run, and their results compared. Row order is ignored, numbers are compared at 2 decimals, and extra columns are allowed, missing ones are not. These rules were written before the first prompt.

**Prompt versions** ([core/ask.py](core/ask.py)), each adding one thing:

| version | adds |
|---|---|
| v1 | the schema and the question (baseline) |
| v2 | plain notes on what the columns mean |
| v3 | six worked examples (none in the eval set) |
| v4 | rules for common text-to-SQL mistakes |
| v5 | permission to say "the data can't answer that" |

Accuracy carries a 95% Wilson interval, and each step is tested against the one before with an exact McNemar test on the same questions.

**Guardrails** ([core/guard.py](core/guard.py)). One statement only, and it must be a SELECT. The database is opened read-only, an SQLite authorizer refuses anything but reads, at most 200 rows come back, and queries are stopped after 2 s. Six deal notes carry prompt-injection payloads. [evals/run_injection.py](evals/run_injection.py) measures how many get through with no defence, with the rows marked as data, and with the reply checked before it is shown.

**The checker is measured too** ([evals/checker_eval.py](evals/checker_eval.py)). Clean summaries are written from the real facts, then one error is planted in each copy. It counts false alarms on clean text and how many planted errors are caught. Its known blind spot is a real number put next to the wrong label, which passes. That case is measured and reported, not hidden.

**Deploy gate** ([evals/gate.py](evals/gate.py), [.github/workflows/ci.yml](.github/workflows/ci.yml)). CI re-scores the live prompt on the frozen test split and fails the build if accuracy drops below, or false answers rise above, the bar in `evals/gate.json`.

**From feedback to tests** ([evals/promote_failures.py](evals/promote_failures.py)). Questions visitors mark "not helpful", and failed requests, are exported for labelling and added to the dev split.

## Run it

Needs Python 3.11+ and Node 20+.

```bash
cp .env.example .env              # then put your Gemini key in .env (never committed)
pip install -r requirements.txt
python -m core.crm                # build the synthetic CRM (seeded, same every time)
python -m unittest discover tests # no model calls

python -m evals.run_ask           # prompt versions on dev and test
python -m evals.run_injection
python -m evals.run_digest
python -m evals.checker_eval      # no model calls
python -m evals.report            # -> RESULTS.md
python -m evals.gate --set        # record the current result as the deploy bar

npm install
npm run api                       # FastAPI on :8000 (terminal 1)
npm run dev                       # Next.js on :3000 (terminal 2)
```

Model answers are cached in `.cache/llm/`, so re-running an eval only pays for prompts that changed.

## Deploy (Vercel)

Import the repo in Vercel, then set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`, `DAILY_REQUEST_CAP`) under Project Settings → Environment Variables. `next.config.mjs` sends `/api/*` to the Python function in `api/index.py`, and the database is rebuilt from the seed into `/tmp` on a cold start.

Telemetry is a SQLite file. On Vercel it lives in `/tmp`, so it is per instance and resets on a cold start. Use a hosted database if the numbers need to persist.

## Layout

```
core/      crm.py (data)  guard.py  llm.py (Gemini, stdlib only)  ask.py  digest.py  checker.py  score.py  stats.py  telemetry.py
evals/     questions.py  run_ask.py  run_injection.py  run_digest.py  checker_eval.py  gate.py  report.py  results/
api/       index.py (FastAPI)
app/       Next.js pages: Ask, Weekly summary, Results, Telemetry
tests/     no-model unit tests
```

## Model and cost

The default is `gemini-3.5-flash-lite`, at $0.30 per million input tokens and $2.50 per million output tokens (Google's pricing page, read 2026-11-13). `gemini-3.8-flash` returned "high demand" errors on the day this was built. To compare models, change `GEMINI_MODEL` and the two price variables in `.env` and re-run the evals.
