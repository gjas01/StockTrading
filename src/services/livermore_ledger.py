from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


CONTINUATION_PCT = 0.03
REVERSAL_PCT = 0.06

COLUMNS = (
    "Secondary Rally",
    "Natural Rally",
    "Upward Trend",
    "Downward Trend",
    "Natural Reaction",
    "Secondary Reaction",
)

COLUMN_KEYS = {
    "Secondary Rally": "secondary_rally",
    "Natural Rally": "natural_rally",
    "Upward Trend": "upward_trend",
    "Downward Trend": "downward_trend",
    "Natural Reaction": "natural_reaction",
    "Secondary Reaction": "secondary_reaction",
}


@dataclass
class LedgerRow:
    trade_date: date
    high: float
    low: float
    close: float
    secondary_rally: Optional[float] = None
    natural_rally: Optional[float] = None
    upward_trend: Optional[float] = None
    downward_trend: Optional[float] = None
    natural_reaction: Optional[float] = None
    secondary_reaction: Optional[float] = None
    note: str = ""
    pivotal: set[str] = field(default_factory=set)


@dataclass
class _LedgerState:
    column: str = "Upward Trend"
    upward_peak: Optional[float] = None
    last_upward: Optional[float] = None
    reaction_low: Optional[float] = None
    last_reaction: Optional[float] = None
    secondary_rally_high: Optional[float] = None
    last_secondary_rally: Optional[float] = None
    downward_trough: Optional[float] = None
    last_downward: Optional[float] = None
    rally_high: Optional[float] = None
    last_natural_rally: Optional[float] = None
    last_secondary_reaction: Optional[float] = None


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    return date.fromisoformat(str(value))


def _append_note(row: LedgerRow, message: str) -> None:
    row.note = f"{row.note} {message}".strip()


def _record(row: LedgerRow, column: str, price: float, pivotal: bool = False) -> None:
    key = COLUMN_KEYS[column]
    setattr(row, key, price)
    if pivotal:
        row.pivotal.add(key)


def _process_upward_trend(state: _LedgerState, row: LedgerRow, high: float, low: float) -> None:
    extended = False
    if state.last_upward is None or high > state.last_upward:
        _record(row, "Upward Trend", high, pivotal=True)
        state.last_upward = high
        state.upward_peak = high if state.upward_peak is None else max(state.upward_peak, high)
        extended = True

    if state.upward_peak and low <= state.upward_peak * (1 - REVERSAL_PCT):
        state.column = "Natural Reaction"
        _record(row, "Natural Reaction", low, pivotal=True)
        state.reaction_low = low
        state.last_reaction = low
        if extended:
            _append_note(
                row,
                "Same day: upward extension then Natural Reaction (day low -6% from new pivot high)",
            )
        else:
            _append_note(row, "Natural Reaction opened (day low -6% from pivot high)")


def _process_natural_reaction(state: _LedgerState, row: LedgerRow, high: float, low: float) -> None:
    prior_reaction_low = state.reaction_low

    if prior_reaction_low is not None and low < prior_reaction_low:
        _record(row, "Natural Reaction", low, pivotal=True)
        state.reaction_low = low
        state.last_reaction = low
        _append_note(row, "Danger signal: reaction low breached")
        state.column = "Downward Trend"
        state.last_downward = low
        state.downward_trough = low
        _record(row, "Downward Trend", low, pivotal=True)
        return

    extended = False
    if state.last_reaction is None or low < state.last_reaction:
        _record(row, "Natural Reaction", low, pivotal=True)
        state.reaction_low = low
        state.last_reaction = low
        extended = True

    if state.reaction_low and high >= state.reaction_low * (1 + CONTINUATION_PCT):
        state.column = "Secondary Rally"
        state.secondary_rally_high = high
        state.last_secondary_rally = high
        _record(row, "Secondary Rally", high, pivotal=True)
        if extended:
            _append_note(
                row,
                "Same day: reaction low extension then Secondary Rally (day high +3% from pivot low)",
            )


