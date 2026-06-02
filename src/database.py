"""
SQLite storage for SIMvest.
Strategy: INSERT OR REPLACE on (date, symbol) for prices / fx_rates / macro.
indicator_summary and risk_signals append every run (history preserved).
Tradeoff: multiple runs same day → multiple rows in summary/signals tables,
but only the latest run_date matters for queries.
"""
import math
import sqlite3
from datetime import date as _date
from pathlib import Path

import pandas as pd

DEFAULT_DB = "data/market_data.db"

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS prices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT    NOT NULL,
    symbol     TEXT    NOT NULL,
    asset_type TEXT,
    name       TEXT,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    source     TEXT    DEFAULT 'yfinance',
    created_at TEXT    DEFAULT (datetime('now')),
    UNIQUE(date, symbol)
);

CREATE TABLE IF NOT EXISTS indicator_summary (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date           TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    asset_type         TEXT,
    name               TEXT,
    latest_date        TEXT,
    latest_close       REAL,
    return_1d_pct      REAL,
    return_1w_pct      REAL,
    return_1m_pct      REAL,
    return_3m_pct      REAL,
    ma_20              REAL,
    ma_60              REAL,
    distance_ma20_pct  REAL,
    distance_ma60_pct  REAL,
    volatility_20d_pct REAL,
    trend_status       TEXT,
    created_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS macro_indicators (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    series_id  TEXT NOT NULL,
    name       TEXT,
    value      REAL,
    source     TEXT DEFAULT 'FRED',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, series_id)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    name       TEXT,
    value      REAL,
    source     TEXT DEFAULT 'yfinance',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(date, symbol)
);

CREATE TABLE IF NOT EXISTS risk_signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    signal_name TEXT NOT NULL,
    level       TEXT,
    score       REAL,
    comment     TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL UNIQUE,
    file_path   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS news (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    published_at   TEXT,
    source         TEXT,
    headline       TEXT,
    category       TEXT,
    related_assets TEXT,
    summary        TEXT,
    url            TEXT,
    impact_level   TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);
"""


# ── Core helpers ──────────────────────────────────────────────────────────────

def _conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _f(v) -> float | None:
    """Safe float conversion; returns None for NaN/None."""
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def init_db(db_path: str = DEFAULT_DB) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _conn(db_path) as conn:
        conn.executescript(_DDL)


def save_prices(df: pd.DataFrame, db_path: str = DEFAULT_DB) -> int:
    """Save latest close from indicator_summary df into prices table."""
    if df.empty:
        return 0
    today = str(_date.today())
    rows = [
        (today, str(r.get("symbol", "")), str(r.get("asset_type", "")),
         str(r.get("name", "")), None, None, None, _f(r.get("latest_close")), None)
        for _, r in df.iterrows()
    ]
    sql = ("INSERT OR REPLACE INTO prices "
           "(date, symbol, asset_type, name, open, high, low, close, volume) "
           "VALUES (?,?,?,?,?,?,?,?,?)")
    with _conn(db_path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def save_indicator_summary(df: pd.DataFrame, db_path: str = DEFAULT_DB) -> int:
    if df.empty:
        return 0
    run_date = str(_date.today())
    cols = ("run_date,symbol,asset_type,name,latest_date,latest_close,"
            "return_1d_pct,return_1w_pct,return_1m_pct,return_3m_pct,"
            "ma_20,ma_60,distance_ma20_pct,distance_ma60_pct,"
            "volatility_20d_pct,trend_status")
    sql = f"INSERT INTO indicator_summary ({cols}) VALUES ({','.join(['?']*16)})"
    rows = [
        (run_date, str(r.get("symbol", "")), str(r.get("asset_type", "")),
         str(r.get("name", "")), str(r.get("latest_date", "")),
         _f(r.get("latest_close")), _f(r.get("return_1d_pct")),
         _f(r.get("return_1w_pct")), _f(r.get("return_1m_pct")),
         _f(r.get("return_3m_pct")), _f(r.get("ma_20")), _f(r.get("ma_60")),
         _f(r.get("distance_ma20_pct")), _f(r.get("distance_ma60_pct")),
         _f(r.get("volatility_20d_pct")), str(r.get("trend_status", "")))
        for _, r in df.iterrows()
    ]
    with _conn(db_path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def save_risk_signals(signals: list[dict], db_path: str = DEFAULT_DB) -> int:
    if not signals:
        return 0
    run_date = str(_date.today())
    sql = ("INSERT INTO risk_signals (run_date, signal_name, level, score, comment) "
           "VALUES (?,?,?,?,?)")
    rows = [(run_date, s["signal"], s.get("lv", ""), None, s.get("note", ""))
            for s in signals]
    with _conn(db_path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def save_macro(df: pd.DataFrame, db_path: str = DEFAULT_DB) -> int:
    """Save FRED macro data. df must have columns: key, series_id, value, date."""
    if df.empty:
        return 0
    sql = ("INSERT OR REPLACE INTO macro_indicators (date, series_id, name, value) "
           "VALUES (?,?,?,?)")
    rows = [(str(r.get("date", "")), str(r.get("series_id", "")),
             str(r.get("key", "")), _f(r.get("value")))
            for _, r in df.iterrows()
            if r.get("value") not in (None, "N/A")]
    with _conn(db_path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def load_latest_indicator_summary(db_path: str = DEFAULT_DB) -> pd.DataFrame:
    try:
        with _conn(db_path) as conn:
            return pd.read_sql_query(
                "SELECT * FROM indicator_summary "
                "WHERE run_date=(SELECT MAX(run_date) FROM indicator_summary) "
                "ORDER BY asset_type, symbol",
                conn,
            )
    except Exception:
        return pd.DataFrame()


def load_latest_risk_signals(db_path: str = DEFAULT_DB) -> pd.DataFrame:
    try:
        with _conn(db_path) as conn:
            return pd.read_sql_query(
                "SELECT * FROM risk_signals "
                "WHERE run_date=(SELECT MAX(run_date) FROM risk_signals) "
                "ORDER BY id",
                conn,
            )
    except Exception:
        return pd.DataFrame()


def load_price_history(symbol: str, db_path: str = DEFAULT_DB) -> pd.DataFrame:
    try:
        with _conn(db_path) as conn:
            return pd.read_sql_query(
                "SELECT date, close FROM prices WHERE symbol=? ORDER BY date",
                conn, params=(symbol,),
            )
    except Exception:
        return pd.DataFrame()


def load_signal_history(limit: int = 70, db_path: str = DEFAULT_DB) -> pd.DataFrame:
    try:
        with _conn(db_path) as conn:
            return pd.read_sql_query(
                "SELECT run_date, signal_name, level FROM risk_signals "
                "ORDER BY run_date DESC LIMIT ?",
                conn, params=(limit,),
            )
    except Exception:
        return pd.DataFrame()


def save_daily_report_record(report_date: str, file_path: str,
                              db_path: str = DEFAULT_DB) -> None:
    sql = "INSERT OR REPLACE INTO daily_reports (report_date, file_path) VALUES (?,?)"
    with _conn(db_path) as conn:
        conn.execute(sql, (report_date, file_path))
