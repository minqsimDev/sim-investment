"""
SIM INVESTMENT CLI — daily data pipeline.
Usage: python main.py

Fetches price history → calculates indicators → saves to SQLite → prints summary.
Run once a day (e.g. via cron or manual trigger) to populate the dashboard DB pages.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from core.brand import APP_NAME
from core.config_loader import load_config
from data.fetcher import fetch_all
from src.indicators import build_summary
from src.risk import compute_regime_signals
from src.database import (
    DEFAULT_DB, init_db,
    save_prices, save_indicator_summary, save_risk_signals, save_macro, save_consensus,
)


def _consensus_universe() -> list[str]:
    """배치 적재할 컨센서스 종목(US+KR 유니버스). UI 상수에서 모으되 실패해도 배치는 계속."""
    tickers: list[str] = []
    try:
        from ui.pages.us_stocks import _STOCK_KOR
        tickers += list(_STOCK_KOR.keys())
    except Exception as e:
        print(f"  ⚠  US 유니버스 로드 실패: {e}", file=sys.stderr)
    try:
        from ui.pages.kr_stocks import _KR_UNIVERSE, _KR_NEW_LISTINGS
        tickers += [u[0] for u in _KR_UNIVERSE + _KR_NEW_LISTINGS]
    except Exception as e:
        print(f"  ⚠  KR 유니버스 로드 실패: {e}", file=sys.stderr)
    return list(dict.fromkeys(t for t in tickers if t))

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", "{:,.2f}".format)


def main():
    config = load_config()
    print(f"{APP_NAME}  |  base currency: {config['user']['base_currency']}")

    # ── DB setup ──────────────────────────────────────────────────────────────
    Path("data").mkdir(exist_ok=True)
    init_db(DEFAULT_DB)
    print(f"DB: {DEFAULT_DB}")

    # ── Fetch live snapshot + 6-month history in parallel ────────────────────
    print("Fetching live snapshot + 6-month history (parallel)...")
    live = None
    summary = pd.DataFrame()
    with ThreadPoolExecutor(max_workers=2) as ex:
        live_f    = ex.submit(fetch_all, config)
        summary_f = ex.submit(build_summary, config)
        try:
            live = live_f.result()
        except Exception as e:
            print(f"  ⚠  Live fetch failed: {e}", file=sys.stderr)
        try:
            summary = summary_f.result()
            print(f"  {len(summary)} symbols processed")
        except Exception as e:
            print(f"  ⚠  Indicator calculation failed: {e}", file=sys.stderr)

    # ── Compute risk signals ──────────────────────────────────────────────────
    signals = []
    if live is not None:
        signals = compute_regime_signals(live)
        print(f"  {len(signals)} risk signals computed")

    # ── Save to DB ────────────────────────────────────────────────────────────
    if not summary.empty:
        n = save_prices(summary, DEFAULT_DB)
        print(f"  Prices saved: {n} rows")
        n = save_indicator_summary(summary, DEFAULT_DB)
        print(f"  Indicator summary saved: {n} rows")

    if signals:
        n = save_risk_signals(signals, DEFAULT_DB)
        print(f"  Risk signals saved: {n} rows")

    if live is not None and live.get("macro") is not None and not live["macro"].empty:
        n = save_macro(live["macro"], DEFAULT_DB)
        print(f"  Macro indicators saved: {n} rows")

    # ── 네이버 애널리스트 컨센서스 적재(US+KR 유니버스) ──────────────────────────
    try:
        from src.analyst_naver import fetch_naver_targets
        universe = _consensus_universe()
        if universe:
            cdf = fetch_naver_targets(universe)
            n = save_consensus(cdf, DEFAULT_DB)
            print(f"  Consensus saved: {n}/{len(universe)} tickers (목표가 보유분)")
    except Exception as e:
        print(f"  ⚠  Consensus fetch/save failed: {e}", file=sys.stderr)

    # ── 종가 히스토리 1년 백필(차트·스파크라인 DB-우선 서빙용) ───────────────────────
    # 앱 batch_close_history 가 price_history 를 즉시 읽어 서브탭/스파크라인 첫 진입 지연 제거.
    # 백필은 yfinance 벌크(1다운로드, 빠름) — 토스 캔들 throttle 회피.
    try:
        from data.price_source import _yf_close_history
        from src.database import save_close_history
        univ: set[str] = set()
        for k in ("my_etfs", "benchmark_etfs", "us_stocks", "kr_stocks", "crypto"):
            univ |= {e["ticker"] for e in config.get(k, [])}
        univ |= set(config["commodities"].values()) | {v["ticker"] for v in config["fx"].values()}
        # 페이지·스파크라인 유니버스도 포함 → 앱이 차트로 그리는 전 종목 DB화(첫 진입도 빠르게).
        # UI 상수 형태가 바뀌어도 배치가 죽지 않게 각각 try.
        def _tk(x):
            return x[0] if isinstance(x, (list, tuple)) else x
        try:
            from ui.pages.us_stocks import _US_UNIVERSE, _US_NEW_LISTINGS, _US_BENCH
            univ |= {_tk(x) for x in _US_UNIVERSE} | {_tk(x) for x in _US_NEW_LISTINGS} | set(_US_BENCH)
        except Exception as _e: print(f"  (us universe skip: {_e})", file=sys.stderr)
        try:
            from ui.pages.kr_stocks import _KR_UNIVERSE, _KOSPI_BENCH
            univ |= {_tk(x) for x in _KR_UNIVERSE} | set(_KOSPI_BENCH)
        except Exception as _e: print(f"  (kr universe skip: {_e})", file=sys.stderr)
        try:
            from ui.pages.etf import _KR_ETF_UNIVERSE
            univ |= {x[2] if isinstance(x, (list, tuple)) and len(x) > 2 else _tk(x) for x in _KR_ETF_UNIVERSE}
        except Exception as _e: print(f"  (etf universe skip: {_e})", file=sys.stderr)
        try:
            from ui.pages.crypto import _CRYPTO_UNIVERSE
            univ |= {x[1] if isinstance(x, (list, tuple)) and len(x) > 1 else _tk(x) for x in _CRYPTO_UNIVERSE}
        except Exception as _e: print(f"  (crypto universe skip: {_e})", file=sys.stderr)
        try:
            from ui.pages.market import _CAT_POOLS, _spark_ticker_for
            for pool in _CAT_POOLS.values():
                for key, _nm, src in pool:
                    univ.add(_spark_ticker_for(key, src))
        except Exception as _e: print(f"  (spark universe skip: {_e})", file=sys.stderr)
        univ = [t for t in dict.fromkeys(univ) if t]   # dedup + 빈값 제거
        hist = _yf_close_history(univ, "1y")
        n = save_close_history(hist, DEFAULT_DB)
        print(f"  Price history saved: {n} rows ({len(hist)}/{len(univ)} tickers)")
    except Exception as e:
        print(f"  ⚠  Price history backfill failed: {e}", file=sys.stderr)

    # ── Print summary ─────────────────────────────────────────────────────────
    if summary.empty:
        print("\nNo indicator data to display.")
        return

    order = ["my_etf", "benchmark", "us_stock", "commodity", "fx", "crypto"]
    disp  = [
        "symbol", "name", "latest_date", "latest_close",
        "return_1d_pct", "return_1w_pct", "return_1m_pct", "return_3m_pct",
        "distance_ma20_pct", "distance_ma60_pct", "volatility_20d_pct", "trend_status",
    ]

    print()
    for at in order:
        grp = summary[summary["asset_type"] == at]
        if grp.empty:
            continue
        label = at.upper().replace("_", " ")
        print(f"{'─' * 90}")
        print(f"  {label}")
        print(f"{'─' * 90}")
        print(grp[[c for c in disp if c in grp.columns]].to_string(index=False))
        print()

    # Risk signals summary
    if signals:
        print("─" * 90)
        print("  RISK SIGNALS")
        print("─" * 90)
        for s in signals:
            print(f"  {s['signal']:<30}  {s['lv']:<12}  {s['note']}")
        print()

    # 텔레그램 위험 알림 — 데이터 갱신 후 규칙 평가·발송(설정된 경우). 파이프라인과 분리(best-effort).
    try:
        from src.telegram_alert import run as run_alerts, is_configured
        if is_configured():
            run_alerts(verbose=True)
    except Exception as e:
        print(f"[telegram] 알림 평가 건너뜀: {e}")

    print("Done. Dashboard pages will reflect this data on next load.")


if __name__ == "__main__":
    main()
