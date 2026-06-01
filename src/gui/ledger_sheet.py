from __future__ import annotations

import tempfile
import tkinter as tk
import webbrowser
from html import escape
from pathlib import Path
from tkinter import messagebox, ttk

from src import db
from src.services.livermore_ledger import LedgerRow, build_ledger


COLUMN_HEADERS = {
    "secondary_rally": "Secondary Rally",
    "natural_rally": "Natural Rally",
    "upward_trend": "Upward Trend",
    "downward_trend": "Downward Trend",
    "natural_reaction": "Natural Reaction",
    "secondary_reaction": "Secondary Reaction",
}

TREE_COLUMNS = [
    ("date", "Date", 92, "w"),
    ("high", "High", 72, "e"),
    ("low", "Low", 72, "e"),
    ("close", "Close", 72, "e"),
    ("secondary_rally", "Secondary Rally", 96, "e"),
    ("natural_rally", "Natural Rally", 96, "e"),
    ("upward_trend", "Upward Trend", 96, "e"),
    ("downward_trend", "Downward Trend", 96, "e"),
    ("natural_reaction", "Natural Reaction", 108, "e"),
    ("secondary_reaction", "Secondary Reaction", 112, "e"),
    ("note", "Note", 220, "w"),
]


def _format_cell(row: LedgerRow, key: str) -> tuple[str, bool, bool, bool]:
    value = getattr(row, key)
    if value is None:
        return "", False, False, False
    return (
        f"{value:.2f}",
        key in row.pivotal,
        key in row.blue,
        key in row.red,
    )


def _display_cell(row: LedgerRow, key: str) -> str:
    value, pivotal, blue, red = _format_cell(row, key)
    if not value:
        return ""
    markers = ""
    if pivotal:
        markers += "*"
    if blue:
        markers += "^"
    if red:
        markers += "!"
    return f"{value}{markers}"


def _row_values(row: LedgerRow) -> tuple[str, ...]:
    values = [
        row.trade_date.isoformat(),
        f"{row.high:.2f}",
        f"{row.low:.2f}",
        f"{row.close:.2f}",
    ]
    for key in COLUMN_HEADERS:
        values.append(_display_cell(row, key))
    values.append(row.note)
    return tuple(values)


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
            text, pivotal, blue, red = _format_cell(row, key)
            css_classes = []
            if pivotal:
                css_classes.append("pivot")
            if blue:
                css_classes.append("near-upper")
            if red:
                css_classes.append("near-lower")
            css = f' class="{" ".join(css_classes)}"' if css_classes else ""
            cells.append(f"<td{css}>{escape(text)}</td>")
        cells.append(f"<td>{escape(row.note)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    subtitle = (
        f"{price_count} trading day(s). Underline = pivot point only. "
        f"Blue = within 1.5% of upper pivot; red = within 1.5% of lower pivot."
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
    .near-upper {{
      color: #0b5cab;
      font-weight: 600;
    }}
    .near-lower {{
      color: #b00020;
      font-weight: 600;
    }}
    td.near-upper.pivot, td.near-lower.pivot {{
      text-decoration: underline;
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
    Jesse Livermore Market Key ledger. Wait for 6% from the first close to establish trend.
    Blank cells = no new extreme. Underline = confirmed pivot only (upper after reaction opens,
    lower after rally opens). Blue / red = within 1.5% of upper / lower pivot.
  </p>
  <div class="ledgers">
    {_ledger_table_html(primary_title, primary_rows, primary_count)}
    {_ledger_table_html(secondary_title, secondary_rows, secondary_count)}
  </div>
</body>
</html>
"""


class _LedgerPanelWidgets:
    def __init__(self, frame, title, subtitle, tree):
        self.frame = frame
        self.title = title
        self.subtitle = subtitle
        self.tree = tree


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

        style = ttk.Style()
        style.configure("Ledger.Treeview", font=("Consolas", 10))
        style.configure("Ledger.Treeview.Heading", font=("Consolas", 10, "bold"))

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        self.primary_panel = self._make_ledger_panel(paned)
        self.secondary_panel = self._make_ledger_panel(paned)
        paned.add(self.primary_panel.frame, weight=1)
        paned.add(self.secondary_panel.frame, weight=1)

        self.load_ledgers()

    def _make_ledger_panel(self, parent):
        frame = ttk.Frame(parent)

        title = ttk.Label(frame, font=("Segoe UI", 10, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(frame)
        subtitle.pack(anchor="w", pady=(0, 4))

        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        column_ids = [col_id for col_id, _, _, _ in TREE_COLUMNS]
        tree = ttk.Treeview(
            table,
            columns=column_ids,
            show="headings",
            height=24,
            style="Ledger.Treeview",
        )
        tree.grid(row=0, column=0, sticky="nsew")

        for col_id, heading, width, anchor in TREE_COLUMNS:
            tree.heading(col_id, text=heading, anchor=anchor)
            stretch = col_id == "note"
            tree.column(col_id, width=width, minwidth=width, anchor=anchor, stretch=stretch)

        y_scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(table, orient="horizontal", command=tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        return _LedgerPanelWidgets(frame, title, subtitle, tree)

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
        self._populate_panel(self.primary_panel, primary_title, primary_rows, primary_count)
        self._populate_panel(self.secondary_panel, secondary_title, secondary_rows, secondary_count)

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
                "Grid markers: * pivot, ^ near upper pivot (blue in print), ! near lower pivot (red in print). "
                "Most cells stay blank until a new extreme is recorded."
            )
        )

    def _populate_panel(self, panel, title: str, rows: list[LedgerRow], price_count: int) -> None:
        panel.title.configure(text=title)
        if not rows:
            panel.subtitle.configure(text="No price history. Pull prices for this stock first.")
        else:
            panel.subtitle.configure(
                text=(
                    f"{price_count} trading day(s). "
                    "6% trend / 3% continuation. * pivot  ^ upper  ! lower"
                )
            )

        for item in panel.tree.get_children():
            panel.tree.delete(item)

        for row in rows:
            panel.tree.insert("", "end", values=_row_values(row))

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
