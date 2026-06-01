import tkinter as tk
from tkinter import messagebox, ttk

from src import db
from src.gui.ledger_sheet import open_ledger_sheet


def _stock_label(stock: dict) -> str:
    return (
        f"{stock['CountryName']} / {stock['ExchangeName']} / "
        f"{stock['Ticker']} - {stock['FullName']}"
    )


def _pair_label(pair: dict) -> tuple[str, str]:
    primary = (
        f"{pair['PrimaryTicker']} ({pair['PrimaryCountryName']} / "
        f"{pair['PrimaryExchangeName']})"
    )
    secondary = (
        f"{pair['SecondaryTicker']} ({pair['SecondaryCountryName']} / "
        f"{pair['SecondaryExchangeName']})"
    )
    return primary, secondary


class PairTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        form = ttk.Frame(self)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Primary stock:").grid(row=0, column=0, sticky="w")
        self.primary_var = tk.StringVar()
        self.primary_combo = ttk.Combobox(
            form, textvariable=self.primary_var, state="readonly", width=50
        )
        self.primary_combo.grid(row=0, column=1, padx=8, sticky="ew")

        ttk.Label(form, text="Secondary stock:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.secondary_var = tk.StringVar()
        self.secondary_combo = ttk.Combobox(
            form, textvariable=self.secondary_var, state="readonly", width=50
        )
        self.secondary_combo.grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Button(form, text="Add Pair", command=self.add_pair).grid(
            row=2, column=1, sticky="e", pady=(12, 0)
        )

        ttk.Label(self, text="Pairs").grid(row=1, column=0, sticky="w", pady=(16, 4))

        list_frame = ttk.Frame(self)
        list_frame.grid(row=2, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("id", "primary", "secondary"),
            show="headings",
            height=14,
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("primary", text="Primary")
        self.tree.heading("secondary", text="Secondary")
        self.tree.column("id", width=60, stretch=False)
        self.tree.column("primary", width=360, stretch=True)
        self.tree.column("secondary", width=360, stretch=True)
        self.tree.bind("<Double-1>", self.open_selected_ledger)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.open_button = ttk.Button(
            actions,
            text="Open Ledger Sheet",
            command=self.open_selected_ledger,
            state="disabled",
        )
        self.open_button.pack(side="left")
        ttk.Label(
            actions,
            text="Double-click a pair or select and open the printable Livermore ledger sheet.",
        ).pack(side="left", padx=(12, 0))

        self.stocks = []
        self.pairs_by_id: dict[str, dict] = {}
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        self.refresh_stocks()
        self.refresh_list()

    def _on_selection_changed(self, _event=None):
        if self.tree.selection():
            self.open_button.configure(state="normal")
        else:
            self.open_button.configure(state="disabled")

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

        selected = self.tree.selection()
        selected_id = self.tree.item(selected[0])["values"][0] if selected else None

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.pairs_by_id.clear()

        for pair in pairs:
            primary, secondary = _pair_label(pair)
            pair_id = str(pair["PairID"])
            self.pairs_by_id[pair_id] = pair
            self.tree.insert("", "end", iid=pair_id, values=(pair["PairID"], primary, secondary))

        if selected_id is not None and str(selected_id) in self.pairs_by_id:
            self.tree.selection_set(str(selected_id))
        elif self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])

        self._on_selection_changed()

    def open_selected_ledger(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Ledger", "Select a pair first.")
            return
        pair = self.pairs_by_id.get(selection[0])
        if not pair:
            return
        open_ledger_sheet(self.winfo_toplevel(), pair)

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
            if pair_id is not None:
                self.tree.selection_set(str(pair_id))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
