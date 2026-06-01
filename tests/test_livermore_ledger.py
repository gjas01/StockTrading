import unittest
from datetime import date, timedelta

from src.services.livermore_ledger import CONTINUATION_PCT, REVERSAL_PCT, build_ledger


def _price(day: date, high: float, low: float, close: float | None = None) -> dict:
    if close is None:
        close = (high + low) / 2
    return {"TradeDate": day, "High": high, "Low": low, "Close": close}


def _bootstrap_up(start: date, basis: float = 100.0) -> list[dict]:
    """First bar sets close; second bar triggers +6% up trend on day high."""
    return [
        _price(start, basis, basis - 1, basis),
        _price(start + timedelta(days=1), basis * (1 + REVERSAL_PCT + 0.005), basis * 1.04, basis * 1.05),
    ]


def _bootstrap_down(start: date, basis: float = 100.0) -> list[dict]:
    return [
        _price(start, basis, basis - 1, basis),
        _price(start + timedelta(days=1), basis * 0.99, basis * (1 - REVERSAL_PCT - 0.005), basis * 0.95),
    ]


class LivermoreLedgerTests(unittest.TestCase):
    def test_waits_for_six_percent_from_first_close_before_trend(self):
        start = date(2024, 1, 1)
        prices = [
            _price(start, 100, 99, 100),
            _price(start + timedelta(days=1), 104, 99, 103),
        ]
        rows = build_ledger(prices)
        self.assertIsNone(rows[0].upward_trend)
        self.assertIsNone(rows[1].upward_trend)

    def test_opens_natural_reaction_when_day_low_breaks_six_percent_from_cycle_high(self):
        start = date(2024, 1, 1)
        prices = _bootstrap_up(start)
        peak = prices[-1]["High"]
        prices.extend(
            [
                _price(start + timedelta(days=2), peak + 1, peak - 0.5),
                _price(start + timedelta(days=3), peak, peak * (1 - REVERSAL_PCT)),
            ]
        )
        rows = build_ledger(prices)
        reaction_rows = [row for row in rows if row.natural_reaction is not None]
        self.assertTrue(reaction_rows)
        pivot_rows = [row for row in rows if "upward_trend" in row.pivotal]
        self.assertTrue(pivot_rows)

    def test_marks_pivot_upper_only_when_natural_reaction_opens(self):
        start = date(2024, 1, 1)
        prices = _bootstrap_up(start, 100)
        peak = 106.5
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.extend(
            [
                _price(start + timedelta(days=2), peak - 0.5, peak - 1),
                _price(start + timedelta(days=3), peak, peak * (1 - REVERSAL_PCT)),
            ]
        )
        rows = build_ledger(prices)
        ut_rows = [row for row in rows if row.upward_trend is not None]
        pivot_ut_rows = [row for row in ut_rows if "upward_trend" in row.pivotal]
        self.assertEqual(len(pivot_ut_rows), 1)
        self.assertEqual(pivot_ut_rows[0].upward_trend, peak)
        self.assertTrue(any(row.natural_reaction is not None for row in rows))

    def test_detects_secondary_rally_after_three_percent_bounce(self):
        start = date(2024, 1, 1)
        peak = 106.5
        reaction_low = peak * (1 - REVERSAL_PCT)
        bounce_high = reaction_low * (1 + CONTINUATION_PCT)
        prices = _bootstrap_up(start, 100)
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.extend(
            [
                _price(start + timedelta(days=2), peak, reaction_low),
                _price(start + timedelta(days=3), bounce_high, bounce_high - 1),
            ]
        )
        rows = build_ledger(prices)
        rally_rows = [row for row in rows if row.secondary_rally is not None]
        self.assertTrue(rally_rows)
        pivot_rows = [row for row in rows if "natural_reaction" in row.pivotal]
        self.assertTrue(pivot_rows)

    def test_detects_secondary_reaction_on_three_percent_rollover(self):
        start = date(2024, 1, 1)
        peak = 106.5
        reaction_low = peak * (1 - REVERSAL_PCT)
        secondary_high = reaction_low * (1 + CONTINUATION_PCT)
        rollover_low = secondary_high * (1 - CONTINUATION_PCT)
        prices = _bootstrap_up(start, 100)
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.extend(
            [
                _price(start + timedelta(days=2), peak, reaction_low),
                _price(start + timedelta(days=3), secondary_high, secondary_high - 1),
                _price(start + timedelta(days=4), rollover_low + 1, rollover_low),
            ]
        )
        rows = build_ledger(prices)
        self.assertTrue(any(row.secondary_reaction is not None for row in rows))

    def test_leaves_cells_blank_when_no_new_extreme(self):
        start = date(2024, 1, 1)
        peak = 106.5
        prices = _bootstrap_up(start, 100)
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.append(_price(start + timedelta(days=2), peak - 0.5, peak - 1))
        rows = build_ledger(prices)
        self.assertIsNone(rows[-1].upward_trend)

    def test_resumes_up_trend_after_three_percent_above_pivot_upper(self):
        start = date(2024, 1, 1)
        peak = 106.5
        reaction_low = peak * (1 - REVERSAL_PCT)
        secondary_high = reaction_low * (1 + CONTINUATION_PCT)
        resume_high = peak * (1 + CONTINUATION_PCT)
        prices = _bootstrap_up(start, 100)
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.extend(
            [
                _price(start + timedelta(days=2), peak, reaction_low),
                _price(start + timedelta(days=3), secondary_high, secondary_high - 1),
                _price(start + timedelta(days=4), resume_high, resume_high - 2),
            ]
        )
        rows = build_ledger(prices)
        resume_row = rows[-1]
        self.assertIsNotNone(resume_row.upward_trend)
        self.assertEqual(resume_row.upward_trend, resume_high)

    def test_flips_to_down_trend_when_three_percent_below_pivot_lower(self):
        start = date(2024, 1, 1)
        peak = 106.5
        reaction_low = peak * (1 - REVERSAL_PCT)
        secondary_high = reaction_low * (1 + CONTINUATION_PCT)
        break_low = reaction_low * (1 - CONTINUATION_PCT)
        prices = _bootstrap_up(start, 100)
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.extend(
            [
                _price(start + timedelta(days=2), peak, reaction_low),
                _price(start + timedelta(days=3), secondary_high, secondary_high - 1),
                _price(start + timedelta(days=4), secondary_high, break_low),
            ]
        )
        rows = build_ledger(prices)
        last = rows[-1]
        self.assertIsNotNone(last.downward_trend)

    def test_highlights_near_upper_pivot_in_blue(self):
        start = date(2024, 1, 1)
        peak = 106.5
        reaction_low = peak * (1 - REVERSAL_PCT)
        near_upper = peak * (1 - 0.01)
        prices = _bootstrap_up(start, 100)
        prices[1] = _price(start + timedelta(days=1), peak, 104, 105)
        prices.extend(
            [
                _price(start + timedelta(days=2), peak, reaction_low),
                _price(start + timedelta(days=3), near_upper, near_upper - 1),
            ]
        )
        rows = build_ledger(prices)
        rally_row = next(row for row in rows if row.secondary_rally is not None)
        self.assertIn("secondary_rally", rally_row.blue)

    def test_down_trend_mirror_opens_natural_rally(self):
        start = date(2024, 1, 1)
        prices = _bootstrap_down(start, 100)
        trough = prices[1]["Low"]
        prices.append(_price(start + timedelta(days=2), trough * (1 + REVERSAL_PCT), trough + 0.5))
        rows = build_ledger(prices)
        self.assertTrue(any(row.natural_rally is not None for row in rows))
        pivot_rows = [row for row in rows if "downward_trend" in row.pivotal]
        self.assertTrue(pivot_rows)


if __name__ == "__main__":
    unittest.main()
