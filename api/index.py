"""The API behind the live demo (FastAPI). Locally: uvicorn api.index:app --port 8000.
On Vercel this file is the Python function and Next.js rewrites /api/* to it.

Every model-backed request is traced (latency, tokens, cost, outcome) and can
be rated by the visitor. The demo spends the owner's Gemini key, so requests
are capped per visitor per hour and per day overall.
"""
import json
import sys
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from core import ask, config, crm, digest, llm, telemetry  # noqa: E402

app = FastAPI(title="Ask the CRM", docs_url="/api/docs", openapi_url="/api/openapi.json")
crm.ensure()

EXAMPLES = [
    "Which sales agent has the highest total won revenue?",
    "What was total won revenue last quarter?",
    "How many deals have been engaging for more than 90 days?",
    "What is the win rate for each product?",
    "Which accounts in the software sector have open deals?",
    "What do the most recent notes on Kestrel Systems deals say?",
    "What is the customer satisfaction score for Halcyon Labs?",
]

# ponytail: in-memory, per serverless instance; a shared store (Redis/KV) if abuse ever matters.
_hits: dict[str, deque] = defaultdict(deque)


def _limit(request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    q, now = _hits[ip], time.time()
    while q and q[0] < now - 3600:
        q.popleft()
    if len(q) >= config.PER_IP_PER_HOUR:
        raise HTTPException(429, "You've asked a lot in the last hour. Please try again later.")
    if telemetry.requests_since(86400) >= config.DAILY_REQUEST_CAP:
        raise HTTPException(429, "The demo has reached today's limit. Please come back tomorrow.")
    q.append(now)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=config.MAX_QUESTION_CHARS)
    version: str = ask.CURRENT


class DigestIn(BaseModel):
    week_end: str
    version: str = digest.CURRENT


class FeedbackIn(BaseModel):
    trace_id: str
    helpful: bool


@app.get("/api/health")
def health():
    return {"ok": True, "model": config.GEMINI_MODEL, "key_set": bool(config.GEMINI_API_KEY),
            "as_of": crm.AS_OF.isoformat()}


@app.get("/api/examples")
def examples():
    return {"examples": EXAMPLES, "versions": ask.VERSIONS, "current": ask.CURRENT}


@app.post("/api/ask")
def ask_route(body: AskIn, request: Request):
    if body.version not in ask.VERSIONS:
        raise HTTPException(400, f"version must be one of {ask.VERSIONS}")
    _limit(request)
    t0 = time.perf_counter()
    try:
        out = ask.answer(body.question.strip(), body.version)
    except llm.LLMError as e:
        tid = telemetry.log("ask", question=body.question, ok=False, error=str(e)[:200],
                            latency_ms=(time.perf_counter() - t0) * 1000, version=body.version)
        raise HTTPException(503, {"message": "The model is unavailable right now. Please try again in a minute.",
                                  "trace_id": tid})
    out["trace_id"] = telemetry.log(
        "ask", question=body.question, ok=out["error"] is None, error=out["error"],
        latency_ms=out["latency_ms"], llm_calls=out["llm_calls"], in_tokens=out["in_tokens"],
        out_tokens=out["out_tokens"], cost_usd=out["cost_usd"], abstained=out["abstained"], version=body.version)
    return out


@app.get("/api/weeks")
def weeks():
    return {"weeks": [w.isoformat() for w in digest.week_ends(12)], "versions": digest.VERSIONS,
            "current": digest.CURRENT}


@app.post("/api/digest")
def digest_route(body: DigestIn, request: Request):
    valid = {w.isoformat() for w in digest.week_ends(12)}
    if body.week_end not in valid or body.version not in digest.VERSIONS:
        raise HTTPException(400, "unknown week or version")
    _limit(request)
    t0 = time.perf_counter()
    try:
        out = digest.generate(date.fromisoformat(body.week_end), body.version)
    except llm.LLMError as e:
        tid = telemetry.log("digest", question=body.week_end, ok=False, error=str(e)[:200],
                            latency_ms=(time.perf_counter() - t0) * 1000, version=body.version)
        raise HTTPException(503, {"message": "The model is unavailable right now. Please try again in a minute.",
                                  "trace_id": tid})
    out["trace_id"] = telemetry.log(
        "digest", question=body.week_end, ok=True, latency_ms=out["latency_ms"], llm_calls=out["llm_calls"],
        in_tokens=out["in_tokens"], out_tokens=out["out_tokens"], cost_usd=out["cost_usd"], version=body.version)
    return out


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    if not telemetry.feedback(body.trace_id, body.helpful):
        raise HTTPException(404, "unknown trace")
    return {"ok": True}


@app.get("/api/telemetry")
def telemetry_route():
    return telemetry.summary()


@app.get("/api/results")
def results():
    out = {}
    for name in ("ask", "injection", "digest", "checker"):
        f = config.RESULTS_DIR / f"{name}.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if name == "ask":   # the per-question detail is large; the summary is what the page shows
                wrong = [{"id": k, "question": v["question"], "split": v["split"],
                          "kind": v["by_version"].get(ask.CURRENT, {}).get("kind"),
                          "sql": v["by_version"].get(ask.CURRENT, {}).get("sql"), "gold_sql": v["gold_sql"]}
                         for k, v in data.pop("items").items()
                         if v["split"] == "dev" and not v["by_version"].get(ask.CURRENT, {}).get("right", True)]
                data["current_dev_misses"] = wrong[:25]
            out[name] = data
    return out
