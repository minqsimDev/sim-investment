"""HTML iframe embedding helper — centralises components.v1.html usage."""
from __future__ import annotations

import streamlit as st


def embed_html(html: str, height: int, scrolling: bool = False) -> None:
    """Render `html` inside an isolated iframe of the given height."""
    _cv1 = getattr(st, "components").v1
    _cv1.html(html, height=height, scrolling=scrolling)
