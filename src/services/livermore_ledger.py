from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional


CONTINUATION_PCT = 0.03
REVERSAL_PCT = 0.06
NEAR_PIVOT_PCT = 0.015


@dataclass(frozen=True)
class _Thresholds:
    continuation: float
    reversal: float
    near_pivot: float

    @classmethod
    def from_multiplier(cls, multiplier: float = 1.0) -> _Thresholds:
        scale = multiplier if multiplier > 0 else 1.0
        return cls(
            continuation=CONTINUATION_PCT * scale,
            reversal=REVERSAL_PCT * scale,
            near_pivot=NEAR_PIVOT_PCT * scale,
        )

    def label(self, pct: float) -> str:
        return f"{pct * 100:.2f}%"

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
    open: float
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
    blue: set[str] = field(default_factory=set)
    red: set[str] = field(default_factory=set)


@dataclass
class _LedgerState:
    thresholds: _Thresholds = field(default_factory=_Thresholds.from_multiplier)
    phase: Literal[
        "waiting",
        "up_trend",
        "natural_reaction",
        "secondary_rally",
        "secondary_reaction",
        "down_trend",
        "natural_rally",
    ] = "waiting"
    trend: Literal["up", "down"] = "up"
    first_close: Optional[float] = None

    cycle_extreme: Optional[float] = None
    last_primary: Optional[float] = None
    primary_extreme_date: Optional[date] = None

    natural_extreme: Optional[float] = None
    last_natural: Optional[float] = None
    natural_extreme_date: Optional[date] = None

    secondary_rally_extreme: Optional[float] = None
    last_secondary_rally: Optional[float] = None
    sr_peak_before_reaction: Optional[float] = None

    secondary_reaction_extreme: Optional[float] = None
    last_secondary_reaction: Optional[float] = None

    pivot_upper: Optional[float] = None
    pivot_lower: Optional[float] = None


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    return date.fromisoformat(str(value))


def _append_note(row: LedgerRow, message: str) -> None:
    row.note = f"{row.note} {message}".strip()


def _write(row: LedgerRow, column: str, price: float) -> None:
    setattr(row, COLUMN_KEYS[column], price)


def _mark_pivot_on_row(rows: list[LedgerRow], trade_date: date, column: str) -> None:
    key = COLUMN_KEYS[column]
    for row in rows:
        if row.trade_date == trade_date and getattr(row, key) is not None:
            row.pivotal.add(key)
            return


def _mark_primary_pivot(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], column: str
) -> None:
    if state.primary_extreme_date == row.trade_date:
        row.pivotal.add(COLUMN_KEYS[column])
    elif state.primary_extreme_date is not None:
        _mark_pivot_on_row(rows, state.primary_extreme_date, column)


def _mark_natural_pivot(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], column: str
) -> None:
    if state.natural_extreme_date == row.trade_date:
        row.pivotal.add(COLUMN_KEYS[column])
    elif state.natural_extreme_date is not None:
        _mark_pivot_on_row(rows, state.natural_extreme_date, column)


def _reset_bull_correction(state: _LedgerState) -> None:
    state.natural_extreme = None
    state.last_natural = None
    state.natural_extreme_date = None
    state.secondary_rally_extreme = None
    state.last_secondary_rally = None
    state.sr_peak_before_reaction = None
    state.secondary_reaction_extreme = None
    state.last_secondary_reaction = None
    state.pivot_upper = None
    state.pivot_lower = None


def _reset_bear_correction(state: _LedgerState) -> None:
    _reset_bull_correction(state)


def _start_up_trend(state: _LedgerState, row: LedgerRow, high: float) -> None:
    state.phase = "up_trend"
    state.trend = "up"
    state.cycle_extreme = high
    state.last_primary = high
    state.primary_extreme_date = row.trade_date
    _write(row, "Upward Trend", high)


def _start_down_trend(state: _LedgerState, row: LedgerRow, low: float) -> None:
    state.phase = "down_trend"
    state.trend = "down"
    state.cycle_extreme = low
    state.last_primary = low
    state.primary_extreme_date = row.trade_date
    _write(row, "Downward Trend", low)


