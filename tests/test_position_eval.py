"""보유 평가/통화 — 평가금액=라이브(수량×현재가), 매입금액=고정, 환산은 티커기준 USD 판정.

회귀: 파서가 미국주식 currency를 'KRW'로 오태깅하거나 미국주식을 ETF로 오분류하면, 환율이
평가금액엔 적용되고 매입금액엔 안 돼(또는 반대) 수익률이 폭발했음.
→ _holding_currency 가 티커/카테고리로 USD를 robust 판정하고, _position_eval 이 평가·매입에
동일 fx_factor 를 일관 적용.
"""
from ui.pages.portfolio import _position_eval, _holding_currency, _category_for_holding


# ── _category_for_holding: 파서의 ETF 오분류 보정 ─────────────────────────────
def test_spcx_mislabeled_etf_becomes_us_stock():
    # 파서가 SPCX(스페이스X)를 etf로 오분류 → 이름에 ETF 없고 비한국 티커 → 미국주식
    assert _category_for_holding({"name": "스페이스X", "asset_class": "etf"}, "SPCX") == "미국주식"


def test_real_us_etf_stays_etf_by_name():
    assert _category_for_holding({"name": "S&P500 ETF", "asset_class": "etf"}, "SPY") == "ETF"


def test_korean_etf_stays_etf():
    assert _category_for_holding({"name": "KODEX 종합채권", "asset_class": "etf"}, "273130.KS") == "ETF"


# ── _holding_currency: 티커/카테고리 기준 robust 판정 ──────────────────────────
def test_us_stock_is_usd_even_if_currency_mistagged_krw():
    assert _holding_currency({"currency": "KRW"}, "AAPL", "미국주식") == "USD"


def test_us_stock_is_usd_even_if_miscategorized_etf():
    # SPCX(스페이스X)가 파서에서 ETF로 오분류돼도 비한국 티커 → USD
    assert _holding_currency({}, "SPCX", "ETF") == "USD"


def test_kr_stock_is_krw():
    assert _holding_currency({}, "005930.KS", "국내주식") == "KRW"


def test_korean_etf_is_krw():
    assert _holding_currency({}, "273130.KS", "ETF") == "KRW"   # .KS → 원화


def test_crypto_is_krw():
    assert _holding_currency({}, "BTC-USD", "크립토") == "KRW"   # 국내거래소 원화


# ── _position_eval: 평가금액·매입금액에 동일 환산 일관 적용 ───────────────────
def _eval(category, qty, current, fx_factor, direct_market, **kw):
    args = dict(direct_cost=None, avg_price=None, direct_gain=None,
                direct_gain_pct=None, direct_today=None, change=None)
    args.update(kw)
    return _position_eval(category, qty, current, fx_factor, direct_market, **args)


def test_us_stock_value_and_cost_use_same_fx():
    # AAPL 140주, 현재가 $283.78, 매입 $27,543.52, 환율 1535 → 평가·매입 모두 ×환율 일관
    mv, mv_local, cost, gl, gl_local, gpct, today = _eval(
        "미국주식", qty=140, current=283.78, fx_factor=1535,
        direct_market=999, direct_cost=27543.52, change=1.0)
    assert round(mv) == round(140 * 283.78 * 1535)       # 라이브 평가금액
    assert round(cost) == round(27543.52 * 1535)         # 매입금액도 ×환율(일관)
    assert round(gpct, 1) == round((140 * 283.78 - 27543.52) / 27543.52 * 100, 1)  # ≈ +44%
    assert 30 < gpct < 60                                 # 폭발(수천%) 아님


def test_kr_stock_no_fx():
    mv, _l, cost, gl, *_ = _eval("국내주식", qty=3, current=80_000.0, fx_factor=1,
                                 direct_market=999, direct_cost=180_000)
    assert mv == 3 * 80_000.0
    assert cost == 180_000


def test_crypto_keeps_snapshot():
    mv, _l, _c, gl, *_ = _eval("크립토", qty=0.09, current=60_000.0, fx_factor=1,
                               direct_market=8_535_833, direct_gain=-6_812_663)
    assert mv == 8_535_833
    assert gl == -6_812_663


def test_stock_without_live_price_falls_back_to_snapshot():
    mv, *_ = _eval("미국주식", qty=10, current=None, fx_factor=1535, direct_market=2000.0)
    assert mv == 2000.0 * 1535   # 스냅샷 평가금액 × 환율
