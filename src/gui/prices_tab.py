import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from src.services.price_sync import pull_missing_prices


class PricesTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)

        self.pull_button = ttk.Button(self, text="Pull Missing Prices", command=self.start_pull)
        self.pull_button.pack(anchor="w")

        self.log = scrolledtext.ScrolledText(self, height=24, width=100, state="disabled")
        self.log.pack(fill="both", expand=True, pady=(12, 0))

    def append_log(self, message: str):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_pull(self):
        self.pull_button.configure(state="disabled")
        self.append_log("Starting price pull...")

        def worker():
            try:
                pull_missing_prices(self._thread_safe_log)
            finally:
                self.after(0, lambda: self.pull_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _thread_safe_log(self, message: str):
        self.after(0, lambda: self.append_log(message))
