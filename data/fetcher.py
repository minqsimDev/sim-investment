import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from core.config_loader import load_config
from data import price_source
from data.providers.fred_provider import FredProvider


def fetch_all(config: dict | None = None, force: bool = False) -> dict:
    if config is None:
        config = load_config()

    etf_tickers    = [e["ticker"] for e in config["my_etfs"]]
    bench_tickers  = [e["ticker"] for e in config["benchmark_etfs"]]
    stock_tickers  = [s["ticker"] for s in config["us_stocks"]]
    kr_tickers     = [s["ticker"] for s in config.get("kr_stocks", [])]
    comm_tickers   = list(config["commodities"].values())
    fx_tickers     = [v["ticker"] for v in config["fx"].values()]
    crypto_tickers = [c["ticker"] for c in config.get("crypto", [])]
    holding_tickers = [
        h["ticker"]
        for h in config.get("holdings", [])
        if h.get("ticker") and h.get("asset_class", h.get("category", "")).lower() != "cash"
    ]

    all_tickers = etf_tickers + bench_tickers + stock_tickers + kr_tickers + comm_tickers + fx_tickers + crypto_tickers + holding_tickers

    # Run yfinance bulk download and FRED macro fetch in parallel
    # 토스 우선 + yfinance 폴백(지시서 3장). 토스 전일대비는 캔들 조회라
    # 첫 호출(콜드 캐시)이 길 수 있어 타임아웃을 넉넉히 둔다(이후 당일 캐시).
    with ThreadPoolExecutor(max_workers=4) as ex:
        prices_future = ex.submit(price_source.fetch_prices_bulk, all_tickers, force)
        macro_future  = ex.submit(_fetch_macro, config)
        prices = prices_future.result(timeout=45)
        macro  = macro_future.result(timeout=15)

    results = {
        "fetched_at": datetime.now().isoformat(),
        "my_etfs":    _build_price_df(config["my_etfs"],       prices, extra_cols=["name", "category", "benchmark", "hedged"]),
        "benchmarks": _build_price_df(config["benchmark_etfs"], prices, extra_cols=["name", "category"]),
        "us_stocks":  _build_price_df(config["us_stocks"],     prices, extra_cols=["name", "sector", "mktcap_rank", "role"]),
        "kr_stocks":  _build_price_df(config.get("kr_stocks", []), prices, extra_cols=["name", "sector", "mktcap_rank"]),
        "commodities": _build_commodities_df(config["commodities"], prices),
        "fx":         _build_fx_df(config["fx"], prices),
        "macro":      macro,
        "crypto":     _build_price_df(config.get("crypto", []), prices, extra_cols=["name", "symbol", "category"]),
        "holdings":   _build_holdings_df(config.get("holdings", []), prices),
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


def _build_holdings_df(holdings: list[dict], prices: dict) -> pd.DataFrame:
    rows = []
    for asset in holdings:
        ticker = asset.get("ticker", "")
        p = prices.get(ticker) if ticker else None
        row = dict(asset)
        row["ticker"] = ticker
        row["price"] = asset.get("price", p["price"] if p else "N/A")
        row["prev_close"] = asset.get("prev_close", p["prev_close"] if p else "N/A")
        row["change"] = asset.get("change", p["change"] if p else "N/A")
        row["change_pct"] = asset.get("change_pct", p["change_pct"] if p else "N/A")
        rows.append(row)
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
                "prev_value": data.get("prev_value") if data else None,
                "year_ago_value": data.get("year_ago_value") if data else None,
                "date": data["date"] if data else "N/A",
            })
        return pd.DataFrame(rows)
    except EnvironmentError:
        return pd.DataFrame(columns=["key", "series_id", "value", "prev_value", "year_ago_value", "date"])
