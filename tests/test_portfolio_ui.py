from ui.pages.portfolio import _holdings_panel_html, _holdings_table_html, _portfolio_today_state


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

    assert "₩600,000" in html
    assert "≈ $394.22" in html
    assert "상세</div>" in html
    assert 'details class="pd-row-actions"' in html
    assert "pd-holding-card" not in html


def test_holdings_panel_wraps_compact_table():
    html = _holdings_panel_html("핵심 보유종목", "비중순", [POSITION], {"TSLA": 420})

    assert "pd-list-panel" in html
    assert "핵심 보유종목" in html
    assert "pd-table-card" in html
    assert "hcv-card" not in html
