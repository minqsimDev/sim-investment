"""포트폴리오 포맷·파싱 헬퍼 — portfolio.py에서 분리(순수 함수, 잎 의존성).
외부 의존: re·pandas·html·format(won/currency)·core.journey.krw_compact 및 상호 호출만.
"""
from __future__ import annotations

import re
import html as html_lib

import pandas as pd

from format import won, currency as _cur


def _parse_price_num(price_str: str) -> float | None:
    try:
        return float(price_str.replace("$", "").replace("₩", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _krw_short(value: float) -> str:
    from core.journey import krw_compact  # 전 화면 공통 단일 포맷
    return krw_compact(value)


def _num(value) -> float | None:
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").replace("₩", "").strip()
        if cleaned.upper() in {"", "N/A", "NA", "NONE", "NULL", "—", "-"}:
            return None
        value = cleaned
    try:
        f = float(value)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _price(value, currency: str) -> str:
    f = _num(value)
    if f is None:
        return "N/A"
    return _cur(f, currency)  # ₩/$ 심볼 표기 단일 출처


def _pct(value) -> tuple[str, str]:
    f = _num(value)
    if f is None:
        return "N/A", "pct-flat"
    cls = "pct-pos" if f > 0 else ("pct-neg" if f < 0 else "pct-flat")
    return f"{f:+.2f}%", cls


def _escape(value) -> str:
    return html_lib.escape(str(value or ""))


def _ticker_key(code: str) -> str:
    return str(code or "").replace(".KS", "").replace(".KQ", "").upper()


def _issuer_from_name(name: str) -> str:
    first = str(name or "ETF").split()[0].strip()
    return first if first else "ETF"


def _first(row: dict, *keys: str):
    lowered = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and row.get(key) not in (None, "", "N/A", "NA", "—"):
            return row.get(key)
        val = lowered.get(key.lower())
        if val not in (None, "", "N/A", "NA", "—"):
            return val
    return None


def _money(value: float | None, currency: str = "KRW", signed: bool = False, compact: bool = False) -> str:
    # 표기는 format.py 단일 출처에 위임. None 만 포트폴리오 문구('데이터 대기')로 처리.
    if value is None:
        return "데이터 대기"
    if compact and currency == "KRW":
        return won(value, signed=signed)          # 억·만, 심볼 없음(기존 _krw_short 동작)
    return _cur(value, currency, signed=signed)    # ₩/$ 심볼 표기


def _fmt_qty(value: float | None, est: bool = False) -> str:
    if value is None:
        return "데이터 대기"
    if est:  # 평가액÷현재가 추정치 → '약 N주'
        return f"약 {round(value):,}주"
    if abs(value - round(value)) < 0.000001:
        return f"{value:,.0f}주"
    return f"{value:,.4f}".rstrip("0").rstrip(".") + "주"


def _tone(value: float | None, threshold: float = 0.0) -> str:
    if value is None or abs(value) <= threshold:
        return "pd-neu"
    return "pd-pos" if value > 0 else "pd-neg"


def _norm_name(s) -> str:
    """이름 매칭용 정규화 — 공백 제거 + 소문자(예: '미국나스닥 테크'='미국나스닥테크')."""
    return re.sub(r"\s+", "", str(s or "")).lower()
