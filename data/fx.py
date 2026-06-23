"""USD/KRW 환율 단일 출처(SSOT).

해석 순서: ① 시장데이터(data['fx'] — 토스 우선·yfinance 폴백) → ② 보조 무료 FX API
(키 불필요, 15분 캐시) → ③ 상수 폴백(FX_FALLBACK).

이전엔 환율 가져오기가 portfolio.py UI 안의 자체 HTTP 호출 등 여러 곳에 흩어져 있었음.
이 모듈 하나로 모아 'UI 가 직접 외부 호출' 분산을 제거한다.
"""
from __future__ import annotations

import json
import time
import urllib.request

FX_FALLBACK = 1450.0          # 모든 소스 실패 시 폴백(상수)
_LIVE_URL = "https://open.er-api.com/v6/latest/USD"
_TTL = 900                    # 보조 API 메모 캐시(초) — 15분
_cache: dict = {"rate": None, "ts": 0.0}


def fetch_live_usdkrw() -> float | None:
    """보조 무료 FX API로 USD/KRW. 키 불필요, 15분 메모 캐시. 실패 시 None."""
    now = time.time()
    if _cache["rate"] and (now - _cache["ts"]) < _TTL:
        return _cache["rate"]
    try:
        with urllib.request.urlopen(_LIVE_URL, timeout=6) as r:
            rate = json.load(r).get("rates", {}).get("KRW")
        v = float(rate) if rate else None
        if v:
            _cache.update(rate=v, ts=now)
        return v
    except Exception:
        return None


def usdkrw(data: dict | None = None) -> float | None:
    """USD/KRW 환율(단일 출처). data['fx'](시장데이터) 1순위 → 보조 실시간 API.
    모두 실패하면 None — 호출부에서 `usdkrw(data) or FX_FALLBACK` 로 폴백."""
    if data:
        fx = data.get("fx")
        try:
            if fx is not None and not fx.empty and "pair" in fx.columns:
                row = fx[fx["pair"] == "usd_krw"]
                if not row.empty:
                    rate = float(row.iloc[0].get("rate"))
                    if rate:
                        return rate
        except Exception:
            pass
    return fetch_live_usdkrw()
