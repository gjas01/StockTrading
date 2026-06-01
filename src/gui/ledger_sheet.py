from __future__ import annotations

import tempfile
import tkinter as tk
import webbrowser
from html import escape
from pathlib import Path
from tkinter import messagebox, ttk

from src import db
from src.services.livermore_ledger import COLUMNS, COLUMN_KEYS, LedgerRow, build_ledger


COLUMN_HEADERS = {
    "secondary_rally": "Secondary Rally",
    "natural_rally": "Natural Rally",
    "upward_trend": "Upward Trend",
    "downward_trend": "Downward Trend",
    "natural_reaction": "Natural Reaction",
    "secondary_reaction": "Secondary Reaction",
}


def _format_cell(row: LedgerRow, key: str) -> tuple[str, bool]:
    value = getattr(row, key)
    if value is None:
        return "", False
    return f"{value:.2f}", key in row.pivotal


def _ledger_table_html(title: str, rows: list[LedgerRow], price_count: int) -> str:
    if not rows:
        return f"<h2>{escape(title)}</h2><p>No price history available.</p>"

    header = (
        "<tr>"
        "<th>Date</th><th>High</th><th>Low</th><th>Close</th>"
        + "".join(f"<th>{escape(COLUMN_HEADERS[key])}</th>" for key in COLUMN_HEADERS)
        + "<th>Note</th></tr>"
    )
    body_rows = []
    for row in rows:
        cells = [
            f"<td>{row.trade_date.isoformat()}</td>",
            f"<td>{row.high:.2f}</td>",
            f"<td>{row.low:.2f}</td>",
            f"<td>{row.close:.2f}</td>",
        ]
        for key in COLUMN_HEADERS:
            text, pivotal = _format_cell(row, key)
            css = ' class="pivot"' if pivotal else ""
            cells.append(f"<td{css}>{escape(text)}</td>")
        cells.append(f"<td>{escape(row.note)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    subtitle = (
        f"{price_count} trading day(s). Pivotal extremes underlined "
        f"(highs on up moves, lows on down moves; 3% / 6% bands)."
    )
    return f"""
    <section class="ledger-block">
      <h2>{escape(title)}</h2>
      <p class="subtitle">{escape(subtitle)}</p>
      <table>
        <thead>{header}</thead>
        <tbody>{"".join(body_rows)}</tbody>
      </table>
    </section>
    """


