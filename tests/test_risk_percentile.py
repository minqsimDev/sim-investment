"""리스크 신호 백분위 보정(B) — 고정 임계값 대신 자기 1년 분포 백분위로 판정.

상위 25% → 강함 밴드, 하위 25% → 약함 밴드. 표본 부족(<60)이면 추세(고정 임계값)로 폴백.
"""
import pandas as pd
from src.risk import compute_regime_signals


def _bm(spy_d1=0.0):
    return {"benchmarks": pd.DataFrame([{"ticker": "SPY", "change_pct": spy_d1}])}


def _risk(sigs):
    return next(s for s in sigs if s["signal"] == "Risk-on / Risk-off")


def test_recent_spike_top_percentile_is_risk_on():
    # 230일 평탄 후 최근 +10% 급등 → 현재 20일수익률이 1년 분포 최상위 → RISK-ON
    s = pd.Series([100.0] * 230 + [100.0 + 0.5 * i for i in range(1, 21)])
    sig = _risk(compute_regime_signals(_bm(), closes={"SPY": s}))
    assert sig["lv"] == "RISK-ON"
    assert "상위" in sig["note"]          # 백분위 표기
    assert sig["score"] >= 75


def test_recent_drop_bottom_percentile_is_risk_off():
    s = pd.Series([100.0] * 230 + [100.0 - 0.5 * i for i in range(1, 21)])
    sig = _risk(compute_regime_signals(_bm(), closes={"SPY": s}))
    assert sig["lv"] == "RISK-OFF"
    assert sig["score"] <= 25


def test_short_history_falls_back_to_trend():
    # 40일(20일수익률 표본 <60) → 백분위 불가 → 추세(고정 임계값) 폴백, '상위' 표기 없음
    s = pd.Series([100.0 + i for i in range(40)])
    sig = _risk(compute_regime_signals(_bm(), closes={"SPY": s}))
    assert "상위" not in sig["note"]
    assert "1개월" in sig["note"]


def test_dollar_level_percentile():
    # DXY 레벨 백분위 — 최근 값이 1년 최고권 → STRONG
    dxy = pd.Series([95.0 + (i % 5) for i in range(200)] + [110.0])
    data = {"fx": pd.DataFrame([{"pair": "dxy", "ticker": "DX-Y.NYB",
                                 "rate": 110.0, "change_pct": 0.1}])}
    sig = next(s for s in compute_regime_signals(data, closes={"dxy": dxy})
               if s["signal"] == "Dollar Strength")
    assert sig["lv"] == "STRONG"
    assert "상위" in sig["note"]
