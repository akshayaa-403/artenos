"""Turn what went wrong in the live demo into new test questions.

Collects every question a visitor marked "not helpful", plus every request
that failed, into evals/inbox.json. Label each one by hand (write its gold
SQL, or mark it unanswerable), then move it into evals/questions.py. Add new
questions to `dev` only, so the frozen test split stays comparable.

    python -m evals.promote_failures
"""
import json
from pathlib import Path

from core import telemetry


def main():
    s = telemetry.summary()
    seen, inbox = set(), []
    for r in s["not_helpful"] + [r for r in s["recent"] if not r["ok"]]:
        q = (r.get("question") or "").strip()
        if q and q not in seen:
            seen.add(q)
            inbox.append({"question": q, "why": "marked not helpful" if r["feedback"] == 0 else f"failed: {r['error']}",
                          "trace": r["id"], "gold_sql": None, "answerable": None})
    path = Path(__file__).with_name("inbox.json")
    path.write_text(json.dumps(inbox, indent=1), encoding="utf-8")
    print(f"{len(inbox)} question(s) to label -> {path}")


if __name__ == "__main__":
    main()
