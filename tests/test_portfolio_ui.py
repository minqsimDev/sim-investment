from ui.pages.portfolio import (
    _holdings_panel_html,
    _holdings_table_html,
    _portfolio_today_state,
    _journey_eta_display,
    _yf_history_symbol,
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


def test_journey_eta_unreachable_when_growth_negative():
    # 연 성장률(CAGR) 음수 → 현재 추세로는 투자 실패
    m = {"cagr_pct": -12.3, "years_to_goal": None}
    assert _journey_eta_display(m, current=50_000_000, target=100_000_000) == "투자 실패"


def test_journey_eta_unreachable_when_growth_flat():
    m = {"cagr_pct": 0.0, "years_to_goal": None}
    assert _journey_eta_display(m, current=50_000_000, target=100_000_000) == "투자 실패"


def test_journey_eta_shows_period_when_growing():
    # 성장 중이면 기간 라벨(투자 실패가 아님)
    m = {"cagr_pct": 8.0, "years_to_goal": 3.5}
    out = _journey_eta_display(m, current=50_000_000, target=100_000_000)
    assert out != "투자 실패"
    assert "년" in out or "개월" in out


def test_journey_eta_reached_goal():
    m = {"cagr_pct": -5.0, "years_to_goal": None}  # 음수여도 이미 목표 넘었으면 도달
    assert _journey_eta_display(m, current=120_000_000, target=100_000_000) == "목표 도달"


def test_yf_history_symbol_crypto_gets_usd_pair():
    # bare 'BTC' 는 yfinance 에서 엉뚱한 주식 → 'BTC-USD'(USD)로 정규화
    assert _yf_history_symbol("BTC", None, "크립토") == ("BTC-USD", "USD")
    assert _yf_history_symbol("eth", None, "크립토") == ("ETH-USD", "USD")


def test_yf_history_symbol_keeps_normal_tickers():
    assert _yf_history_symbol("005930.KS", "KRW", "국내주식") == ("005930.KS", "KRW")
    assert _yf_history_symbol("TSLA", "USD", "미국주식") == ("TSLA", "USD")
    assert _yf_history_symbol("BTC-USD", "USD", "크립토") == ("BTC-USD", "USD")
