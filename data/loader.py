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
