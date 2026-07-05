from datetime import date

import math
import pytest

from core.goal_engine import (
    years_to_target, required_cagr, monthly_topup_needed,
    shock_delay_years, monthly_avg_deposit,
)


def test_years_to_target_basic():
    # 7억 → 15억, 연 20% ≈ 4.18년
    y = years_to_target(7e8, 15e8, 0.20)
    assert 4.0 < y < 4.4
    assert years_to_target(15e8, 15e8, 0.20) == 0.0      # 이미 달성
    assert years_to_target(7e8, 15e8, 0.0) is None       # 페이스 없음 → 도달 불가
    assert years_to_target(7e8, 15e8, -0.05) is None


def test_required_cagr_roundtrip():
    # years_to_target 의 역함수 관계
    r = required_cagr(7e8, 15e8, 4.18)
    assert abs(years_to_target(7e8, 15e8, r) - 4.18) < 0.01
    assert required_cagr(15e8, 10e8, 5) == 0.0            # 이미 달성
    assert required_cagr(7e8, 15e8, 0) is None


def test_monthly_topup():
    # 페이스가 필요수익률보다 높으면 적립 불필요
    assert monthly_topup_needed(7e8, 15e8, 0.30, 4.0) == 0.0
    # 페이스 13.2%로 4.2년 내 15억: 상당한 월 적립 필요, 양수·합리 범위
    m = monthly_topup_needed(7e8, 15e8, 0.132, 4.2)
    assert 4e6 < m < 1.2e7
    # 검산: 적립 반영 미래가치가 목표에 근접
    r, t = 0.132, 4.2
    rm = (1 + r) ** (1 / 12) - 1
    fv = 7e8 * (1 + r) ** t + m * (((1 + rm) ** (t * 12) - 1) / rm)
    assert abs(fv - 15e8) / 15e8 < 0.001
    # 수익률 0이어도 단순 분할로 계산됨
    m0 = monthly_topup_needed(7e8, 15e8, 0.0, 4.0)
    assert abs(m0 - (8e8 / 48)) < 1


def test_shock_delay():
    # 비중 50% 종목 -30% → 계좌 -15% → 연 13.2% 페이스로 ≈1.3년 지연
    d = shock_delay_years(0.132, 50.0, 0.30)
    assert 1.0 < d < 1.6
    assert shock_delay_years(0.0, 50.0) is None
    assert shock_delay_years(0.132, 0.0) == pytest.approx(0.0)


def test_monthly_avg_deposit():
    today = date(2026, 7, 5)
    deps = [
        {"date": "2026-06-10", "amount": 3_000_000},
        {"date": "2026-05-10", "amount": 2_000_000},
        {"date": "2025-01-01", "amount": 99_000_000},   # 6개월 밖 → 제외
    ]
    assert monthly_avg_deposit(deps, months=6, today=today) == pytest.approx(5_000_000 / 6)
    assert monthly_avg_deposit([], months=6, today=today) == 0.0
    assert monthly_avg_deposit(None) == 0.0
