"""
Analyst price targets.
- Consensus (yfinance): Yahoo Finance aggregated mean/high/low
- Individual (FMP):     Per-analyst price targets with firm name and date
"""
from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

_FMP_KEY        = os.getenv("FMP_API_KEY", "")
_FMP_BASE       = "https://financialmodelingprep.com/api"   # legacy v3/v4
_FMP_STABLE     = "https://financialmodelingprep.com"       # new stable API

_REC_KOR = {
    "strong_buy":  "강력매수",
    "buy":         "매수",
    "hold":        "보유",
    "underperform":"시장하회",
    "sell":        "매도",
    "strong_sell": "강력매도",
}


def fmp_available() -> bool:
    """True when a non-empty FMP API key is configured."""
    return bool(_FMP_KEY and _FMP_KEY.strip())


# ── Consensus (yfinance) ──────────────────────────────────────────────────────

def _safe(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _fetch_one_yf(tk: str) -> dict:
    row: dict = {"ticker": tk}
    try:
        info = yf.Ticker(tk).info
        cur  = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        mean = _safe(info.get("targetMeanPrice"))
        high = _safe(info.get("targetHighPrice"))
        low  = _safe(info.get("targetLowPrice"))
        rec  = info.get("recommendationKey", "")
        n    = info.get("numberOfAnalystOpinions")
        upside = round((mean - cur) / cur * 100, 1) if mean and cur else None
        row.update({
            "현재가":     cur,
            "목표가_평균": mean,
            "목표가_최고": high,
            "목표가_최저": low,
            "상승여력%":  upside,
            "투자의견":   _REC_KOR.get(rec, rec) if rec and rec.lower() not in ("none", "na", "") else "—",
            "애널리스트수": int(n) if n else None,
            "시총":       _safe(info.get("marketCap")),   # 산점도 점 크기·상위 라벨 랭킹용
        })
    except Exception:
        pass
    return row


def fetch_analyst_targets(tickers: list[str]) -> pd.DataFrame:
    """Yahoo Finance consensus targets for a list of tickers (parallelized)."""
    if not tickers:
        return pd.DataFrame(columns=[
            "ticker", "현재가", "목표가_평균", "목표가_최고", "목표가_최저",
            "상승여력%", "투자의견", "애널리스트수", "시총",
        ])
    with ThreadPoolExecutor(max_workers=min(len(tickers), 10)) as ex:
        futures = {ex.submit(_fetch_one_yf, tk): tk for tk in tickers}
        rows = [f.result() for f in as_completed(futures)]
    rows.sort(key=lambda r: tickers.index(r["ticker"]))
    return pd.DataFrame(rows)


# ── Individual analyst targets (FMP) ─────────────────────────────────────────

def _fmp_get(endpoint: str, params: dict) -> list | None:
    """GET from FMP stable API. Returns parsed JSON list or None on error."""
    try:
        resp = requests.get(
            f"{_FMP_STABLE}/stable/{endpoint}",
            params={**params, "apikey": _FMP_KEY},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data if isinstance(data, list) else None
    except Exception:
        return None


def fetch_fmp_target_trend(ticker: str) -> dict | None:
    """
    Fetch price target trend from FMP for a single ticker.
    Combines:
      - /stable/price-target-summary  → avg targets by period + analyst count
      - /stable/price-target-consensus → high / low / consensus / median

    Returns a dict with keys:
      lastMonth_avg, lastMonth_count,
      lastQuarter_avg, lastQuarter_count,
      lastYear_avg, lastYear_count,
      consensus, median, high, low
    or None if unavailable.
    """
    if not fmp_available():
        return None

    result: dict = {}

    summary = _fmp_get("price-target-summary", {"symbol": ticker})
    if summary:
        s = summary[0]
        result.update({
            "lastMonth_avg":     s.get("lastMonthAvgPriceTarget"),
            "lastMonth_count":   s.get("lastMonthCount"),
            "lastQuarter_avg":   s.get("lastQuarterAvgPriceTarget"),
            "lastQuarter_count": s.get("lastQuarterCount"),
            "lastYear_avg":      s.get("lastYearAvgPriceTarget"),
            "lastYear_count":    s.get("lastYearCount"),
        })

    consensus = _fmp_get("price-target-consensus", {"symbol": ticker})
    if consensus:
        c = consensus[0]
        result.update({
            "consensus": c.get("targetConsensus"),
            "median":    c.get("targetMedian"),
            "high":      c.get("targetHigh"),
            "low":       c.get("targetLow"),
        })

    return result if result else None


def fetch_fmp_target_trends_bulk(tickers: list[str]) -> dict[str, dict | None]:
    """Fetch FMP target trends for multiple tickers in parallel."""
    if not tickers or not fmp_available():
        return {tk: None for tk in tickers}

    def _fetch(tk):
        return tk, fetch_fmp_target_trend(tk)

    with ThreadPoolExecutor(max_workers=min(len(tickers), 5)) as ex:
        return dict(ex.map(_fetch, tickers))
