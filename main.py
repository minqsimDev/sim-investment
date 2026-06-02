"""
SIMvest CLI — daily data pipeline.
Usage: python main.py

Fetches price history → calculates indicators → saves to SQLite → prints summary.
Run once a day (e.g. via cron or manual trigger) to populate the dashboard DB pages.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from core.config_loader import load_config
from data.fetcher import fetch_all
from src.indicators import build_summary
from src.risk import compute_regime_signals
from src.database import (
    DEFAULT_DB, init_db,
    save_prices, save_indicator_summary, save_risk_signals, save_macro,
)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", "{:,.2f}".format)


def main():
    config = load_config()
    print(f"SIMvest  |  base currency: {config['user']['base_currency']}")

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

    # ── Print summary ─────────────────────────────────────────────────────────
    if summary.empty:
        print("\nNo indicator data to display.")
        return

    order = ["my_etf", "benchmark", "us_stock", "commodity", "fx"]
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

    print("Done. Dashboard pages will reflect this data on next load.")


if __name__ == "__main__":
    main()
