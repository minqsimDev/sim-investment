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
    return fetch_all(prefer_db=True)   # 앱은 DB(배치 적재) 우선 — API 지연 제거(SSOT). 미충족 시 라이브 폴백.


@st.cache_data(ttl=900, show_spinner=False)
def batch_close_history(tickers_key: str, period: str = "6mo", _bucket: int = 0) -> dict:
    """티커 묶음의 종가 시계열을 1회 배치 다운로드. {ticker: Close Series}.
    여러 페이지(미국·한국·크립토·ETF)가 같은 패턴으로 쓰던 로더를 단일 캐시로 통합.
    tickers_key=콤마조인(캐시 키) · _bucket=장중 캐시 버스팅 키."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    # DB 우선(배치가 백필한 price_history) → 미존재 종목만 라이브 보강. 차트·스파크라인 가속.
    try:
        from src.database import load_close_history, DEFAULT_DB
        from datetime import date, timedelta
        _days = {"5d": 8, "1mo": 33, "3mo": 96, "6mo": 190, "1y": 372,
                 "2y": 740, "5y": 1850, "ytd": 372, "max": 3000}.get(period, 190)
        since = (date.today() - timedelta(days=_days)).isoformat()
        out = {t: s for t, s in load_close_history(tickers, since, DEFAULT_DB).items()
               if s is not None and len(s) >= 2}
        missing = [t for t in tickers if t not in out]
        if missing:
            from data import price_source
            live = price_source.fetch_close_history(missing, period) or {}
            out.update(live)
            # 라이브로 가져온 종목은 DB에 적재 → 다음 조회부터 DB 히트(자가 치유, 배치 미백필분 흡수)
            try:
                from src.database import save_close_history
                save_close_history(live, DEFAULT_DB)
            except Exception:
                pass
        return out
    except Exception:
        try:
            from data import price_source
            return price_source.fetch_close_history(tickers, period)
        except Exception:
            return {}


@st.cache_data(ttl=900, show_spinner=False)
def batch_history(tickers_key: str, period: str = "1y", _bucket: int = 0) -> dict:
    """OHLCV 히스토리 배치 → {ticker: DataFrame[Close, Volume]}. price_source 단일 진입점.
    거래량이 필요한 ETF 규모·시장 스파크라인용(close-only는 batch_close_history)."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    try:
        from data import price_source
        return price_source.fetch_history(tickers, period)
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def batch_quotes(tickers_key: str, _bucket: int = 0) -> dict:
    """보강 시세를 DB(quotes, 배치 적재) 우선으로 1회 조회 → 미존재(계정별 비주류 보유)만 라이브 + 자가 적재.
    batch_close_history 와 동일한 DB-first→missing→live→self-heal 패턴의 quotes판(UI가 src.database·
    price_source를 직접 만지지 않게 로더 계층에 단일화). 60초 캐시. tickers_key=콤마조인(캐시 키)."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    try:
        from src.database import load_quotes, DEFAULT_DB
        out = {t: q for t, q in load_quotes(db_path=DEFAULT_DB, tickers=tickers).items()
               if q.get("price") is not None}
    except Exception:
        out = {}
    missing = [t for t in tickers if t not in out]
    if missing:
        from data import price_source
        live = price_source.fetch_prices_bulk(missing) or {}
        out.update(live)
        try:   # 라이브로 가져온 비주류 보유는 DB에 적재 → 다음부터 DB 히트(자가 치유)
            from src.database import save_quotes, DEFAULT_DB
            save_quotes({t: q for t, q in live.items() if q and q.get("price") is not None}, DEFAULT_DB)
        except Exception:
            pass
    return out


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
def load_risk_signals_cached(db_path: str) -> "object":
    """SQLite risk signals — 30 min cache to skip repeated disk reads per render."""
    from src.database import load_latest_risk_signals
    return load_latest_risk_signals(db_path)


@st.cache_data(ttl=86400, show_spinner=False)
def load_target_prices() -> dict[str, float]:
    """Analyst consensus target prices — 네이버 금융 단일 소스(yfinance 경로 제거).
    애널리스트 전망 전반과 동일 출처로 일원화 → 목표가/상승여력 표시 일관성 확보. 24h 캐시."""
    import pandas as pd
    from src.analyst_naver import fetch_naver_targets

    df = fetch_naver_targets(list(_TP_TICKERS))
    out: dict[str, float] = {}
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        tp = r.get("목표가_평균")
        if tp is not None and not pd.isna(tp):
            out[str(r["ticker"])] = float(tp)
    return out


def load_consensus_targets(tickers: list[str]):
    """애널리스트 컨센서스 — DB(배치 적재) 우선 + DB에 없는 종목만 라이브 네이버 폴백.
    네이버 비공식 API 가용성 리스크를 DB(last-known-good)로 흡수. fetch_naver_targets 드롭인 반환형."""
    import pandas as pd
    from src.analyst_naver import fetch_naver_targets, _COLS
    from src.database import load_latest_consensus, DEFAULT_DB

    tickers = [t for t in tickers if t]
    by_tk: dict = {}
    try:
        db = load_latest_consensus(DEFAULT_DB)
        if db is not None and not db.empty:
            by_tk = {r["ticker"]: r.to_dict() for _, r in db.iterrows()}
    except Exception:
        by_tk = {}
    missing = [t for t in tickers if t not in by_tk]
    if missing:
        live = fetch_naver_targets(missing)   # DB에 없는 것만 라이브
        for _, r in live.iterrows():
            by_tk[r["ticker"]] = r.to_dict()
    rows = [by_tk[t] for t in tickers if t in by_tk]
    return pd.DataFrame(rows, columns=_COLS) if rows else pd.DataFrame(columns=_COLS)


def clear_market_cache() -> None:
    load_market_data.clear()
