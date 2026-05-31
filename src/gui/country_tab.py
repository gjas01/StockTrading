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
        self.columnconfigure(1, weight=1)

    def add_country(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Enter a country name.")
            return
        try:
            country_id = db.country_insert(name)
            messagebox.showinfo("Success", f"Country added (ID {country_id}).")
            self.name_var.set("")
            for callback in self.refresh_callbacks:
                callback()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
