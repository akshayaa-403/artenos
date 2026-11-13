"""The deploy gate: block a change if the live prompt gets worse on the frozen test split.

    python -m evals.gate          # exit 1 if below the bar in evals/gate.json
    python -m evals.gate --set    # record the current result as the bar

Runs in CI on every push that touches core/ or evals/ (see .github/workflows/ci.yml).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core import ask, config, guard
from evals.questions import load
from evals.run_ask import grade, summarise

BAR = Path(__file__).with_name("gate.json")


def measure():
    items = [i for i in load() if i["split"] == "test"]
    for i in items:
        i["gold_rows"] = guard.run(i["sql"])[1] if i["sql"] else None
    with ThreadPoolExecutor(4) as pool:
        graded = list(pool.map(lambda it: grade(it, ask.CURRENT), items))
    return summarise(items, {it["id"]: g for it, g in zip(items, graded)})


def main():
    r = measure()
    line = (f"{ask.CURRENT} on test ({config.GEMINI_MODEL}): accuracy {r['accuracy']:.1%}, "
            f"false answers on unanswerable {r['false_answer_rate']:.0%}")
    if "--set" in sys.argv:
        BAR.write_text(json.dumps({"version": ask.CURRENT, "model": config.GEMINI_MODEL,
                                   "min_accuracy": r["accuracy"],
                                   "max_false_answer_rate": r["false_answer_rate"]}, indent=1))
        print("Bar set:", line)
        return
    if not BAR.exists():
        print("No bar yet (run with --set). Measured:", line)
        return
    bar = json.loads(BAR.read_text())
    print("Measured:", line)
    print(f"Bar:      accuracy >= {bar['min_accuracy']:.1%}, false answers <= {bar['max_false_answer_rate']:.0%}")
    if r["accuracy"] < bar["min_accuracy"] or r["false_answer_rate"] > bar["max_false_answer_rate"]:
        print("BLOCKED: the change makes the live prompt worse on the frozen test set.")
        sys.exit(1)
    print("PASSED")


if __name__ == "__main__":
    main()
