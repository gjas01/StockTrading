import tkinter as tk
from tkinter import messagebox, ttk

from src import db


def _stock_label(stock: dict) -> str:
    return (
        f"{stock['CountryName']} / {stock['ExchangeName']} / "
        f"{stock['Ticker']} - {stock['FullName']}"
    )


class PairTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        ttk.Label(self, text="Primary stock:").grid(row=0, column=0, sticky="w")
        self.primary_var = tk.StringVar()
        self.primary_combo = ttk.Combobox(
            self, textvariable=self.primary_var, state="readonly", width=50
        )
        self.primary_combo.grid(row=0, column=1, padx=8, sticky="ew")

        ttk.Label(self, text="Secondary stock:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.secondary_var = tk.StringVar()
        self.secondary_combo = ttk.Combobox(
            self, textvariable=self.secondary_var, state="readonly", width=50
        )
        self.secondary_combo.grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Button(self, text="Add Pair", command=self.add_pair).grid(
            row=2, column=1, sticky="e", pady=(12, 0)
        )

        ttk.Label(self, text="Pairs").grid(row=3, column=0, columnspan=2, sticky="w", pady=(16, 4))

        list_frame = ttk.Frame(self)
        list_frame.grid(row=4, column=0, columnspan=2, sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("id", "primary", "secondary"),
            show="headings",
            height=12,
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("primary", text="Primary")
        self.tree.heading("secondary", text="Secondary")
        self.tree.column("id", width=60, stretch=False)
        self.tree.column("primary", width=320, stretch=True)
        self.tree.column("secondary", width=320, stretch=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.stocks = []
        self.refresh_stocks()
        self.refresh_list()

    def refresh_stocks(self):
        try:
            self.stocks = db.stock_list()
        except Exception as exc:
            self.stocks = []
            messagebox.showerror("Database Error", str(exc))
            return

        labels = [_stock_label(stock) for stock in self.stocks]
        self.primary_combo["values"] = labels
        self.secondary_combo["values"] = labels
        if labels:
            if not self.primary_var.get():
                self.primary_combo.current(0)
            if not self.secondary_var.get():
                self.secondary_combo.current(1 if len(labels) > 1 else 0)

    def refresh_list(self):
        try:
            pairs = db.pair_list()
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))
            pairs = []

        for item in self.tree.get_children():
            self.tree.delete(item)
        for pair in pairs:
            primary = (
                f"{pair['PrimaryTicker']} ({pair['PrimaryCountryName']} / "
                f"{pair['PrimaryExchangeName']}) - {pair['PrimaryFullName']}"
            )
            secondary = (
                f"{pair['SecondaryTicker']} ({pair['SecondaryCountryName']} / "
                f"{pair['SecondaryExchangeName']}) - {pair['SecondaryFullName']}"
            )
            self.tree.insert("", "end", values=(pair["PairID"], primary, secondary))

    def _stock_id_from_label(self, label: str) -> int | None:
        for stock in self.stocks:
            if _stock_label(stock) == label:
                return int(stock["StockID"])
        return None

    def add_pair(self):
        primary_id = self._stock_id_from_label(self.primary_var.get())
        secondary_id = self._stock_id_from_label(self.secondary_var.get())
        if primary_id is None or secondary_id is None:
            messagebox.showwarning("Validation", "Select both primary and secondary stocks.")
            return
        if primary_id == secondary_id:
            messagebox.showwarning("Validation", "Primary and secondary stock must be different.")
            return
        try:
            pair_id = db.pair_insert(primary_id, secondary_id)
            messagebox.showinfo("Success", f"Pair added (ID {pair_id}).")
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
