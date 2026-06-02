from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Optional


RATIO_TOLERANCE = 0.001
VERIFY_TOLERANCE = 0.002


@dataclass
class AdjustmentResult:
    needed: bool
    factor: float = 1.0
    message: str = ""


from src.db import _parse_date


def _normalize_date(value) -> date:
    return _parse_date(value)


def compute_adjustment(
    stored_rows: list[dict],
    fetched_rows: list[dict],
) -> AdjustmentResult:
    stored_by_date = {_normalize_date(row["TradeDate"]): row for row in stored_rows}
    ratios: list[tuple[date, float]] = []

    for fetched in fetched_rows:
        trade_date = _normalize_date(fetched["TradeDate"])
        stored = stored_by_date.get(trade_date)
        if not stored:
            continue
        stored_close = float(stored["Close"])
        fetched_close = float(fetched["Close"])
        if stored_close == 0:
            continue
        ratios.append((trade_date, fetched_close / stored_close))

    if not ratios:
        return AdjustmentResult(needed=False, message="No overlap dates to compare.")

    values = [ratio for _, ratio in ratios]
    if all(abs(value - 1.0) <= RATIO_TOLERANCE for value in values):
        return AdjustmentResult(needed=False, message="Overlap prices match; no adjustment required.")

    reference = median(values)
    consistent = [value for value in values if abs(value - reference) / reference <= VERIFY_TOLERANCE]
    if len(consistent) < 2:
        return AdjustmentResult(
            needed=False,
            factor=reference,
            message=(
                "Overlap ratios are inconsistent; skipping adjustment. "
                f"Ratios: {[round(v, 6) for v in values]}"
            ),
        )

    verify_pairs = consistent[:2]
    if any(abs(value - reference) / reference > VERIFY_TOLERANCE for value in verify_pairs):
        return AdjustmentResult(
            needed=False,
            factor=reference,
            message="Could not verify adjustment factor using two overlap days.",
        )

    if abs(reference - 1.0) <= RATIO_TOLERANCE:
        return AdjustmentResult(
            needed=False,
            message="Overlap prices match; no adjustment required.",
        )

    return AdjustmentResult(
        needed=True,
        factor=reference,
        message=f"Applying adjustment factor {reference:.6f} using {len(consistent)} overlap day(s).",
    )


def fetch_window(latest_date: Optional[date], today: Optional[date] = None) -> tuple[date, date]:
    end = today or date.today()
    if latest_date is None:
        start = end - timedelta(days=730)
    else:
        start = latest_date - timedelta(days=5)
    return start, end
