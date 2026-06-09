import tkinter as tk
from tkinter import messagebox, ttk

from src import db
from src.gui.ledger_sheet import open_ledger_sheet


def _stock_label(stock: dict) -> str:
    return (
        f"{stock['CountryName']} / {stock['ExchangeName']} / "
        f"{stock['Ticker']} - {stock['FullName']}"
    )


def _group_display(group: dict) -> tuple[str, str, str, str]:
    name = group.get("GroupName", "")
    s1 = f"{group['Stock1Ticker']} ({group['Country1Name']} / {group['Exchange1Name']})"
    s2 = f"{group['Stock2Ticker']} ({group['Country2Name']} / {group['Exchange2Name']})"
    s3 = f"{group['Stock3Ticker']} ({group['Country3Name']} / {group['Exchange3Name']})"
    return name, s1, s2, s3


class GroupTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        # ── Entry form ────────────────────────────────────────────────────
        form = ttk.Frame(self)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Group name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=40).grid(
            row=0, column=1, padx=8, sticky="ew"
        )

        ttk.Label(form, text="Stock 1:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.stock1_var = tk.StringVar()
        self.stock1_combo = ttk.Combobox(
            form, textvariable=self.stock1_var, state="readonly", width=55
        )
        self.stock1_combo.grid(row=1, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Label(form, text="Stock 2:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.stock2_var = tk.StringVar()
        self.stock2_combo = ttk.Combobox(
            form, textvariable=self.stock2_var, state="readonly", width=55
        )
        self.stock2_combo.grid(row=2, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Label(form, text="Stock 3:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.stock3_var = tk.StringVar()
        self.stock3_combo = ttk.Combobox(
            form, textvariable=self.stock3_var, state="readonly", width=55
        )
        self.stock3_combo.grid(row=3, column=1, padx=8, pady=(8, 0), sticky="ew")

        ttk.Button(form, text="Add Group", command=self.add_group).grid(
            row=4, column=1, sticky="e", pady=(12, 0)
        )

        # ── Group list ────────────────────────────────────────────────────
        ttk.Label(self, text="Groups").grid(row=1, column=0, sticky="w", pady=(16, 4))

        list_frame = ttk.Frame(self)
        list_frame.grid(row=2, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("id", "name", "stock1", "stock2", "stock3"),
            show="headings",
            height=12,
        )
        self.tree.heading("id",     text="ID")
        self.tree.heading("name",   text="Group Name")
        self.tree.heading("stock1", text="Stock 1")
        self.tree.heading("stock2", text="Stock 2")
        self.tree.heading("stock3", text="Stock 3")
        self.tree.column("id",     width=50,  stretch=False)
        self.tree.column("name",   width=200, stretch=True)
        self.tree.column("stock1", width=260, stretch=True)
        self.tree.column("stock2", width=260, stretch=True)
        self.tree.column("stock3", width=260, stretch=True)
        self.tree.bind("<Double-1>", self.open_selected_ledger)
        self.tree.bind("<Delete>",   self.delete_selected_group)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ── Action buttons ────────────────────────────────────────────────
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.open_button = ttk.Button(
            actions,
            text="Open Ledger Sheet",
            command=self.open_selected_ledger,
            state="disabled",
        )
        self.open_button.pack(side="left")
        self.delete_button = ttk.Button(
            actions,
            text="Delete Group",
            command=self.delete_selected_group,
            state="disabled",
        )
        self.delete_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            actions,
            text="Double-click to open the ledger sheet.  "
                 "Select a group and press Delete or use Delete Group.",
        ).pack(side="left", padx=(12, 0))

        self.stocks: list[dict] = []
        self.groups_by_id: dict[str, dict] = {}
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        self.refresh_stocks()
        self.refresh_list()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _on_selection_changed(self, _event=None):
        state = "normal" if self.tree.selection() else "disabled"
        self.open_button.configure(state=state)
        self.delete_button.configure(state=state)

    def _stock_id_from_label(self, label: str) -> int | None:
        for stock in self.stocks:
            if _stock_label(stock) == label:
                return int(stock["StockID"])
        return None

    # ── Refresh ───────────────────────────────────────────────────────────

    def refresh_stocks(self):
        try:
            self.stocks = db.stock_list()
        except Exception as exc:
            self.stocks = []
            messagebox.showerror("Database Error", str(exc))
            return

        labels = [_stock_label(s) for s in self.stocks]
        for combo in (self.stock1_combo, self.stock2_combo, self.stock3_combo):
            combo["values"] = labels
        if labels:
            if not self.stock1_var.get():
                self.stock1_combo.current(0)
            if not self.stock2_var.get():
                self.stock2_combo.current(min(1, len(labels) - 1))
            if not self.stock3_var.get():
                self.stock3_combo.current(min(2, len(labels) - 1))

    def refresh_list(self):
        try:
            groups = db.group_list()
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))
            groups = []

        selected = self.tree.selection()
        selected_id = self.tree.item(selected[0])["values"][0] if selected else None

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.groups_by_id.clear()

        for group in groups:
            name, s1, s2, s3 = _group_display(group)
            gid = str(group["GroupID"])
            self.groups_by_id[gid] = group
            self.tree.insert("", "end", iid=gid, values=(group["GroupID"], name, s1, s2, s3))

        if selected_id is not None and str(selected_id) in self.groups_by_id:
            self.tree.selection_set(str(selected_id))
        elif self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])

        self._on_selection_changed()

    # ── Actions ───────────────────────────────────────────────────────────

    def open_selected_ledger(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Ledger", "Select a group first.")
            return
        group = self.groups_by_id.get(selection[0])
        if not group:
            return
        fresh = db.group_get(int(group["GroupID"]))
        if fresh:
            group = fresh
        open_ledger_sheet(self.winfo_toplevel(), group)

    def delete_selected_group(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Delete Group", "Select a group first.")
            return "break" if _event is not None else None

        group = self.groups_by_id.get(selection[0])
        if not group:
            return "break" if _event is not None else None

        name, s1, s2, s3 = _group_display(group)
        confirmed = messagebox.askyesno(
            "Delete Group",
            f"Delete group #{group['GroupID']} — {name}?\n\n"
            f"Stock 1: {s1}\nStock 2: {s2}\nStock 3: {s3}\n\n"
            "This cannot be undone.",
            icon="warning",
        )
        if not confirmed:
            return "break" if _event is not None else None

        try:
            db.group_delete(int(group["GroupID"]))
            self.refresh_list()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

        return "break" if _event is not None else None

    def add_group(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Enter a group name.")
            return

        s1_id = self._stock_id_from_label(self.stock1_var.get())
        s2_id = self._stock_id_from_label(self.stock2_var.get())
        s3_id = self._stock_id_from_label(self.stock3_var.get())

        if None in (s1_id, s2_id, s3_id):
            messagebox.showwarning("Validation", "Select all three stocks.")
            return
        if len({s1_id, s2_id, s3_id}) < 3:
            messagebox.showwarning("Validation", "All three stocks must be different.")
            return

        try:
            group_id = db.group_insert(name, s1_id, s2_id, s3_id)
            messagebox.showinfo("Success", f"Group '{name}' added (ID {group_id}).")
            self.name_var.set("")
            self.refresh_list()
            if group_id is not None:
                self.tree.selection_set(str(group_id))
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