def _open_natural_reaction(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], low: float, *, same_day: bool = False
) -> None:
    if state.cycle_extreme is not None:
        _mark_primary_pivot(state, row, rows, "Upward Trend")
        state.pivot_upper = state.cycle_extreme
    state.phase = "natural_reaction"
    state.natural_extreme = low
    state.last_natural = low
    state.natural_extreme_date = row.trade_date
    _write(row, "Natural Reaction", low)
    if same_day:
        _append_note(
            row,
            "Same day: upward extension then Natural Reaction (day low -"
            f"{state.thresholds.label(state.thresholds.reversal)} from new pivot high)",
        )
    else:
        _append_note(
            row,
            f"Natural Reaction opened (-{state.thresholds.label(state.thresholds.reversal)} from cycle high)",
        )


def _open_secondary_rally(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float
) -> None:
    if state.natural_extreme_date is not None:
        _mark_natural_pivot(state, row, rows, "Natural Reaction")
        state.pivot_lower = state.natural_extreme
    state.phase = "secondary_rally"
    state.last_secondary_rally = high
    state.secondary_rally_extreme = high
    _write(row, "Secondary Rally", high)
    _maybe_blue_secondary_rally(row, state, high)
    _append_note(
        row,
        f"Secondary Rally opened (+{state.thresholds.label(state.thresholds.continuation)} from reaction low)",
    )


def _open_natural_rally(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, *, same_day: bool = False
) -> None:
    if state.cycle_extreme is not None:
        _mark_primary_pivot(state, row, rows, "Downward Trend")
        state.pivot_lower = state.cycle_extreme
    state.phase = "natural_rally"
    state.natural_extreme = high
    state.last_natural = high
    state.natural_extreme_date = row.trade_date
    _write(row, "Natural Rally", high)
    if same_day:
        _append_note(
            row,
            "Same day: downward extension then Natural Rally (day high +"
            f"{state.thresholds.label(state.thresholds.reversal)} from new pivot low)",
        )
    else:
        _append_note(
            row,
            f"Natural Rally opened (+{state.thresholds.label(state.thresholds.reversal)} from cycle low)",
        )


def _open_secondary_reaction_down(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], low: float
) -> None:
    if state.natural_extreme_date is not None:
        _mark_natural_pivot(state, row, rows, "Natural Rally")
        state.pivot_upper = state.natural_extreme
    state.phase = "secondary_reaction"
    state.last_secondary_reaction = low
    state.secondary_reaction_extreme = low
    _write(row, "Secondary Reaction", low)
    _append_note(
        row,
        f"Secondary Reaction opened (-{state.thresholds.label(state.thresholds.continuation)} from rally high)",
    )


def _maybe_blue_secondary_rally(row: LedgerRow, state: _LedgerState, high: float) -> None:
    if state.pivot_upper and high >= state.pivot_upper * (1 - state.thresholds.near_pivot):
        row.blue.add(COLUMN_KEYS["Secondary Rally"])


def _maybe_red_secondary_reaction(row: LedgerRow, state: _LedgerState, low: float) -> None:
    if state.pivot_lower and low <= state.pivot_lower * (1 + state.thresholds.near_pivot):
        row.red.add(COLUMN_KEYS["Secondary Reaction"])


def _resume_up_trend(state: _LedgerState, row: LedgerRow, high: float) -> None:
    _reset_bull_correction(state)
    state.phase = "up_trend"
    state.trend = "up"
    state.cycle_extreme = high
    state.last_primary = high
    state.primary_extreme_date = row.trade_date
    _write(row, "Upward Trend", high)
    _append_note(
        row,
        f"Upward Trend resumed (+{state.thresholds.label(state.thresholds.continuation)} above pivot upper)",
    )


def _resume_down_trend(state: _LedgerState, row: LedgerRow, low: float) -> None:
    _reset_bear_correction(state)
    state.phase = "down_trend"
    state.trend = "down"
    state.cycle_extreme = low
    state.last_primary = low
    state.primary_extreme_date = row.trade_date
    _write(row, "Downward Trend", low)
    _append_note(
        row,
        f"Downward Trend resumed (-{state.thresholds.label(state.thresholds.continuation)} below pivot upper)",
    )


def _flip_to_down_trend(state: _LedgerState, row: LedgerRow, low: float) -> None:
    _reset_bull_correction(state)
    _start_down_trend(state, row, low)
    _append_note(
        row,
        f"Downward Trend started (-{state.thresholds.label(state.thresholds.continuation)} below pivot lower)",
    )


def _flip_to_up_trend(state: _LedgerState, row: LedgerRow, high: float) -> None:
    _reset_bear_correction(state)
    _start_up_trend(state, row, high)
    _append_note(
        row,
        f"Upward Trend started (+{state.thresholds.label(state.thresholds.continuation)} above pivot lower)",
    )


