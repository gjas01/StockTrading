import unittest
from datetime import date, timedelta

from src.services.livermore_ledger import REVERSAL_PCT, build_ledger


def _price(day: date, high: float, low: float, close: float | None = None) -> dict:
    if close is None:
        close = (high + low) / 2
    return {"TradeDate": day, "High": high, "Low": low, "Close": close}


class LivermoreLedgerTests(unittest.TestCase):
    def test_opens_natural_reaction_when_day_low_breaks_six_percent_from_pivot_high(self):
        start = date(2024, 1, 1)
        prices = [_price(start + timedelta(days=i), 100 + (i * 2), 99 + (i * 2)) for i in range(5)]
        prices.append(_price(start + timedelta(days=5), 102, 101))
        rows = build_ledger(prices)
        reaction_rows = [row for row in rows if row.natural_reaction is not None]
        self.assertTrue(reaction_rows)
        self.assertIn("Natural Reaction", reaction_rows[-1].note)
        self.assertIn("natural_reaction", reaction_rows[-1].pivotal)

    def test_detects_secondary_rally_after_three_percent_bounce_on_day_high(self):
        start = date(2024, 1, 1)
        prices = [
            _price(start, 100, 99),
            _price(start + timedelta(days=1), 106, 104),
            _price(start + timedelta(days=2), 100, 99),
            _price(start + timedelta(days=3), 103, 101.5),
        ]
        rows = build_ledger(prices)
        rally_rows = [row for row in rows if row.secondary_rally is not None]
        self.assertTrue(rally_rows)

    def test_detects_rollover_on_day_low_after_failed_secondary_high(self):
        start = date(2024, 1, 1)
        peak = 100.0
        reaction_low = peak * (1 - REVERSAL_PCT)
        secondary_high = reaction_low * (1 + 0.03)
        rollover_low = secondary_high * (1 - 0.03)

        prices = [
            _price(start, peak, peak - 1),
            _price(start + timedelta(days=1), reaction_low + 1, reaction_low),
            _price(start + timedelta(days=2), secondary_high, secondary_high - 1),
            _price(start + timedelta(days=3), rollover_low + 1, rollover_low),
        ]
        rows = build_ledger(prices)
        notes = [row.note for row in rows if row.note]
        self.assertTrue(any("Rollover" in note for note in notes))
        rollover_rows = [row for row in rows if row.secondary_reaction is not None]
        self.assertTrue(rollover_rows)
        self.assertIn("secondary_reaction", rollover_rows[-1].pivotal)


    def test_same_day_upward_extension_and_reversal(self):
        start = date(2024, 1, 1)
        prices = [
            _price(start, 96, 95),
            _price(start + timedelta(days=1), 98, 97),
            _price(start + timedelta(days=2), 101, 93),
        ]
        rows = build_ledger(prices)
        day = rows[-1]
        self.assertEqual(day.upward_trend, 101)
        self.assertEqual(day.natural_reaction, 93)
        self.assertIn("upward_trend", day.pivotal)
        self.assertIn("natural_reaction", day.pivotal)
        self.assertIn("Same day", day.note)

    def test_same_day_downward_extension_and_reversal(self):
        start = date(2024, 1, 1)
        prices = [
            _price(start, 100, 99),
            _price(start + timedelta(days=1), 106, 104),
            _price(start + timedelta(days=2), 100, 99),
            _price(start + timedelta(days=3), 94, 93),
            _price(start + timedelta(days=4), 90, 85),
            _price(start + timedelta(days=5), 92, 84),
        ]
        rows = build_ledger(prices)
        day = rows[-1]
        self.assertEqual(day.downward_trend, 84)
        self.assertIsNotNone(day.natural_rally)
        self.assertIn("Same day", day.note)


if __name__ == "__main__":
    unittest.main()
