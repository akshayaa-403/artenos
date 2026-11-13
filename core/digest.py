"""The Monday sales summary: facts from SQL, words from the model, numbers checked.

Three versions:
    v1  "write the summary" with the week's facts
    v2  + use only the numbers given; no new arithmetic, no "doubled" unless given
    v3  v2, then the checker runs; if it flags numbers, one rewrite is asked for
"""
import json
import sqlite3
import time
from datetime import date, timedelta

from core import checker, crm, llm

VERSIONS = ["v1", "v2", "v3"]
CURRENT = "v3"


def week_ends(n=12):
    """The last n full weeks (Monday to Sunday), newest first, as Sunday dates."""
    last = crm.AS_OF - timedelta(days=(crm.AS_OF.weekday() + 1) % 7)
    return [last - timedelta(weeks=i) for i in range(n)]


def facts(end: date):
    con = sqlite3.connect(f"file:{crm.ensure().as_posix()}?mode=ro", uri=True)
    start, pend, pstart = end - timedelta(days=6), end - timedelta(days=7), end - timedelta(days=13)
    q = lambda sql, *a: con.execute(sql, a).fetchone()

    def won(a, b):
        return q("SELECT COUNT(*), COALESCE(SUM(close_value),0) FROM sales_pipeline "
                 "WHERE deal_stage='Won' AND close_date BETWEEN ? AND ?", a.isoformat(), b.isoformat())
    (wn, wv), (pwn, pwv) = won(start, end), won(pstart, pend)
    lost = q("SELECT COUNT(*) FROM sales_pipeline WHERE deal_stage='Lost' AND close_date BETWEEN ? AND ?",
             start.isoformat(), end.isoformat())[0]
    engaged = q("SELECT COUNT(*) FROM sales_pipeline WHERE engage_date BETWEEN ? AND ?",
                start.isoformat(), end.isoformat())[0]
    top_agent = q("SELECT sales_agent, SUM(close_value) v FROM sales_pipeline WHERE deal_stage='Won' "
                  "AND close_date BETWEEN ? AND ? GROUP BY 1 ORDER BY v DESC LIMIT 1",
                  start.isoformat(), end.isoformat()) or ("nobody", 0)
    top_product = q("SELECT product, SUM(close_value) v FROM sales_pipeline WHERE deal_stage='Won' "
                    "AND close_date BETWEEN ? AND ? GROUP BY 1 ORDER BY v DESC LIMIT 1",
                    start.isoformat(), end.isoformat()) or ("none", 0)
    biggest = q("SELECT close_value, account, product FROM sales_pipeline WHERE deal_stage='Won' "
                "AND close_date BETWEEN ? AND ? ORDER BY close_value DESC LIMIT 1",
                start.isoformat(), end.isoformat()) or (0, "none", "none")
    open_sql = ("FROM sales_pipeline p JOIN products pr USING(product) WHERE p.engage_date <= ? "
                "AND (p.close_date IS NULL OR p.close_date > ?)")
    stalled = q("SELECT COUNT(*) " + open_sql + " AND julianday(?) - julianday(p.engage_date) > 60",
                end.isoformat(), end.isoformat(), end.isoformat())[0]
    open_value = q("SELECT COALESCE(SUM(pr.sales_price),0) " + open_sql, end.isoformat(), end.isoformat())[0]
    qstart = date(end.year, 3 * ((end.month - 1) // 3) + 1, 1)
    qtd = q("SELECT COALESCE(SUM(close_value),0) FROM sales_pipeline WHERE deal_stage='Won' "
            "AND close_date BETWEEN ? AND ?", qstart.isoformat(), end.isoformat())[0]
    con.close()

    f = [
        ("week", "Week", f"{start.isoformat()} to {end.isoformat()}", "text"),
        ("won_deals", "Deals won this week", wn, "count"),
        ("won_revenue", "Revenue won this week (USD)", wv, "usd"),
        ("prev_won_deals", "Deals won the week before", pwn, "count"),
        ("prev_won_revenue", "Revenue won the week before (USD)", pwv, "usd"),
        ("revenue_change_pct", "Change in revenue vs the week before (%)",
         round((wv - pwv) / pwv * 100, 1) if pwv else None, "pct"),
        ("revenue_ratio", "Revenue this week divided by the week before",
         round(wv / pwv, 2) if pwv else None, "ratio"),
        ("lost_deals", "Deals lost this week", lost, "count"),
        ("win_rate_pct", "Win rate this week, won / (won + lost) (%)",
         round(wn / (wn + lost) * 100, 1) if wn + lost else None, "pct"),
        ("new_engaged", "New deals that started engaging this week", engaged, "count"),
        ("top_agent", "Top agent by revenue won this week", top_agent[0], "text"),
        ("top_agent_revenue", "Revenue won by the top agent (USD)", top_agent[1], "usd"),
        ("top_product", "Top product by revenue won this week", top_product[0], "text"),
        ("top_product_revenue", "Revenue won from the top product (USD)", top_product[1], "usd"),
        ("largest_deal_value", "Largest deal won this week (USD)", biggest[0], "usd"),
        ("largest_deal_account", "Account of the largest deal", biggest[1], "text"),
        ("largest_deal_product", "Product of the largest deal", biggest[2], "text"),
        ("stalled_deals", "Open deals engaging for more than 60 days", stalled, "count"),
        ("open_pipeline_value", "List value of all open engaging deals (USD)", open_value, "usd"),
        ("qtd_revenue", "Revenue won so far this quarter (USD)", qtd, "usd"),
    ]
    return [{"id": i, "label": l, "value": v, "unit": u} for i, l, v, u in f if v is not None]


BASE = ("You write the Monday sales summary for a B2B sales team.\n"
        "Here are last week's figures as JSON:\n{facts}\n\n"
        "Write 4 to 6 short, plain sentences for the team: how the week went, who and what led, "
        "and what needs attention.")
STRICT = ("\nUse only numbers that appear in the figures, exactly as given. You may round money "
          "(e.g. $48,250 to $48.3k or $48k). Do not calculate anything new: no new totals, averages, "
          "differences or percentages, and no words like 'doubled', 'half' or 'a third' unless the figures "
          "give that ratio. Write counts as digits.")
REPAIR = ("Your summary below contains numbers that are not in the figures: {bad}.\n"
          "Rewrite it, keeping everything else, so that every number comes from the figures exactly "
          "(rounding money is fine). Reply with the summary only.\n\nFigures:\n{facts}\n\nSummary:\n{text}")


def prompt(fs, version):
    p = BASE.format(facts=json.dumps(fs, indent=1))
    return p + STRICT if version in ("v2", "v3") else p


def generate(end: date, version=CURRENT, cache=False):
    t0 = time.perf_counter()
    fs = facts(end)
    replies = [llm.generate(prompt(fs, version), temperature=0.3, max_tokens=500, cache=cache)]
    text = replies[0].text.strip()
    result = checker.check(text, fs)
    first = {"text": text, "stated": result["stated"], "unsupported": result["unsupported"]}
    if version == "v3" and result["unsupported"]:
        bad = ", ".join(f'"{m["text"]}"' for m in result["mentions"] if not m["ok"])
        replies.append(llm.generate(REPAIR.format(bad=bad, facts=json.dumps(fs, indent=1), text=text),
                                    temperature=0, max_tokens=500, cache=cache))
        text = replies[-1].text.strip()
        result = checker.check(text, fs)
    return {"week_end": end.isoformat(), "version": version, "facts": fs, "text": text,
            "check": result, "first_draft": first if len(replies) > 1 else None,
            "latency_ms": (time.perf_counter() - t0) * 1000, "llm_calls": len(replies),
            "in_tokens": sum(r.in_tokens for r in replies), "out_tokens": sum(r.out_tokens for r in replies),
            "cost_usd": sum(r.cost_usd for r in replies)}
