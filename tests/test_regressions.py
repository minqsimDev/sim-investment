import builtins
import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_login_import_does_not_require_vision_parser(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "core.vision_parser":
            raise AssertionError("login should import vision parser only when analyzing images")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("ui.pages.login", None)

    importlib.import_module("ui.pages.login")


def test_vision_parser_import_does_not_require_google_genai(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "google" or name.startswith("google."):
            raise AssertionError("google-genai should be imported only during image parsing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sys.modules.pop("core.vision_parser", None)

    module = importlib.import_module("core.vision_parser")
    with pytest.raises(EnvironmentError):
        module.parse_portfolio_image(b"not-an-image")


def test_deprecated_streamlit_apis_not_used():
    """Use st.iframe instead of deprecated Streamlit component HTML helpers."""
    checked = [
        ROOT / "ui" / "components" / "mountain_scene.py",
        ROOT / "ui" / "pages" / "market.py",
    ]

    for path in checked:
        source = path.read_text(encoding="utf-8")
        assert "streamlit.components" not in source, f"deprecated components module used in {path.name}"
        assert "components.html(" not in source, f"deprecated components.html used in {path.name}"
        assert "components.v1.html(" not in source, f"deprecated components.v1.html used in {path.name}"
        assert "_stc.html(" not in source, f"deprecated component html alias used in {path.name}"
        assert 'getattr(st, "components")' not in source, f"deprecated components API hidden via getattr in {path.name}"
        assert "getattr(st, 'components')" not in source, f"deprecated components API hidden via getattr in {path.name}"
