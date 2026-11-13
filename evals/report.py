"""Write RESULTS.md from evals/results/*.json.  python -m evals.report"""
import json

from core import config

R = config.RESULTS_DIR
pct = lambda x: "n/a" if x is None else f"{x:.1%}"
p0 = lambda x: "n/a" if x is None else f"{x:.0%}"


def load(name):
    f = R / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def main():
    out = ["# Results", "",
           "Public/synthetic data. These reproduce a method I used at a previous job; they are not that "
           "company's system, data or results.", ""]

    a = load("ask.json")
    out += ["## 1. Ask the CRM: prompt versions", ""]
    if a:
        out += [f"Model `{a['model']}`, run {a['run_at']}. Execution match against gold SQL; "
                "95% Wilson intervals; McNemar exact test between consecutive versions.", ""]
        for split in ("dev", "test"):
            s = a["splits"].get(split)
            if not s:
                continue
            first = next(iter(s["by_version"].values()))
            out += [f"**{split}** ({first['n']} questions, {first['unanswerable_n']} unanswerable)"
                    + (" (prompts were tuned on dev only)" if split == "test" else ""), "",
                    "| version | accuracy | 95% CI | answerable correct | false answers on unanswerable |",
                    "|---|---|---|---|---|"]
            for v, r in s["by_version"].items():
                out.append(f"| {v} | {pct(r['accuracy'])} | {pct(r['ci95'][0])} to {pct(r['ci95'][1])} | "
                           f"{pct(r['answerable_accuracy'])} | {p0(r['false_answer_rate'])} |")
            out += ["", "| change | gained | lost | p |", "|---|---|---|---|"]
            for m in s["mcnemar"]:
                out.append(f"| {m['from']} to {m['to']} | {m['only_to_right']} | {m['only_from_right']} | {m['p']:.3f} |")
            out.append("")
    else:
        out += ["Not run yet: `python -m evals.run_ask`.", ""]

    i = load("injection.json")
    out += ["## 1b. Prompt injection through deal notes", ""]
    if i:
        s = i["attack_success"]
        out += [f"{i['n']} attacks (6 planted notes x 2 questions), model `{i['model']}`.", "",
                "| defence | attacks that got through |", "|---|---|",
                f"| none | {p0(s['undefended'])} |", f"| rows marked as data | {p0(s['prompt_only'])} |",
                f"| + reply check | {p0(s['prompt_and_check'])} |", ""]
    else:
        out += ["Not run yet: `python -m evals.run_injection`.", ""]

    d = load("digest.json")
    out += ["## 2. Monday summary: numbers not in the data", ""]
    if d:
        out += [f"12 weeks, model `{d['model']}`. Rate = unsupported numbers / numbers stated.", "",
                "| version | unsupported / stated | rate | 95% CI | summaries with any |", "|---|---|---|---|---|"]
        for v, r in d["by_version"].items():
            out.append(f"| {v} | {r['unsupported']} / {r['numbers_stated']} | {pct(r['unsupported_rate'])} | "
                       f"{pct(r['ci95'][0])} to {pct(r['ci95'][1])} | {r['digests_with_any_unsupported']} / {r['digests']} |")
        out.append("")
    else:
        out += ["Not run yet: `python -m evals.run_digest`.", ""]

    c = load("checker.json")
    out += ["## 2b. How good is the checker?", ""]
    if c:
        out += [f"{c['clean_summaries']} clean summaries written from the real facts; one planted error per copy.", "",
                f"False alarms on clean summaries: {p0(c['false_alarm_rate'])}", "",
                "| planted error | caught |", "|---|---|"]
        for k, t in c["by_error"].items():
            out.append(f"| {k} | {t['caught']} / {t['planted']} |")
        out += ["", "`swapped` (a real number put next to the wrong label) is the known blind spot: "
                "the checker checks values, not which label they belong to.", ""]
    else:
        out += ["Not run yet: `python -m evals.checker_eval`.", ""]

    (config.ROOT / "RESULTS.md").write_text("\n".join(out), encoding="utf-8")
    print("->", config.ROOT / "RESULTS.md")


if __name__ == "__main__":
    main()
