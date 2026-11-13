"""How good is the number checker itself? No model needed.

Clean summaries are written from the real facts in three styles (money as
$48,250 / $48.3k / $0.05M, counts as digits or words). Then one known error is
planted in a copy of each, and we count how often the checker flags the copy
with more unsupported numbers than the clean original.

Error types:
    changed   a real number nudged by 10-30%                      should be caught
    word      a count written as the wrong word ("seven")          should be caught
    ratio     "revenue doubled" / "half of..." when it didn't       should be caught
    swapped   a real number moved to the wrong label               the known blind spot

    python -m evals.checker_eval
"""
import json
import random
import re
import time

from core import checker, config, digest

WORD = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
        10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
        16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty"}


def money(v, style):
    if style == "k":
        return f"${v / 1000:.1f}k"
    if style == "m":
        return f"${v / 1e6:.2f}M"
    return f"${v:,.0f}"


def count(v, words):
    return WORD[v] if words and v in WORD else str(v)


def write(f, style):
    """A clean summary from facts dict f. style: 'a', 'b' or 'c'."""
    ms = {"a": "k", "b": "full", "c": "k"}[style]
    words = style == "b"
    s = []
    if style == "c":
        s.append(f"- Won: {count(f['won_deals'], 0)} deals, {money(f['won_revenue'], ms)}")
        s.append(f"- Lost: {count(f['lost_deals'], 0)} deals")
        if "win_rate_pct" in f:
            s.append(f"- Win rate: {f['win_rate_pct']}%")
        s.append(f"- Top agent: {f['top_agent']} ({money(f['top_agent_revenue'], ms)})")
        s.append(f"- Stalled deals (60+ days): {f['stalled_deals']}")
        s.append(f"- Quarter to date: {money(f['qtd_revenue'], 'm')}")
        return "\n".join(s)
    s.append(f"Last week we won {count(f['won_deals'], words)} deals worth {money(f['won_revenue'], ms)}"
             f", against {count(f['prev_won_deals'], words)} deals and {money(f['prev_won_revenue'], ms)} the week before.")
    if "revenue_change_pct" in f:
        d = "up" if f["revenue_change_pct"] >= 0 else "down"
        s.append(f"Revenue was {d} {abs(f['revenue_change_pct'])}% on the week.")
    s.append(f"{f['top_agent']} led with {money(f['top_agent_revenue'], ms)}, and {f['top_product']} "
             f"was the top product at {money(f['top_product_revenue'], ms)}.")
    s.append(f"The biggest deal was {money(f['largest_deal_value'], 'full')} from {f['largest_deal_account']}.")
    if "win_rate_pct" in f:
        s.append(f"We lost {count(f['lost_deals'], words)} deals, for a win rate of {f['win_rate_pct']}%.")
    s.append(f"{count(f['stalled_deals'], words).capitalize()} deals have been engaging for more than 60 days, "
             f"and the open pipeline is worth {money(f['open_pipeline_value'], 'm')}.")
    return " ".join(s)


def plant(text, f, facts, kind, rng):
    """Return text with one error of this kind, or None if it can't be planted."""
    values = {x["value"] for x in facts if isinstance(x["value"], (int, float))}
    if kind == "changed":
        ms = [m for m in checker.extract(text) if m["kind"] in ("money", "number") and m["value"] >= 3]
        if not ms:
            return None
        m = rng.choice(ms)
        for factor in rng.sample([0.7, 0.8, 0.9, 1.15, 1.25, 1.3], 6):
            nv = m["value"] * factor
            if m["kind"] == "number":
                nv = round(nv)
                new = str(nv)
            else:
                raw = m["text"]
                new = (f"${nv / 1000:.1f}k" if raw.lower().endswith("k") else
                       f"${nv / 1e6:.2f}M" if raw.lower().endswith("m") else f"${nv:,.0f}")
            fake = {"id": "x", "value": nv, "unit": "usd" if m["kind"] == "money" else "count"}
            if not any(checker.verify({**m, "value": nv}, [x]) for x in facts if x is not fake):
                return text[:m["start"]] + new + text[m["end"]:]
        return None
    if kind == "word":
        ms = [m for m in checker.extract(text) if m["kind"] == "word"]
        if not ms:
            return None
        m = rng.choice(ms)
        options = [w for n, w in WORD.items() if n not in values]
        return text[:m["start"]] + rng.choice(options) + text[m["end"]:] if options else None
    if kind == "ratio":
        ratio = f.get("revenue_ratio")
        if ratio is None or not 1.8 < ratio < 2.2:
            return text + " Revenue doubled on the week."
        return text + " Revenue was halved on the week."
    if kind == "swapped":
        counts = [x for x in facts if x["unit"] == "count" and isinstance(x["value"], int)]
        ms = [m for m in checker.extract(text) if m["kind"] == "number"]
        for m in ms:
            other = [x for x in counts if x["value"] != m["value"] and str(x["value"]) not in text]
            if other:
                return text[:m["start"]] + str(rng.choice(other)["value"]) + text[m["end"]:]
        return None


def main():
    rng = random.Random(11)
    weeks = digest.week_ends(12)
    kinds = ["changed", "word", "ratio", "swapped"]
    tally = {k: {"planted": 0, "caught": 0} for k in kinds}
    clean_flagged, clean_total, examples = 0, 0, []
    for w in weeks:
        facts = digest.facts(w)
        f = {x["id"]: x["value"] for x in facts}
        for style in "abc":
            text = write(f, style)
            base = checker.check(text, facts)["unsupported"]
            clean_total += 1
            if base:
                clean_flagged += 1
                examples.append({"type": "false_alarm", "text": text,
                                 "flagged": [m["text"] for m in checker.check(text, facts)["mentions"] if not m["ok"]]})
            for kind in kinds:
                bad = plant(text, f, facts, kind, rng)
                if bad is None:
                    continue
                caught = checker.check(bad, facts)["unsupported"] > base
                tally[kind]["planted"] += 1
                tally[kind]["caught"] += caught
                if not caught and len(examples) < 12:
                    examples.append({"type": f"missed_{kind}", "text": bad})
    for k in kinds:
        t = tally[k]
        t["recall"] = t["caught"] / t["planted"] if t["planted"] else None
    out = {"run_at": time.strftime("%Y-%m-%d %H:%M"), "clean_summaries": clean_total,
           "false_alarm_rate": clean_flagged / clean_total, "by_error": tally, "examples": examples}
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RESULTS_DIR / "checker.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"  clean summaries flagged (false alarms): {clean_flagged}/{clean_total}")
    for k, t in tally.items():
        print(f"  {k:8} caught {t['caught']}/{t['planted']}")
    print("->", path)


if __name__ == "__main__":
    main()
