"""
Indicator calculations for all tracked assets.
Fetches 6 months of daily closes via yfinance (independent of the 5-day fetcher).
"""
import numpy as np
import pandas as pd
import yfinance as yf

from core.config_loader import load_config

_PERIOD = "6mo"  # enough for 3M return + 60D MA + buffer


# ── History fetch ─────────────────────────────────────────────────────────────

def _fetch_history(tickers: list[str]) -> dict[str, pd.Series]:
    if not tickers:
        return {}
    try:
        # 토스 covered 종목은 일봉 캔들, 나머지는 yfinance(지시서 — 토스 일원화)
        from data import price_source
        out = price_source.fetch_close_history(tickers, _PERIOD)
    except Exception:
        return {t: pd.Series(dtype=float, name=t) for t in tickers}
    return {t: out.get(t, pd.Series(dtype=float, name=t)) for t in tickers}


# ── Per-symbol calculations ────────────────────────────────────────────────────

def _pct_return(closes: pd.Series, n: int) -> float | None:
    """% change from n trading days ago to latest. None if insufficient data."""
    if len(closes) < n + 1:
        return None
    past = float(closes.iloc[-(n + 1)])
    now  = float(closes.iloc[-1])
    if past == 0:
        return None
    return round((now - past) / past * 100, 2)


def _calc(closes: pd.Series) -> dict:
    out = dict(
        latest_date=None, latest_close=None,
        return_1d_pct=None, return_1w_pct=None,
        return_1m_pct=None, return_3m_pct=None,
        ma_20=None, ma_60=None,
        distance_ma20_pct=None, distance_ma60_pct=None,
        volatility_20d_pct=None, trend_status="N/A",
    )
    if closes.empty:
        return out

    latest = float(closes.iloc[-1])
    out["latest_date"]  = str(closes.index[-1].date())
    out["latest_close"] = round(latest, 4)

    out["return_1d_pct"] = _pct_return(closes, 1)
    out["return_1w_pct"] = _pct_return(closes, 5)
    out["return_1m_pct"] = _pct_return(closes, 21)
    out["return_3m_pct"] = _pct_return(closes, 63)

    if len(closes) >= 20:
        ma20 = float(closes.iloc[-20:].mean())
        out["ma_20"]             = round(ma20, 4)
        out["distance_ma20_pct"] = round((latest - ma20) / ma20 * 100, 2)

    if len(closes) >= 60:
        ma60 = float(closes.iloc[-60:].mean())
        out["ma_60"]             = round(ma60, 4)
        out["distance_ma60_pct"] = round((latest - ma60) / ma60 * 100, 2)

    # 20-day realized volatility (annualized, %)
    if len(closes) >= 21:
        log_ret = np.log(closes.iloc[-21:] / closes.iloc[-21:].shift(1)).dropna()
        if len(log_ret) >= 20:
            out["volatility_20d_pct"] = round(float(log_ret.std() * np.sqrt(252) * 100), 2)

    # Trend
    ma20 = out["ma_20"]
    ma60 = out["ma_60"]
    if ma20 is not None and ma60 is not None:
        if latest > ma20 and ma20 > ma60:
            out["trend_status"] = "bullish"
        elif latest < ma20 and ma20 < ma60:
            out["trend_status"] = "bearish"
        else:
            out["trend_status"] = "neutral"

    return out


# ── Public API ────────────────────────────────────────────────────────────────

_COLS = [
    "symbol", "asset_type", "name", "latest_date", "latest_close",
    "return_1d_pct", "return_1w_pct", "return_1m_pct", "return_3m_pct",
    "ma_20", "ma_60", "distance_ma20_pct", "distance_ma60_pct",
    "volatility_20d_pct", "trend_status",
]


def build_summary(config: dict | None = None) -> pd.DataFrame:
    """Return indicator DataFrame for every tracked asset."""
    if config is None:
        config = load_config()

    assets: list[tuple[str, str, str]] = []  # (ticker, asset_type, name)
    for e in config["my_etfs"]:
        assets.append((e["ticker"], "my_etf", e["name"]))
    for b in config["benchmark_etfs"]:
        assets.append((b["ticker"], "benchmark", b["name"]))
    for s in config["us_stocks"]:
        assets.append((s["ticker"], "us_stock", s["name"]))
    for s in config.get("kr_stocks", []):
        assets.append((s["ticker"], "kr_stock", s["name"]))
    for name, ticker in config["commodities"].items():
        assets.append((ticker, "commodity", name))
    for pair, info in config["fx"].items():
        assets.append((info["ticker"], "fx", pair))
    for c in config.get("crypto", []):
        assets.append((c["ticker"], "crypto", c["name"]))

    tickers = [a[0] for a in assets]
    history = _fetch_history(tickers)

    rows = []
    for ticker, asset_type, name in assets:
        ind = _calc(history.get(ticker, pd.Series(dtype=float)))
        rows.append({"symbol": ticker, "asset_type": asset_type, "name": name, **ind})

    return pd.DataFrame(rows, columns=_COLS)