def _candle_high_first(
    open_price: float,
    close: float,
    high: float,
    low: float,
    trend: Literal["up", "down"] = "up",
) -> bool:
    """Return True if the high was reached before the low during the day.

    Bearish candle (open > close): high came first, then low.
    Bullish candle (close > open): low came first, then high.
    Doji (open == close): position of close in day's range decides —
      strictly below the midpoint → high first (bearish bias);
      strictly above the midpoint → low first (bullish bias);
      exactly at the midpoint → follow the current trend: up trend moves
      high first (extending in-trend), down trend moves low first.
    """
    if open_price > close:
        return True
    if close > open_price:
        return False
    if high == low:
        return True
    midpoint = (high + low) / 2.0
    if close < midpoint:
        return True
    if close > midpoint:
        return False
    # Exactly at midpoint: defer to trend direction.
    return trend == "up"


def _open_secondary_rally_from_reaction(
    state: _LedgerState, row: LedgerRow, high: float
) -> None:
    """Transition from secondary_reaction back to secondary_rally."""
    state.phase = "secondary_rally"
    prior_peak = state.sr_peak_before_reaction or 0.0
    if high > prior_peak:
        _write(row, "Secondary Rally", high)
        state.last_secondary_rally = high
        state.secondary_rally_extreme = high
        _maybe_blue_secondary_rally(row, state, high)
        _append_note(
            row,
            f"Secondary Rally resumed (+{state.thresholds.label(state.thresholds.continuation)} from secondary reaction low)",
        )
    else:
        state.last_secondary_rally = high
        state.secondary_rally_extreme = high
        _write(row, "Secondary Rally", high)
        _maybe_blue_secondary_rally(row, state, high)
        _append_note(row, "Secondary Rally resumed (below prior peak)")


def _process_waiting(
    state: _LedgerState, row: LedgerRow, high: float, low: float, high_first: bool
) -> None:
    if state.first_close is None:
        state.first_close = float(row.close)
        return

    basis = state.first_close
    if high_first:
        if high >= basis * (1 + state.thresholds.reversal):
            _start_up_trend(state, row, high)
            _append_note(
                row,
                f"Initial Up Trend (+{state.thresholds.label(state.thresholds.reversal)} above first close, day high)",
            )
        elif low <= basis * (1 - state.thresholds.reversal):
            _start_down_trend(state, row, low)
            _append_note(
                row,
                f"Initial Down Trend (-{state.thresholds.label(state.thresholds.reversal)} below first close, day low)",
            )
    else:
        if low <= basis * (1 - state.thresholds.reversal):
            _start_down_trend(state, row, low)
            _append_note(
                row,
                f"Initial Down Trend (-{state.thresholds.label(state.thresholds.reversal)} below first close, day low)",
            )
        elif high >= basis * (1 + state.thresholds.reversal):
            _start_up_trend(state, row, high)
            _append_note(
                row,
                f"Initial Up Trend (+{state.thresholds.label(state.thresholds.reversal)} above first close, day high)",
            )


