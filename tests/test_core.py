"""The checks that need no model. Run: python -m unittest discover tests"""
import unittest

from core import ask, checker, guard, score, stats


class Guard(unittest.TestCase):
    def test_reads_work(self):
        cols, rows, _ = guard.run("SELECT COUNT(*) AS n FROM sales_pipeline")
        self.assertEqual(cols, ["n"])
        self.assertGreater(rows[0][0], 0)

    def test_writes_and_tricks_are_refused(self):
        for sql in ["DELETE FROM sales_pipeline",
                    "SELECT 1; DROP TABLE accounts",
                    "UPDATE accounts SET sector = 'x'",
                    "PRAGMA table_info(accounts)",
                    "ATTACH DATABASE 'x.db' AS x",
                    "WITH x AS (SELECT 1) DELETE FROM accounts",
                    "INSERT INTO products VALUES ('x','y',1)"]:
            with self.subTest(sql=sql), self.assertRaises(guard.QueryError):
                guard.run(sql)

    def test_row_limit(self):
        _, rows, truncated = guard.run("SELECT * FROM sales_pipeline")
        self.assertEqual(len(rows), guard.ROW_LIMIT)
        self.assertTrue(truncated)

    def test_runaway_query_is_stopped(self):
        with self.assertRaises(guard.QueryError):
            guard.run("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c")


class Score(unittest.TestCase):
    def test_order_rounding_and_extra_columns(self):
        self.assertTrue(score.same_result([["a"], ["b"]], [["b"], ["a"]]))
        self.assertTrue(score.same_result([[512.33333]], [[512.33]]))
        self.assertTrue(score.same_result([["Hana Okafor"]], [["hana okafor", 41]]))
        self.assertFalse(score.same_result([[0.53]], [[53.0]]))
        self.assertFalse(score.same_result([["a"], ["b"]], [["a"]]))


class Checker(unittest.TestCase):
    facts = [{"id": "rev", "label": "Revenue", "value": 48250, "unit": "usd"},
             {"id": "n", "label": "Deals won", "value": 12, "unit": "count"},
             {"id": "chg", "label": "Change (%)", "value": -12.3, "unit": "pct"},
             {"id": "r", "label": "Ratio", "value": 0.88, "unit": "ratio"},
             {"id": "s", "label": "Open deals engaging for more than 60 days", "value": 95, "unit": "count"}]

    def test_supported(self):
        text = "We won twelve deals worth $48.3k, down 12% on the week; 95 deals are older than 60 days, on 2026-06-28."
        self.assertEqual(checker.check(text, self.facts)["unsupported"], 0)

    def test_unsupported(self):
        for text in ["We won 14 deals.", "Revenue was $52k.", "Revenue doubled.", "We won thirteen deals."]:
            with self.subTest(text=text):
                self.assertEqual(checker.check(text, self.facts)["unsupported"], 1)


class Stats(unittest.TestCase):
    def test_mcnemar_and_wilson(self):
        b, c, p = stats.mcnemar([True] * 10 + [False] * 10, [True] * 10 + [True] * 10)
        self.assertEqual((b, c), (0, 10))
        self.assertLess(p, 0.01)
        lo, hi = stats.wilson(50, 100)
        self.assertTrue(0.40 < lo < 0.5 < hi < 0.60)


class Parse(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(ask.parse('{"sql": "SELECT 1"}')[0], "SELECT 1")
        self.assertTrue(ask.parse('{"sql": null, "abstain": true, "reason": "no data"}')[1])
        self.assertEqual(ask.parse("```sql\nSELECT 2\n```")[0], "SELECT 2")


if __name__ == "__main__":
    unittest.main()
