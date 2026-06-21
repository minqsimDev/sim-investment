from ui.components.mountain_scene import _build_html


def test_asset_journey_uses_clean_interactive_scene():
    html = _build_html(
        progress=0.42,
        current_asset=630_000_000,
        target_asset=1_500_000_000,
        annual_growth_rate=0.2,
    )

    assert "summit-target" in html
    assert "shelter" in html
    assert "journey-hiker" in html
    assert "journey-panel" in html
    assert "걸어온 길" in html
    assert "앞으로 갈 길" in html
    assert "pngtree" not in html.lower()
