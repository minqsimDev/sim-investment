import streamlit as st
from data.fetcher import fetch_all
from core.config_loader import load_config as _load_config_raw

_TP_TICKERS = ["NVDA", "TSM", "AMD", "AVGO", "MU", "MSFT", "AAPL", "META", "AMZN", "GOOGL", "TSLA", "ASML"]


# Note: TTL 1800s (30min). Tradeoff — quote prices freeze for 30 min between auto-refreshes.
# User can force refresh via the navbar refresh icon (?refresh=1) which clears all caches.
@st.cache_data(ttl=1800, show_spinner=False)
def load_market_data(_bucket: int = 0) -> dict:
    """Shared process-level cache for all pages. One call per 30 min regardless of which page loads first.

    _bucket: 장중 자동 갱신용 캐시 버스팅 키. 기본 0(=종전 30분 캐시). 장중 라이브를 원하는 페이지는
    core.market_hours.live_bucket(...)을 넘기면 개장 중 60초마다 캐시가 자연 만료된다.
    """
    return fetch_all()


@st.cache_data(ttl=86400, show_spinner=False)
def load_app_config() -> dict:
    """YAML config — parsed once per day. Same content unless the file changes."""
    return _load_config_raw()


@st.cache_data(ttl=900, show_spinner=False)
def batch_close_history(tickers_key: str, period: str = "6mo", _bucket: int = 0) -> dict:
    """티커 묶음의 종가 시계열을 1회 배치 다운로드. {ticker: Close Series}.
    여러 페이지(미국·한국·크립토·ETF)가 같은 패턴으로 쓰던 로더를 단일 캐시로 통합.
    tickers_key=콤마조인(캐시 키) · _bucket=장중 캐시 버스팅 키."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period=period, interval="1d",
                              progress=False, auto_adjust=True)
        if raw is None or raw.empty:
            return {}
        out, multi = {}, len(tickers) > 1
        for tk in tickers:
            try:
                closes = raw["Close"][tk].dropna() if multi else raw["Close"].dropna()
                if not closes.empty:
                    out[tk] = closes
            except Exception:
                pass
        return out
    except Exception:
        return {}


def series_last_n(closes, n: int = 63) -> list:
    """종가 시리즈의 최근 n개 → float 리스트(스파크라인용). 비거나 None이면 []."""
    if closes is None or getattr(closes, "empty", True):
        return []
    return [float(v) for v in closes.iloc[-n:].tolist()]


def compute_live_indicators(closes) -> dict:
    """종가에서 1W/1M/3M/MA20 이격·추세 직접 산출(DB 지표 없을 때 라이브 폴백).
    반환 키는 표/UI에서 그대로 쓰는 한글 라벨."""
    if closes is None or getattr(closes, "empty", True):
        return {"1W %": None, "1M %": None, "3M %": None, "MA20 이격%": None, "추세": "—"}

    def _ret(n):
        if len(closes) < n + 1:
            return None
        past = float(closes.iloc[-(n + 1)])
        now = float(closes.iloc[-1])
        return round((now - past) / past * 100, 2) if past != 0 else None

    latest = float(closes.iloc[-1])
    ma20 = float(closes.iloc[-20:].mean()) if len(closes) >= 20 else None
    ma60 = float(closes.iloc[-60:].mean()) if len(closes) >= 60 else None
    if ma20 and ma60:
        trend = "상승" if (latest > ma20 > ma60) else ("하락" if (latest < ma20 < ma60) else "중립")
    elif ma20:
        trend = "상승" if latest > ma20 else "하락"
    else:
        trend = "—"
    return {
        "1W %":      _ret(5),
        "1M %":      _ret(21),
        "3M %":      _ret(63),
        "MA20 이격%": round((latest - ma20) / ma20 * 100, 2) if ma20 else None,
        "추세":       trend,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def load_indicator_summary_cached(db_path: str) -> "object":
    """SQLite indicator summary — 30 min cache to skip repeated disk reads per render."""
    from src.database import load_latest_indicator_summary
    return load_latest_indicator_summary(db_path)


@st.cache_data(ttl=1800, show_spinner=False)
def load_risk_signals_cached(db_path: str) -> "object":
    """SQLite risk signals — 30 min cache to skip repeated disk reads per render."""
    from src.database import load_latest_risk_signals
    return load_latest_risk_signals(db_path)


@st.cache_data(ttl=86400, show_spinner=False)
def load_target_prices() -> dict[str, float]:
    """Analyst consensus target prices — shared 24h cache across all pages."""
    import yfinance as yf
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor

    def _one(tk: str) -> tuple[str, float | None]:
        try:
            from data.session import cached_ticker_info
            info = cached_ticker_info(tk)
            tp = info.get("targetMeanPrice") or info.get("targetMedianPrice")
            if tp is not None and not pd.isna(float(tp)):
                return tk, float(tp)
        except Exception:
            pass
        return tk, None

    with ThreadPoolExecutor(max_workers=min(len(_TP_TICKERS), 12)) as ex:
        pairs = list(ex.map(_one, _TP_TICKERS))
    return {tk: tp for tk, tp in pairs if tp is not None}


def clear_market_cache() -> None:
    load_market_data.clear()
