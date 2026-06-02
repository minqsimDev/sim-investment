import pandas as pd
from datetime import datetime

from core.config_loader import load_config
from data.providers.yfinance_provider import YFinanceProvider
from data.providers.fred_provider import FredProvider


def fetch_all(config: dict | None = None) -> dict:
    if config is None:
        config = load_config()

    yf = YFinanceProvider()

    etf_tickers = [e["ticker"] for e in config["my_etfs"]]
    bench_tickers = [e["ticker"] for e in config["benchmark_etfs"]]
    stock_tickers = [s["ticker"] for s in config["us_stocks"]]
    comm_tickers = list(config["commodities"].values())
    fx_tickers = [v["ticker"] for v in config["fx"].values()]

    all_tickers = etf_tickers + bench_tickers + stock_tickers + comm_tickers + fx_tickers
    prices = yf.fetch_prices_bulk(all_tickers)

    results = {
        "fetched_at": datetime.now().isoformat(),
        "my_etfs": _build_price_df(config["my_etfs"], prices, extra_cols=["name", "category", "benchmark", "hedged"]),
        "benchmarks": _build_price_df(config["benchmark_etfs"], prices, extra_cols=["name", "category"]),
        "us_stocks": _build_price_df(config["us_stocks"], prices, extra_cols=["name", "sector"]),
        "commodities": _build_commodities_df(config["commodities"], prices),
        "fx": _build_fx_df(config["fx"], prices),
        "macro": _fetch_macro(config),
    }

    return results


# ── helpers ──────────────────────────────────────────────────────────────────

def _build_price_df(assets: list[dict], prices: dict, extra_cols: list[str]) -> pd.DataFrame:
    rows = []
    for asset in assets:
        ticker = asset["ticker"]
        p = prices.get(ticker)
        row = {"ticker": ticker}
        for col in extra_cols:
            row[col] = asset.get(col, "N/A")
        row["price"] = p["price"] if p else "N/A"
        row["prev_close"] = p["prev_close"] if p else "N/A"
        row["change"] = p["change"] if p else "N/A"
        row["change_pct"] = p["change_pct"] if p else "N/A"
        rows.append(row)
    return pd.DataFrame(rows)


def _build_commodities_df(commodities: dict, prices: dict) -> pd.DataFrame:
    rows = []
    for name, ticker in commodities.items():
        p = prices.get(ticker)
        rows.append({
            "name": name,
            "ticker": ticker,
            "price": p["price"] if p else "N/A",
            "prev_close": p["prev_close"] if p else "N/A",
            "change": p["change"] if p else "N/A",
            "change_pct": p["change_pct"] if p else "N/A",
        })
    return pd.DataFrame(rows)


def _build_fx_df(fx: dict, prices: dict) -> pd.DataFrame:
    rows = []
    for pair, info in fx.items():
        ticker = info["ticker"]
        p = prices.get(ticker)
        rows.append({
            "pair": pair,
            "ticker": ticker,
            "priority": info.get("priority", "medium"),
            "rate": p["price"] if p else "N/A",
            "prev_rate": p["prev_close"] if p else "N/A",
            "change": p["change"] if p else "N/A",
            "change_pct": p["change_pct"] if p else "N/A",
        })
    return pd.DataFrame(rows)


def _fetch_macro(config: dict) -> pd.DataFrame:
    try:
        fred = FredProvider()
        series_map = config["macro"]["fred_series"]
        bulk = fred.fetch_series_bulk(series_map)
        rows = []
        for key, data in bulk.items():
            rows.append({
                "key": key,
                "series_id": series_map[key],
                "value": data["value"] if data else "N/A",
                "date": data["date"] if data else "N/A",
            })
        return pd.DataFrame(rows)
    except EnvironmentError:
        return pd.DataFrame(columns=["key", "series_id", "value", "date"])
