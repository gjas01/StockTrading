import unittest
from datetime import date

from src.services.adjustment import compute_adjustment, fetch_window


class AdjustmentTests(unittest.TestCase):
    def test_no_adjustment_when_prices_match(self):
        rows = [
            {"TradeDate": date(2024, 1, 2), "Close": 100.0},
            {"TradeDate": date(2024, 1, 3), "Close": 101.0},
        ]
        fetched = [
            {"TradeDate": date(2024, 1, 2), "Close": 100.00005},
            {"TradeDate": date(2024, 1, 3), "Close": 101.00004},
        ]
        result = compute_adjustment(rows, fetched)
        self.assertFalse(result.needed)

    def test_adjustment_detected_for_split(self):
        stored = [
            {"TradeDate": date(2024, 1, 2), "Close": 200.0},
            {"TradeDate": date(2024, 1, 3), "Close": 202.0},
            {"TradeDate": date(2024, 1, 4), "Close": 204.0},
        ]
        fetched = [
            {"TradeDate": date(2024, 1, 2), "Close": 100.0},
            {"TradeDate": date(2024, 1, 3), "Close": 101.0},
            {"TradeDate": date(2024, 1, 4), "Close": 102.0},
        ]
        result = compute_adjustment(stored, fetched)
        self.assertTrue(result.needed)
        self.assertAlmostEqual(result.factor, 0.5, places=4)

    def test_fetch_window_initial_and_overlap(self):
        today = date(2026, 5, 31)
        start, end = fetch_window(None, today)
        self.assertEqual(end, today)
        self.assertEqual((today - start).days, 730)

        latest = date(2026, 5, 20)
        start, end = fetch_window(latest, today)
        self.assertEqual(start, date(2026, 5, 15))
        self.assertEqual(end, today)


if __name__ == "__main__":
    unittest.main()
