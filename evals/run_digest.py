"""Unsupported numbers in the Monday summary, per prompt version.

For each of the last 12 weeks and each version, generate the summary and
count the numbers the checker can't find in that week's facts.
The rate is pooled: unsupported numbers / numbers stated, over all 12 weeks.

    python -m evals.run_digest
"""
import json
import time

from core import config, digest, stats


def main():
    weeks = digest.week_ends(12)
    out = {"model": config.GEMINI_MODEL, "run_at": time.strftime("%Y-%m-%d %H:%M"),
           "weeks": [w.isoformat() for w in weeks], "by_version": {}, "digests": []}
    for v in digest.VERSIONS:
        runs = [digest.generate(w, v, cache=True) for w in weeks]
        stated = sum(r["check"]["stated"] for r in runs)
        bad = sum(r["check"]["unsupported"] for r in runs)
        lo, hi = stats.wilson(bad, stated)
        out["by_version"][v] = {
            "digests": len(runs), "numbers_stated": stated, "unsupported": bad,
            "unsupported_rate": bad / stated if stated else None, "ci95": [lo, hi],
            "digests_with_any_unsupported": sum(1 for r in runs if r["check"]["unsupported"]),
            "repairs_triggered": sum(1 for r in runs if r["first_draft"]),
            "cost_usd": sum(r["cost_usd"] for r in runs)}
        for r in runs:
            out["digests"].append({"version": v, "week_end": r["week_end"], "text": r["text"],
                                   "stated": r["check"]["stated"], "unsupported": r["check"]["unsupported"],
                                   "flagged": [m["text"] for m in r["check"]["mentions"] if not m["ok"]],
                                   "first_draft": r["first_draft"]})
        s = out["by_version"][v]
        print(f"  {v}: {bad}/{stated} numbers unsupported ({s['unsupported_rate']:.1%}), "
              f"{s['digests_with_any_unsupported']}/12 summaries had at least one")
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RESULTS_DIR / "digest.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("->", path)


if __name__ == "__main__":
    main()
