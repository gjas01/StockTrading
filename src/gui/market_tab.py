from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from src import db
from src.services.livermore_ledger import build_ledger, primary_trend


def _trend_score(trend: str | None) -> int:
    if trend == "up":
        return 1
    if trend == "down":
        return -1
    return 0


def _trend_cell(ticker: str, trend: str | None) -> str:
    arrow = {"up": " ▲", "down": " ▼"}.get(trend or "", " ?")
    score = _trend_score(trend)
    score_str = f"{score:+d}" if score != 0 else " 0"
    return f"{ticker}{arrow} ({score_str})"


def _direction_symbol(score: int) -> str:
    if score > 0:
        return "+"
    if score < 0:
        return "−"
    return "="


class MarketTab(ttk.Frame):
    """Tab that calculates the primary-trend direction for every group and
    aggregates to an overall market score."""

    def __init__(self, master):
        super().__init__(master, padding=12)

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))

        self.run_button = ttk.Button(
            toolbar, text="Run Market Overview", command=self._start_run
        )
        self.run_button.pack(side="left")

        self.status_label = ttk.Label(
            toolbar,
            text="Press 'Run Market Overview' to calculate.",
            font=("Segoe UI", 9),
        )
        self.status_label.pack(side="left", padx=(12, 0))

        # ── Treeview ─────────────────────────────────────────────────────────
        columns = ("group_name", "stock1", "stock2", "stock3", "score", "direction")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="none")

        self.tree.heading("group_name", text="Group",       anchor="w")
        self.tree.heading("stock1",     text="Stock 1",     anchor="center")
        self.tree.heading("stock2",     text="Stock 2",     anchor="center")
        self.tree.heading("stock3",     text="Stock 3",     anchor="center")
        self.tree.heading("score",      text="Score",       anchor="center")
        self.tree.heading("direction",  text="Direction",   anchor="center")

        self.tree.column("group_name", width=200, minwidth=120, anchor="w",      stretch=True)
        self.tree.column("stock1",     width=140, minwidth=100, anchor="center", stretch=True)
        self.tree.column("stock2",     width=140, minwidth=100, anchor="center", stretch=True)
        self.tree.column("stock3",     width=140, minwidth=100, anchor="center", stretch=True)
        self.tree.column("score",      width=70,  minwidth=50,  anchor="center", stretch=False)
        self.tree.column("direction",  width=80,  minwidth=60,  anchor="center", stretch=False)

        # Row colour tags
        self.tree.tag_configure("up",      background="#d6f0d6", foreground="#0b4a0b")
        self.tree.tag_configure("down",    background="#fad6d6", foreground="#7a0000")
        self.tree.tag_configure("neutral", background="#f5f5f5", foreground="#444444")
        self.tree.tag_configure(
            "total",
            background="#dde6f0",
            foreground="#00205b",
            font=("Segoe UI", 9, "bold"),
        )

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ── Run button ────────────────────────────────────────────────────────────

    def _start_run(self):
        self.run_button.configure(state="disabled")
        self.status_label.configure(text="Calculating…")
        for item in self.tree.get_children():
            self.tree.delete(item)
        threading.Thread(target=self._worker, daemon=True).start()

    # ── Background worker ──────────────────────────────────────────────────────

    def _worker(self):
        try:
            groups = db.group_list()
            result_rows: list[tuple[str, list[tuple[str, str | None]]]] = []

            for group in groups:
                group_name = group.get("GroupName", f"Group #{group['GroupID']}")
                stock_specs = [
                    (
                        group[f"Stock{n}Ticker"],
                        int(group[f"Stock{n}ID"]),
                        float(group.get(f"Exchange{n}Multiplier") or 1),
                    )
                    for n in (1, 2, 3)
                ]
                stock_trends: list[tuple[str, str | None]] = []
                for ticker, stock_id, multiplier in stock_specs:
                    prices = db.stock_price_list(stock_id)
                    rows = build_ledger(prices, multiplier=multiplier)
                    trend = primary_trend(rows)
                    stock_trends.append((ticker, trend))

                result_rows.append((group_name, stock_trends))

            self.after(0, lambda r=result_rows: self._populate(r))

        except Exception as exc:
            self.after(
                0,
                lambda e=exc: self.status_label.configure(text=f"Error: {e}"),
            )
        finally:
            self.after(0, lambda: self.run_button.configure(state="normal"))

    # ── Populate table ────────────────────────────────────────────────────────

    def _populate(
        self,
        result_rows: list[tuple[str, list[tuple[str, str | None]]]],
    ) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not result_rows:
            self.status_label.configure(text="No groups found.")
            return

        total_score = 0

        for group_name, stock_trends in result_rows:
            raw_sum = sum(_trend_score(trend) for _, trend in stock_trends)
            # Group rating is always +1, -1, or 0 (majority direction, not raw sum)
            group_rating = 1 if raw_sum > 0 else (-1 if raw_sum < 0 else 0)
            total_score += group_rating

            tag = "up" if group_rating > 0 else ("down" if group_rating < 0 else "neutral")
            direction = _direction_symbol(group_rating)

            cells = [
                _trend_cell(ticker, trend) for ticker, trend in stock_trends
            ]
            # Pad to exactly 3 stocks in case fewer exist
            while len(cells) < 3:
                cells.append("")

            self.tree.insert(
                "",
                "end",
                values=(
                    group_name,
                    cells[0],
                    cells[1],
                    cells[2],
                    f"{group_rating:+d}" if group_rating != 0 else "0",
                    direction,
                ),
                tags=(tag,),
            )

        # ── TOTAL row ─────────────────────────────────────────────────────────
        total_direction = _direction_symbol(total_score)
        self.tree.insert(
            "",
            "end",
            values=(
                "TOTAL",
                "",
                "",
                "",
                f"{total_score:+d}" if total_score != 0 else "0",
                total_direction,
            ),
            tags=("total",),
        )

        market_word = (
            "BULLISH" if total_score > 0 else ("BEARISH" if total_score < 0 else "NEUTRAL")
        )
        self.status_label.configure(
            text=(
                f"Overall market: {market_word}  "
                f"(score {total_score:+d} across {len(result_rows)} group(s))"
            )
        )
