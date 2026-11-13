"""Score prompt versions v1-v5 on the question set.

    python -m evals.run_ask                    # all versions, both splits
    python -m evals.run_ask --split dev --versions v4,v5
    python -m evals.run_ask --limit 5          # smoke test

Answers are cached (.cache/llm), so a re-run only pays for prompts that changed.
Writes evals/results/ask.json; `python -m evals.report` turns it into RESULTS.md.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

from core import ask, config, guard, llm, score, stats
from evals.questions import load


def grade(item, version):
    try:
        r = ask.to_sql(item["question"], version, cache=True)
    except llm.LLMError as e:
        return {"right": False, "kind": "llm_error", "detail": str(e)[:200], "sql": None}
    if not item["answerable"]:
        ok = r["abstained"]
        return {"right": ok, "kind": "ok" if ok else "answered_unanswerable", "sql": r["sql"]}
    if r["abstained"]:
        return {"right": False, "kind": "abstained", "sql": None, "detail": r["reason"]}
    try:
        _, rows, _ = guard.run(r["sql"])
    except guard.QueryError as e:
        return {"right": False, "kind": "sql_error", "sql": r["sql"], "detail": str(e)[:200]}
    ok = score.same_result(item["gold_rows"], rows)
    return {"right": ok, "kind": "ok" if ok else "wrong_result", "sql": r["sql"]}


def summarise(items, results):
    n = len(items)
    k = sum(results[i["id"]]["right"] for i in items)
    ans = [i for i in items if i["answerable"]]
    una = [i for i in items if not i["answerable"]]
    ka = sum(results[i["id"]]["right"] for i in ans)
    # The model declined: rightly on an unanswerable question, wrongly on an answerable one.
    abstained = [i for i in items if (not i["answerable"] and results[i["id"]]["right"])
                 or results[i["id"]]["kind"] == "abstained"]
    kinds = {}
    for i in items:
        kinds[results[i["id"]]["kind"]] = kinds.get(results[i["id"]]["kind"], 0) + 1
    lo, hi = stats.wilson(k, n)
    return {
        "n": n, "correct": k, "accuracy": k / n if n else None, "ci95": [lo, hi],
        "answerable_n": len(ans), "answerable_accuracy": ka / len(ans) if ans else None,
        "unanswerable_n": len(una),
        # Of the questions the data can't answer, how many got an answer anyway.
        "false_answer_rate": (sum(1 for i in una if not results[i["id"]]["right"]) / len(una)) if una else None,
        # Of the times it declined, how many were right to.
        "abstain_precision": (sum(1 for i in abstained if not i["answerable"]) / len(abstained)) if abstained else None,
        "outcomes": kinds,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "all"], default="all")
    ap.add_argument("--versions", default=",".join(ask.VERSIONS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    items = [i for i in load() if a.split == "all" or i["split"] == a.split]
    if a.limit:
        items = items[:a.limit]
    for i in items:
        i["gold_rows"] = guard.run(i["sql"])[1] if i["sql"] else None
    versions = a.versions.split(",")

    t0 = time.time()
    per_item = {i["id"]: {} for i in items}
    with ThreadPoolExecutor(a.workers) as pool:
        for v in versions:
            graded = list(pool.map(lambda it: grade(it, v), items))
            for it, g in zip(items, graded):
                per_item[it["id"]][v] = g
            right = sum(g["right"] for g in graded)
            print(f"{v}: {right}/{len(items)} right")

    out = {"model": config.GEMINI_MODEL, "run_at": time.strftime("%Y-%m-%d %H:%M"),
           "seconds": round(time.time() - t0), "versions": versions, "splits": {}, "items": {}}
    for split in ("dev", "test"):
        its = [i for i in items if i["split"] == split]
        if not its:
            continue
        s = {"by_version": {v: summarise(its, {i["id"]: per_item[i["id"]][v] for i in its}) for v in versions},
             "mcnemar": []}
        for prev, cur in zip(versions, versions[1:]):
            b, c, p = stats.mcnemar([per_item[i["id"]][prev]["right"] for i in its],
                                    [per_item[i["id"]][cur]["right"] for i in its])
            s["mcnemar"].append({"from": prev, "to": cur, "only_from_right": b, "only_to_right": c, "p": p})
        out["splits"][split] = s
    for i in items:
        out["items"][i["id"]] = {"question": i["question"], "split": i["split"],
                                 "answerable": i["answerable"], "gold_sql": i["sql"], "by_version": per_item[i["id"]]}

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RESULTS_DIR / ("ask.json" if not a.limit else "ask_smoke.json")
    path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    for split, s in out["splits"].items():
        print(f"\n{split}:")
        for v, r in s["by_version"].items():
            print(f"  {v}  {r['accuracy']:.1%}  [{r['ci95'][0]:.1%}, {r['ci95'][1]:.1%}]  "
                  f"false answers on unanswerable: {r['false_answer_rate'] if r['false_answer_rate'] is None else format(r['false_answer_rate'], '.0%')}")
        for m in s["mcnemar"]:
            print(f"  {m['from']}->{m['to']}: +{m['only_to_right']} / -{m['only_from_right']}  p={m['p']:.3f}")
    print("->", path)


if __name__ == "__main__":
    main()
