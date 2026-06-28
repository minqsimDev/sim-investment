"""보유 1건 평가금액 재계산(_position_eval) — 주식은 라이브, 크립토는 스냅샷 유지.

회귀 방지: 종목 추가 시점의 스크린샷 평가금액으로 고정돼 시세 변동이 반영되지 않던 버그.
"""
from ui.pages.portfolio import _position_eval


def _mv(category, qty, current, fx_factor, direct_market, **kw):
    args = dict(direct_cost=None, avg_price=None, direct_gain=None,
                direct_gain_pct=None, direct_today=None, change=None, fx=1)
    args.update(kw)
    return _position_eval(category, qty, current, fx_factor, direct_market, **args)


def test_us_stock_recomputes_market_value_from_live_price():
    # 미국주식(currency=USD 정상): 스냅샷 무시, 보유수량×라이브가×환율로 재계산.
    mv, mv_local, cost, gl, gl_local, gpct, today = _mv(
        "미국주식", qty=10, current=200.0, fx_factor=1300,
        direct_market=999_999, direct_cost=1500.0, change=5.0, fx=1300)
    assert mv == 10 * 200.0 * 1300            # 스냅샷(999,999) 무시, 라이브 재계산
    assert mv_local == 10 * 200.0             # 현지통화(USD) 평가액
    assert cost == 1500.0 * 1300              # 원가 = 매입금액(USD) × 환율
    assert gl == mv - cost                    # 손익 = 평가금액 - 원가
    assert round(gpct, 2) == round(gl / cost * 100, 2)
    assert today == 10 * 5.0 * 1300           # 오늘변동 = 수량×일변동×환율(라이브)


def test_us_stock_with_buggy_krw_currency_still_applies_fx():
    # 회귀: 저장 currency='KRW'(구 파싱 버그)면 fx_factor=1 이지만, 미국주식 현재가는 USD라
    # 반드시 환율 적용돼야 함(price_fx). 매입금액은 원화로 저장된 케이스(fx_factor=1).
    mv, mv_local, cost, gl, *_ = _mv(
        "미국주식", qty=140, current=283.78, fx_factor=1,      # currency='KRW' → fx_factor=1
        direct_market=41_694_800, direct_cost=27_543_519, fx=1535)
    assert round(mv) == round(140 * 283.78 * 1535)   # USD 현재가에 환율 적용(₩39,729 축소 버그 방지)
    assert mv != 140 * 283.78                          # 환율 미적용 버그값이 아님
    assert cost == 27_543_519                          # 매입금액은 원화 그대로(fx_factor=1)
    assert gl == mv - cost


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
