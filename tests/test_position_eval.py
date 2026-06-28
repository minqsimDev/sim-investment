"""보유 1건 평가 산출(_position_eval) — 브로커 스냅샷(증권사 값) 기준.

회귀 방지: 우리 시세로 보유수량×현재가 재계산하면 출처 차이로 수익률이 증권사와 어긋나 "엉망"으로
보였음 → 평가금액·손익·수익률은 스냅샷(direct_*) 그대로 사용. 현재가는 표시용으로만 라이브.
"""
from ui.pages.portfolio import _position_eval


def _eval(category, qty, current, fx_factor, direct_market, **kw):
    args = dict(direct_cost=None, avg_price=None, direct_gain=None,
                direct_gain_pct=None, direct_today=None, change=None, fx=1)
    args.update(kw)
    return _position_eval(category, qty, current, fx_factor, direct_market, **args)


def test_stock_uses_broker_snapshot_not_live_recompute():
    # 라이브 현재가가 있어도 평가금액·손익은 스냅샷(증권사 값) 유지 — 수량×현재가 재계산 금지.
    mv, mv_local, cost, gl, gl_local, gpct, today = _eval(
        "미국주식", qty=10, current=999.0, fx_factor=1,
        direct_market=2_000_000, direct_gain=500_000, direct_gain_pct=33.3, fx=1500)
    assert mv == 2_000_000           # 스냅샷 그대로(10×999×환율 아님)
    assert gl == 500_000             # 증권사 평가손익 그대로
    assert gpct == 33.3              # 증권사 수익률 그대로


def test_usd_snapshot_converted_by_fx():
    # currency=USD(정상)면 fx_factor=환율 → 스냅샷(USD)을 원화로 환산.
    mv, *_ = _eval("미국주식", qty=5, current=None, fx_factor=1500, direct_market=1000)
    assert mv == 1000 * 1500


def test_market_value_from_qty_when_no_snapshot():
    # 스냅샷 평가금액이 없을 때만 수량×현재가로 보강.
    mv, *_ = _eval("국내주식", qty=3, current=80_000.0, fx_factor=1, direct_market=None)
    assert mv == 3 * 80_000.0


def test_crypto_keeps_snapshot():
    mv, _l, _c, gl, *_ = _eval("크립토", qty=0.09, current=60_000.0, fx_factor=1,
                               direct_market=8_535_833, direct_gain=-6_812_663)
    assert mv == 8_535_833
    assert gl == -6_812_663
