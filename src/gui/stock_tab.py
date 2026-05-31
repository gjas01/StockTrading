import tkinter as tk
from tkinter import messagebox, ttk

from src import db


class StockTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        ttk.Label(self, text="Exchange:").grid(row=0, column=0, sticky="w")
        self.exchange_var = tk.StringVar()
        self.exchange_combo = ttk.Combobox(self, textvariable=self.exchange_var, state="readonly", width=38)
        self.exchange_combo.grid(row=0, column=1, padx=8, sticky="ew")

        ttk.Label(self, text="Ticker:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.ticker_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.ticker_var, width=40).grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Label(self, text="Full name:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.full_name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.full_name_var, width=40).grid(row=2, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Button(self, text="Add Stock", command=self.add_stock).grid(row=3, column=1, sticky="e", pady=12)
        self.columnconfigure(1, weight=1)
        self.exchanges = []
        self.refresh_exchanges()

    def refresh_exchanges(self):
        try:
            self.exchanges = db.exchange_list()
        except Exception as exc:
            self.exchanges = []
            messagebox.showerror("Database Error", str(exc))
            return
        labels = [
            f"{exchange['CountryName']} / {exchange['Name']}"
            for exchange in self.exchanges
        ]
        self.exchange_combo["values"] = labels
        if labels and not self.exchange_var.get():
            self.exchange_combo.current(0)

    def _selected_exchange_id(self):
        label = self.exchange_var.get()
        for exchange in self.exchanges:
            current = f"{exchange['CountryName']} / {exchange['Name']}"
            if current == label:
                return int(exchange["ExchangeID"])
        return None

    def add_stock(self):
        exchange_id = self._selected_exchange_id()
        if exchange_id is None:
            messagebox.showwarning("Validation", "Select an exchange.")
            return
        ticker = self.ticker_var.get().strip()
        full_name = self.full_name_var.get().strip()
        if not ticker or not full_name:
            messagebox.showwarning("Validation", "Enter ticker and full name.")
            return
        try:
            stock_id = db.stock_insert(exchange_id, ticker, full_name)
            messagebox.showinfo("Success", f"Stock added (ID {stock_id}).")
            self.ticker_var.set("")
            self.full_name_var.set("")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
