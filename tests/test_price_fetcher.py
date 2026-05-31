import unittest
from datetime import date
from unittest.mock import patch

from src.services.price_fetcher import PriceBar, fetch_prices


class PriceFetcherTests(unittest.TestCase):
    @patch("src.services.price_fetcher.fetch_alpha_vantage")
    @patch("src.services.price_fetcher.fetch_yahoo")
    def test_uses_yahoo_when_available(self, mock_yahoo, mock_alpha):
        bars = [
            PriceBar(date(2024, 1, 2), 1, 2, 0.5, 1.5, 1000),
        ]
        mock_yahoo.return_value = bars
        result = fetch_prices("MSFT", date(2024, 1, 1), date(2024, 1, 3))
        self.assertEqual(result.provider, "yfinance")
        mock_alpha.assert_not_called()

    @patch("src.services.price_fetcher.fetch_alpha_vantage")
    @patch("src.services.price_fetcher.fetch_yahoo")
    def test_falls_back_to_alpha_vantage(self, mock_yahoo, mock_alpha):
        mock_yahoo.side_effect = RuntimeError("yahoo down")
        bars = [
            PriceBar(date(2024, 1, 2), 1, 2, 0.5, 1.5, 1000),
        ]
        mock_alpha.return_value = bars
        result = fetch_prices("MSFT", date(2024, 1, 1), date(2024, 1, 3))
        self.assertEqual(result.provider, "Alpha Vantage")


if __name__ == "__main__":
    unittest.main()
