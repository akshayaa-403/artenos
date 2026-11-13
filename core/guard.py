"""Run model-written SQL safely.

Four layers, each enough on its own for the common cases:
1. Text check: one statement, starting with SELECT or WITH.
2. The database file is opened read-only (SQLite `mode=ro`).
3. An authorizer allows only reads and functions: no writes, no ATTACH,
   no PRAGMA, even if 1 is fooled.
4. Budgets: at most ROW_LIMIT rows returned, and the query is cancelled
   after TIME_LIMIT seconds.
"""
import re
import sqlite3
import time

from core import crm

ROW_LIMIT = 200
TIME_LIMIT = 2.0

_ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", 33)}


class QueryError(Exception):
    pass


def check_sql(sql: str) -> str:
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise QueryError("empty query")
    # ponytail: rejects a ';' even inside a string literal; no real question needs one.
    if ";" in sql:
        raise QueryError("only one statement is allowed")
    if not re.match(r"(?is)^\s*(select|with)\b", sql):
        raise QueryError("only SELECT queries are allowed")
    return sql


def _authorize(action, *_):
    return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY


def run(sql: str):
    """Returns (columns, rows, truncated). Raises QueryError."""
    sql = check_sql(sql)
    path = crm.ensure()
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    deadline = time.monotonic() + TIME_LIMIT
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    con.set_authorizer(_authorize)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(ROW_LIMIT + 1)
    except sqlite3.Error as e:
        msg = "query took too long" if "interrupt" in str(e).lower() else str(e)
        raise QueryError(msg) from None
    finally:
        con.close()
    return cols, [list(r) for r in rows[:ROW_LIMIT]], len(rows) > ROW_LIMIT
