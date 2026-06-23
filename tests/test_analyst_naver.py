from src.analyst_naver import (
    _opinion_label,
    _us_query_variants,
    _parse_consensus,
    _is_us,
)


def test_opinion_label_bands():
    assert _opinion_label("4.6") == "강력매수"
    assert _opinion_label("4.0") == "매수"
    assert _opinion_label("3.0") == "보유"
    assert _opinion_label("2.0") == "시장하회"
    assert _opinion_label("1.2") == "매도"
    assert _opinion_label(None) == "—"


def test_us_query_variants_handles_dash():
    # BRK-B 는 네이버 검색에서 'BRK-B' 로 안 잡혀 변형 시도 필요
    assert _us_query_variants("BRK-B") == ["BRK-B", "BRK.B", "BRKB"]
    assert _us_query_variants("AAPL") == ["AAPL"]


def test_is_us_vs_kr():
    assert _is_us("AAPL") is True
    assert _is_us("005930.KS") is False
    assert _is_us("000660.KQ") is False


def test_parse_consensus_extracts_common_fields():
    ci = {"priceTargetMean": "461,250", "recommMean": "4.04", "createDate": "2026-06-22"}
    out = _parse_consensus(ci)
    assert out["목표가_평균"] == 461250.0
    assert out["투자의견"] == "매수"
    assert out["의견점수"] == 4.04        # 산점도 Y축용 raw recommMean(1~5)
    assert out["기준일"] == "2026-06-22"


def test_parse_consensus_empty():
    out = _parse_consensus({})
    assert out["목표가_평균"] is None
    assert out["투자의견"] == "—"
    assert out["의견점수"] is None
    assert out["기준일"] is None