def _process_up_trend(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish candle: high came first — extend trend on high, then check low for reversal
        # against the (possibly updated) cycle extreme.
        extended = False
        if state.last_primary is None or high > state.last_primary:
            _write(row, "Upward Trend", high)
            state.last_primary = high
            if state.cycle_extreme is None or high >= state.cycle_extreme:
                state.cycle_extreme = high
                state.primary_extreme_date = row.trade_date
            extended = True

        if state.cycle_extreme and low <= state.cycle_extreme * (1 - state.thresholds.reversal):
            _open_natural_reaction(state, row, rows, low, same_day=extended)
    else:
        # Bullish candle: low came first — check low against the current cycle extreme for a
        # reversal before the high has a chance to extend.  If the reversal fires we stop; the
        # high extension never happened yet, so same_day=False.
        if state.cycle_extreme and low <= state.cycle_extreme * (1 - state.thresholds.reversal):
            _open_natural_reaction(state, row, rows, low, same_day=False)
            return

        if state.last_primary is None or high > state.last_primary:
            _write(row, "Upward Trend", high)
            state.last_primary = high
            if state.cycle_extreme is None or high >= state.cycle_extreme:
                state.cycle_extreme = high
                state.primary_extreme_date = row.trade_date


def _process_natural_reaction(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish candle: high came first — check for a secondary rally reversal before
        # recording any new reaction low.
        if state.natural_extreme and high >= state.natural_extreme * (1 + state.thresholds.continuation):
            _open_secondary_rally(state, row, rows, high)
            return

        if state.last_natural is None or low < state.last_natural:
            _write(row, "Natural Reaction", low)
            state.last_natural = low
            state.natural_extreme = low
            state.natural_extreme_date = row.trade_date
    else:
        # Bullish candle: low came first — extend the reaction, then check the high for a
        # secondary rally against the (possibly updated) natural extreme.
        if state.last_natural is None or low < state.last_natural:
            _write(row, "Natural Reaction", low)
            state.last_natural = low
            state.natural_extreme = low
            state.natural_extreme_date = row.trade_date

        if state.natural_extreme and high >= state.natural_extreme * (1 + state.thresholds.continuation):
            _open_secondary_rally(state, row, rows, high)


def _process_secondary_rally(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish: high-driven events first, then low-driven events.
        if state.pivot_upper and high >= state.pivot_upper * (1 + state.thresholds.continuation):
            _resume_up_trend(state, row, high)
            return

        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _flip_to_down_trend(state, row, low)
            return

        if state.secondary_rally_extreme and low <= state.secondary_rally_extreme * (
            1 - state.thresholds.continuation
        ):
            state.sr_peak_before_reaction = state.secondary_rally_extreme
            state.phase = "secondary_reaction"
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _write(row, "Secondary Reaction", low)
            _maybe_red_secondary_reaction(row, state, low)
            _append_note(
                row,
                f"Secondary Reaction (-{state.thresholds.label(state.thresholds.continuation)} below secondary rally high)",
            )
            return

        if state.last_secondary_rally is None or high > state.last_secondary_rally:
            _write(row, "Secondary Rally", high)
            state.last_secondary_rally = high
            state.secondary_rally_extreme = high
            _maybe_blue_secondary_rally(row, state, high)
    else:
        # Bullish: low-driven events first, then high-driven events.
        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _flip_to_down_trend(state, row, low)
            return

        if state.secondary_rally_extreme and low <= state.secondary_rally_extreme * (
            1 - state.thresholds.continuation
        ):
            state.sr_peak_before_reaction = state.secondary_rally_extreme
            state.phase = "secondary_reaction"
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _write(row, "Secondary Reaction", low)
            _maybe_red_secondary_reaction(row, state, low)
            _append_note(
                row,
                f"Secondary Reaction (-{state.thresholds.label(state.thresholds.continuation)} below secondary rally high)",
            )
            return

        if state.pivot_upper and high >= state.pivot_upper * (1 + state.thresholds.continuation):
            _resume_up_trend(state, row, high)
            return

        if state.last_secondary_rally is None or high > state.last_secondary_rally:
            _write(row, "Secondary Rally", high)
            state.last_secondary_rally = high
            state.secondary_rally_extreme = high
            _maybe_blue_secondary_rally(row, state, high)


def _process_secondary_reaction(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish: check high for secondary rally first, against the current
        # last_secondary_reaction (before any new low extends it).
        threshold = (state.last_secondary_reaction or low) * (1 + state.thresholds.continuation)
        if high >= threshold:
            _open_secondary_rally_from_reaction(state, row, high)
            return

        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _flip_to_down_trend(state, row, low)
            return

        if state.last_secondary_reaction is None or low < state.last_secondary_reaction:
            _write(row, "Secondary Reaction", low)
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _maybe_red_secondary_reaction(row, state, low)
    else:
        # Bullish: low comes first — extend the reaction, then check high for secondary rally
        # against the (possibly updated) last_secondary_reaction.
        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _flip_to_down_trend(state, row, low)
            return

        if state.last_secondary_reaction is None or low < state.last_secondary_reaction:
            _write(row, "Secondary Reaction", low)
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _maybe_red_secondary_reaction(row, state, low)

        threshold = (state.last_secondary_reaction or low) * (1 + state.thresholds.continuation)
        if high >= threshold and not (
            state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation)
        ):
            _open_secondary_rally_from_reaction(state, row, high)


def _process_down_trend(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish candle: high came first — check high for a reversal (natural rally) before
        # the low has a chance to extend the trend.  If it fires we stop; no extension happened
        # yet, so same_day=False.
        if state.cycle_extreme and high >= state.cycle_extreme * (1 + state.thresholds.reversal):
            _open_natural_rally(state, row, rows, high, same_day=False)
            return

        if state.last_primary is None or low < state.last_primary:
            _write(row, "Downward Trend", low)
            state.last_primary = low
            if state.cycle_extreme is None or low <= state.cycle_extreme:
                state.cycle_extreme = low
                state.primary_extreme_date = row.trade_date
    else:
        # Bullish candle: low came first — extend trend on low, then check high for reversal
        # against the (possibly updated) cycle extreme.
        extended = False
        if state.last_primary is None or low < state.last_primary:
            _write(row, "Downward Trend", low)
            state.last_primary = low
            if state.cycle_extreme is None or low <= state.cycle_extreme:
                state.cycle_extreme = low
                state.primary_extreme_date = row.trade_date
            extended = True

        if state.cycle_extreme and high >= state.cycle_extreme * (1 + state.thresholds.reversal):
            _open_natural_rally(state, row, rows, high, same_day=extended)


def _process_natural_rally(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if not high_first:
        # Bullish candle: low came first — check for a secondary reaction reversal before
        # recording any new rally high.
        if state.natural_extreme and low <= state.natural_extreme * (1 - state.thresholds.continuation):
            _open_secondary_reaction_down(state, row, rows, low)
            return

        if state.last_natural is None or high > state.last_natural:
            _write(row, "Natural Rally", high)
            state.last_natural = high
            state.natural_extreme = high
            state.natural_extreme_date = row.trade_date
    else:
        # Bearish candle: high came first — extend the rally, then check the low for a
        # secondary reaction against the (possibly updated) natural extreme.
        if state.last_natural is None or high > state.last_natural:
            _write(row, "Natural Rally", high)
            state.last_natural = high
            state.natural_extreme = high
            state.natural_extreme_date = row.trade_date

        if state.natural_extreme and low <= state.natural_extreme * (1 - state.thresholds.continuation):
            _open_secondary_reaction_down(state, row, rows, low)


def _process_secondary_reaction_down(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish: high-driven events first, then low-driven events.
        if state.pivot_upper and high >= state.pivot_upper * (1 + state.thresholds.continuation):
            _flip_to_up_trend(state, row, high)
            return

        # Check secondary rally trigger against current last_secondary_reaction (before low extends).
        threshold = (state.last_secondary_reaction or low) * (1 + state.thresholds.continuation)
        if high >= threshold:
            state.phase = "secondary_rally"
            state.last_secondary_rally = high
            state.secondary_rally_extreme = high
            _write(row, "Secondary Rally", high)
            _maybe_blue_secondary_rally(row, state, high)
            _append_note(
                row,
                f"Secondary Rally resumed (+{state.thresholds.label(state.thresholds.continuation)} from secondary reaction low)",
            )
            return

        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _resume_down_trend(state, row, low)
            return

        if state.last_secondary_reaction is None or low < state.last_secondary_reaction:
            _write(row, "Secondary Reaction", low)
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _maybe_red_secondary_reaction(row, state, low)
    else:
        # Bullish: low comes first — extend reaction, then check high for flip or secondary rally
        # against the (possibly updated) last_secondary_reaction.
        if state.pivot_upper and high >= state.pivot_upper * (1 + state.thresholds.continuation):
            _flip_to_up_trend(state, row, high)
            return

        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _resume_down_trend(state, row, low)
            return

        if state.last_secondary_reaction is None or low < state.last_secondary_reaction:
            _write(row, "Secondary Reaction", low)
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _maybe_red_secondary_reaction(row, state, low)

        threshold = (state.last_secondary_reaction or low) * (1 + state.thresholds.continuation)
        if high >= threshold and not (
            state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation)
        ):
            state.phase = "secondary_rally"
            state.last_secondary_rally = high
            state.secondary_rally_extreme = high
            _write(row, "Secondary Rally", high)
            _maybe_blue_secondary_rally(row, state, high)
            _append_note(
                row,
                f"Secondary Rally resumed (+{state.thresholds.label(state.thresholds.continuation)} from secondary reaction low)",
            )


def _process_secondary_rally_down(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if high_first:
        # Bearish: high-driven events first, then low-driven events.
        if state.pivot_upper and high >= state.pivot_upper * (1 + state.thresholds.continuation):
            _flip_to_up_trend(state, row, high)
            return

        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _resume_down_trend(state, row, low)
            return

        if state.secondary_rally_extreme and low <= state.secondary_rally_extreme * (
            1 - state.thresholds.continuation
        ):
            state.sr_peak_before_reaction = state.secondary_rally_extreme
            state.phase = "secondary_reaction"
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _write(row, "Secondary Reaction", low)
            _maybe_red_secondary_reaction(row, state, low)
            _append_note(
                row,
                f"Secondary Reaction (-{state.thresholds.label(state.thresholds.continuation)} below secondary rally high)",
            )
            return

        if state.last_secondary_rally is None or high > state.last_secondary_rally:
            _write(row, "Secondary Rally", high)
            state.last_secondary_rally = high
            state.secondary_rally_extreme = high
            _maybe_blue_secondary_rally(row, state, high)
    else:
        # Bullish: low-driven events first, then high-driven events.
        if state.pivot_lower and low <= state.pivot_lower * (1 - state.thresholds.continuation):
            _resume_down_trend(state, row, low)
            return

        if state.secondary_rally_extreme and low <= state.secondary_rally_extreme * (
            1 - state.thresholds.continuation
        ):
            state.sr_peak_before_reaction = state.secondary_rally_extreme
            state.phase = "secondary_reaction"
            state.last_secondary_reaction = low
            state.secondary_reaction_extreme = low
            _write(row, "Secondary Reaction", low)
            _maybe_red_secondary_reaction(row, state, low)
            _append_note(
                row,
                f"Secondary Reaction (-{state.thresholds.label(state.thresholds.continuation)} below secondary rally high)",
            )
            return

        if state.pivot_upper and high >= state.pivot_upper * (1 + state.thresholds.continuation):
            _flip_to_up_trend(state, row, high)
            return

        if state.last_secondary_rally is None or high > state.last_secondary_rally:
            _write(row, "Secondary Rally", high)
            state.last_secondary_rally = high
            state.secondary_rally_extreme = high
            _maybe_blue_secondary_rally(row, state, high)


def _process_day(
    state: _LedgerState, row: LedgerRow, rows: list[LedgerRow], high: float, low: float, high_first: bool
) -> None:
    if state.phase == "waiting":
        _process_waiting(state, row, high, low, high_first)
    elif state.phase == "up_trend":
        _process_up_trend(state, row, rows, high, low, high_first)
    elif state.phase == "natural_reaction":
        _process_natural_reaction(state, row, rows, high, low, high_first)
    elif state.phase == "secondary_rally":
        if state.trend == "up":
            _process_secondary_rally(state, row, rows, high, low, high_first)
        else:
            _process_secondary_rally_down(state, row, rows, high, low, high_first)
    elif state.phase == "secondary_reaction":
        if state.trend == "up":
            _process_secondary_reaction(state, row, rows, high, low, high_first)
        else:
            _process_secondary_reaction_down(state, row, rows, high, low, high_first)
    elif state.phase == "down_trend":
        _process_down_trend(state, row, rows, high, low, high_first)
    elif state.phase == "natural_rally":
        _process_natural_rally(state, row, rows, high, low, high_first)


def build_ledger(prices: list[dict], multiplier: float = 1.0) -> list[LedgerRow]:
    if not prices:
        return []

    ordered = sorted(prices, key=lambda row: _as_date(row["TradeDate"]))
    state = _LedgerState(thresholds=_Thresholds.from_multiplier(multiplier))
    rows: list[LedgerRow] = []

    for price_row in ordered:
        trade_date = _as_date(price_row["TradeDate"])
        high = float(price_row["High"])
        low = float(price_row["Low"])
        close = float(price_row["Close"])
        open_price = float(
            price_row["Open"]
            if price_row.get("Open") is not None
            else (high + low) / 2.0
        )
        ledger_row = LedgerRow(
            trade_date=trade_date,
            open=open_price,
            high=high,
            low=low,
            close=close,
        )
        high_first = _candle_high_first(open_price, close, high, low, state.trend)
        _process_day(state, ledger_row, rows, high, low, high_first)
        rows.append(ledger_row)

    return rows


def threshold_labels(multiplier: float = 1.0) -> tuple[str, str, str]:
    thresholds = _Thresholds.from_multiplier(multiplier)
    return (
        thresholds.label(thresholds.reversal),
        thresholds.label(thresholds.continuation),
        thresholds.label(thresholds.near_pivot),
    )


def primary_trend(rows: list[LedgerRow]) -> Literal["up", "down"] | None:
    """Return the primary trend direction based on the most recently recorded
    Upward Trend or Downward Trend entry.

    Scans the ledger rows in reverse and returns "up" or "down" as soon as an
    entry is found in either of those columns.  Returns ``None`` if no primary
    trend has been established yet (ledger still in the waiting phase).
    """
    for row in reversed(rows):
        if row.upward_trend is not None:
            return "up"
        if row.downward_trend is not None:
            return "down"
    return None
