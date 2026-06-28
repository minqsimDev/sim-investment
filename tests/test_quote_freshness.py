"""보유 보강 시세 라이브 적격성(_live_eligible) — 마감-인지 DB-우선의 핵심.

규칙: 라이브는 '해당 시장이 개장 중인 비크립토' 티커만. 크립토는 09:00 스냅샷 고정(앱 라이브 X),
마감 시장은 DB(종가)만. → 일요일(전 시장 마감)엔 아무것도 라이브로 안 침.
"""
from datetime import datetime, timezone
from ui.pages import portfolio  # noqa: F401  (loader import 경로 워밍)
from data.loader import _live_eligible

KR, US, CRYPTO, FX = "005930.KS", "AAPL", "BTC-USD", "EURUSD=X"
ALL = [KR, US, CRYPTO, FX]


def _utc(y, mo, d, h):
    return datetime(y, mo, d, h, tzinfo=timezone.utc)


def test_us_open_window():
    # 2026-06-29(월) 14:00 UTC = ET 10:00 → 미국 개장, KR 마감
    elig = set(_live_eligible(ALL, _utc(2026, 6, 29, 14)))
    assert US in elig
    assert FX in elig          # 외환은 주중 개장
    assert KR not in elig       # KST 23:00 → 마감
    assert CRYPTO not in elig   # 크립토는 항상 제외(9시 고정)


def test_kr_open_window():
    # 2026-06-29(월) 01:00 UTC = KST 10:00 → 한국 개장, 미국 마감
    elig = set(_live_eligible(ALL, _utc(2026, 6, 29, 1)))
    assert KR in elig
    assert US not in elig
    assert CRYPTO not in elig


def test_sunday_all_closed():
    # 2026-06-28(일) → 전 시장 마감 → 라이브 대상 없음
    assert _live_eligible(ALL, _utc(2026, 6, 28, 12)) == []
