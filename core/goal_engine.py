"""
목표 엔진 — 필요수익률 역산·도달 예상·갭 레버·충격 지연 계산.

core/journey.py(journey_metrics)가 '실제 페이스(CAGR)'를 재고, 여기는 그 페이스로
"목표까지 몇 년, 뭘 당길 수 있나(적립·기간·수익률)"를 수치화한다. 순수 함수만 둔다.
"""
import math
from datetime import date, timedelta


def years_to_target(current: float, target: float, annual_rate: float) -> float | None:
    """현행 페이스(연 r)로 목표까지 걸리는 년수. 이미 달성=0, 페이스≤0이면 None(도달 불가)."""
    if current >= target:
        return 0.0
    if current <= 0 or annual_rate is None or annual_rate <= 0:
        return None
    return math.log(target / current) / math.log(1 + annual_rate)


def required_cagr(current: float, target: float, years_left: float) -> float | None:
    """목표 기한 내 도달에 필요한 연복리 수익률."""
    if current <= 0 or years_left is None or years_left <= 0:
        return None
    if current >= target:
        return 0.0
    return (target / current) ** (1 / years_left) - 1


def monthly_topup_needed(current: float, target: float, annual_rate: float,
                         years_left: float) -> float | None:
    """현행 수익률을 유지하며 기한 내 도달하는 데 필요한 월 적립액. 적립 없이도 충분하면 0."""
    if years_left is None or years_left <= 0:
        return None
    if current >= target:
        return 0.0
    r = max(annual_rate or 0.0, 0.0)
    n = years_left * 12
    fv_current = current * (1 + r) ** years_left
    gap = target - fv_current
    if gap <= 0:
        return 0.0
    if r <= 0:
        return gap / n
    rm = (1 + r) ** (1 / 12) - 1  # 월복리 환산
    return gap * rm / ((1 + rm) ** n - 1)


def shock_delay_years(annual_rate: float, weight_pct: float, shock: float = 0.30) -> float | None:
    """최대 종목이 -shock 만큼 빠질 때 목표 도달이 몇 년 늦어지는가.
    계좌가 (1 - 비중×shock)배가 된 뒤 같은 페이스로 복구한다는 가정의 로그 환산."""
    if annual_rate is None or annual_rate <= 0:
        return None
    hit = 1 - (weight_pct / 100) * shock
    if hit <= 0:
        return None
    return math.log(1 / hit) / math.log(1 + annual_rate)


def monthly_avg_deposit(deposits: list[dict] | None, months: int = 6,
                        today: date | None = None) -> float:
    """최근 N개월 입금 합 ÷ N — 월평균 적립. deposits=[{'date':'YYYY-MM-DD','amount':원}]."""
    today = today or date.today()
    cutoff = (today - timedelta(days=months * 30.44)).isoformat()
    tot = sum(float(d.get("amount") or 0) for d in (deposits or [])
              if str(d.get("date", "")) >= cutoff)
    return tot / months if tot else 0.0
