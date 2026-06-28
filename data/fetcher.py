import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from core.config_loader import load_config
from data import price_source
from data.providers.fred_provider import FredProvider


def resilient_prices(prices: dict) -> dict:
    """라이브 시세 → DB 스냅샷 저장 + 실패분 DB 백필. DB 접근 실패해도 라이브 그대로 반환.
    라이브-우선 복원력 계층 — 신선도가 중요한 현재가 경로(보유 보강 등)의 단일 출처."""
    try:
        from src.database import save_quotes, load_quotes, DEFAULT_DB
    except Exception:
        return prices
    prices = dict(prices or {})
    live_ok = {tk: q for tk, q in prices.items() if q and q.get("price") is not None}
    try:
        save_quotes(live_ok, DEFAULT_DB)
    except Exception:
        pass
    missing = [tk for tk, q in prices.items() if not (q and q.get("price") is not None)]
    if missing:
        try:
            db = load_quotes(db_path=DEFAULT_DB, tickers=missing)   # 실패분만 조회(전체 스캔 회피)
        except Exception:
            db = {}
        for tk in missing:
            if tk in db:
                prices[tk] = db[tk]
    return prices


def _db_prices(all_tickers: list[str]) -> dict | None:
    """DB quotes 가 충분히 채워졌으면 {ticker: quote} 반환, 아니면 None(→ 라이브 폴백).
    앱 요청 경로(prefer_db)는 이 DB값(배치가 적재)을 즉시 읽어 API 지연을 없앤다(SSOT)."""
    try:
        from src.database import load_quotes, DEFAULT_DB
        dbq = load_quotes(db_path=DEFAULT_DB)
    except Exception:
        return None
    if not dbq:
        return None
    have = sum(1 for t in all_tickers if dbq.get(t) and dbq[t].get("price") is not None)
    if have < max(1, int(len(all_tickers) * 0.6)):   # DB 미충족(콜드/배치 전) → 라이브로
        return None
    return {t: dbq.get(t) for t in all_tickers}


def fetch_all(config: dict | None = None, force: bool = False, prefer_db: bool = False) -> dict:
    """prefer_db=True(앱 요청 경로): DB quotes 우선 읽기(즉시). 미충족 시에만 라이브.
    prefer_db=False(배치/강제): 라이브 fetch → DB 적재(앱이 읽을 SSOT를 따뜻하게 유지)."""
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
    prices = _db_prices(all_tickers) if (prefer_db and not force) else None
    if prices is not None:
        # DB 즉시 서빙(앱 경로) — 라이브 API 안 침. 신선도는 배치 스냅샷이 책임.
        macro = _fetch_macro(config)
    else:
        # 라이브 경로(배치/강제/ DB 미충족) — fetch 후 DB 적재.
        with ThreadPoolExecutor(max_workers=4) as ex:
            prices_future = ex.submit(price_source.fetch_prices_bulk, all_tickers, force)
            macro_future  = ex.submit(_fetch_macro, config)
            prices = prices_future.result(timeout=45)
            macro  = macro_future.result(timeout=15)
        # 복원력 + DB-서빙: 라이브 성공분은 DB 스냅샷으로 저장(배치·앱이 DB를 따뜻하게 유지),
        # 라이브 실패(None)분은 DB 마지막값(last-known-good)으로 백필 → 소스 장애에도 화면 유지.
        prices = resilient_prices(prices)

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
