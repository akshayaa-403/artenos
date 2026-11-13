"""Execution match: does the model's query return the same answer as the gold one?

Rules, decided before any prompt was written:
- Rows are compared as a multiset: row order never matters.
- Numbers are compared after rounding to 2 decimals, so 512.3333 and 512.33
  match; 0.53 and 53.0 do not (a win rate is a percentage, as the data notes say).
- Strings ignore case and surrounding spaces. NULL only matches NULL.
- Extra columns are allowed: if some choice of the model's columns, in some
  order, equals the gold result, it is a match ("name, revenue" answers
  "which agent?"). Missing columns are not.
"""
from collections import Counter
from itertools import islice, permutations


def _norm(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v) + 0.0, 2)
    try:
        return round(float(v), 2)          # "12.0" from a text column
    except (TypeError, ValueError):
        return str(v).strip().lower()


def _bag(rows, idx):
    return Counter(tuple(_norm(r[i]) for i in idx) for r in rows)


def same_result(gold_rows, pred_rows) -> bool:
    if not gold_rows or not pred_rows:
        return not gold_rows and not pred_rows
    k, m = len(gold_rows[0]), len(pred_rows[0])
    if m < k or len(gold_rows) != len(pred_rows):
        return False
    want = _bag(gold_rows, range(k))
    # ponytail: tries at most 5040 column orders (7 columns); plenty for these answers.
    return any(_bag(pred_rows, idx) == want for idx in islice(permutations(range(m), k), 5040))
