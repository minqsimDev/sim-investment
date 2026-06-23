"""지시서 3장 — 소스 추상화 + 폴백 레이어.

호출부는 소스를 모른다. yfinance 스타일 심볼을 그대로 입력받아 내부에서
토스/yfinance 로 라우팅한다. 반환 형태는 기존 YFinanceProvider.fetch_prices_bulk
와 동일(+currency/source) 이라 fetcher.py 에서 그대로 교체 가능.

라우팅(2장 검증 결과 기준):
  국내·미국 주식/ETF, USD/KRW   → 토스 (실패 시 yfinance 폴백)
  원자재 선물·비USD환율·지수·크립토 → yfinance (토스 미지원)

폴백 발생은 로그로 남겨 커버리지를 추적한다(지시서 3장).
"""
import logging
import time
from datetime import date

from data.providers.toss_provider import TossClient
from data.providers.yfinance_provider import YFinanceProvider

log = logging.getLogger(__name__)

_yf = YFinanceProvider()
_toss: TossClient | None = None
_prev_close_cache: dict[tuple, float | None] = {}  # (toss_sym, date) -> prev close
_CHART_THROTTLE = 0.34  # MARKET_DATA_CHART 그룹 초당 3건 한도 준수


def _toss_client() -> TossClient:
    global _toss
    if _toss is None:
        _toss = TossClient()
    return _toss


# ── 라우팅 분류 ────────────────────────────────────────────────────────────
def _classify(ticker: str) -> tuple[str, object]:
    """('toss_price', toss_sym) | ('toss_fx', (base,quote)) | ('yfinance', ticker)"""
    if ticker.endswith(".KS"):
        return ("toss_price", ticker[:-3])          # 005930.KS -> 005930
    if ticker == "USDKRW=X":
        return ("toss_fx", ("USD", "KRW"))
    if (ticker.endswith(("=F", "=X")) or ticker.startswith("^")
            or ticker == "DX-Y.NYB" or ticker.endswith("-USD")):
        return ("yfinance", ticker)                 # 선물·비USD환율·지수·크립토
    return ("toss_price", ticker)                   # 미국 티커


