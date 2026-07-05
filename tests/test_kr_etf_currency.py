"""국내 ETF 인식 회귀 — 티커가 6자리 코드(.KS 미부착)이거나 없어도
KRW·ETF·.KS 시세티커로 정확히 처리돼야 한다 (USD 오판 → 평가액 ×환율 폭증 방지)."""
from ui.pages.portfolio import _category_for_holding, _holding_currency, _quote_ticker


def test_kr_etf_bare_code():
    row = {"name": "TIGER 미국S&P500", "ticker": "379800", "asset_class": "etf",
           "평가금액": 5_000_000, "수익률": 10.0}
    cat = _category_for_holding(row, "379800")
    assert cat == "ETF"
    assert _holding_currency(row, "379800", cat) == "KRW"       # ← 버그: USD 였음
    assert _quote_ticker("379800", cat) == "379800.KS"          # ← 버그: 379800 그대로였음


def test_kr_etf_no_ticker():
    row = {"name": "KODEX 200", "asset_class": "etf", "평가금액": 3_000_000}
    cat = _category_for_holding(row, "")
    assert cat == "ETF"
    assert _holding_currency(row, "", cat) == "KRW"             # 발행사 접두로 국내 판정


def test_kr_etf_ks_suffix_still_ok():
    row = {"name": "TIGER 미국나스닥100", "ticker": "133690.KS"}
    cat = _category_for_holding(row, "133690.KS")
    assert cat == "ETF"
    assert _holding_currency(row, "133690.KS", cat) == "KRW"
    assert _quote_ticker("133690.KS", cat) == "133690.KS"


def test_us_etf_unaffected():
    row = {"name": "SPDR S&P 500 ETF", "ticker": "SPY", "asset_class": "etf"}
    cat = _category_for_holding(row, "SPY")
    assert cat == "ETF"
    assert _holding_currency(row, "SPY", cat) == "USD"          # 해외 ETF 는 그대로 USD
    assert _quote_ticker("SPY", cat) == "SPY"


def test_kr_stock_bare_code_quote():
    # 국내주식도 6자리 코드면 시세 조회용 .KS 부착
    assert _quote_ticker("005930", "국내주식") == "005930.KS"