def build_pair_ledger_html(
    pair_title: str,
    primary_title: str,
    primary_rows: list[LedgerRow],
    primary_count: int,
    secondary_title: str,
    secondary_rows: list[LedgerRow],
    secondary_count: int,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(pair_title)} - Livermore Ledgers</title>
  <style>
    body {{
      font-family: "Segoe UI", Arial, sans-serif;
      margin: 24px;
      color: #111;
    }}
    h1 {{ margin-bottom: 4px; }}
    .intro {{ margin-bottom: 24px; color: #333; }}
    .ledgers {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
    }}
    .ledger-block {{ break-inside: avoid; }}
    .subtitle {{ font-size: 12px; color: #444; margin-top: 0; }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 11px;
    }}
    th, td {{
      border: 1px solid #999;
      padding: 4px 6px;
      text-align: right;
    }}
    th:first-child, td:first-child,
    th:last-child, td:last-child {{
      text-align: left;
    }}
    th {{ background: #eee; }}
    .pivot {{
      text-decoration: underline;
      font-weight: 600;
    }}
    @media print {{
      body {{ margin: 12px; }}
      .ledgers {{ grid-template-columns: 1fr 1fr; }}
      .no-print {{ display: none; }}
    }}
  </style>
</head>
<body>
  <h1>{escape(pair_title)}</h1>
  <p class="intro">
    Jesse Livermore Market Key ledgers. Underlined prices are pivotal extremes:
    day highs mark up-move pivots; day lows mark down-move pivots.
    Reversal checks use the opposite side of the bar (low against an up pivot, high against a down pivot).
  </p>
  <div class="ledgers">
    {_ledger_table_html(primary_title, primary_rows, primary_count)}
    {_ledger_table_html(secondary_title, secondary_rows, secondary_count)}
  </div>
</body>
</html>
"""


class LedgerSheetWindow(ttk.Frame):
    """Separate printable ledger view for a stock pair."""

    def __init__(self, master, pair: dict):
        super().__init__(master, padding=12)
        self.pair = pair
        self._html = ""

        primary_label = (
            f"{pair['PrimaryTicker']} ({pair['PrimaryCountryName']} / {pair['PrimaryExchangeName']})"
        )
        secondary_label = (
            f"{pair['SecondaryTicker']} ({pair['SecondaryCountryName']} / {pair['SecondaryExchangeName']})"
        )
        title = f"Pair #{pair['PairID']}: {primary_label}  /  {secondary_label}"

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text=title, font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(toolbar, text="Print", command=self.print_sheet).pack(side="right", padx=(6, 0))
        ttk.Button(toolbar, text="Open in Browser", command=self.open_in_browser).pack(side="right")

        self.status_var = ttk.Label(
            self,
            text="Loading ledgers...",
            wraplength=1200,
        )
        self.status_var.pack(anchor="w", pady=(0, 8))

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        self.primary_text = self._make_text_widget(paned)
        self.secondary_text = self._make_text_widget(paned)
        paned.add(self.primary_text.master, weight=1)
        paned.add(self.secondary_text.master, weight=1)

        self.load_ledgers()

    def _make_text_widget(self, parent):
        frame = ttk.Frame(parent)
        text = tk.Text(
            frame,
            wrap="none",
            font=("Consolas", 10),
            width=60,
            height=30,
        )
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text.tag_configure("header", font=("Consolas", 10, "bold"))
        text.tag_configure("pivot", underline=True, font=("Consolas", 10, "bold"))
        text.configure(state="disabled")
        return text

    def _load_stock_ledger(self, stock_id: int, ticker: str, role: str) -> tuple[list[LedgerRow], int]:
        prices = db.stock_price_list(stock_id)
        rows = build_ledger(prices)
        return rows, len(prices)

    def load_ledgers(self):
        try:
            primary_rows, primary_count = self._load_stock_ledger(
                int(self.pair["PrimaryStockID"]),
                self.pair["PrimaryTicker"],
                "Primary",
            )
            secondary_rows, secondary_count = self._load_stock_ledger(
                int(self.pair["SecondaryStockID"]),
                self.pair["SecondaryTicker"],
                "Secondary",
            )
        except Exception as exc:
            self.status_var.configure(text=str(exc))
            return

        primary_title = f"Primary: {self.pair['PrimaryTicker']}"
        secondary_title = f"Secondary: {self.pair['SecondaryTicker']}"
        self._populate_text(self.primary_text, primary_title, primary_rows, primary_count)
        self._populate_text(self.secondary_text, secondary_title, secondary_rows, secondary_count)

        pair_title = (
            f"Pair #{self.pair['PairID']}: {self.pair['PrimaryTicker']} / {self.pair['SecondaryTicker']}"
        )
        self._html = build_pair_ledger_html(
            pair_title,
            primary_title,
            primary_rows,
            primary_count,
            secondary_title,
            secondary_rows,
            secondary_count,
        )
        self.status_var.configure(
            text=(
                "Underlined prices are pivotal extremes. "
                "Up-move columns use day highs; down-move columns use day lows. "
                "Use Print or Open in Browser for a printable sheet."
            )
        )

    def _populate_text(self, widget, title: str, rows: list[LedgerRow], price_count: int) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", f"{title}\n", "header")
        widget.insert("end", f"{price_count} trading day(s)\n\n", "header")

        headers = ["Date", "High", "Low", "Close", *COLUMN_HEADERS.values(), "Note"]
        widget.insert("end", "\t".join(headers) + "\n", "header")

        for row in rows:
            line_parts = [
                row.trade_date.isoformat(),
                f"{row.high:.2f}",
                f"{row.low:.2f}",
                f"{row.close:.2f}",
            ]
            start = widget.index("end-1c")
            widget.insert("end", "\t".join(line_parts))

            for key in COLUMN_HEADERS:
                widget.insert("end", "\t")
                value, pivotal = _format_cell(row, key)
                if value:
                    if pivotal:
                        widget.insert("end", value, "pivot")
                    else:
                        widget.insert("end", value)

            widget.insert("end", "\t")
            widget.insert("end", row.note)
            widget.insert("end", "\n")

        widget.configure(state="disabled")
        widget.yview_moveto(1.0)

    def _write_html_tempfile(self) -> Path:
        temp = Path(tempfile.gettempdir()) / f"stock_pair_{self.pair['PairID']}_ledgers.html"
        temp.write_text(self._html, encoding="utf-8")
        return temp

    def open_in_browser(self):
        if not self._html:
            messagebox.showwarning("Ledger", "No ledger data to display.")
            return
        path = self._write_html_tempfile()
        webbrowser.open(path.as_uri())

    def print_sheet(self):
        if not self._html:
            messagebox.showwarning("Ledger", "No ledger data to print.")
            return
        path = self._write_html_tempfile()
        webbrowser.open(path.as_uri())
        messagebox.showinfo(
            "Print",
            "The printable ledger sheet opened in your browser.\n"
            "Use Ctrl+P (or the browser Print menu) to print.",
        )


def open_ledger_sheet(parent, pair: dict):
    window = tk.Toplevel(parent)
    window.title(f"Livermore Ledgers - Pair #{pair['PairID']}")
    window.geometry("1400x800")
    sheet = LedgerSheetWindow(window, pair)
    sheet.pack(fill="both", expand=True)