def _to_float(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _quote(price, prev, currency, source) -> dict:
    change = round(price - prev, 4) if price is not None and prev else None
    change_pct = round((price - prev) / prev * 100, 2) if change is not None else None
    return {"price": price, "prev_close": prev, "change": change,
            "change_pct": change_pct, "currency": currency, "source": source}


def _infer_currency(ticker: str) -> str | None:
    if ticker.endswith(".KS"):
        return "KRW"
    if ticker.endswith(("=X", "=F")) or ticker.startswith("^") or ticker.endswith("-USD"):
        return None
    return "USD"


def _toss_prev_close(toss_sym: str) -> float | None:
    """일봉으로 전일 종가 조회. 일 단위 값이라 (심볼,날짜)로 캐시."""
    key = (toss_sym, date.today())
    if key in _prev_close_cache:
        return _prev_close_cache[key]
    time.sleep(_CHART_THROTTLE)
    candles = _toss_client().get_daily_candles(toss_sym, count=2)
    prev = _to_float(candles[1]["closePrice"]) if candles and len(candles) >= 2 else None
    _prev_close_cache[key] = prev
    return prev


# ── 공개 인터페이스 ────────────────────────────────────────────────────────
def fetch_prices_bulk(tickers: list[str], force: bool = False,
                      with_change: bool = True) -> dict[str, dict | None]:
    """YFinanceProvider.fetch_prices_bulk 드롭인 대체.
    with_change=False 면 토스 전일대비(캔들) 조회를 건너뛴다(빠름)."""
    results: dict[str, dict | None] = {t: None for t in tickers}
    if not tickers:
        return results

    toss_price_map: dict[str, list[str]] = {}   # toss_sym -> [원본 ticker]
    toss_fx: dict[str, tuple] = {}              # ticker -> (base, quote)
    yf_list: list[str] = []
    for t in tickers:
        kind, key = _classify(t)
        if kind == "toss_price":
            toss_price_map.setdefault(key, []).append(t)
        elif kind == "toss_fx":
            toss_fx[t] = key
        else:
            yf_list.append(t)

    fallbacks: list[str] = []

    # 토스 현재가 (배치 1콜)
    if toss_price_map:
        try:
            prices = _toss_client().get_prices(list(toss_price_map))
        except Exception as e:
            log.warning("토스 시세 배치 실패 → 전건 yfinance 폴백: %s", e)
            prices = {}
        for toss_sym, origs in toss_price_map.items():
            p = prices.get(toss_sym)
            if not p:
                fallbacks.extend(origs)
                continue
            price = _to_float(p["lastPrice"])
            # 전일종가: 배치 응답에 있으면 그대로(종목당 캔들 호출·throttle 제거 → 첫 로딩 단축),
            # 없을 때만 일봉 캔들로 폴백.
            prev = None
            if with_change:
                prev = _to_float(p.get("prevClose"))
                if prev is None:
                    prev = _toss_prev_close(toss_sym)
            for o in origs:
                results[o] = _quote(price, prev, p.get("currency"), "toss")

    # 토스 환율 (USD/KRW)
    for o, (base, quote) in toss_fx.items():
        try:
            fx = _toss_client().get_exchange_rate(base, quote)
        except Exception:
            fx = None
        if fx:
            results[o] = _quote(_to_float(fx["rate"]), None, quote, "toss")
        else:
            fallbacks.append(o)

    # yfinance (원래 yfinance 대상 + 토스 폴백)
    if fallbacks:
        log.info("yfinance 폴백 발생(%d건): %s", len(fallbacks), fallbacks)
    yf_all = yf_list + fallbacks
    if yf_all:
        yfres = _yf.fetch_prices_bulk(yf_all, force)
        for t in yf_all:
            r = yfres.get(t)
            if r:
                results[t] = {**r, "currency": _infer_currency(t), "source": "yfinance"}

    return results


def get_quote(ticker: str, with_change: bool = True) -> dict | None:
    """단건 조회 편의 함수(지시서 3장 인터페이스)."""
    return fetch_prices_bulk([ticker], with_change=with_change).get(ticker)


# ── 종가 히스토리(일봉) ─────────────────────────────────────────────────────
# 토스 covered 종목은 일봉 캔들로, 나머지(선물·지수·비USD환율·크립토)는 yfinance.
_PERIOD_BARS = {"5d": 7, "1mo": 25, "3mo": 68, "6mo": 135, "1y": 260,
                "2y": 520, "5y": 1300, "ytd": 260, "max": 2200}


def _toss_close_series(toss_sym: str, bars: int):
    """일봉을 bars 개 이상 모아 날짜 오름차순 종가 Series 반환(yfinance Close 호환)."""
    import pandas as pd
    collected: dict = {}
    before = None
    client = _toss_client()
    while len(collected) < bars:
        time.sleep(_CHART_THROTTLE)
        candles, nxt = client.fetch_candles(toss_sym, count=200, before=before)
        if not candles:
            break
        for c in candles:
            ts, cp = c.get("timestamp"), _to_float(c.get("closePrice"))
            if ts and cp is not None:
                collected[ts] = cp
        if not nxt:
            break
        before = nxt
    if not collected:
        return None
    s = pd.Series(collected)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def _yf_close_history(tickers: list[str], period: str) -> dict:
    from data.session import cached_download
    raw = cached_download(tickers, period=period, interval="1d",
                          progress=False, auto_adjust=True)
    out: dict = {}
    if raw is None or getattr(raw, "empty", True):
        return out
    multi = len(tickers) > 1
    for tk in tickers:
        try:
            closes = raw["Close"][tk] if multi else raw["Close"]
            if hasattr(closes, "columns"):   # 단일 티커가 DataFrame 으로 올 때(yfinance 버전차)
                closes = closes.iloc[:, 0]
            closes = closes.dropna()
            if not closes.empty:
                out[tk] = closes
        except Exception:
            pass
    return out


def fetch_close_history(tickers: list[str], period: str = "6mo") -> dict:
    """{ticker: 날짜오름차순 종가 Series}. loader.batch_close_history 드롭인.
    토스 covered=일봉 캔들 / 그 외=yfinance / 토스 실패 시 종목단위 yfinance 폴백."""
    out: dict = {}
    if not tickers:
        return out
    bars = _PERIOD_BARS.get(period, 135)

    toss_syms: dict[str, list[str]] = {}
    yf_list: list[str] = []
    for t in tickers:
        kind, key = _classify(t)
        if kind == "toss_price":
            toss_syms.setdefault(key, []).append(t)
        else:
            yf_list.append(t)   # 선물·지수·비USD환율·크립토·USD/KRW(환율 히스토리)

    fallbacks: list[str] = []
    for toss_sym, origs in toss_syms.items():
        try:
            s = _toss_close_series(toss_sym, bars)
        except Exception as e:
            log.warning("토스 캔들 실패 %s: %s", toss_sym, e)
            s = None
        if s is None or s.empty:
            fallbacks.extend(origs)
        else:
            for o in origs:
                out[o] = s

    if fallbacks:
        log.info("종가 히스토리 yfinance 폴백(%d건): %s", len(fallbacks), fallbacks)
    yf_all = yf_list + fallbacks
    if yf_all:
        out.update(_yf_close_history(yf_all, period))
    return out
