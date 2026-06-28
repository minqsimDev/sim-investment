"""보유 1건 평가 산출(_position_eval) — 평가금액=라이브(수량×현재가), 매입금액=고정.

핵심: 평가금액은 현재가로 변하고 매입금액(원가)은 스냅샷 고정 → 수익률이 시세를 반영.
크립토는 USD/원화 기준 차(프리미엄)로 스냅샷 유지(별도 결정). 라이브 현재가 없으면 스냅샷 폴백.
"""
from ui.pages.portfolio import _position_eval


def _eval(category, qty, current, fx_factor, direct_market, **kw):
    args = dict(direct_cost=None, avg_price=None, direct_gain=None,
                direct_gain_pct=None, direct_today=None, change=None, fx=1)
    args.update(kw)
    return _position_eval(category, qty, current, fx_factor, direct_market, **args)


def test_us_stock_market_value_is_live():
    # 미국주식(currency=USD 정상): 평가금액=수량×현재가×환율, 매입금액 고정.
    mv, mv_local, cost, gl, gl_local, gpct, today = _eval(
        "미국주식", qty=10, current=200.0, fx_factor=1300,
        direct_market=999_999, direct_cost=1500.0, change=5.0, fx=1300)
    assert mv == 10 * 200.0 * 1300       # 스냅샷(999,999) 무시 — 라이브 평가금액
    assert cost == 1500.0 * 1300         # 매입금액 고정(환산)
    assert gl == mv - cost
    assert today == 10 * 5.0 * 1300


def test_us_stock_buggy_krw_currency_still_applies_fx():
    # 회귀: currency='KRW' 오기입이면 fx_factor=1이지만 미국주식 현재가는 USD → price_fx로 환율 적용.
    mv, *_ = _eval("미국주식", qty=140, current=283.78, fx_factor=1,
                   direct_market=41_694_800, direct_cost=27_543_519, fx=1535)
    assert round(mv) == round(140 * 283.78 * 1535)   # 1/환율 축소 버그 방지
    assert mv != 140 * 283.78


def test_kr_stock_market_value_is_live_in_krw():
    mv, _l, cost, gl, *_ = _eval("국내주식", qty=3, current=80_000.0, fx_factor=1,
                                 direct_market=210_000, direct_cost=180_000)
    assert mv == 3 * 80_000.0            # 스냅샷(210,000) 무시
    assert gl == mv - 180_000


def test_crypto_keeps_snapshot():
    mv, _l, _c, gl, *_ = _eval("크립토", qty=0.09, current=60_000.0, fx_factor=1,
                               direct_market=8_535_833, direct_gain=-6_812_663)
    assert mv == 8_535_833               # 크립토는 스냅샷 유지
    assert gl == -6_812_663


def test_stock_without_live_price_falls_back_to_snapshot():
    mv, *_ = _eval("미국주식", qty=10, current=None, fx_factor=1300, direct_market=2_000_000)
    assert mv == 2_000_000 * 1300        # 라이브 없음 → 스냅샷 환산 폴백
