import tkinter as tk
from tkinter import ttk

from src.gui.country_tab import CountryTab
from src.gui.exchange_tab import ExchangeTab
from src.gui.pair_tab import PairTab
from src.gui.prices_tab import PricesTab
from src.gui.stock_tab import StockTab


class StockTradingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Stock Trading")
        self.geometry("1000x700")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.exchange_tab = ExchangeTab(notebook)
        self.pair_tab = PairTab(notebook)
        self.stock_tab = StockTab(notebook, refresh_callbacks=[self.pair_tab.refresh_stocks])
        self.country_tab = CountryTab(
            notebook,
            refresh_callbacks=[self.exchange_tab.refresh_countries],
        )
        self.exchange_tab.refresh_callbacks = [self.stock_tab.refresh_exchanges]
        self.prices_tab = PricesTab(notebook)

        notebook.add(self.country_tab, text="Country")
        notebook.add(self.exchange_tab, text="Exchange")
        notebook.add(self.stock_tab, text="Stock")
        notebook.add(self.pair_tab, text="Pair")
        notebook.add(self.prices_tab, text="Prices")

        self.bind("<Visibility>", self._on_visible)

    def _on_visible(self, _event):
        self.country_tab.refresh_list()
        self.exchange_tab.refresh_countries()
        self.exchange_tab.refresh_list()
        self.stock_tab.refresh_exchanges()
        self.stock_tab.refresh_list()


def main():
    app = StockTradingApp()
    app.mainloop()
