"""
시장 개장 여부 판정 + 장중 자동 갱신용 타임 버킷.

- yfinance 데이터는 태생적으로 ~15분 지연이라 '틱 단위 실시간'은 불가능하다.
- 대신 '장중이면 캐시를 짧게(60s) + 화면 자동 갱신'으로 소스가 주는 한 가장 최신을 유지한다.
- 공휴일은 MVP 범위에서 제외(요일·시간만 판정). 필요 시 별도 휴장 캘린더로 보강.
"""
from __future__ import annotations

import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

# 장중/장마감 캐시 TTL(초)
TTL_OPEN = 60
TTL_CLOSED = 900

# 정규장 시간 (현지 시각) — (개장, 마감, 타임존)
_SESSIONS = {
    "US": (dtime(9, 30), dtime(16, 0), "America/New_York"),
    "KR": (dtime(9, 0),  dtime(15, 30), "Asia/Seoul"),
}


def market_of(ticker: str) -> str:
    """티커 → 시장 구분. (US / KR / CRYPTO / FX)"""
    t = ticker.upper()
    if t.endswith(".KS") or t.endswith(".KQ") or t in ("^KS11", "^KQ11"):
        return "KR"
    if t.endswith("-USD"):
        return "CRYPTO"
    if t.endswith("=X") or t.startswith("DX-Y") or t == "DX-Y.NYB":
        return "FX"
    return "US"


def is_open(market: str, now: datetime | None = None) -> bool:
    """해당 시장이 지금 정규장 중인가."""
    market = market.upper()
    if market == "CRYPTO":
        return True  # 24/7
    if market == "FX":
        # 외환은 사실상 24/5 — 주중이면 개장으로 본다(일요일 저녁 개장은 단순화상 제외).
        ref = now or datetime.now(ZoneInfo("America/New_York"))
        return ref.weekday() < 5
    sess = _SESSIONS.get(market)
    if sess is None:
        return False
    open_t, close_t, tz = sess
    ref = (now.astimezone(ZoneInfo(tz)) if now else datetime.now(ZoneInfo(tz)))
    if ref.weekday() >= 5:  # 토·일 휴장
        return False
    return open_t <= ref.time() <= close_t


def any_open(markets: list[str], now: datetime | None = None) -> bool:
    return any(is_open(m, now) for m in markets)


def ttl_for(market: str, now: datetime | None = None) -> int:
    """장중이면 짧은 TTL(60s), 장마감이면 긴 TTL(900s)."""
    return TTL_OPEN if is_open(market, now) else TTL_CLOSED


def live_bucket(markets: list[str], now: datetime | None = None) -> int:
    """장중이면 60초마다, 장마감이면 900초마다 바뀌는 정수.

    @st.cache_data 키에 끼워 넣으면 장중엔 60초 주기로 캐시가 자연 만료된다.
    """
    period = TTL_OPEN if any_open(markets, now) else TTL_CLOSED
    return int(time.time() // period)
