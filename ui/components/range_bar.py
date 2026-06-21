"""
52주 레인지 바 (공용) — 막대(저~고) · 점(현재) · 우측 라벨(고점 근접/중간/바닥 근접).

원자재·지수·환율 등에서 52주 내 현재 위치를 한눈에 보여주는 동일 컴포넌트.
52주 범위는 yfinance 1년 일봉에서 계산한다(DB indicator_summary에는 52주 최저/최고 컬럼이 없음).

- fetch_52w_range(ticker): (low, high, current) 또는 None
- range_bar_html(items):   items=[{name, unit?, low, high, current, d1?}]
"""
from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_52w_range(ticker: str):
    """52주(1년) 최저·최고·현재가 → (low, high, current) 또는 None."""
    try:
        from data.session import cached_download
        raw = cached_download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if raw is None or raw.empty:
            return None
        c = raw["Close"]
        if hasattr(c, "columns"):
            c = c.iloc[:, 0]
        c = c.dropna()
        if len(c) < 2:
            return None
        return float(c.min()), float(c.max()), float(c.iloc[-1])
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_52w_ranges(tickers_key: str) -> dict:
    """여러 티커의 52주 (low, high, current)를 한 번의 배치 다운로드로 산출.
    tickers_key=콤마조인 문자열(캐시 키). 반환: {ticker: (low, high, current)} (산출 가능한 것만).
    페이지 게이지바에서 종목별 fetch_52w_range를 루프로 부르던 N회 다운로드를 1회로 줄인다."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    out: dict[str, tuple] = {}
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period="1y", interval="1d", progress=False, auto_adjust=True)
        if raw is None or raw.empty:
            return {}
        multi = len(tickers) > 1
        for tk in tickers:
            try:
                c = raw["Close"][tk].dropna() if multi else raw["Close"].dropna()
                if hasattr(c, "columns"):
                    c = c.iloc[:, 0].dropna()
                if len(c) >= 2:
                    out[tk] = (float(c.min()), float(c.max()), float(c.iloc[-1]))
            except Exception:
                pass
    except Exception:
        return {}
    return out


_RANGE_CSS = """<style>
.rb-wrap{margin:2px 0 6px}
.rb-row{display:grid;grid-template-columns:120px minmax(0,1fr) 168px;gap:16px;align-items:center;
  padding:12px 0;border-top:1px solid #262A33}
.rb-row:first-child{border-top:none}
.rb-name{font-size:13px;font-weight:850;color:#E7E9EE}
.rb-name small{display:block;color:#7E8694;font-size:10px;font-weight:700;margin-top:2px}
.rb-track{position:relative;height:8px;border-radius:999px;background:#1F232B;border:1px solid #262A33}
.rb-fill{position:absolute;left:0;top:0;bottom:0;border-radius:999px;background:#2A2E37}
.rb-dot{position:absolute;top:50%;width:13px;height:13px;border-radius:50%;background:#D9A441;
  border:2px solid #0E0F13;transform:translate(-50%,-50%);box-shadow:0 2px 8px rgba(217,164,65,.35)}
.rb-lo,.rb-hi{position:absolute;top:13px;font-size:9px;font-weight:700;color:#7E8694;font-variant-numeric:tabular-nums}
.rb-lo{left:0}.rb-hi{right:0}
.rb-right{text-align:right}
.rb-cur{font-size:15px;font-weight:950;color:#E7E9EE;font-variant-numeric:tabular-nums;line-height:1}
.rb-pos{display:inline-block;font-size:10px;font-weight:850;border-radius:999px;padding:2px 9px;margin-top:5px}
.rb-pos.hi{background:rgba(217,164,65,.15);color:#D9A441}
.rb-pos.mid{background:rgba(100,107,121,.18);color:#9AA0AD}
.rb-pos.lo{background:rgba(77,144,240,.15);color:#4D90F0}
.rb-chips{margin-top:6px;display:flex;gap:5px;justify-content:flex-end;flex-wrap:wrap}
.rb-chip{font-size:10px;font-weight:800;border-radius:6px;padding:2px 7px;font-variant-numeric:tabular-nums;
  background:#1E2029;border:1px solid #262A33}
.rb-chip.pos{color:#F25560}.rb-chip.neg{color:#4D90F0}.rb-chip.neu{color:#9AA0AD}
@media(max-width:760px){.rb-row{grid-template-columns:1fr}.rb-right{text-align:left}.rb-chips{justify-content:flex-start}}
</style>"""


def _hex_rgba(hex_c: str, a: float) -> str:
    h = hex_c.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def range_bar_html(items: list[dict], *, fmt: str = "{:,.2f}") -> str:
    """items=[{name, unit?, low, high, current, d1?, color?}] → 레인지 바 HTML.
    color 주면 점=시그니처 솔리드·채움=반투명(원자재 상징색). 없으면 채움=등락색·점=골드.
    위치 라벨: 상단 75%+ '고점 근접', 하단 25%- '바닥 근접', 그 외 '중간'."""
    rows = ""
    for it in items:
        lo, hi, cur = it["low"], it["high"], it["current"]
        pos = (cur - lo) / (hi - lo) if hi > lo else 0.5
        pct = max(0.0, min(1.0, pos)) * 100
        if pos >= 0.75:
            lab, cls = "고점 근접", "hi"
        elif pos <= 0.25:
            lab, cls = "바닥 근접", "lo"
        else:
            lab, cls = "중간", "mid"

        def _chip(v, lbl):
            if not isinstance(v, (int, float)):
                return ""
            c = "pos" if v > 0 else ("neg" if v < 0 else "neu")
            return f'<span class="rb-chip {c}">{lbl} {v:+.2f}%</span>'

        # 색: color(원자재 시그니처) 주면 점=솔리드·채움=반투명. 없으면 채움=등락색·점=골드.
        _color = it.get("color")
        if _color:
            _fill = _hex_rgba(_color, 0.38)
            _dot_style = f"left:{pct:.1f}%;background:{_color};box-shadow:0 2px 8px {_hex_rgba(_color, .35)}"
        else:
            _d1 = it.get("d1")
            _fill = ("rgba(242,85,96,.42)" if isinstance(_d1, (int, float)) and _d1 > 0
                     else "rgba(77,144,240,.42)" if isinstance(_d1, (int, float)) and _d1 < 0
                     else "#2A2E37")
            _dot_style = f"left:{pct:.1f}%"

        rows += (
            f'<div class="rb-row">'
            f'<div class="rb-name">{it["name"]}<small>{it.get("unit","")}</small></div>'
            f'<div class="rb-track"><i class="rb-fill" style="width:{pct:.1f}%;background:{_fill}"></i>'
            f'<span class="rb-dot" style="{_dot_style}"></span>'
            f'<span class="rb-lo">{fmt.format(lo)}</span><span class="rb-hi">{fmt.format(hi)}</span></div>'
            f'<div class="rb-right"><div class="rb-cur">{fmt.format(cur)}</div>'
            f'<span class="rb-pos {cls}">{lab}</span>'
            f'<div class="rb-chips">{_chip(it.get("d1"),"1D")}</div></div>'
            f'</div>'
        )
    return f'{_RANGE_CSS}<div class="rb-wrap">{rows}</div>'
