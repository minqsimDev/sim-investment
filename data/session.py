"""
Disk-level cache wrapper for yfinance downloads.

yfinance 1.x blocks requests_cache sessions, so we cache the resulting
DataFrames ourselves. This prevents duplicate network calls when Streamlit
cache entries expire or multiple pages fetch overlapping tickers.

Cache location: <project>/.cache/yf_data/
TTL: 900 s (15 min) — fresh enough for price data, prevents hammering Yahoo.
"""
from __future__ import annotations

import hashlib
import pickle
import time
from pathlib import Path
from typing import Any

import yfinance as yf

_CACHE_DIR = Path(__file__).parent.parent / ".cache" / "yf_data"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULT_TTL = 900  # 15 min

# ── Yahoo 차트 API 직접 폴백 ──────────────────────────────────────────────────
# yfinance 라이브러리가 crumb/쿠키/레이트리밋으로 전종목 실패해도 Yahoo 데이터 자체는 살아있다.
# UA 헤더로 chart 엔드포인트를 직접 호출해 yf.download 와 동일한 (Field,Ticker) MultiIndex 로 복구.
_YH_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _range_for_start(start) -> str:
    import pandas as pd
    from datetime import date
    try:
        days = (date.today() - pd.to_datetime(start).date()).days
    except Exception:
        return "1y"
    for tok, d in (("5d", 7), ("1mo", 31), ("3mo", 93), ("6mo", 186),
                   ("1y", 372), ("2y", 744), ("5y", 1860)):
        if days <= d:
            return tok
    return "max"


def _yahoo_chart_one(ticker: str, rng: str, interval: str):
    import json
    import urllib.request
    import pandas as pd
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?range={rng}&interval={interval}")
    req = urllib.request.Request(url, headers=_YH_HEADERS)
    with urllib.request.urlopen(req, timeout=8) as r:
        res = json.load(r)["chart"]["result"][0]
    ts = res.get("timestamp") or []
    if not ts:
        return None
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    df = pd.DataFrame({
        "Open": q.get("open"), "High": q.get("high"), "Low": q.get("low"),
        "Close": adj if adj else q.get("close"), "Volume": q.get("volume"),
    }, index=pd.to_datetime(ts, unit="s"))
    return df.dropna(how="all")


def _yahoo_direct_download(tickers, rng: str, interval: str):
    """yf.download 폴백 — chart API를 티커별 병렬 호출 후 동일 형태로 합친다."""
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor
    is_list = isinstance(tickers, list)
    tlist = tickers if is_list else [tickers]
    frames: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(len(tlist), 12) or 1) as ex:
        futs = {ex.submit(_yahoo_chart_one, t, rng, interval): t for t in tlist}
        for fut, t in futs.items():
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    frames[t] = df
            except Exception:
                pass
    if not frames:
        return pd.DataFrame()
    if not is_list:                          # 단일 티커 → 평탄한 컬럼(yfinance 단일 형태)
        return frames[tlist[0]]
    out = pd.concat(frames, axis=1)          # 컬럼=(Ticker, Field)
    return out.swaplevel(0, 1, axis=1).sort_index(axis=1)  # → (Field, Ticker) = yfinance 멀티 형태


def _cache_key(*args: Any) -> str:
    payload = str(args).encode()
    return hashlib.md5(payload).hexdigest()


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.pkl"


def _load(key: str, ttl: int) -> Any | None:
    p = _cache_path(key)
    if p.exists() and (time.time() - p.stat().st_mtime) < ttl:
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _save(key: str, data: Any) -> None:
    p = _cache_path(key)
    try:
        with open(p, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass


def cached_download(
    tickers: str | list[str],
    period: str = "1mo",
    interval: str = "1d",
    ttl: int | None = None,
    **kwargs,
):
    """Drop-in for yf.download() with disk-level caching.

    start/end(kwargs)가 주어지면 그 구간이 캐시 키·다운로드 기준(period 무시).
    yfinance는 period와 start를 함께 주면 period가 우선하므로, start가 있으면 period를 넘기지 않는다.

    ttl을 명시하지 않으면 티커가 속한 시장의 개장 여부로 자동 결정한다(장중 60s / 장마감 900s).
    """
    if isinstance(tickers, list):
        key_tickers = ",".join(sorted(tickers))
    else:
        key_tickers = tickers
    if ttl is None:
        # 첫 티커 기준 시장 개장 여부로 TTL 자동 — 장중이면 60초로 짧게 잡아 near-live 유지
        try:
            from core.market_hours import market_of, ttl_for
            first = key_tickers.split(",")[0]
            ttl = ttl_for(market_of(first))
        except Exception:
            ttl = _DEFAULT_TTL
    start = kwargs.get("start")
    end = kwargs.get("end")
    if start is not None:
        key = _cache_key(key_tickers, "range", str(start), str(end), interval)
    else:
        key = _cache_key(key_tickers, period, interval)
    cached = _load(key, ttl)
    if cached is not None:
        return cached
    import pandas as pd
    try:
        if start is not None:
            result = yf.download(tickers, interval=interval, **kwargs)
        else:
            result = yf.download(tickers, period=period, interval=interval, **kwargs)
    except Exception:
        result = pd.DataFrame()
    # yfinance 라이브러리 실패(전종목 빈 결과) 시 Yahoo 차트 API 직접 폴백으로 시세 복구
    if result is None or result.empty:
        rng = _range_for_start(start) if start is not None else period
        try:
            result = _yahoo_direct_download(tickers, rng, interval)
        except Exception:
            result = pd.DataFrame()
        if start is not None and result is not None and not result.empty:
            try:
                result = result[result.index >= pd.to_datetime(start)]
            except Exception:
                pass
    if result is not None and not result.empty:
        _save(key, result)
    return result


def cached_ticker_info(ticker: str, ttl: int = 86400) -> dict:
    """Cached yf.Ticker(ticker).info — TTL 24 h, same as target-price Streamlit cache."""
    key = _cache_key("info", ticker)
    cached = _load(key, ttl)
    if cached is not None:
        return cached
    try:
        info = yf.Ticker(ticker).info
        _save(key, info)
        return info
    except Exception:
        return {}
