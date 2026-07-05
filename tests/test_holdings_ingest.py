"""인제스트 정규화 게이트 — 파서의 불안정 출력이 저장 전에 표준형으로 확정되는지."""
from core.holdings_ingest import canonicalize_holdings


def test_kr_etf_bare_code_normalized():
    clean, dropped = canonicalize_holdings([
        {"name": "TIGER 미국S&P500", "ticker": "360750", "asset_class": "etf",
         "평가금액": 5_000_000, "수익률": 12.5},
    ])
    assert not dropped
    h = clean[0]
    assert h["ticker"] == "360750.KS"
    assert h["currency"] == "KRW"
    assert h["asset_class"] == "etf"


def test_kr_etf_no_ticker_currency_krw():
    clean, _ = canonicalize_holdings([{"name": "KODEX 200", "평가금액": 3_000_000}])
    assert clean[0]["currency"] == "KRW"
    assert clean[0]["asset_class"] == "etf"


def test_us_stock_and_etf_usd():
    clean, _ = canonicalize_holdings([
        {"name": "엔비디아", "ticker": "NVDA", "평가금액": 18488.7},
        {"name": "SPDR S&P 500 ETF", "ticker": "SPY", "asset_class": "etf", "평가금액": 1000},
    ])
    assert clean[0]["currency"] == "USD" and clean[0]["asset_class"] == "us_stock"
    assert clean[1]["currency"] == "USD" and clean[1]["asset_class"] == "etf"


def test_crypto_suffix_and_krw():
    clean, _ = canonicalize_holdings([
        {"name": "비트코인", "ticker": "BTC", "asset_class": "crypto", "평가금액": 8_500_000},
    ])
    assert clean[0]["ticker"] == "BTC-USD"
    assert clean[0]["currency"] == "KRW"   # 국내거래소 원화 평가


def test_parser_wrong_currency_ignored():
    # 파서가 미국주식에 currency=KRW 오태깅해도 티커 기준 USD 확정
    clean, _ = canonicalize_holdings([
        {"name": "테슬라", "ticker": "TSLA", "currency": "KRW", "평가금액": 232442.1},
    ])
    assert clean[0]["currency"] == "USD"


def test_unreadable_rows_reported_not_silently_dropped():
    clean, dropped = canonicalize_holdings([
        {"name": "삼성전자", "ticker": "005930.KS", "평가금액": 31_000_000},
        {"name": "읽다만종목"},                       # 금액·수량 없음
        {"ticker": "???", "평가금액": 100},            # 이름 없음
    ])
    assert len(clean) == 1
    assert len(dropped) == 2
    assert dropped[0]["name"] == "읽다만종목" and "캡처" in dropped[0]["reason"]
    assert dropped[1]["name"] == "(이름 없음)"


def test_qty_avgprice_without_eval_ok():
    clean, dropped = canonicalize_holdings([
        {"name": "기아", "ticker": "000270", "보유수량": 10, "평균단가": 120000},
    ])
    assert not dropped and clean[0]["ticker"] == "000270.KS"
