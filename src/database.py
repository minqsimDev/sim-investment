"""
SQLite storage for SIM INVESTMENT.
Strategy: INSERT OR REPLACE on (date, symbol) for prices / fx_rates / macro.
indicator_summary and risk_signals append every run (history preserved).
Tradeoff: multiple runs same day → multiple rows in summary/signals tables,
but only the latest run_date matters for queries.
"""
import math
import os
import sqlite3
from datetime import date as _date, datetime as _dt, timedelta as _td
from pathlib import Path

import pandas as pd

# 기본은 소스트리 내 data/ (로컬 dev). Docker 운영에선 DB_PATH 로 패키지 밖 영속 경로를
# 지정한다 — data/ 는 파이썬 패키지라 볼륨으로 덮으면 코드가 가려지기 때문.
DEFAULT_DB = os.getenv("DB_PATH", "data/market_data.db")

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

-- 네이버 애널리스트 컨센서스(배치 적재). 비공식 API 가용성 리스크를 last-known-good 캐시로 흡수.
CREATE TABLE IF NOT EXISTS consensus (
    run_date      TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    target_mean   REAL,
    opinion       TEXT,
    opinion_score REAL,
    base_date     TEXT,
    coverage      REAL,
    created_at    TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (run_date, ticker)
);

-- 최신 시세 스냅샷(티커당 1행). 라이브 성공 시 갱신, 소스 장애 시 last-known-good 백필용.
CREATE TABLE IF NOT EXISTS quotes (
    ticker     TEXT PRIMARY KEY,
    price      REAL,
    prev_close REAL,
    change     REAL,
    change_pct REAL,
    currency   TEXT,
    source     TEXT,
    updated_at TEXT
);

-- 종가 히스토리(차트·스파크라인용). 배치가 1년치 백필·일 갱신, 앱은 DB-우선 읽기.
CREATE TABLE IF NOT EXISTS price_history (
    symbol TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_price_history_symbol ON price_history(symbol, date);
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


def save_consensus(df: pd.DataFrame, db_path: str = DEFAULT_DB) -> int:
    """네이버 컨센서스(fetch_naver_targets 결과) 저장. 목표가 있는 행만 적재(나머진 라이브 폴백 대상)."""
    if df is None or df.empty:
        return 0
    run_date = str(_date.today())
    sql = ("INSERT OR REPLACE INTO consensus "
           "(run_date, ticker, target_mean, opinion, opinion_score, base_date, coverage) "
           "VALUES (?,?,?,?,?,?,?)")
    rows = []
    for _, r in df.iterrows():
        tm = _f(r.get("목표가_평균"))
        if tm is None:
            continue
        rows.append((run_date, str(r.get("ticker", "")), tm,
                     str(r.get("투자의견") or ""), _f(r.get("의견점수")),
                     str(r.get("기준일") or ""), _f(r.get("커버리지"))))
    if not rows:
        return 0
    with _conn(db_path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def load_latest_consensus(db_path: str = DEFAULT_DB) -> pd.DataFrame:
    """최신 run_date 컨센서스 → fetch_naver_targets 동일 컬럼(ticker·목표가_평균·투자의견·의견점수·기준일·커버리지)."""
    try:
        with _conn(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT ticker, target_mean, opinion, opinion_score, base_date, coverage "
                "FROM consensus WHERE run_date=(SELECT MAX(run_date) FROM consensus)",
                conn,
            )
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    return df.rename(columns={
        "target_mean": "목표가_평균", "opinion": "투자의견", "opinion_score": "의견점수",
        "base_date": "기준일", "coverage": "커버리지",
    })


def save_quotes(prices: dict, db_path: str = DEFAULT_DB) -> int:
    """라이브 시세 스냅샷 저장(price 있는 것만). 소스 장애 시 백필용 last-known-good."""
    now = _dt.now().isoformat(timespec="seconds")
    rows = []
    for tk, q in (prices or {}).items():
        if not q or _f(q.get("price")) is None:
            continue
        rows.append((str(tk), _f(q.get("price")), _f(q.get("prev_close")), _f(q.get("change")),
                     _f(q.get("change_pct")), str(q.get("currency") or ""), str(q.get("source") or ""), now))
    if not rows:
        return 0
    sql = ("INSERT OR REPLACE INTO quotes "
           "(ticker, price, prev_close, change, change_pct, currency, source, updated_at) "
           "VALUES (?,?,?,?,?,?,?,?)")
    with _conn(db_path) as conn:
        conn.executemany(sql, rows)
    return len(rows)


def load_quotes(max_age_sec: int = 7 * 86400, db_path: str = DEFAULT_DB,
                tickers: list[str] | None = None) -> dict:
    """{ticker: quote dict} — max_age_sec 보다 오래된 행은 제외. fetch_prices_bulk 동일 형태(source 'db').
    tickers 지정 시 해당 티커만 SQL(WHERE IN)로 조회 → 전체 테이블 스캔 회피(보유 보강 등 소수 조회용)."""
    sql = "SELECT ticker, price, prev_close, change, change_pct, currency, updated_at FROM quotes"
    try:
        with _conn(db_path) as conn:
            if tickers:
                ph = ",".join("?" * len(tickers))
                rows = conn.execute(f"{sql} WHERE ticker IN ({ph})", tuple(tickers)).fetchall()
            else:
                rows = conn.execute(sql).fetchall()
    except Exception:
        return {}
    cutoff = _dt.now() - _td(seconds=max_age_sec)
    out: dict = {}
    for tk, price, prev, chg, chgp, cur, upd in rows:
        try:
            if upd and _dt.fromisoformat(upd) < cutoff:
                continue
        except Exception:
            pass
        out[tk] = {"price": price, "prev_close": prev, "change": chg,
                   "change_pct": chgp, "currency": cur or None, "source": "db"}
    return out


def save_close_history(hist: dict, db_path: str = DEFAULT_DB) -> int:
    """{ticker: Close Series(index=날짜)} → price_history 일괄 적재(INSERT OR REPLACE). 반환 행수."""
    rows = []
    for sym, s in (hist or {}).items():
        if s is None or getattr(s, "empty", True):
            continue
        for idx, val in s.dropna().items():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            rows.append((sym, d, float(val)))
    if not rows:
        return 0
    with _conn(db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO price_history (symbol, date, close) VALUES (?,?,?)", rows)
    return len(rows)


def load_close_history(symbols: list[str], since: str, db_path: str = DEFAULT_DB) -> dict:
    """price_history 에서 {ticker: Close Series(날짜 오름차순)} (since 이후). 없으면 {}."""
    if not symbols:
        return {}
    out: dict = {}
    try:
        ph = ",".join("?" * len(symbols))
        with _conn(db_path) as conn:
            rows = conn.execute(
                f"SELECT symbol, date, close FROM price_history "
                f"WHERE symbol IN ({ph}) AND date >= ? ORDER BY date",
                (*symbols, since),
            ).fetchall()
    except Exception:
        return {}
    by_sym: dict = {}
    for sym, d, close in rows:
        by_sym.setdefault(sym, []).append((d, close))
    for sym, pairs in by_sym.items():
        idx = pd.to_datetime([d for d, _ in pairs])
        out[sym] = pd.Series([c for _, c in pairs], index=idx, name="Close")
    return out


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

