import json
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator, Optional

from dotenv import load_dotenv
import pyodbc
from pyodbc import connect as connect_db

load_dotenv()

_DRIVER_PREFERENCE = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


def _resolve_driver() -> str:
    override = os.environ.get("AI_DB_DRIVER", "").strip()
    installed = pyodbc.drivers()
    installed_lookup = {driver.casefold(): driver for driver in installed}

    if override:
        driver = installed_lookup.get(override.casefold())
        if driver:
            return driver
        if override in installed:
            return override
        raise RuntimeError(
            f"Configured AI_DB_DRIVER '{override}' is not installed. "
            f"Available drivers: {', '.join(installed) or 'none'}"
        )

    for preferred in _DRIVER_PREFERENCE:
        if preferred in installed:
            return preferred

    for driver in installed:
        if "sql server" in driver.casefold():
            return driver

    raise RuntimeError(
        "No SQL Server ODBC driver found. Install 'ODBC Driver 18 for SQL Server' "
        "or set AI_DB_DRIVER to an installed driver. "
        f"Available drivers: {', '.join(installed) or 'none'}"
    )


def _driver_options(driver: str, trusted: bool) -> str:
    if "ODBC Driver 18" in driver:
        if trusted:
            return "Encrypt=optional;TrustServerCertificate=yes;"
        return "Encrypt=yes;TrustServerCertificate=no;"
    if "ODBC Driver 17" in driver:
        if trusted:
            return "Encrypt=optional;"
        return "Encrypt=yes;"
    return ""


def db_connection():
    trusted = os.environ.get("AI_DB_TRUSTED", "0") in ("1", "true", "True", "yes")
    server = os.environ.get("AI_DB_SERVER", "cg-test.database.windows.net,1433")
    database = os.environ.get("AI_DB_DATABASE", "OpenAI")
    driver = _resolve_driver()
    options = _driver_options(driver, trusted)

    if trusted:
        cnxn_str = (
            f"DRIVER={{{driver}}};"
            "MARS_Connection=no;"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"{options}"
            "Trusted_Connection=yes;"
            "APP=Stock Trading;"
        )
    else:
        login = os.environ.get("AI_DB_LOGIN", "UserService")
        password = os.environ.get("AI_DB_PASSWORD", "")
        cnxn_str = (
            f"DRIVER={{{driver}}};"
            "MARS_Connection=no;"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={login};"
            f"PWD={password};"
            f"{options}"
            "APP=Stock Trading;"
        )

    cnxn = connect_db(cnxn_str, timeout=30)
    cnxn.autocommit = True
    return cnxn


@contextmanager
def get_cursor() -> Iterator[Any]:
    conn = db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def _parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    if hasattr(value, "date"):
        return value.date()
    raise TypeError(f"Unsupported date value: {value!r}")


def _row_to_dict(cursor, row) -> dict:
    columns = [column[0] for column in cursor.description]
    result = {}
    for column, value in zip(columns, row):
        if isinstance(value, Decimal):
            result[column] = float(value)
        elif isinstance(value, datetime):
            result[column] = value.date() if column.endswith("Date") else value
        elif isinstance(value, str) and column.endswith("Date"):
            result[column] = _parse_date(value)
        else:
            result[column] = value
    return result


def _odbc_param(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _odbc_params(params: tuple) -> tuple:
    return tuple(_odbc_param(value) for value in params)


def fetch_all(proc: str, params: tuple = ()) -> list[dict]:
    with get_cursor() as cursor:
        if params:
            placeholders = ", ".join("?" for _ in params)
            cursor.execute(f"EXEC {proc} {placeholders}", _odbc_params(params))
        else:
            cursor.execute(f"EXEC {proc}")
        if not cursor.description:
            return []
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]


def fetch_one(proc: str, params: tuple = ()) -> Optional[dict]:
    rows = fetch_all(proc, params)
    return rows[0] if rows else None


def execute_proc(proc: str, params: tuple = ()) -> Optional[dict]:
    return fetch_one(proc, params)


def country_insert(name: str) -> Optional[int]:
    row = execute_proc("stocks.Country_Insert", (name,))
    return int(row["CountryID"]) if row and row.get("CountryID") is not None else None


def country_list() -> list[dict]:
    return fetch_all("stocks.Country_List")


def exchange_insert(country_id: int, name: str, yahoo_suffix: str = "") -> Optional[int]:
    row = execute_proc(
        "stocks.Exchange_Insert",
        (country_id, name, yahoo_suffix or None),
    )
    return int(row["ExchangeID"]) if row and row.get("ExchangeID") is not None else None


def exchange_list(country_id: Optional[int] = None) -> list[dict]:
    if country_id is None:
        return fetch_all("stocks.Exchange_List")
    return fetch_all("stocks.Exchange_List", (country_id,))


def stock_insert(exchange_id: int, ticker: str, full_name: str) -> Optional[int]:
    row = execute_proc("stocks.Stock_Insert", (exchange_id, ticker, full_name))
    return int(row["StockID"]) if row and row.get("StockID") is not None else None


def stock_delete(stock_id: int) -> None:
    execute_proc("stocks.Stock_Delete", (stock_id,))


def stock_list(exchange_id: Optional[int] = None) -> list[dict]:
    if exchange_id is None:
        return fetch_all("stocks.Stock_List")
    return fetch_all("stocks.Stock_List", (exchange_id,))


def stock_list_for_price_pull() -> list[dict]:
    return fetch_all("stocks.Stock_ListForPricePull")


def stock_price_get_latest_date(stock_id: int) -> Optional[date]:
    row = execute_proc("stocks.StockPrice_GetLatestDate", (stock_id,))
    if not row:
        return None
    latest = row.get("LatestDate")
    if latest is None:
        return None
    return _parse_date(latest)


def stock_price_get_overlap(stock_id: int, from_date: date, to_date: date) -> list[dict]:
    return fetch_all("stocks.StockPrice_GetOverlap", (stock_id, from_date, to_date))


def stock_price_list(stock_id: int) -> list[dict]:
    return fetch_all("stocks.StockPrice_List", (stock_id,))


def stock_price_apply_adjustment(stock_id: int, factor: float) -> int:
    row = execute_proc("stocks.StockPrice_ApplyAdjustment", (stock_id, factor))
    return int(row["RowsAdjusted"]) if row and row.get("RowsAdjusted") is not None else 0


def stock_price_merge(stock_id: int, prices: list[dict]) -> int:
    payload = json.dumps(prices, default=str)
    row = execute_proc("stocks.StockPrice_Merge", (stock_id, payload))
    return int(row["RowsMerged"]) if row and row.get("RowsMerged") is not None else 0


def pair_insert(primary_stock_id: int, secondary_stock_id: int) -> Optional[int]:
    row = execute_proc("stocks.Pair_Insert", (primary_stock_id, secondary_stock_id))
    return int(row["PairID"]) if row and row.get("PairID") is not None else None


def pair_list() -> list[dict]:
    return fetch_all("stocks.Pair_List")


def pair_delete(pair_id: int) -> None:
    execute_proc("stocks.Pair_Delete", (pair_id,))
