import tkinter as tk
from tkinter import messagebox, ttk

from src import db


class CountryTab(ttk.Frame):
    def __init__(self, master, refresh_callbacks=None):
        super().__init__(master, padding=12)
        self.refresh_callbacks = refresh_callbacks or []

        ttk.Label(self, text="Country name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=40).grid(row=0, column=1, padx=8, sticky="ew")
        ttk.Button(self, text="Add Country", command=self.add_country).grid(row=0, column=2)

        ttk.Label(self, text="Countries").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(16, 4)
        )

        list_frame = ttk.Frame(self)
        list_frame.grid(row=2, column=0, columnspan=3, sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        self.tree = ttk.Treeview(list_frame, columns=("id", "name"), show="headings", height=12)
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.column("id", width=80, stretch=False)
        self.tree.column("name", width=300, stretch=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.refresh_list()

    def refresh_list(self):
        try:
            countries = db.country_list()
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))
            countries = []

        for item in self.tree.get_children():
            self.tree.delete(item)
        for country in countries:
            self.tree.insert("", "end", values=(country["CountryID"], country["Name"]))

    def add_country(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Enter a country name.")
            return
        try:
            country_id = db.country_insert(name)
            messagebox.showinfo("Success", f"Country added (ID {country_id}).")
            self.name_var.set("")
            self.refresh_list()
            for callback in self.refresh_callbacks:
                callback()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
