from __future__ import annotations

from datetime import timedelta

from src import db
from src.services.adjustment import compute_adjustment, fetch_window
from src.services.price_fetcher import FetchResult, bars_to_dicts, fetch_prices


def pull_missing_prices(log) -> None:
    stocks = db.stock_list_for_price_pull()
    if not stocks:
        log("No stocks configured.")
        return

    log(f"Pulling prices for {len(stocks)} stock(s)...")
    for stock in stocks:
        stock_id = int(stock["StockID"])
        symbol = stock["YahooSymbol"]
        label = f"{stock['Ticker']} ({symbol})"
        try:
            latest = db.stock_price_get_latest_date(stock_id)
            start, end = fetch_window(latest)
            log(f"{label}: fetching {start} to {end} (latest stored: {latest or 'none'})")

            result: FetchResult = fetch_prices(symbol, start, end)
            if not result.bars:
                log(f"{label}: no prices returned from {result.provider}.")
                continue

            fetched_dicts = bars_to_dicts(result.bars)
            if latest is not None:
                overlap_start = latest - timedelta(days=5)
                stored_overlap = db.stock_price_get_overlap(stock_id, overlap_start, latest)
                overlap_bars = [
                    bar for bar in result.bars if overlap_start <= bar.trade_date <= latest
                ]
                overlap_dicts = bars_to_dicts(overlap_bars)
                adjustment = compute_adjustment(stored_overlap, overlap_dicts)
                log(f"{label}: {adjustment.message}")
                if adjustment.needed:
                    adjusted_rows = db.stock_price_apply_adjustment(stock_id, adjustment.factor)
                    log(f"{label}: adjusted {adjusted_rows} historical row(s).")

            merged = db.stock_price_merge(stock_id, fetched_dicts)
            log(f"{label}: merged {merged} row(s) via {result.provider}.")
        except Exception as exc:
            log(f"{label}: ERROR - {exc}")

    log("Price pull complete.")
