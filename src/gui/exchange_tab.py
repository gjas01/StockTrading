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

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=1, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Clear Form", command=self.clear_form).pack(side="left", padx=(0, 8))
        self.save_button = ttk.Button(
            buttons,
            text="Save Changes",
            command=self.save_exchange,
            state="disabled",
        )
        self.save_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Add Exchange", command=self.add_exchange).pack(side="left")

        ttk.Label(self, text="Exchanges").grid(row=7, column=0, columnspan=2, sticky="w", pady=(16, 4))
        ttk.Label(
            self,
            text="Select an exchange below to load it into the form for editing.",
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 4))

        list_frame = ttk.Frame(self)
        list_frame.grid(row=9, column=0, columnspan=2, sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(9, weight=1)

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
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.countries = []
        self.exchanges_by_id: dict[str, dict] = {}
        self.refresh_countries()
        self.refresh_list()

    def _on_selection_changed(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self.save_button.configure(state="disabled")
            return

        exchange = self.exchanges_by_id.get(selection[0])
        if not exchange:
            self.save_button.configure(state="disabled")
            return

        self.save_button.configure(state="normal")
        self.country_var.set(exchange["CountryName"])
        self.name_var.set(exchange["Name"])
        self.suffix_var.set(exchange.get("YahooSuffix") or "")
        self.multiplier_var.set(_format_multiplier(exchange.get("Multiplier")))

    def clear_form(self):
        self.tree.selection_remove(self.tree.selection())
        self.name_var.set("")
        self.suffix_var.set("")
        self.multiplier_var.set("1")
        if self.countries:
            self.country_combo.current(0)
        self.save_button.configure(state="disabled")

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

        selected = self.tree.selection()
        selected_id = self.tree.item(selected[0])["values"][0] if selected else None

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.exchanges_by_id.clear()

        for exchange in exchanges:
            exchange_id = str(exchange["ExchangeID"])
            self.exchanges_by_id[exchange_id] = exchange
            self.tree.insert(
                "",
                "end",
                iid=exchange_id,
                values=(
                    exchange["ExchangeID"],
                    exchange["CountryName"],
                    exchange["Name"],
                    exchange.get("YahooSuffix") or "",
                    _format_multiplier(exchange.get("Multiplier")),
                ),
            )

        if selected_id is not None and str(selected_id) in self.exchanges_by_id:
            self.tree.selection_set(str(selected_id))
        else:
            self.save_button.configure(state="disabled")

        self._on_selection_changed()

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

    def _form_values(self) -> tuple[int, str, str, float] | None:
        country_id = self._selected_country_id()
        if country_id is None:
            messagebox.showwarning("Validation", "Select a country.")
            return None
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Enter an exchange name.")
            return None
        multiplier = self._parse_multiplier()
        if multiplier is None:
            return None
        return country_id, name, self.suffix_var.get().strip(), multiplier

    def save_exchange(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Validation", "Select an exchange to save.")
            return

        values = self._form_values()
        if values is None:
            return

        country_id, name, suffix, multiplier = values
        exchange_id = int(selection[0])
        try:
            db.exchange_update(exchange_id, country_id, name, suffix, multiplier)
            messagebox.showinfo("Success", f"Exchange updated (ID {exchange_id}).")
            self.refresh_list()
            self.tree.selection_set(str(exchange_id))
            for callback in self.refresh_callbacks:
                callback()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def add_exchange(self):
        values = self._form_values()
        if values is None:
            return

        country_id, name, suffix, multiplier = values
        try:
            exchange_id = db.exchange_insert(country_id, name, suffix, multiplier)
            messagebox.showinfo("Success", f"Exchange added (ID {exchange_id}).")
            self.clear_form()
            self.refresh_list()
            if exchange_id is not None:
                self.tree.selection_set(str(exchange_id))
            for callback in self.refresh_callbacks:
                callback()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
