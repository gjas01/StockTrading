import unittest
from datetime import date, datetime

from src.db import _odbc_param, _odbc_params


class DbOdbcParamTests(unittest.TestCase):
    def test_converts_date_to_iso_string(self):
        self.assertEqual(_odbc_param(date(2026, 5, 29)), "2026-05-29")

    def test_converts_datetime_to_midnight_datetime(self):
        value = datetime(2026, 5, 29, 15, 30)
        self.assertEqual(_odbc_param(value), datetime(2026, 5, 29))

    def test_leaves_other_types_unchanged(self):
        self.assertEqual(_odbc_param(42), 42)
        self.assertEqual(_odbc_param("payload"), "payload")

    def test_prepares_tuple(self):
        self.assertEqual(
            _odbc_params((1, date(2026, 5, 29), 3.5)),
            (1, "2026-05-29", 3.5),
        )


if __name__ == "__main__":
    unittest.main()
