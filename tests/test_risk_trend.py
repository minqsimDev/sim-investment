"""리스크 신호 추세 기반(A) — 20거래일 추세로 산출, DB 히스토리 없으면 1D 폴백.

핵심: 마감/주말엔 1D 변동%가 죽어 신호가 NEUTRAL로 쏠리던 문제를, 추세(price_history)로 해소.
"""
import pandas as pd
from src.risk import compute_regime_signals


def _bm(spy_d1=0.0):
    return {"benchmarks": pd.DataFrame([
        {"ticker": "SPY", "change_pct": spy_d1},
        {"ticker": "QQQ", "change_pct": 0.0},
        {"ticker": "SOXX", "change_pct": 0.0},
        {"ticker": "TLT", "change_pct": 0.0},
    ])}


def _series(start, end, n=40):
    return pd.Series([start + (end - start) * i / (n - 1) for i in range(n)])


def _risk_signal(signals):
    return next(s for s in signals if s["signal"] == "Risk-on / Risk-off")


def test_trend_drives_signal_even_when_1d_flat():
    # 장마감: SPY 1D=0 이지만 1개월 추세는 상승 → RISK-ON 유지(추세 사용)
    sig = _risk_signal(compute_regime_signals(_bm(spy_d1=0.0),
                                              closes={"SPY": _series(100, 120)}))
    assert sig["lv"] == "RISK-ON"
    assert "1개월" in sig["note"]


def test_trend_down_is_risk_off():
    sig = _risk_signal(compute_regime_signals(_bm(spy_d1=0.0),
                                              closes={"SPY": _series(120, 100)}))
    assert sig["lv"] == "RISK-OFF"


def test_falls_back_to_1d_when_no_history():
    # closes 없음(DB 미적재) → 1D 변동%로 폴백(기존 동작)
    sig = _risk_signal(compute_regime_signals(_bm(spy_d1=1.0), closes={}))
    assert sig["lv"] == "RISK-ON"
    assert "1D" in sig["note"]


def test_neutral_when_no_data_at_all():
    sig = _risk_signal(compute_regime_signals({"benchmarks": pd.DataFrame()}, closes={}))
    assert sig["lv"] in ("N/A", "NEUTRAL")
