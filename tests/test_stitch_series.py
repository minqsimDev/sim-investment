"""_stitch_series — 근사(현재수량×과거종가)와 실측 스냅샷의 하이브리드 이어붙임."""
import pandas as pd
import pytest

from ui.pages.portfolio import _stitch_series


def _approx(dates: list[str], values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.to_datetime(dates))


def test_no_snapshots_returns_approx_unchanged():
    approx = _approx(["2026-07-01", "2026-07-02"], [100.0, 110.0])
    out, measured_from = _stitch_series(approx, [])
    assert measured_from is None
    pd.testing.assert_series_equal(out, approx)


def test_boundary_before_is_approx_after_is_measured():
    approx = _approx(
        ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06"],
        [100.0, 110.0, 120.0, 130.0],
    )
    snaps = [
        {"date": "2026-07-03", "total": 500.0},
        {"date": "2026-07-06", "total": 520.0},
    ]
    out, measured_from = _stitch_series(approx, snaps)
    assert measured_from == pd.Timestamp("2026-07-03").date()
    # 첫 스냅샷 이전은 근사값 그대로
    assert out[pd.Timestamp("2026-07-01")] == 100.0
    assert out[pd.Timestamp("2026-07-02")] == 110.0
    # 이후는 실측값으로 대체(근사 120/130 무시)
    assert out[pd.Timestamp("2026-07-03")] == 500.0
    assert out[pd.Timestamp("2026-07-06")] == 520.0


def test_gap_days_forward_fill_from_last_measurement():
    approx = _approx(
        ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06"],
        [100.0, 110.0, 120.0, 130.0],
    )
    snaps = [{"date": "2026-07-02", "total": 400.0}]  # 이후 미방문
    out, measured_from = _stitch_series(approx, snaps)
    assert measured_from == pd.Timestamp("2026-07-02").date()
    assert out[pd.Timestamp("2026-07-01")] == 100.0
    # 스냅샷 이후 거래일은 마지막 실측값 ffill
    assert out[pd.Timestamp("2026-07-03")] == 400.0
    assert out[pd.Timestamp("2026-07-06")] == 400.0


def test_approx_none_uses_snapshots_only():
    snaps = [
        {"date": "2026-07-01", "total": 300.0},
        {"date": "2026-07-04", "total": 330.0},
    ]
    out, measured_from = _stitch_series(None, snaps)
    assert measured_from == pd.Timestamp("2026-07-01").date()
    assert out.iloc[0] == 300.0
    assert out.iloc[-1] == 330.0
    # 사이 빈 날은 ffill 로 연결(일별 인덱스)
    assert out[pd.Timestamp("2026-07-02")] == 300.0


def test_invalid_snapshots_ignored():
    approx = _approx(["2026-07-01", "2026-07-02"], [100.0, 110.0])
    snaps = [
        {"date": "2026-07-02", "total": 0},        # 0원 스냅샷 무시
        {"date": "", "total": 999.0},              # 날짜 없음 무시
        {"total": 999.0},                          # date 키 없음 무시
    ]
    out, measured_from = _stitch_series(approx, snaps)
    assert measured_from is None
    pd.testing.assert_series_equal(out, approx)


def test_both_empty_returns_none():
    out, measured_from = _stitch_series(None, [])
    assert out is None
    assert measured_from is None
