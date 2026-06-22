from ui.pages.portfolio import (
    _holdings_panel_html,
    _holdings_table_html,
    _portfolio_today_state,
    _delete_holding,
)


POSITION = {
    "category": "미국주식",
    "name": "테슬라",
    "ticker": "TSLA",
    "currency": "USD",
    "quantity": 1,
    "current_price": 400,
    "market_value": 600_000,
    "market_value_local": 394.22,
    "gain_loss": 120_000,
    "gain_loss_pct": 25.0,
    "today_change_pct": 4.6,
    "weight": 72.1,
}


def test_today_outlier_is_flagged():
    value, note, cls, state = _portfolio_today_state(
        {
            "today_change_amount": 16_000_000,
            "today_change_pct": 5002.43,
            "total_market_value": 323_097,
        }
    )

    assert value == "데이터 확인 필요"
    assert "비정상" in note
    assert cls == "pd-warn"
    assert state == "outlier"


def test_holdings_table_uses_krw_primary_and_usd_secondary():
    html = _holdings_table_html(
        [POSITION],
        {"TSLA": 420},
    )

    assert "₩600,000" in html          # KRW 1차(원화 환산)
    assert "≈ $394.22" in html          # USD 2차(현지통화)
    assert "pd-table-card" in html      # 현재 구조: 테이블형 카드
    assert "여력" in html                # 행 상세(목표가·여력)
    assert "pd-holding-card" not in html  # 옛 카드 그리드 아님


def test_holdings_panel_wraps_compact_table():
    html = _holdings_panel_html("핵심 보유종목", "비중순", [POSITION], {"TSLA": 420})

    assert "pd-list-panel" in html
    assert "핵심 보유종목" in html
    assert "pd-table-card" in html
    assert "hcv-card" not in html


def test_delete_holding_removes_index_and_preserves_order():
    holdings = [
        {"name": "삼성전자", "ticker": "005930.KS"},
        {"name": "SK하이닉스", "ticker": "000660.KS"},
        {"name": "NAVER", "ticker": "035420.KS"},
    ]

    result = _delete_holding(holdings, 1)

    assert [h["name"] for h in result] == ["삼성전자", "NAVER"]
    # 원본 리스트는 변형하지 않는다(새 리스트 반환)
    assert len(holdings) == 3


def test_delete_holding_out_of_range_returns_unchanged_copy():
    holdings = [{"name": "삼성전자", "ticker": "005930.KS"}]

    assert _delete_holding(holdings, 5) == holdings
    assert _delete_holding(holdings, -1) == holdings
