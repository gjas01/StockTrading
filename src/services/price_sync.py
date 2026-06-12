from __future__ import annotations

from datetime import timedelta

from src import db
from src.services.adjustment import compute_adjustment, fetch_window
from src.services.price_fetcher import FetchResult, bars_to_dicts, fetch_prices

_FULL_RELOAD_DAYS = 730


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
            provider = result.provider

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
                    log(
                        f"{label}: adjustment factor {adjustment.factor:.6f} detected — "
                        f"deleting all prices and reloading {_FULL_RELOAD_DAYS} days."
                    )
                    deleted = db.stock_price_delete_all(stock_id)
                    log(f"{label}: deleted {deleted} existing price row(s).")

                    reload_start = end - timedelta(days=_FULL_RELOAD_DAYS)
                    log(f"{label}: re-fetching {reload_start} to {end}...")
                    reload_result = fetch_prices(symbol, reload_start, end)
                    if not reload_result.bars:
                        log(f"{label}: reload returned no data; skipping merge.")
                        continue
                    fetched_dicts = bars_to_dicts(reload_result.bars)
                    provider = reload_result.provider
                    log(
                        f"{label}: reload fetched {len(reload_result.bars)} bar(s) "
                        f"via {provider}."
                    )

            merged = db.stock_price_merge(stock_id, fetched_dicts)
            log(f"{label}: merged {merged} row(s) via {provider}.")

        except Exception as exc:
            log(f"{label}: ERROR - {exc}")

    log("Price pull complete.")
