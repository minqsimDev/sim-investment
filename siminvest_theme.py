"""
siminvest_theme.py — SIM INVESTMENT 다크 테마 헬퍼

config.toml이 색·폰트·라운드를 처리하고, 이 모듈은 Streamlit이
기본 제공하지 않는 "한국식 등락 색(상승=레드 / 하락=블루)"을 담당합니다.
"""

import streamlit as st

UP    = "#F25560"
DOWN  = "#4D90F0"
GOLD  = "#D9A441"
SURFACE = "#16181F"
BORDER  = "rgba(255,255,255,.07)"


def inject_css():
    st.html(f"""
    <style>
      .up   {{ color: {UP};   font-variant-numeric: tabular-nums; font-weight: 600; }}
      .down {{ color: {DOWN}; font-variant-numeric: tabular-nums; font-weight: 600; }}
      .num  {{ font-variant-numeric: tabular-nums; }}
      .sv-metric {{ background:{SURFACE}; border:1px solid {BORDER};
        border-radius:12px; padding:16px 18px; }}
      .sv-metric .l {{ font-size:12px; color:#9AA0AD; }}
      .sv-metric .v {{ font-size:26px; font-weight:600; margin-top:4px;
        font-variant-numeric:tabular-nums; line-height:1.2; }}
      .sv-metric .d {{ font-size:14px; font-weight:600; margin-top:2px;
        font-variant-numeric:tabular-nums; }}
    </style>
    """)


def pct(v: float) -> str:
    cls  = "up" if v >= 0 else "down"
    sign = "+" if v >= 0 else "−"
    return f'<span class="{cls}">{sign}{abs(v):.2f}%</span>'


def metric(label: str, value: str, delta_pct: float):
    cls  = "up" if delta_pct >= 0 else "down"
    sign = "+" if delta_pct >= 0 else "−"
    st.html(f'''
    <div class="sv-metric">
      <div class="l">{label}</div>
      <div class="v">{value}</div>
      <div class="d {cls}">{sign}{abs(delta_pct):.2f}%</div>
    </div>''')


def color_change(val):
    """pandas Styler용: 양수=레드, 음수=블루"""
    if isinstance(val, (int, float)):
        if val > 0:
            return f"color: {UP}"
        if val < 0:
            return f"color: {DOWN}"
    return ""


def bar_color(v: float) -> str:
    return UP if v >= 0 else DOWN


# ── 게이지 온도계 그라디언트 ──────────────────────────────────────────────────
# 리스크·탐욕 게이지 공통 온도계: 차가운 블루(안전/공포) → 골드(중립) → 짙은 주황(위험/탐욕).
# 끝단을 빨강 대신 짙은 주황으로 둬 상승색(#F25560)과 더 분리(적록색약·컨벤션 충돌 회피).
# 색만으로 판단하지 않도록 호출부에서 구간 라벨·흰 바늘(값 위치)을 함께 유지한다.
_GAUGE_TEAL = (58, 143, 194)   # 안전/공포 — 차가운 블루
_GAUGE_GOLD = (217, 164, 65)   # 중립/주의 — 골드
_GAUGE_RED  = (196, 106, 43)   # 위험/탐욕 — 짙은 주황


def _lerp(c1, c2, t: float):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def gauge_gradient_steps(n: int = 24) -> list[dict]:
    """0~100 게이지 배경을 청록→골드→짙은빨강 그라디언트 밴드(n개)로 만든다(plotly steps)."""
    steps = []
    for i in range(n):
        t = i / (n - 1)
        c = _lerp(_GAUGE_TEAL, _GAUGE_GOLD, t / 0.5) if t < 0.5 \
            else _lerp(_GAUGE_GOLD, _GAUGE_RED, (t - 0.5) / 0.5)
        steps.append({"range": [100 * i / n, 100 * (i + 1) / n],
                      "color": f"rgb({c[0]},{c[1]},{c[2]})"})
    return steps
