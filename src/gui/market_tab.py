from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from src import db
from src.gui.ledger_sheet import open_ledger_sheet
from src.services.livermore_ledger import (
    TradingSignal,
    build_ledger,
    find_signals,
    primary_trend,
)


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
    """Tab that calculates primary-trend direction for every group, aggregates
    to an overall market score, and lists active potential buy/sell signals."""

    def __init__(self, master):
        super().__init__(master, padding=12)

        # group iid → full group dict (populated after each run)
        self._groups: dict[str, dict] = {}

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))

        self.run_button = ttk.Button(
            toolbar, text="Run Market Overview", command=self._start_run
        )
        self.run_button.pack(side="left")

        self.ledger_button = ttk.Button(
            toolbar,
            text="Open Ledger Sheet",
            command=self._open_ledger,
            state="disabled",
        )
        self.ledger_button.pack(side="left", padx=(6, 0))

        self.status_label = ttk.Label(
            toolbar,
            text="Press 'Run Market Overview' to calculate.",
            font=("Segoe UI", 9),
        )
        self.status_label.pack(side="left", padx=(12, 0))

        # ── Vertical paned layout ─────────────────────────────────────────────
        paned = ttk.Panedwindow(self, orient="vertical")
        paned.pack(fill="both", expand=True)

        # ── Top pane: group direction table ───────────────────────────────────
        top_frame = ttk.Frame(paned)
        paned.add(top_frame, weight=2)

        top_label = ttk.Label(top_frame, text="Market Direction by Group",
                              font=("Segoe UI", 9, "bold"))
        top_label.pack(anchor="w", pady=(0, 4))

        dir_cols = ("group_name", "stock1", "stock2", "stock3", "score", "direction")
        self.dir_tree = ttk.Treeview(
            top_frame, columns=dir_cols, show="headings", selectmode="browse"
        )
        self.dir_tree.heading("group_name", text="Group",     anchor="w")
        self.dir_tree.heading("stock1",     text="Stock 1",   anchor="center")
        self.dir_tree.heading("stock2",     text="Stock 2",   anchor="center")
        self.dir_tree.heading("stock3",     text="Stock 3",   anchor="center")
        self.dir_tree.heading("score",      text="Score",     anchor="center")
        self.dir_tree.heading("direction",  text="Direction", anchor="center")

        self.dir_tree.column("group_name", width=200, minwidth=120, anchor="w",      stretch=True)
        self.dir_tree.column("stock1",     width=140, minwidth=100, anchor="center", stretch=True)
        self.dir_tree.column("stock2",     width=140, minwidth=100, anchor="center", stretch=True)
        self.dir_tree.column("stock3",     width=140, minwidth=100, anchor="center", stretch=True)
        self.dir_tree.column("score",      width=70,  minwidth=50,  anchor="center", stretch=False)
        self.dir_tree.column("direction",  width=80,  minwidth=60,  anchor="center", stretch=False)

        self.dir_tree.tag_configure("up",      background="#d6f0d6", foreground="#0b4a0b")
        self.dir_tree.tag_configure("down",    background="#fad6d6", foreground="#7a0000")
        self.dir_tree.tag_configure("neutral", background="#f5f5f5", foreground="#444444")
        self.dir_tree.tag_configure(
            "total",
            background="#dde6f0",
            foreground="#00205b",
            font=("Segoe UI", 9, "bold"),
        )
        self.dir_tree.bind("<<TreeviewSelect>>", self._on_select)

        dir_scroll = ttk.Scrollbar(top_frame, orient="vertical", command=self.dir_tree.yview)
        self.dir_tree.configure(yscrollcommand=dir_scroll.set)
        self.dir_tree.pack(side="left", fill="both", expand=True)
        dir_scroll.pack(side="right", fill="y")

        # ── Bottom pane: signals table ────────────────────────────────────────
        bot_frame = ttk.Frame(paned)
        paned.add(bot_frame, weight=1)

        bot_label = ttk.Label(bot_frame, text="Potential Buys & Sells",
                              font=("Segoe UI", 9, "bold"))
        bot_label.pack(anchor="w", pady=(0, 4))

        sig_cols = (
            "group", "ticker", "signal", "date", "pivot", "trigger", "reference", "context"
        )
        self.sig_tree = ttk.Treeview(
            bot_frame, columns=sig_cols, show="headings", selectmode="none"
        )
        self.sig_tree.heading("group",     text="Group",     anchor="w")
        self.sig_tree.heading("ticker",    text="Ticker",    anchor="center")
        self.sig_tree.heading("signal",    text="Signal",    anchor="center")
        self.sig_tree.heading("date",      text="Trigger Date", anchor="center")
        self.sig_tree.heading("pivot",     text="Pivot",     anchor="center")
        self.sig_tree.heading("trigger",   text="Trigger Px", anchor="center")
        self.sig_tree.heading("reference", text="Ref Price", anchor="center")
        self.sig_tree.heading("context",   text="Rule",      anchor="w")

        self.sig_tree.column("group",     width=160, minwidth=100, anchor="w",      stretch=True)
        self.sig_tree.column("ticker",    width=70,  minwidth=60,  anchor="center", stretch=False)
        self.sig_tree.column("signal",    width=60,  minwidth=50,  anchor="center", stretch=False)
        self.sig_tree.column("date",      width=100, minwidth=80,  anchor="center", stretch=False)
        self.sig_tree.column("pivot",     width=90,  minwidth=70,  anchor="center", stretch=False)
        self.sig_tree.column("trigger",   width=90,  minwidth=70,  anchor="center", stretch=False)
        self.sig_tree.column("reference", width=90,  minwidth=70,  anchor="center", stretch=False)
        self.sig_tree.column("context",   width=220, minwidth=160, anchor="w",      stretch=True)

        self.sig_tree.tag_configure(
            "sell", background="#fad6d6", foreground="#7a0000"
        )
        self.sig_tree.tag_configure(
            "buy", background="#d6f0d6", foreground="#0b4a0b"
        )

        sig_scroll = ttk.Scrollbar(bot_frame, orient="vertical", command=self.sig_tree.yview)
        self.sig_tree.configure(yscrollcommand=sig_scroll.set)
        self.sig_tree.pack(side="left", fill="both", expand=True)
        sig_scroll.pack(side="right", fill="y")

    # ── Selection / ledger open ───────────────────────────────────────────────

    def _on_select(self, _event=None) -> None:
        selected = self.dir_tree.selection()
        iid = selected[0] if selected else None
        if iid and iid in self._groups:
            self.ledger_button.configure(state="normal")
        else:
            self.ledger_button.configure(state="disabled")

    def _open_ledger(self) -> None:
        selected = self.dir_tree.selection()
        if not selected:
            return
        group = self._groups.get(selected[0])
        if group is None:
            return
        open_ledger_sheet(self, group)

    # ── Run button ────────────────────────────────────────────────────────────

    def _start_run(self):
        self.run_button.configure(state="disabled")
        self.ledger_button.configure(state="disabled")
        self.status_label.configure(text="Calculating…")
        for item in self.dir_tree.get_children():
            self.dir_tree.delete(item)
        for item in self.sig_tree.get_children():
            self.sig_tree.delete(item)
        self._groups.clear()
        threading.Thread(target=self._worker, daemon=True).start()

    # ── Background worker ─────────────────────────────────────────────────────

    def _worker(self):
        try:
            groups = db.group_list()
            dir_rows: list[tuple[dict, list[tuple[str, str | None]]]] = []
            sig_rows: list[tuple[str, str, TradingSignal]] = []  # (group_name, ticker, signal)

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
                    ledger_rows = build_ledger(prices, multiplier=multiplier)
                    trend = primary_trend(ledger_rows)
                    stock_trends.append((ticker, trend))

                    for sig in find_signals(ledger_rows):
                        sig_rows.append((group_name, ticker, sig))

                dir_rows.append((group, stock_trends))

            self.after(
                0, lambda d=dir_rows, s=sig_rows: self._populate(d, s)
            )

        except Exception as exc:
            self.after(
                0,
                lambda e=exc: self.status_label.configure(text=f"Error: {e}"),
            )
        finally:
            self.after(0, lambda: self.run_button.configure(state="normal"))

    # ── Populate tables ───────────────────────────────────────────────────────

    def _populate(
        self,
        dir_rows: list[tuple[dict, list[tuple[str, str | None]]]],
        sig_rows: list[tuple[str, str, TradingSignal]],
    ) -> None:
        # clear
        for item in self.dir_tree.get_children():
            self.dir_tree.delete(item)
        for item in self.sig_tree.get_children():
            self.sig_tree.delete(item)
        self._groups.clear()

        if not dir_rows:
            self.status_label.configure(text="No groups found.")
            return

        # ── Direction table ───────────────────────────────────────────────────
        total_score = 0
        for group, stock_trends in dir_rows:
            group_name = group.get("GroupName", f"Group #{group['GroupID']}")
            iid = str(group["GroupID"])
            self._groups[iid] = group

            raw_sum = sum(_trend_score(trend) for _, trend in stock_trends)
            group_rating = 1 if raw_sum > 0 else (-1 if raw_sum < 0 else 0)
            total_score += group_rating

            tag = "up" if group_rating > 0 else ("down" if group_rating < 0 else "neutral")
            cells = [_trend_cell(ticker, trend) for ticker, trend in stock_trends]
            while len(cells) < 3:
                cells.append("")

            self.dir_tree.insert(
                "", "end", iid=iid,
                values=(
                    group_name, cells[0], cells[1], cells[2],
                    f"{group_rating:+d}" if group_rating != 0 else "0",
                    _direction_symbol(group_rating),
                ),
                tags=(tag,),
            )

        total_direction = _direction_symbol(total_score)
        self.dir_tree.insert(
            "", "end", iid="TOTAL",
            values=(
                "TOTAL", "", "", "",
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
                f"(score {total_score:+d} across {len(dir_rows)} group(s))"
            )
        )

        # ── Signals table ─────────────────────────────────────────────────────
        # Sort: sells first (by date desc), then buys (by date desc)
        sells = sorted(
            [(g, t, s) for g, t, s in sig_rows if s.direction == "sell"],
            key=lambda x: x[2].trigger_date,
            reverse=True,
        )
        buys = sorted(
            [(g, t, s) for g, t, s in sig_rows if s.direction == "buy"],
            key=lambda x: x[2].trigger_date,
            reverse=True,
        )
        for group_name, ticker, sig in sells + buys:
            self.sig_tree.insert(
                "", "end",
                values=(
                    group_name,
                    ticker,
                    "SELL" if sig.direction == "sell" else "BUY",
                    sig.trigger_date.isoformat(),
                    f"{sig.pivot_price:.2f}",
                    f"{sig.trigger_price:.2f}",
                    f"{sig.reference_price:.2f}",
                    sig.context,
                ),
                tags=(sig.direction,),
            )

        if not sig_rows:
            self.sig_tree.insert(
                "", "end",
                values=("No active signals found.", "", "", "", "", "", "", ""),
            )
