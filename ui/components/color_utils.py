"""색 유틸 — Lab 변환·ΔE(지각 색차)·명도 시프트.

시그니처 색의 구별성(ΔE) 판정과 중복색 명도 조정에 쓰는 공용 프리미티브.
ETF·한국주식·미국주식 등 여러 페이지가 동일 로직을 쓰던 것을 한 곳으로 통합한다.
"""
from __future__ import annotations


def hex_to_lab(h: str) -> tuple[float, float, float]:
    """#RRGGBB → CIE Lab. sRGB→선형→XYZ(D65)→Lab."""
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def f(c):
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    r, g, b = f(r), f(g), f(b)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    x /= 0.95047
    z /= 1.08883

    def g2(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = g2(x), g2(y), g2(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """CIE76 색차 — 두 Lab 좌표의 유클리드 거리. (≈22+ = 또렷이 구별)"""
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def shade(h: str, fct: float) -> str:
    """명도 시프트 — fct≥1 밝게(흰색 쪽), fct<1 어둡게. 같은 테마색 중복 구별용."""
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if fct >= 1:
        r, g, b = (int(c + (255 - c) * (fct - 1)) for c in (r, g, b))
    else:
        r, g, b = (int(c * fct) for c in (r, g, b))
    return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in (r, g, b))
