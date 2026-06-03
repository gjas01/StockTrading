import tkinter as tk
from tkinter import messagebox, ttk

from src import db


def _format_multiplier(value) -> str:
    multiplier = float(value or 1)
    if multiplier == int(multiplier):
        return str(int(multiplier))
    return f"{multiplier:g}"


class ExchangeTab(ttk.Frame):
    def __init__(self, master, refresh_callbacks=None):
        super().__init__(master, padding=12)
        self.refresh_callbacks = refresh_callbacks or []

        ttk.Label(self, text="Country:").grid(row=0, column=0, sticky="w")
        self.country_var = tk.StringVar()
        self.country_combo = ttk.Combobox(self, textvariable=self.country_var, state="readonly", width=38)
        self.country_combo.grid(row=0, column=1, padx=8, sticky="ew")

        ttk.Label(self, text="Exchange name:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=40).grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Label(self, text="Yahoo suffix:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.suffix_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.suffix_var, width=40).grid(row=2, column=1, padx=8, pady=(8, 0), sticky="ew")
        ttk.Label(self, text="Example: .L for London, leave blank for US").grid(
            row=3, column=1, sticky="w", padx=8
        )

        ttk.Label(self, text="Multiplier:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.multiplier_var = tk.StringVar(value="1")
        ttk.Entry(self, textvariable=self.multiplier_var, width=40).grid(
            row=4, column=1, padx=8, pady=(8, 0), sticky="ew"
        )
        ttk.Label(
            self,
            text="Default 1. Scales 3%/6% ledger thresholds (e.g. 1.67 -> 5.01%/10.02%).",
        ).grid(row=5, column=1, sticky="w", padx=8)

        ttk.Button(self, text="Add Exchange", command=self.add_exchange).grid(
            row=6, column=1, sticky="e", pady=(12, 0)
        )

        ttk.Label(self, text="Exchanges").grid(row=7, column=0, columnspan=2, sticky="w", pady=(16, 4))

        list_frame = ttk.Frame(self)
        list_frame.grid(row=8, column=0, columnspan=2, sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(8, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("id", "country", "name", "suffix", "multiplier"),
            show="headings",
            height=12,
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("country", text="Country")
        self.tree.heading("name", text="Exchange")
        self.tree.heading("suffix", text="Yahoo Suffix")
        self.tree.heading("multiplier", text="Multiplier")
        self.tree.column("id", width=60, stretch=False)
        self.tree.column("country", width=120, stretch=True)
        self.tree.column("name", width=160, stretch=True)
        self.tree.column("suffix", width=100, stretch=False)
        self.tree.column("multiplier", width=90, stretch=False)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.countries = []
        self.refresh_countries()
        self.refresh_list()

    def refresh_countries(self):
        try:
            self.countries = db.country_list()
        except Exception as exc:
            self.countries = []
            messagebox.showerror("Database Error", str(exc))
            return
        labels = [country["Name"] for country in self.countries]
        self.country_combo["values"] = labels
        if labels and not self.country_var.get():
            self.country_combo.current(0)

    def refresh_list(self):
        try:
            exchanges = db.exchange_list()
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))
            exchanges = []

        for item in self.tree.get_children():
            self.tree.delete(item)
        for exchange in exchanges:
            self.tree.insert(
                "",
                "end",
                values=(
                    exchange["ExchangeID"],
                    exchange["CountryName"],
                    exchange["Name"],
                    exchange.get("YahooSuffix") or "",
                    _format_multiplier(exchange.get("Multiplier")),
                ),
            )

    def _selected_country_id(self):
        name = self.country_var.get()
        for country in self.countries:
            if country["Name"] == name:
                return int(country["CountryID"])
        return None

    def _parse_multiplier(self) -> float | None:
        text = self.multiplier_var.get().strip()
        if not text:
            return 1.0
        try:
            multiplier = float(text)
        except ValueError:
            messagebox.showwarning("Validation", "Enter a valid numeric multiplier.")
            return None
        if multiplier <= 0:
            messagebox.showwarning("Validation", "Multiplier must be greater than zero.")
            return None
        return multiplier

    def add_exchange(self):
        country_id = self._selected_country_id()
        if country_id is None:
            messagebox.showwarning("Validation", "Select a country.")
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Enter an exchange name.")
            return
        multiplier = self._parse_multiplier()
        if multiplier is None:
            return
        try:
            exchange_id = db.exchange_insert(
                country_id,
                name,
                self.suffix_var.get().strip(),
                multiplier,
            )
            messagebox.showinfo("Success", f"Exchange added (ID {exchange_id}).")
            self.name_var.set("")
            self.suffix_var.set("")
            self.multiplier_var.set("1")
            self.refresh_list()
            for callback in self.refresh_callbacks:
                callback()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
