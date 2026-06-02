import unittest
from datetime import date, datetime

import pandas as pd

from src.services.price_fetcher import _to_date


class PriceFetcherDateTests(unittest.TestCase):
    def test_converts_pandas_timestamp_to_date(self):
        ts = pd.Timestamp("2026-05-29")
        self.assertEqual(_to_date(ts), date(2026, 5, 29))
        self.assertIsInstance(_to_date(ts), date)
        self.assertNotIsInstance(_to_date(ts), datetime)

    def test_converts_datetime_to_date(self):
        self.assertEqual(_to_date(datetime(2026, 5, 29, 15, 0)), date(2026, 5, 29))

    def test_leaves_date_unchanged(self):
        value = date(2026, 5, 29)
        self.assertIs(_to_date(value), value)


if __name__ == "__main__":
    unittest.main()
