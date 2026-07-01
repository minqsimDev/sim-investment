"""시장 레짐(국면) 판정 — 전체현황 나침반·시장 페이지·리스크가 공유하는 단일 출처.
compute_regime_signals(원지표) → 신호 → compass_model(가중 스코어) → 방향/해석/톤.
"""
import pandas as pd
import streamlit as st

from data.loader import load_market_data  # 기존 overview 와 동일 소스
from src.risk import compute_regime_signals


@st.cache_data(ttl=1800, show_spinner=False)
def cached_regime_signals(fetched_at: str) -> list[dict]:
    """레짐 신호 계산을 시장데이터 타임스탬프로 캐시(리런마다 재계산 방지)."""
    return compute_regime_signals(load_market_data())


def compass_model(sig_map: dict, btc_chg, kweb_chg) -> tuple[str, str, int, str]:
    score = 0

    def _col(key: str) -> str:
        return sig_map.get(key, {}).get("col", "na")

    for key, weight in [("Semiconductor Momentum", 2), ("Tech Momentum", 2)]:
        col = _col(key)
        if col == "low":
            score += weight
        elif col == "high":
            score -= weight
    for key, weight in [("Rate Pressure", 2), ("Dollar Strength", 1), ("Korea FX Risk", 1)]:
        col = _col(key)
        if col == "high":
            score -= weight
        elif col == "low":
            score += 1
    if btc_chg is not None:
        if btc_chg > 2:
            score += 1
        elif btc_chg < -2:
            score -= 1
    if kweb_chg is not None:
        if kweb_chg > 1.5:
            score += 1
        elif kweb_chg < -1.5:
            score -= 1

    angle = max(-42, min(42, score * 9))
    if score >= 3:
        return "우상향 유지", "AI·반도체 중심의 위험선호가 우세합니다. 금리와 달러 변화만 계속 점검하세요.", angle, "good"
    if score <= -3:
        return "방어 모드", "금리·달러·위험회피 압력이 커졌습니다. 변동성 큰 자산군의 움직임을 먼저 확인하세요.", angle, "risk"
    return "혼조 구간", "방향성은 아직 중립입니다. 강한 자산과 약한 자산이 갈리는지 확인하세요.", angle, "watch"


def _safe(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def regime_verdict(data: dict) -> dict:
    """시장데이터 → 레짐 판정 일괄. 반환 {direction,note,tone,angle,signals,sig_map}."""
    signals = cached_regime_signals(data["fetched_at"])
    sig_map = {s["signal"]: s for s in signals}
    _bm = data.get("benchmarks", pd.DataFrame())
    _cr = data.get("crypto", pd.DataFrame())
    _bm_chg = {} if _bm.empty else dict(zip(_bm["ticker"], _bm["change_pct"]))
    _cry_chg = {} if _cr.empty else dict(zip(_cr["ticker"], _cr["change_pct"]))
    direction, note, angle, tone = compass_model(
        sig_map, _safe(_cry_chg.get("BTC-USD")), _safe(_bm_chg.get("KWEB")))
    return {"direction": direction, "note": note, "tone": tone,
            "angle": angle, "signals": signals, "sig_map": sig_map}
