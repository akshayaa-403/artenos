"""The eval set for Ask the CRM: 155 questions, 133 answerable and 22 (14%) that the data can't answer.

Each answerable question has a gold SQL query; its result is the expected
answer (scored by core/score.py). Unanswerable ones expect an abstention.

The split is fixed before any prompt is run: a seeded shuffle, stratified so
both splits have the same share of unanswerable questions. Prompts are only
ever tuned on `dev`; `test` is for reporting.

    python -m evals.questions   # write evals/questions.json (the published set)
"""
import json
import random
from pathlib import Path

WON = "deal_stage = 'Won'"
WR = "100.0 * SUM(deal_stage = 'Won') / SUM(deal_stage IN ('Won','Lost'))"
TODAY = "'2026-06-28'"


def _many(question, sql, values):
    return [(question.format(v=v), sql.format(v=v)) for v in values]


ANSWERABLE = [
    # --- counts and lookups -------------------------------------------------
    *_many("How many deals are currently in the {v} stage?",
           "SELECT COUNT(*) FROM sales_pipeline WHERE deal_stage = '{v}'", ["Engaging", "Prospecting"]),
    *_many("How many deals has {v} won in total?",
           f"SELECT COUNT(*) FROM sales_pipeline WHERE sales_agent = '{{v}}' AND {WON}",
           ["Aiden Marsh", "Hana Okafor", "Ola Mensah"]),
    *_many("How many deals did {v} lose?",
           "SELECT COUNT(*) FROM sales_pipeline WHERE sales_agent = '{v}' AND deal_stage = 'Lost'",
           ["Gus Templeton", "Kira Solberg"]),
    *_many("What is the total revenue from won {v} deals?",
           f"SELECT SUM(close_value) FROM sales_pipeline WHERE product = '{{v}}' AND {WON}",
           ["Starter", "Insight Pro", "Enterprise Plus"]),
    *_many("What is the average close value of won {v} deals?",
           f"SELECT AVG(close_value) FROM sales_pipeline WHERE product = '{{v}}' AND {WON}",
           ["Standard", "Advanced", "Enterprise"]),
    *_many("How many products are in the {v} series?",
           "SELECT COUNT(*) FROM products WHERE series = '{v}'", ["Core", "Analytics"]),
    *_many("What is the list price of {v}?",
           "SELECT sales_price FROM products WHERE product = '{v}'", ["Insight", "Enterprise Plus"]),
    *_many("How many accounts are in the {v} sector?",
           "SELECT COUNT(*) FROM accounts WHERE sector = '{v}'", ["software", "retail", "energy"]),
    ("Which accounts were established before 1980?",
     "SELECT account FROM accounts WHERE year_established < 1980"),
    ("How many accounts were established after 2000?",
     "SELECT COUNT(*) FROM accounts WHERE year_established > 2000"),
    ("Which account has the highest annual revenue?",
     "SELECT account FROM accounts ORDER BY revenue_musd DESC LIMIT 1"),
    ("Which account has the fewest employees?",
     "SELECT account FROM accounts ORDER BY employees ASC LIMIT 1"),
    *_many("How many sales agents report to {v}?",
           "SELECT COUNT(*) FROM sales_teams WHERE manager = '{v}'", ["Dana Whitlock", "Priya Venkatesh"]),
    *_many("Who is {v}'s manager?",
           "SELECT manager FROM sales_teams WHERE sales_agent = '{v}'", ["Eli Novak", "Jules Amari"]),
    *_many("Which regional office does {v} work in?",
           "SELECT regional_office FROM sales_teams WHERE sales_agent = '{v}'", ["Bea Lindqvist", "Nico Draper"]),
    ("How many deals have no account assigned?",
     "SELECT COUNT(*) FROM sales_pipeline WHERE account IS NULL"),
    ("What is the most expensive product?",
     "SELECT product FROM products ORDER BY sales_price DESC LIMIT 1"),
    ("What is the cheapest product in the Analytics series?",
     "SELECT product FROM products WHERE series = 'Analytics' ORDER BY sales_price ASC LIMIT 1"),
    *_many("How many employees does {v} have?",
           "SELECT employees FROM accounts WHERE account = '{v}'", ["Dunmore Works", "Vantage Learning"]),
    ("Which sector has the most accounts?",
     "SELECT sector FROM accounts GROUP BY sector ORDER BY COUNT(*) DESC, sector LIMIT 1"),
    *_many("What is the average annual revenue, in millions of USD, of accounts in the {v} sector?",
           "SELECT AVG(revenue_musd) FROM accounts WHERE sector = '{v}'", ["finance", "medical"]),
    ("How many deals are there in total?", "SELECT COUNT(*) FROM sales_pipeline"),
    ("How many sales agents are there?", "SELECT COUNT(*) FROM sales_teams"),

    # --- aggregates across tables ------------------------------------------
    *_many("What is the total won revenue for {v}'s team?",
           "SELECT SUM(p.close_value) FROM sales_pipeline p JOIN sales_teams t ON t.sales_agent = p.sales_agent "
           "WHERE t.manager = '{v}' AND p.deal_stage = 'Won'",
           ["Dana Whitlock", "Marcus Oyelaran", "Priya Venkatesh"]),
    ("Which sales agent has the highest total won revenue?",
     f"SELECT sales_agent FROM sales_pipeline WHERE {WON} GROUP BY sales_agent ORDER BY SUM(close_value) DESC LIMIT 1"),
    ("Which sales agent has won the most deals?",
     f"SELECT sales_agent FROM sales_pipeline WHERE {WON} GROUP BY sales_agent ORDER BY COUNT(*) DESC LIMIT 1"),
    ("Which sales agent has won the fewest deals?",
     f"SELECT sales_agent FROM sales_pipeline WHERE {WON} GROUP BY sales_agent ORDER BY COUNT(*) ASC LIMIT 1"),
    *_many("What is {v}'s win rate?",
           f"SELECT {WR} FROM sales_pipeline WHERE sales_agent = '{{v}}'",
           ["Cole Hartigan", "Farah Quint", "Mona Fairweather"]),
    *_many("What is the win rate for {v}?",
           f"SELECT {WR} FROM sales_pipeline WHERE product = '{{v}}'", ["Starter", "Enterprise"]),
    ("Which product has the highest win rate?",
     f"SELECT product FROM sales_pipeline GROUP BY product ORDER BY {WR} DESC LIMIT 1"),
    ("Which sector has brought in the most won revenue?",
     "SELECT a.sector FROM sales_pipeline p JOIN accounts a ON a.account = p.account "
     "WHERE p.deal_stage = 'Won' GROUP BY a.sector ORDER BY SUM(p.close_value) DESC LIMIT 1"),
    *_many("What is the total won revenue from accounts in the {v} sector?",
           "SELECT SUM(p.close_value) FROM sales_pipeline p JOIN accounts a ON a.account = p.account "
           "WHERE a.sector = '{v}' AND p.deal_stage = 'Won'", ["telecom", "education"]),
    ("Which regional office has the highest total won revenue?",
     "SELECT t.regional_office FROM sales_pipeline p JOIN sales_teams t ON t.sales_agent = p.sales_agent "
     "WHERE p.deal_stage = 'Won' GROUP BY t.regional_office ORDER BY SUM(p.close_value) DESC LIMIT 1"),
    *_many("How many open deals does {v} have?",
           "SELECT COUNT(*) FROM sales_pipeline WHERE sales_agent = '{v}' AND deal_stage IN ('Prospecting','Engaging')",
           ["Dina Rosales", "Ivo Brandt"]),
    ("What is the total list value of all deals currently in the Engaging stage?",
     "SELECT SUM(pr.sales_price) FROM sales_pipeline p JOIN products pr ON pr.product = p.product "
     "WHERE p.deal_stage = 'Engaging'"),
    *_many("With how many different accounts has {v} won deals?",
           f"SELECT COUNT(DISTINCT account) FROM sales_pipeline WHERE sales_agent = '{{v}}' AND {WON}",
           ["Leo Castellan", "Aiden Marsh"]),
    ("Which account has the most won deals?",
     f"SELECT account FROM sales_pipeline WHERE {WON} GROUP BY account ORDER BY COUNT(*) DESC, account LIMIT 1"),
    ("Which account has generated the most won revenue?",
     f"SELECT account FROM sales_pipeline WHERE {WON} GROUP BY account ORDER BY SUM(close_value) DESC LIMIT 1"),
    ("List the top 3 sales agents by won revenue.",
     f"SELECT sales_agent FROM sales_pipeline WHERE {WON} GROUP BY sales_agent ORDER BY SUM(close_value) DESC LIMIT 3"),
    ("List the top 5 accounts by won revenue.",
     f"SELECT account FROM sales_pipeline WHERE {WON} GROUP BY account ORDER BY SUM(close_value) DESC LIMIT 5"),
    ("What percentage of won revenue came from the Platform series?",
     "SELECT 100.0 * SUM(CASE WHEN pr.series = 'Platform' THEN p.close_value ELSE 0 END) / SUM(p.close_value) "
     "FROM sales_pipeline p JOIN products pr ON pr.product = p.product WHERE p.deal_stage = 'Won'"),
    ("Which manager's team has the best win rate?",
     f"SELECT t.manager FROM sales_pipeline p JOIN sales_teams t ON t.sales_agent = p.sales_agent "
     f"GROUP BY t.manager ORDER BY 100.0 * SUM(p.deal_stage = 'Won') / SUM(p.deal_stage IN ('Won','Lost')) DESC LIMIT 1"),
    ("How many won deals had a close value above 20,000 dollars?",
     f"SELECT COUNT(*) FROM sales_pipeline WHERE {WON} AND close_value > 20000"),
    ("What is the largest single won deal value?",
     f"SELECT MAX(close_value) FROM sales_pipeline WHERE {WON}"),
    ("Which sales agent closed the largest single won deal?",
     f"SELECT sales_agent FROM sales_pipeline WHERE {WON} ORDER BY close_value DESC LIMIT 1"),
    ("Which product series has the highest average won deal value?",
     "SELECT pr.series FROM sales_pipeline p JOIN products pr ON pr.product = p.product "
     "WHERE p.deal_stage = 'Won' GROUP BY pr.series ORDER BY AVG(p.close_value) DESC LIMIT 1"),
    *_many("What is the total won revenue from the {v} series?",
           "SELECT SUM(p.close_value) FROM sales_pipeline p JOIN products pr ON pr.product = p.product "
           "WHERE pr.series = '{v}' AND p.deal_stage = 'Won'", ["Core", "Platform"]),
    ("Which agent has the most open deals?",
     "SELECT sales_agent FROM sales_pipeline WHERE deal_stage IN ('Prospecting','Engaging') "
     "GROUP BY sales_agent ORDER BY COUNT(*) DESC, sales_agent LIMIT 1"),
    ("How many deals has each manager's team won? Give manager and count.",
     "SELECT t.manager, COUNT(*) FROM sales_pipeline p JOIN sales_teams t ON t.sales_agent = p.sales_agent "
     "WHERE p.deal_stage = 'Won' GROUP BY t.manager"),
    ("What is the won revenue per product? Give product and revenue.",
     f"SELECT product, SUM(close_value) FROM sales_pipeline WHERE {WON} GROUP BY product"),
    ("How many deals are in each stage? Give stage and count.",
     "SELECT deal_stage, COUNT(*) FROM sales_pipeline GROUP BY deal_stage"),
    ("What is the overall win rate across all closed deals?",
     f"SELECT {WR} FROM sales_pipeline"),

    # --- time ---------------------------------------------------------------
    *_many("How many deals were won in {v}?",
           f"SELECT COUNT(*) FROM sales_pipeline WHERE {WON} AND strftime('%Y-%m', close_date) = '{{v}}'",
           ["2025-03", "2025-11", "2026-04"]),
    *_many("What was total won revenue in {v}?",
           f"SELECT SUM(close_value) FROM sales_pipeline WHERE {WON} AND strftime('%Y', close_date) = '{{v}}'",
           ["2025", "2026"]),
    ("What was total won revenue last quarter?",
     f"SELECT SUM(close_value) FROM sales_pipeline WHERE {WON} AND close_date BETWEEN '2026-01-01' AND '2026-03-31'"),
    ("What is total won revenue so far this quarter?",
     f"SELECT SUM(close_value) FROM sales_pipeline WHERE {WON} AND close_date BETWEEN '2026-04-01' AND '2026-06-30'"),
    *_many("How many deals entered the Engaging stage in {v}?",
           "SELECT COUNT(*) FROM sales_pipeline WHERE strftime('%Y-%m', engage_date) = '{v}'",
           ["2025-06", "2026-02"]),
    ("Which month of 2025 had the highest won revenue? Give the month as YYYY-MM.",
     f"SELECT strftime('%Y-%m', close_date) FROM sales_pipeline WHERE {WON} AND close_date LIKE '2025-%' "
     f"GROUP BY 1 ORDER BY SUM(close_value) DESC LIMIT 1"),
    ("On average, how many days does a won deal take from engage date to close date?",
     f"SELECT AVG(julianday(close_date) - julianday(engage_date)) FROM sales_pipeline WHERE {WON}"),
    ("On average, how many days do won Enterprise deals take from engage date to close date?",
     f"SELECT AVG(julianday(close_date) - julianday(engage_date)) FROM sales_pipeline WHERE {WON} AND product = 'Enterprise'"),
    *_many("How many deals has {v} closed, won or lost, in 2026?",
           "SELECT COUNT(*) FROM sales_pipeline WHERE sales_agent = '{v}' AND deal_stage IN ('Won','Lost') "
           "AND close_date LIKE '2026-%'", ["Bea Lindqvist", "Farah Quint"]),
    *_many("How many deals have been in the Engaging stage for more than {v} days?",
           f"SELECT COUNT(*) FROM sales_pipeline WHERE deal_stage = 'Engaging' "
           f"AND julianday({TODAY}) - julianday(engage_date) > {{v}}", ["60", "90"]),
    ("Which agent has the most deals that have been engaging for more than 60 days?",
     f"SELECT sales_agent FROM sales_pipeline WHERE deal_stage = 'Engaging' AND julianday({TODAY}) - julianday(engage_date) > 60 "
     "GROUP BY sales_agent ORDER BY COUNT(*) DESC, sales_agent LIMIT 1"),
    *_many("What was {v}'s won revenue in 2025?",
           f"SELECT SUM(close_value) FROM sales_pipeline WHERE sales_agent = '{{v}}' AND {WON} AND close_date LIKE '2025-%'",
           ["Cole Hartigan", "Kira Solberg"]),
    ("How many deals were won between 2026-06-22 and 2026-06-28?",
     f"SELECT COUNT(*) FROM sales_pipeline WHERE {WON} AND close_date BETWEEN '2026-06-22' AND '2026-06-28'"),
    ("How much revenue was won in the last 30 days?",
     f"SELECT SUM(close_value) FROM sales_pipeline WHERE {WON} AND julianday({TODAY}) - julianday(close_date) < 30"),
    ("How many Enterprise Plus deals were won in 2026?",
     f"SELECT COUNT(*) FROM sales_pipeline WHERE {WON} AND product = 'Enterprise Plus' AND close_date LIKE '2026-%'"),
    ("Which agent won the most revenue in Q1 2026?",
     f"SELECT sales_agent FROM sales_pipeline WHERE {WON} AND close_date BETWEEN '2026-01-01' AND '2026-03-31' "
     "GROUP BY sales_agent ORDER BY SUM(close_value) DESC LIMIT 1"),
    ("What was the win rate in 2025?",
     f"SELECT {WR} FROM sales_pipeline WHERE close_date LIKE '2025-%'"),
    ("How many deals were lost in May 2026?",
     "SELECT COUNT(*) FROM sales_pipeline WHERE deal_stage = 'Lost' AND close_date BETWEEN '2026-05-01' AND '2026-05-31'"),
    ("What was the date of the most recent won deal?",
     f"SELECT MAX(close_date) FROM sales_pipeline WHERE {WON}"),
    ("When did the earliest deal enter the Engaging stage?",
     "SELECT MIN(engage_date) FROM sales_pipeline"),
    ("What was the won revenue for each month of 2026? Give month (YYYY-MM) and revenue.",
     f"SELECT strftime('%Y-%m', close_date), SUM(close_value) FROM sales_pipeline WHERE {WON} "
     "AND close_date LIKE '2026-%' GROUP BY 1"),

    # --- accounts and notes -------------------------------------------------
    *_many("How many notes have been written about deals with {v}?",
           "SELECT COUNT(*) FROM deal_notes n JOIN sales_pipeline p ON p.opportunity_id = n.opportunity_id "
           "WHERE p.account = '{v}'", ["Fernway Group", "Tidewater Energy"]),
    ("When was the most recent deal note written?", "SELECT MAX(written_on) FROM deal_notes"),
    ("Which agent's deals have the most notes?",
     "SELECT p.sales_agent FROM deal_notes n JOIN sales_pipeline p ON p.opportunity_id = n.opportunity_id "
     "GROUP BY p.sales_agent ORDER BY COUNT(*) DESC, p.sales_agent LIMIT 1"),
    *_many("Which products has {v} bought from us?",
           f"SELECT DISTINCT product FROM sales_pipeline WHERE account = '{{v}}' AND {WON}",
           ["Juniper Health", "Redfern Capital"]),
    *_many("How many deals has {v} lost with us?",
           "SELECT COUNT(*) FROM sales_pipeline WHERE account = '{v}' AND deal_stage = 'Lost'",
           ["Cobalt Networks", "Silverton Works"]),
    *_many("How much revenue have we won from {v}?",
           f"SELECT SUM(close_value) FROM sales_pipeline WHERE account = '{{v}}' AND {WON}",
           ["Brightline Systems", "Westbrook Capital"]),
    ("Which sales agent has won the most revenue from Meridian Networks?",
     f"SELECT sales_agent FROM sales_pipeline WHERE account = 'Meridian Networks' AND {WON} "
     "GROUP BY sales_agent ORDER BY SUM(close_value) DESC LIMIT 1"),
    ("How many accounts have never won a deal with us?",
     f"SELECT COUNT(*) FROM accounts a WHERE NOT EXISTS (SELECT 1 FROM sales_pipeline p WHERE p.account = a.account AND p.{WON})"),
    ("How many accounts in the North region are there?",
     "SELECT COUNT(*) FROM accounts WHERE region = 'North'"),
    ("Which region's accounts have brought in the most won revenue?",
     "SELECT a.region FROM sales_pipeline p JOIN accounts a ON a.account = p.account WHERE p.deal_stage = 'Won' "
     "GROUP BY a.region ORDER BY SUM(p.close_value) DESC LIMIT 1"),
    ("What is the total won revenue from accounts with more than 10,000 employees?",
     "SELECT SUM(p.close_value) FROM sales_pipeline p JOIN accounts a ON a.account = p.account "
     "WHERE a.employees > 10000 AND p.deal_stage = 'Won'"),
    ("How many open deals are with accounts in the finance sector?",
     "SELECT COUNT(*) FROM sales_pipeline p JOIN accounts a ON a.account = p.account "
     "WHERE a.sector = 'finance' AND p.deal_stage IN ('Prospecting','Engaging')"),
    ("Which account established before 1990 has generated the most won revenue?",
     "SELECT a.account FROM sales_pipeline p JOIN accounts a ON a.account = p.account "
     "WHERE a.year_established < 1990 AND p.deal_stage = 'Won' GROUP BY a.account ORDER BY SUM(p.close_value) DESC LIMIT 1"),
    ("What is the average annual revenue in millions of USD across all accounts?",
     "SELECT AVG(revenue_musd) FROM accounts"),
    ("Which products has Ola Mensah never won a deal for?",
     f"SELECT product FROM products WHERE product NOT IN (SELECT product FROM sales_pipeline WHERE sales_agent = 'Ola Mensah' AND {WON})"),
    ("How many different products has Halcyon Energy bought?",
     f"SELECT COUNT(DISTINCT product) FROM sales_pipeline WHERE account = 'Halcyon Energy' AND {WON}"),
    ("What is the average won deal value for the Insight product in 2026?",
     f"SELECT AVG(close_value) FROM sales_pipeline WHERE {WON} AND product = 'Insight' AND close_date LIKE '2026-%'"),
    ("What is the total discount given on won deals, list price minus close value, summed?",
     "SELECT SUM(pr.sales_price - p.close_value) FROM sales_pipeline p JOIN products pr ON pr.product = p.product "
     "WHERE p.deal_stage = 'Won'"),
    ("How many won deals closed above the product's list price?",
     "SELECT COUNT(*) FROM sales_pipeline p JOIN products pr ON pr.product = p.product "
     "WHERE p.deal_stage = 'Won' AND p.close_value > pr.sales_price"),
    ("Which agents have a win rate above 60 percent?",
     f"SELECT sales_agent FROM sales_pipeline GROUP BY sales_agent HAVING {WR} > 60"),
    ("How many agents on Dana Whitlock's team have won more than 40 deals?",
     "SELECT COUNT(*) FROM (SELECT p.sales_agent FROM sales_pipeline p JOIN sales_teams t ON t.sales_agent = p.sales_agent "
     "WHERE t.manager = 'Dana Whitlock' AND p.deal_stage = 'Won' GROUP BY p.sales_agent HAVING COUNT(*) > 40)"),
    ("Which accounts in the software sector have open deals?",
     "SELECT DISTINCT p.account FROM sales_pipeline p JOIN accounts a ON a.account = p.account "
     "WHERE a.sector = 'software' AND p.deal_stage IN ('Prospecting','Engaging')"),
    ("What is the smallest won deal value?",
     f"SELECT MIN(close_value) FROM sales_pipeline WHERE {WON}"),
]

