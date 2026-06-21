from ui.pages.risk_signals import (
    _portfolio_impact_html,
    _signal_matrix_html,
    _summary_cards_html,
)


def test_risk_signal_matrix_has_aligned_columns():
    html = _signal_matrix_html(
        [
            {"signal": "Rate Pressure", "lv": "HIGH", "col": "high"},
            {"signal": "Semiconductor Momentum", "lv": "BULLISH", "col": "low"},
        ]
    )

    assert "rsk-matrix-head" in html
    assert "상태" in html
    assert "해석" in html
    assert "대응 후보" in html
    assert html.count("rsk-matrix-row") == 2


def test_portfolio_impact_uses_table_not_card_grid():
    html = _portfolio_impact_html()

    assert "rsk-impact-table" in html
    assert "rsk-impact-row head" in html
    assert "rsk-impact-card" not in html


def test_summary_cards_render_four_equal_items():
    html = _summary_cards_html(
        55,
        "warn",
        "주의 구간",
        [
            {"signal": "Rate Pressure", "lv": "HIGH", "col": "high"},
            {"signal": "Dollar Strength", "lv": "MEDIUM", "col": "mid"},
            {"signal": "Semiconductor Momentum", "lv": "BULLISH", "col": "low"},
        ],
    )

    assert "rsk-kpi-row" in html
    assert html.count("rsk-kpi") >= 4
    assert "종합 리스크" in html