def _process_secondary_rally(state: _LedgerState, row: LedgerRow, high: float, low: float) -> None:
    if state.upward_peak and high > state.upward_peak:
        state.column = "Upward Trend"
        _record(row, "Upward Trend", high, pivotal=True)
        state.last_upward = high
        state.upward_peak = high
        state.secondary_rally_high = None
        state.last_secondary_rally = None
        if low <= high * (1 - REVERSAL_PCT):
            state.column = "Natural Reaction"
            _record(row, "Natural Reaction", low, pivotal=True)
            state.reaction_low = low
            state.last_reaction = low
            _append_note(
                row,
                "Same day: resumed Upward Trend then Natural Reaction from new pivot high",
            )
        return

    extended = False
    if state.last_secondary_rally is None or high > state.last_secondary_rally:
        _record(row, "Secondary Rally", high, pivotal=True)
        state.last_secondary_rally = high
        state.secondary_rally_high = high if state.secondary_rally_high is None else max(
            state.secondary_rally_high, high
        )
        extended = True
        if state.upward_peak and state.secondary_rally_high <= state.upward_peak * (1 - CONTINUATION_PCT):
            _append_note(row, "Secondary rally failed to reach within 3% of primary high")

    if (
        state.secondary_rally_high
        and state.upward_peak
        and state.secondary_rally_high <= state.upward_peak * (1 - CONTINUATION_PCT)
        and low <= state.secondary_rally_high * (1 - CONTINUATION_PCT)
    ):
        state.column = "Secondary Reaction"
        _record(row, "Secondary Reaction", low, pivotal=True)
        state.last_secondary_reaction = low
        if extended:
            _append_note(
                row,
                "Same day: secondary rally extension then rollover (day low -3% from new pivot high)",
            )
        else:
            _append_note(row, "Rollover: day low -3% from secondary rally pivot high (shave signal)")
        return

    if not extended and state.last_secondary_rally and high < state.last_secondary_rally:
        _record(row, "Secondary Rally", high)


def _process_secondary_reaction(state: _LedgerState, row: LedgerRow, high: float, low: float) -> None:
    extended = False
    if state.last_secondary_reaction is None or low < state.last_secondary_reaction:
        _record(row, "Secondary Reaction", low, pivotal=True)
        state.last_secondary_reaction = low
        extended = True

    if state.reaction_low and low < state.reaction_low:
        _append_note(row, "Exit: broke natural reaction low")
        state.column = "Downward Trend"
        state.last_downward = low
        state.downward_trough = low
        _record(row, "Downward Trend", low, pivotal=True)
        return

    if high >= (state.last_secondary_reaction or low) * (1 + CONTINUATION_PCT):
        state.column = "Natural Rally"
        state.rally_high = high
        state.last_natural_rally = high
        _record(row, "Natural Rally", high, pivotal=True)
        if extended:
            _append_note(
                row,
                "Same day: secondary reaction extension then Natural Rally (day high +3% from pivot low)",
            )


def _process_downward_trend(state: _LedgerState, row: LedgerRow, high: float, low: float) -> None:
    extended = False
    if state.last_downward is None or low < state.last_downward:
        _record(row, "Downward Trend", low, pivotal=True)
        state.last_downward = low
        state.downward_trough = low if state.downward_trough is None else min(state.downward_trough, low)
        extended = True

    if state.downward_trough and high >= state.downward_trough * (1 + REVERSAL_PCT):
        state.column = "Natural Rally"
        state.rally_high = high
        state.last_natural_rally = high
        _record(row, "Natural Rally", high, pivotal=True)
        if extended:
            _append_note(
                row,
                "Same day: downward extension then Natural Rally (day high +6% from new pivot low)",
            )
        else:
            _append_note(row, "Natural Rally opened (day high +6% from pivot low)")


def _process_natural_rally(state: _LedgerState, row: LedgerRow, high: float, low: float) -> None:
    extended = False
    if state.last_natural_rally is None or high > state.last_natural_rally:
        _record(row, "Natural Rally", high, pivotal=True)
        state.last_natural_rally = high
        state.rally_high = high if state.rally_high is None else max(state.rally_high, high)
        extended = True

    if state.rally_high and low <= state.rally_high * (1 - CONTINUATION_PCT):
        state.column = "Secondary Reaction"
        state.last_secondary_reaction = low
        _record(row, "Secondary Reaction", low, pivotal=True)
        if extended:
            _append_note(
                row,
                "Same day: natural rally extension then Secondary Reaction (day low -3% from new pivot high)",
            )
        else:
            _append_note(row, "Secondary reaction (day low -3% from rally pivot high)")


def build_ledger(prices: list[dict]) -> list[LedgerRow]:
    if not prices:
        return []

    ordered = sorted(prices, key=lambda row: _as_date(row["TradeDate"]))
    state = _LedgerState()
    rows: list[LedgerRow] = []

    for price_row in ordered:
        trade_date = _as_date(price_row["TradeDate"])
        high = float(price_row["High"])
        low = float(price_row["Low"])
        close = float(price_row["Close"])
        ledger_row = LedgerRow(trade_date=trade_date, high=high, low=low, close=close)

        if state.column == "Upward Trend":
            _process_upward_trend(state, ledger_row, high, low)
        elif state.column == "Natural Reaction":
            _process_natural_reaction(state, ledger_row, high, low)
        elif state.column == "Secondary Rally":
            _process_secondary_rally(state, ledger_row, high, low)
        elif state.column == "Secondary Reaction":
            _process_secondary_reaction(state, ledger_row, high, low)
        elif state.column == "Downward Trend":
            _process_downward_trend(state, ledger_row, high, low)
        elif state.column == "Natural Rally":
            _process_natural_rally(state, ledger_row, high, low)

        rows.append(ledger_row)

    return rows
