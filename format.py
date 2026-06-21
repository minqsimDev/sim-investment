"""금액·통화 표기 단일 출처(전 화면 공통).

- won(n)       : 원화를 억·만 한국식 축약. 심볼 없음. 헤드라인·큰 금액용.
                 (예: 559,376,395 → '5억 5,938만')
- currency(n)  : 통화 기호를 항상 표기(₩ / $). 단가·환율 등 정밀 금액용.
                 compact=True 면 KRW 를 '₩' + 억·만 축약으로.

정책(하이브리드): 헤드라인·큰 금액은 won(), 정밀 금액(단가·환율)은 currency().
퍼센트·지수 포인트엔 쓰지 않는다(수량/금액 전용).

억·만 축약 로직은 core.journey.krw_compact 를 단일 출처로 재사용한다.
"""
from __future__ import annotations

from core.journey import krw_compact


def won(value, *, signed: bool = False) -> str:
    """원화 → 억·만 축약(심볼 없음). signed=True 면 양수에 '+' 부호."""
    if value is None:
        return "—"
    body = krw_compact(value)  # 음수는 '-' 포함, 억·만 단위
    if signed and float(value) > 0:
        return "+" + body
    return body


def currency(value, code: str = "KRW", *, compact: bool = False, signed: bool = False) -> str:
    """통화 금액 → 항상 ₩/$ 심볼. compact=True 면 KRW 를 억·만 축약."""
    if value is None:
        return "—"
    sign = ""
    v = value
    if signed:
        sign = "+" if value > 0 else ("-" if value < 0 else "")
        v = abs(value)
    if code == "KRW":
        body = ("₩" + krw_compact(v)) if compact else f"₩{v:,.0f}"
    else:
        body = f"${v:,.0f}" if abs(v) >= 1000 else f"${v:,.2f}"
    return f"{sign}{body}"
