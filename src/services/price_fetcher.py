from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import os
import requests
import yfinance as yf


@dataclass
class PriceBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class FetchResult:
    bars: list[PriceBar]
    provider: str


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    return datetime.fromisoformat(str(value)[:10]).date()


def _bars_to_dicts(bars: list[PriceBar]) -> list[dict]:
    return [
        {
            "TradeDate": bar.trade_date.isoformat(),
            "Open": bar.open,
            "High": bar.high,
            "Low": bar.low,
            "Close": bar.close,
            "Volume": bar.volume,
        }
        for bar in bars
    ]


def bars_to_dicts(bars: list[PriceBar]) -> list[dict]:
    return _bars_to_dicts(bars)


def fetch_yahoo(symbol: str, start: date, end: date) -> list[PriceBar]:
    ticker = yf.Ticker(symbol)
    history = ticker.history(
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=True,
    )
    if history is None or history.empty:
        return []

    bars: list[PriceBar] = []
    for index, row in history.iterrows():
        bars.append(
            PriceBar(
                trade_date=_to_date(index),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
        )
    return bars


def fetch_alpha_vantage(symbol: str, start: date, end: date) -> list[PriceBar]:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is not configured.")

    response = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    series = payload.get("Time Series (Daily)")
    if not series:
        note = payload.get("Note") or payload.get("Information") or payload.get("Error Message")
        raise RuntimeError(note or "Alpha Vantage returned no daily series.")

    bars: list[PriceBar] = []
    for day_str, values in series.items():
        trade_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        if trade_date < start or trade_date > end:
            continue
        bars.append(
            PriceBar(
                trade_date=trade_date,
                open=float(values["1. open"]),
                high=float(values["2. high"]),
                low=float(values["3. low"]),
                close=float(values["5. adjusted close"]),
                volume=int(float(values["6. volume"])),
            )
        )
    bars.sort(key=lambda bar: bar.trade_date)
    return bars


def fetch_prices(symbol: str, start: date, end: date) -> FetchResult:
    errors: list[str] = []

    try:
        bars = fetch_yahoo(symbol, start, end)
        if bars:
            return FetchResult(bars=bars, provider="yfinance")
        errors.append("yfinance returned no data")
    except Exception as exc:
        errors.append(f"yfinance: {exc}")

    try:
        bars = fetch_alpha_vantage(symbol, start, end)
        if bars:
            return FetchResult(bars=bars, provider="Alpha Vantage")
        errors.append("Alpha Vantage returned no data")
    except Exception as exc:
        errors.append(f"Alpha Vantage: {exc}")

    raise RuntimeError("; ".join(errors))
