"""Request traces for the live demo: latency, tokens, cost, failures, feedback.

One SQLite file. Locally it persists in .data/; on Vercel it lives in /tmp,
so it is per instance and resets on a cold start.
ponytail: per-instance store; move to a hosted database (Vercel Postgres,
Turso) when the numbers need to survive restarts.
"""
import sqlite3
import time
import uuid

from core import config

_DDL = """
CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY, ts REAL NOT NULL, route TEXT NOT NULL, question TEXT,
  ok INTEGER NOT NULL, error TEXT, latency_ms REAL, llm_calls INTEGER,
  in_tokens INTEGER, out_tokens INTEGER, cost_usd REAL,
  abstained INTEGER, feedback INTEGER, version TEXT
)"""


def _con():
    con = sqlite3.connect(config.TELEMETRY_DB)
    con.execute(_DDL)
    return con


def log(route, *, question=None, ok=True, error=None, latency_ms=0.0, llm_calls=0,
        in_tokens=0, out_tokens=0, cost_usd=0.0, abstained=None, version=None):
    tid = uuid.uuid4().hex[:12]
    with _con() as con:
        con.execute("INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tid, time.time(), route, question, int(ok), error, latency_ms, llm_calls,
                     in_tokens, out_tokens, cost_usd,
                     None if abstained is None else int(abstained), None, version))
    return tid


def feedback(trace_id, up: bool):
    with _con() as con:
        return con.execute("UPDATE traces SET feedback=? WHERE id=?", (int(up), trace_id)).rowcount == 1


def requests_since(seconds):
    with _con() as con:
        return con.execute("SELECT COUNT(*) FROM traces WHERE ts > ?",
                           (time.time() - seconds,)).fetchone()[0]


def _pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def summary():
    now = time.time()
    with _con() as con:
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute("SELECT * FROM traces ORDER BY ts DESC")]
    def window(sec):
        return [r for r in rows if r["ts"] > now - sec]
    out = {}
    for name, sec in (("24h", 86400), ("7d", 7 * 86400), ("all", float("inf"))):
        rs = window(sec)
        lat = [r["latency_ms"] for r in rs if r["ok"]]
        rated = [r for r in rs if r["feedback"] is not None]
        out[name] = {
            "requests": len(rs),
            "failure_rate": (sum(1 for r in rs if not r["ok"]) / len(rs)) if rs else None,
            "p50_ms": _pct(lat, 50), "p95_ms": _pct(lat, 95),
            "cost_per_request_usd": (sum(r["cost_usd"] or 0 for r in rs) / len(rs)) if rs else None,
            "total_cost_usd": sum(r["cost_usd"] or 0 for r in rs),
            "abstain_rate": (sum(1 for r in rs if r["abstained"]) / len(rs)) if rs else None,
            "helpful_rate": (sum(r["feedback"] for r in rated) / len(rated)) if rated else None,
            "rated": len(rated),
        }
    keep = ("id", "ts", "route", "question", "ok", "error", "latency_ms", "cost_usd", "abstained", "feedback")
    out["recent"] = [{k: r[k] for k in keep} for r in rows[:25]]
    out["not_helpful"] = [{k: r[k] for k in keep} for r in rows if r["feedback"] == 0][:50]
    return out
