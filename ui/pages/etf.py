"""시장 — ETF 탭. 미국 지수·섹터 ETF(QQQ·SPY·SOXX·GLD·TLT 등) + 국내 ETF.

미국·한국과 동일 골격(스캔 레이어 + 슬림 표). 데이터는 load_market_data()
benchmarks·my_etfs 소스 재사용(자동 산출, 하드코딩 금지).
"""
from __future__ import annotations

import streamlit as st

from data.loader import load_market_data
from ui.components.dash_style import (
    empty_state,
    inject_css, jj_footer, mark_active_nav, show_skeleton,
    mkt_page_header, mkt_section_header, period_radio,
)
from ui.components.scan_layer import scan_layer_html
from ui.components.slim_table import slim_table
from ui.components.range_bar import fetch_52w_ranges, range_bar_html
from ui.components.color_utils import shade as _shade

# 종목 내용(추종 대상)에 맞는 시그니처 색 — 이름/티커 키워드 매칭(구체적 항목 먼저).
# 앵커 색은 색상환에 고르게 펼쳐 ΔE(지각 거리)≥22를 만족 — 비교 차트에서 서로 또렷이 구별된다.
_ETF_THEME = [
    (("반도체", "SOXX", "SMH"),                              "#17B0C0"),  # 반도체 = 칩 시안
    (("2차전지", "배터리", "전지"),                            "#46B36A"),  # 2차전지 = 그린
    (("골드", "금 ", "금E", "GLD", "골드선물"),                "#D9A441"),  # 금 = 골드
    (("은 ", "은E", "SLV"),                                  "#B6BCC8"),  # 은 = 실버
    (("채권", "국고채", "국채", "장기채", "TLT", "AGG", "CD금리"), "#5F8C7A"),  # 채권 = 안정 청록
    (("고배당", "배당", "리츠", "부동산"),                      "#C19A4E"),  # 배당·리츠 = 머스타드
    (("나스닥", "QQQ", "테크"),                               "#8A5CD6"),  # 나스닥·테크 = 바이올렛
    (("코스닥",),                                            "#D85A93"),  # 코스닥 = 로즈(성장)
    (("S&P", "SPY", "미국S&P", "KODEX 200", "다우", "DIA"),    "#3D7BE0"),  # 대형 지수 = 마켓 블루
]
# 같은 테마 중복 시 명도 시프트 단계 — 어둡게 우선(밝은 영역엔 은·실버가 몰려 충돌하므로).
_DEDUP_SHIFTS = [1.0, 0.6, 1.7, 0.45]
# 테마 미매칭 ETF 폴백 — 구별 잘 되는 Dark2 계열
_ETF_PALETTE = [
    "#26C0A0", "#E0843C", "#9B8AE0", "#E84D9B", "#8DC63F", "#E6C229", "#C9925A", "#6FB1E0",
]


def _etf_color(name: str, ticker: str) -> str | None:
    """ETF 이름/티커 → 추종 대상에 맞는 시그니처 색(매칭 시), 없으면 None."""
    s = f"{name} {ticker}".upper()
    for keys, col in _ETF_THEME:
        if any(k.upper() in s for k in keys):
            return col
    return None


# 명도 시프트(_shade)는 ui.components.color_utils 공용 모듈 사용(상단 import)

# 주요 국내 ETF 유니버스 — 시장 조망용(대표 지수·섹터·채권·해외). '시장' 탭은 제너럴 시장 파악이
# 목적이므로 보유(config my_etfs)가 아니라 시총/대표 큐레이션을 노출한다(보유는 포트폴리오 영역).
# (group, name, ticker) — 티커는 yfinance 실데이터 확인됨.
# 동일 지수 추종 중복 트래커(TIGER 200/코스닥150/반도체, ACE S&P500)는 제외하고 20종 큐레이션.
_KR_ETF_UNIVERSE = [
    ("대표 지수",   "KODEX 200",          "069500.KS"),
    ("대표 지수",   "KODEX 코스닥150",     "229200.KS"),
    ("섹터·테마",   "KODEX 반도체",        "091160.KS"),
    ("섹터·테마",   "KODEX 2차전지산업",   "305720.KS"),
    ("배당·리츠",   "KODEX 고배당",        "279530.KS"),
    ("채권·현금",   "KODEX 종합채권액티브", "273130.KS"),
    ("해외·원자재", "TIGER 미국S&P500",    "360750.KS"),
    ("해외·원자재", "KODEX 골드선물(H)",   "132030.KS"),
]  # 각 그룹 대표만 8종으로 큐레이션(레버리지·인버스·중복 트래커 제외 → 시장 조망 핵심)
_KR_ETF_GROUPS = ["대표 지수", "섹터·테마", "배당·리츠", "채권·현금", "해외·원자재"]


