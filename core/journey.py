"""
자산 여정 계산 — 연 성장률(CAGR)·진행률·예상 기간·페이스를 자동 산출.
하드코딩 금지: 입력값 4(+1)개만 받아 전부 계산한다.
"""
import math
from datetime import date, timedelta


def journey_metrics(start_date, start_value, current_value, target_value,
                    target_date=None, today=None):
    """
    start_date    : 투자 시점 (date)
    start_value   : 초기 투자금
    current_value : 현재 자산
    target_value  : 목표 금액
    target_date   : 목표 기한 (date, 페이스용·선택)
    """
    today = today or date.today()
    years = max((today - start_date).days / 365.25, 1e-9)

    cagr = (current_value / start_value) ** (1 / years) - 1 if start_value > 0 else 0.0
    progress = current_value / target_value if target_value > 0 else 0.0
    remaining = max(target_value - current_value, 0)

    if cagr > 0 and 0 < current_value < target_value:
        yrs = math.log(target_value / current_value) / math.log(1 + cagr)
    else:
        yrs = None

    pace_months = None
    if yrs is not None and target_date is not None:
        eta = today + timedelta(days=yrs * 365.25)
        pace_months = round((target_date - eta).days / 30.44)  # +면 예정보다 빠름

    return {
        "cagr_pct": cagr * 100,
        "progress_pct": progress * 100,
        "remaining": remaining,
        "years_to_goal": yrs,
        "pace_months": pace_months,
    }


def krw_compact(value) -> str:
    """원화 금액을 한글 단위로 표기 (전 화면 공통 단일 포맷).

    · 1억 이상 → 'N억 N,NNN만'  (예: 159,001,000 → '1억 5,900만')
    · 1만 이상 → 'N,NNN만'
    · 그 미만 → 천단위 콤마
    퍼센트·단가·지수 포인트에는 쓰지 않는다(수량/금액 전용).
    """
    if value is None:
        return "—"
    v = float(value)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 100_000_000:
        eok = int(v // 100_000_000)
        man = int(round((v % 100_000_000) / 10_000))
        if man >= 10_000:          # 반올림 자리올림 → 억으로 승격
            eok += 1
            man = 0
        return f"{sign}{eok:,}억" + (f" {man:,}만" if man else "")
    if v >= 10_000:
        return f"{sign}{int(round(v / 10_000)):,}만"
    return f"{sign}{v:,.0f}"


def pct_weight(value) -> str:
    """비중(%) 숫자 표기 (전 화면 공통). '%'는 호출부에서 붙인다.

    반올림 정수 기본, 소수가 유의미할 때만 1자리.
    예: 78.0→'78', 70.04→'70', 52.0→'52', 62.9→'62.9'.
    """
    if value is None:
        return "—"
    v = float(value)
    if abs(v - round(v)) < 0.05:
        return f"{round(v):d}"
    return f"{v:.1f}"


def eta_label(years_to_goal) -> str:
    """예상 기간을 'N년 M개월' 형태로."""
    if years_to_goal is None:
        return "—"
    months = max(0, round(years_to_goal * 12))
    y, m = divmod(months, 12)
    if y and m:
        return f"{y}년 {m}개월"
    if y:
        return f"{y}년"
    return f"{m}개월"


def stage_label(progress_pct: float) -> str:
    """진행률 구간 라벨."""
    if progress_pct >= 100:
        return "목표 도달"
    if progress_pct >= 66:
        return "막바지 구간"
    if progress_pct >= 33:
        return "순항 중"
    return "초반 구간"


def milestones(target_value: float) -> list[float]:
    """목표금액 기준 자동 분할 체크포인트 (1/3, 2/3, 목표)."""
    return [target_value / 3, target_value * 2 / 3, target_value]
