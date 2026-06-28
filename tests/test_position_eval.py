"""보유 1건 평가금액 재계산(_position_eval) — 주식은 라이브, 크립토는 스냅샷 유지.

회귀 방지: 종목 추가 시점의 스크린샷 평가금액으로 고정돼 시세 변동이 반영되지 않던 버그.
"""
from ui.pages.portfolio import _position_eval


def _mv(category, qty, current, fx_factor, direct_market, **kw):
    args = dict(direct_cost=None, avg_price=None, direct_gain=None,
                direct_gain_pct=None, direct_today=None, change=None)
    args.update(kw)
    return _position_eval(category, qty, current, fx_factor, direct_market, **args)


def test_us_stock_recomputes_market_value_from_live_price():
    # 미국주식: 스냅샷 평가금액(direct_market)은 무시, 보유수량×라이브가×환율로 재계산.
    # direct_cost(매입금액)는 USD 기준이라 ×환율로 원화 환산(기존 의미 유지).
    mv, mv_local, cost, gl, gl_local, gpct, today = _mv(
        "미국주식", qty=10, current=200.0, fx_factor=1300,
        direct_market=999_999, direct_cost=1500.0, change=5.0)
    assert mv == 10 * 200.0 * 1300            # 스냅샷(999,999) 무시, 라이브 재계산
    assert mv_local == 10 * 200.0             # 현지통화(USD) 평가액
    assert cost == 1500.0 * 1300              # 원가 = 매입금액(USD) × 환율
    assert gl == mv - cost                    # 손익 = 평가금액 - 원가
    assert round(gpct, 2) == round(gl / cost * 100, 2)
    assert today == 10 * 5.0 * 1300           # 오늘변동 = 수량×일변동×환율(라이브)


def test_kr_stock_recomputes_in_krw():
    mv, mv_local, cost, gl, *_ = _mv(
        "국내주식", qty=3, current=80_000.0, fx_factor=1,
        direct_market=210_000, direct_cost=180_000)
    assert mv == 3 * 80_000.0                  # 스냅샷(210,000) 무시
    assert mv_local == mv                      # 원화는 환산 없음
    assert gl == mv - 180_000


def test_crypto_keeps_snapshot_value():
    # 크립토는 USD/원화 기준 차이 때문에 라이브 재계산하지 않고 브로커 스냅샷 유지.
    mv, mv_local, cost, gl, gl_local, gpct, today = _mv(
        "크립토", qty=0.09, current=60_000.0, fx_factor=1,
        direct_market=8_535_833, direct_gain=-6_812_663)
    assert mv == 8_535_833                     # 스냅샷 그대로
    assert gl == -6_812_663                    # 스냅샷 손익 그대로


def test_stock_without_live_price_falls_back_to_snapshot():
    mv, *_ = _mv("미국주식", qty=10, current=None, fx_factor=1300,
                 direct_market=2_000_000)
    assert mv == 2_000_000 * 1300              # 라이브 없음 → 스냅샷 환산 폴백
