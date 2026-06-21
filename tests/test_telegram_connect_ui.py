def test_render_importable():
    import ui.pages.telegram_connect as tc
    assert hasattr(tc, "render")
