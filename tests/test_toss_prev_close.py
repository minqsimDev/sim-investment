from data.providers.toss_provider import prev_close_from_row


def test_prev_close_picks_known_keys():
    # 토스 /prices 응답이 전일종가를 어떤 키로 주든 그 값을 뽑는다(배치로 전일종가 확보 → 종목당 캔들 호출 제거)
    for key in ("base", "previousClose", "prevClose", "basePrice", "closePrice"):
        assert prev_close_from_row({"lastPrice": 100, key: 95.5}) == 95.5


def test_prev_close_none_when_absent():
    # 전일종가 필드가 없으면 None → 호출부가 캔들 폴백으로 처리
    assert prev_close_from_row({"lastPrice": 100, "currency": "KRW"}) is None


def test_prev_close_ignores_non_numeric():
    assert prev_close_from_row({"base": "N/A", "lastPrice": 100}) is None
