"""price_source 라우팅 스위치 — USE_TOSS 로 토스/yfinance 단일 지점 전환."""
import data.price_source as ps


def test_use_toss_off_routes_everything_to_yfinance(monkeypatch):
    monkeypatch.setattr(ps, "USE_TOSS", False)
    # 토스가 강점이던 국내·미국·USDKRW 도 전부 yfinance 로(원본 심볼 그대로)
    assert ps._classify("005930.KS") == ("yfinance", "005930.KS")
    assert ps._classify("AAPL") == ("yfinance", "AAPL")
    assert ps._classify("USDKRW=X") == ("yfinance", "USDKRW=X")
    # 원래 yfinance 대상도 당연히 yfinance
    assert ps._classify("BTC-USD") == ("yfinance", "BTC-USD")
    assert ps._classify("GC=F") == ("yfinance", "GC=F")


def test_use_toss_on_keeps_toss_routing(monkeypatch):
    monkeypatch.setattr(ps, "USE_TOSS", True)
    assert ps._classify("005930.KS") == ("toss_price", "005930")
    assert ps._classify("AAPL") == ("toss_price", "AAPL")
    assert ps._classify("USDKRW=X") == ("toss_fx", ("USD", "KRW"))
    # 토스 미지원군은 켜져 있어도 yfinance
    assert ps._classify("BTC-USD") == ("yfinance", "BTC-USD")
    assert ps._classify("^VIX") == ("yfinance", "^VIX")


def test_source_label_follows_use_toss(monkeypatch):
    from ui.components import live_refresh as lr
    # 토스 켜짐: 기존대로 KR/US=토스, 크립토=yf, 혼합
    monkeypatch.setattr(ps, "USE_TOSS", True)
    assert lr._source_label(["KR"]) == "토스증권 시세"
    assert lr._source_label(["CRYPTO"]) == "yfinance ~15분 지연"
    assert lr._source_label(["KR", "CRYPTO"]) == "토스·yfinance 혼합"
    # 토스 꺼짐(단일 소스): KR/US 도 실제론 yfinance → 라벨도 yfinance(거짓표기 금지)
    monkeypatch.setattr(ps, "USE_TOSS", False)
    assert lr._source_label(["KR"]) == "yfinance ~15분 지연"
    assert lr._source_label(["KR", "US"]) == "yfinance ~15분 지연"
    assert lr._source_label(["KR", "CRYPTO"]) == "yfinance ~15분 지연"