UNANSWERABLE = [
    "What is the customer satisfaction score for Kestrel Systems?",
    "Which deals will close next month?",
    "How much commission did Aiden Marsh earn in 2025?",
    "What is the phone number of our contact at Halcyon Labs?",
    "Which country is Juniper Health headquartered in?",
    "How many sales calls did Farah Quint make last week?",
    "What is our marketing spend this quarter?",
    "Which competitor did we lose the Granite Systems deal to?",
    "What will total revenue be in Q3 2026?",
    "How many website visitors did Brightline Retail have?",
    "Which agent has the highest employee satisfaction rating?",
    "What is the gross margin on the Enterprise product?",
    "How many support tickets has Zephyr Energy opened?",
    "Who is the CEO of Meridian Networks?",
    "How long has Hana Okafor worked here?",
    "When does Oakridge Energy's contract come up for renewal?",
    "What is Leo Castellan's sales quota for 2026?",
    "How many leads came from the spring trade show?",
    "What is the average deal size in euros?",
    "Which accounts churned last year?",
    "How many hours did the team spend on the Cobalt Capital deal?",
    "What discount code did Pinecrest Health use?",
]

SEED = 20260628


def load():
    """-> list of dicts: id, question, sql (None if unanswerable), answerable, split."""
    items = [{"question": q, "sql": s, "answerable": True} for q, s in ANSWERABLE] + \
            [{"question": q, "sql": None, "answerable": False} for q in UNANSWERABLE]
    rng = random.Random(SEED)
    out = []
    for flag in (True, False):
        group = [x for x in items if x["answerable"] is flag]
        rng.shuffle(group)
        cut = round(len(group) / 3)                    # one third to test
        for i, x in enumerate(group):
            out.append({**x, "split": "test" if i < cut else "dev"})
    for i, x in enumerate(sorted(out, key=lambda x: x["question"])):
        x["id"] = f"q{i + 1:03d}"
    return sorted(out, key=lambda x: x["id"])


if __name__ == "__main__":
    data = load()
    path = Path(__file__).with_name("questions.json")
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    n = lambda f: sum(1 for x in data if f(x))
    print(f"{len(data)} questions: {n(lambda x: x['answerable'])} answerable, "
          f"{n(lambda x: not x['answerable'])} unanswerable; "
          f"dev {n(lambda x: x['split'] == 'dev')}, test {n(lambda x: x['split'] == 'test')} -> {path}")
