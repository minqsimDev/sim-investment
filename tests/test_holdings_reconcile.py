"""보유 금액 자릿수(소수점 유실) 결정론적 보정 테스트."""
from core.holdings_reconcile import reconcile_holding, reconcile_holdings


def _approx(a, b, tol=0.02):
    return abs(a - b) / max(abs(b), 1e-9) <= tol


def test_decimal_loss_fixed_by_pershare_anchor():
    # "$41,694.80" 이 41694800 로 ×1000 부풀려진 경우 — 주당 현재가 앵커로 ÷1000 복원
    h = {"shares": 140, "current_price": 281.74,
         "eval_amount": 41694800, "purchase_amount": 27543519, "profit_loss_pct": 51.2}
    reconcile_holding(h)
    assert _approx(h["eval_amount"], 41694.8)
    assert abs(h["eval_amount"] / (140 * 281.74) - 1) < 0.15      # 앵커 근방
    # eval 만 앵커가 있으니 purchase 는 손익률(plp)로 재계산되어 일관성 유지
    assert _approx(h["purchase_amount"], h["eval_amount"] / 1.512)
    assert _approx(h["profit_loss"], h["eval_amount"] - h["purchase_amount"])


def test_correct_values_untouched():
    # 정상 스케일(주당가와 일치)은 건드리지 않는다
    h = {"shares": 583, "current_price": 411.84,
         "eval_amount": 232442.1, "purchase_amount": 128502.55, "profit_loss_pct": 80.68}
    reconcile_holding(h)
    assert h["eval_amount"] == 232442.1
    assert h["purchase_amount"] == 128502.55


def test_x100_loss():
    h = {"shares": 10, "current_price": 50.0, "eval_amount": 50000, "profit_loss_pct": 0}
    reconcile_holding(h)
    assert _approx(h["eval_amount"], 500)


def test_price_fn_anchor_when_pershare_missing():
    # 주당가가 화면에 없을 때 price_fn(라이브 시세)으로 앵커 — 복구 시나리오
    h = {"ticker": "AAPL", "shares": 140,
         "eval_amount": 41694800, "purchase_amount": 27543519, "profit_loss_pct": 51.2}
    reconcile_holding(h, price_fn=lambda tk, ac: 281.74)
    assert _approx(h["eval_amount"], 41694.8)


def test_no_anchor_is_safe():
    # 앵커 전혀 없으면 금액을 건드리지 않고 크래시도 없다
    h = {"shares": None, "eval_amount": 41694800, "profit_loss_pct": 51.2}
    reconcile_holding(h)
    assert h["eval_amount"] == 41694800


def test_krw_holding_with_usd_anchor_not_falsely_scaled():
    # USD 네이티브 앵커(price_fn)+fx 가 있을 때, 화면 금액이 정상 KRW면 ×10ⁿ 오보정하지 않는다.
    # 비트코인: 0.0901498 BTC, 라이브 $59789, 저장 평가 8,535,833 KRW(정상) — 그대로 둬야.
    h = {"ticker": "BTC", "asset_class": "crypto", "shares": 0.0901498,
         "eval_amount": 8535833, "purchase_amount": 15348497, "profit_loss_pct": -44.39}
    reconcile_holding(h, price_fn=lambda tk, ac: 59789.0, fx=1300.0)
    assert h["eval_amount"] == 8535833


def test_korean_field_aliases_synced():
    h = {"shares": 140, "현재가": 281.74, "평가금액": 41694800, "수익률": 51.2}
    reconcile_holdings([h])
    assert _approx(h["평가금액"], 41694.8)
    assert _approx(h["eval_amount"], 41694.8)   # 영문 별칭도 함께 채워짐