@st.cache_data(ttl=900, show_spinner=False)
def _etf_history(tickers_key: str, period: str = "6mo") -> dict:
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period=period, interval="1d", progress=False, auto_adjust=True)
        if raw.empty:
            return {}
        out, multi = {}, len(tickers) > 1
        for tk in tickers:
            try:
                closes = raw["Close"][tk].dropna() if multi else raw["Close"].dropna()
                if not closes.empty:
                    out[tk] = closes
            except Exception:
                pass
        return out
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def _etf_turnover(tickers_key: str) -> dict:
    """티커별 거래대금(거래량×종가, 최근 20일 평균) — 규모/유동성 순위 산출용(매일 자동 갱신)."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if raw.empty:
            return {}
        out, multi = {}, len(tickers) > 1
        for tk in tickers:
            try:
                c = (raw["Close"][tk] if multi else raw["Close"]).dropna()
                v = (raw["Volume"][tk] if multi else raw["Volume"]).dropna()
                tv = (c * v).dropna()
                if not tv.empty:
                    out[tk] = float(tv.tail(20).mean())
            except Exception:
                pass
        return out
    except Exception:
        return {}


def _ind(closes) -> dict:
    if closes is None or getattr(closes, "empty", True):
        return {"3M %": None, "추세": "—", "MA20 이격%": None}

    def _ret(n):
        if len(closes) < n + 1:
            return None
        past, now = float(closes.iloc[-(n + 1)]), float(closes.iloc[-1])
        return round((now - past) / past * 100, 2) if past else None

    latest = float(closes.iloc[-1])
    ma20 = float(closes.iloc[-20:].mean()) if len(closes) >= 20 else None
    ma60 = float(closes.iloc[-60:].mean()) if len(closes) >= 60 else None
    if ma20 and ma60:
        trend = "상승" if latest > ma20 > ma60 else ("하락" if latest < ma20 < ma60 else "중립")
    elif ma20:
        trend = "상승" if latest > ma20 else "하락"
    else:
        trend = "—"
    return {"3M %": _ret(63), "추세": trend,
            "MA20 이격%": round((latest - ma20) / ma20 * 100, 2) if ma20 else None}


def _us_items(bm, history) -> list[dict]:
    items = []
    for _, r in bm.iterrows():
        tk = r.get("ticker", "")
        if not tk:
            continue
        s = history.get(tk)
        ind = _ind(s)
        items.append({
            "name": r.get("name", tk), "ticker": tk,
            "price": r.get("price") if isinstance(r.get("price"), (int, float)) else None,
            "d1": r.get("change_pct") if isinstance(r.get("change_pct"), (int, float)) else None,
            "series": [float(v) for v in s.iloc[-63:].tolist()] if s is not None and not s.empty else [],
            "ma20": ind["MA20 이격%"], "m3": ind["3M %"], "trend": ind["추세"],
        })
    return items


def _kr_items(history) -> list[dict]:
    items = []
    for _group, name, tk in _KR_ETF_UNIVERSE:
        s = history.get(tk)
        price = float(s.iloc[-1]) if s is not None and not s.empty else None
        d1 = (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
              if s is not None and len(s) >= 2 and s.iloc[-2] else None)
        ind = _ind(s)
        items.append({
            "name": name, "ticker": tk, "price": price, "d1": d1,
            "series": [float(v) for v in s.iloc[-63:].tolist()] if s is not None and not s.empty else [],
            "ma20": ind["MA20 이격%"], "m3": ind["3M %"], "trend": ind["추세"],
        })
    return items


def _render_etf_section(items: list[dict], *, price_fmt: str, key: str, chart_cap: int = 8):
    """원자재·외환과 동일 구성: 스캔 → 게이지바(테마색) → 표로보기 토글 → 가격 추이 비교(상위 N·spline)."""
    import plotly.graph_objects as go
    items = [it for it in items if it.get("price") is not None]
    if not items:
        empty_state("ETF 데이터 준비 중")
        return
    # 종목 내용(추종 대상)에 맞는 시그니처 색. 테마 미매칭은 폴백 팔레트.
    # 같은 테마색이 겹치면(예: SOXX·SMH 둘 다 반도체) 명도를 단계별로 밝혀 구별.
    _used, _pal_i = {}, 0
    for it in items:
        c = _etf_color(it["name"], it["ticker"])
        if c is None:
            c = _ETF_PALETTE[_pal_i % len(_ETF_PALETTE)]
            _pal_i += 1
        n = _used.get(c, 0)
        _used[c] = n + 1
        it["color"] = _shade(c, _DEDUP_SHIFTS[min(n, len(_DEDUP_SHIFTS) - 1)]) if n else c

    # 스캔 레이어
    scan = [{"name": it["name"], "d1": it["d1"], "ma20": it["ma20"],
             "series": it["series"], "color": it["color"]} for it in items]
    _scan = scan_layer_html(scan)
    if _scan:
        st.markdown(_scan, unsafe_allow_html=True)

    # 52주 게이지 바 — 1회 배치 다운로드
    _rb = []
    _ranges = fetch_52w_ranges(",".join(it["ticker"] for it in items))
    for it in items:
        rng = _ranges.get(it["ticker"])
        if not rng:
            continue
        lo, hi, cur = rng
        _rb.append({"name": it["name"], "unit": "", "low": lo, "high": hi, "current": cur,
                    "d1": it["d1"], "color": it["color"]})
    if _rb:
        st.markdown(range_bar_html(_rb, fmt=price_fmt), unsafe_allow_html=True)
        st.caption("규모(거래대금 20일 평균) 상위순 · 막대 = 52주 최저~최고 · 점 = 현재가 · 우측 라벨 = 범위 내 위치")

    # 정밀 표 — 표로 보기 토글 뒤로(기본 접힘)
    if st.toggle("표로 보기", key=f"etf_{key}_tbl", value=False):
        rows = sorted(
            [{"ETF": it["name"], "현재가": it["price"], "1D %": it["d1"],
              "3M %": it["m3"], "추세": it["trend"]} for it in items],
            key=lambda x: abs(x["1D %"]) if isinstance(x["1D %"], (int, float)) else -1, reverse=True)
        slim_table(rows, key=f"etf_{key}", name_key="ETF",
                   price_key="현재가", price_fmt=price_fmt, show_conclusion=False, col_toggle=False)

    # 가격 추이 비교(상위 chart_cap종 · 기준=100 정규화 · spline) — 원자재·외환과 동일 양식
    _top = items[:chart_cap]
    st.markdown(mkt_section_header("가격 추이 비교", f"규모 상위 {len(_top)}종 · 기준일=100 정규화로 한눈에 비교"),
                unsafe_allow_html=True)
    _plabel, _pcode = period_radio(f"etf_{key}_period")
    chist = _etf_history(",".join(it["ticker"] for it in _top), period=_pcode)
    fig, plotted = go.Figure(), 0
    for it in _top:
        s = chist.get(it["ticker"])
        if s is None or s.empty or len(s) < 2 or not float(s.iloc[0]):
            continue
        fig.add_trace(go.Scatter(
            x=s.index, y=s / float(s.iloc[0]) * 100, mode="lines", name=it["name"],
            line=dict(color=it["color"], width=2, shape="spline", smoothing=0.6),
            hovertemplate=f"{it['name']}: %{{y:.1f}}<extra></extra>",
        ))
        plotted += 1
    if plotted:
        fig.update_layout(
            margin=dict(l=0, r=0, t=6, b=36), height=300,
            paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
            xaxis=dict(showgrid=False, showline=True, linecolor="#262A33",
                       tickfont=dict(size=9, color="#7E8694")),
            yaxis=dict(showgrid=True, gridcolor="#262A33", tickformat=".0f", side="right",
                       tickfont=dict(size=9, color="#7E8694")),
            legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="right", x=1,
                        font=dict(size=11, color="#C9CDD4"), bgcolor="rgba(0,0,0,0)"),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        empty_state("차트 데이터 준비 중")


def render(embedded: bool = False):
    if not embedded:
        inject_css()
        mark_active_nav("/market")
        st.markdown(mkt_page_header("📦", "ETF", "미국 지수·섹터 ETF · 국내 ETF · 1D%·3M·추세"),
                    unsafe_allow_html=True)

    ph = show_skeleton()
    data = load_market_data()
    ph.empty()

    bm = data.get("benchmarks")
    if bm is None or bm.empty:
        empty_state("ETF 데이터 준비 중")
        if not embedded:
            st.markdown(jj_footer(), unsafe_allow_html=True)
        return

    # 6개월 종가 일괄(3M·추세·현재가·1D%·스파크) — 벤치마크 + 주요 국내 ETF 한 번에
    tks = [r.get("ticker", "") for _, r in bm.iterrows() if r.get("ticker")]
    tks += [tk for _, _, tk in _KR_ETF_UNIVERSE]
    _all_tks = sorted(set(t for t in tks if t))
    history = _etf_history(",".join(_all_tks))
    turnover = _etf_turnover(",".join(_all_tks))   # 규모(거래대금) 순위 — 매일 자동 갱신

    def _top_by_size(items: list[dict], n: int = 7) -> list[dict]:
        for it in items:
            it["turnover"] = turnover.get(it["ticker"], 0.0)
        return sorted(items, key=lambda x: x["turnover"], reverse=True)[:n]

    # 미국 ETF / 한국 ETF 라디오 탭 → 규모(거래대금) 상위 7종, 순위 변경 시 자동 반영
    # 사이드 탭은 우측 정렬·글자 가운데(아래 섹션의 period_radio 전역 CSS 공유)
    _side = st.radio("ETF 구분", ["미국 ETF", "한국 ETF"], index=0, horizontal=True,
                     key="etf_side", label_visibility="collapsed")
    if _side == "미국 ETF":
        _render_etf_section(_top_by_size(_us_items(bm, history)), price_fmt="${:,.2f}", key="us")
    else:
        _render_etf_section(_top_by_size(_kr_items(history)), price_fmt="{:,.0f}", key="kr")

    st.caption("ETF는 타 자산군(지수·원자재·채권)을 추종하는 상품 · 데이터는 실시간이 아닐 수 있습니다 · "
               "내 보유 ETF는 포트폴리오에서 확인하세요")
    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)
