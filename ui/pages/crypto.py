"""시장 — 크립토 탭. 시총 상위 주요 코인 Top 10. 스캔 레이어 + 슬림 표(미국·한국과 동일 규격)."""
from __future__ import annotations

import streamlit as st

from ui.components.dash_style import (
    empty_state,
    inject_css, jj_footer, mark_active_nav, show_skeleton,
    mkt_page_header, mkt_section_header, period_radio,
)
from ui.components.scan_layer import scan_layer_html
from ui.components.slim_table import slim_table
from ui.components.range_bar import fetch_52w_ranges, range_bar_html
from ui.components.live_refresh import live_refresh
from data.loader import batch_close_history, series_last_n


def _crypto_history(tickers_key: str, _bucket: int = 0) -> dict:
    """6개월 일봉 종가 — 공용 batch_close_history 위임."""
    return batch_close_history(tickers_key, "6mo", _bucket)


def _ind(closes) -> dict:
    """종가에서 3M%·추세·MA20 이격 자동 산출."""
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
    return {
        "3M %": _ret(63),
        "추세": trend,
        "MA20 이격%": round((latest - ma20) / ma20 * 100, 2) if ma20 else None,
    }


# 주요 코인 유니버스(시총 상위 Top 10) — '시장' 탭은 제너럴 시장 조망이므로 보유(config 3종)가
# 아니라 시총 상위를 노출한다(보유는 포트폴리오 영역). 스테이블코인·서브센트(SHIB) 제외.
# 순서 = 시총 랭크. (name, ticker) — yfinance 실데이터 확인됨.
_CRYPTO_UNIVERSE = [
    ("비트코인", "BTC-USD"), ("이더리움", "ETH-USD"), ("리플", "XRP-USD"),
    ("BNB", "BNB-USD"),     ("솔라나", "SOL-USD"),   ("도지코인", "DOGE-USD"),
]  # 시총 상위 주요 6종(과다 노출 방지). 색 맵엔 그 외 코인도 남겨둠(향후 확장용)
# 코인별 시그니처 색(비교 차트 정규화 라인) — 원자재 탭과 동일 양식. 범례로 구분되니 브랜드색 사용.
_CRYPTO_COLOR = {
    "BTC-USD": "#F7931A", "ETH-USD": "#627EEA", "XRP-USD": "#9AA0AD", "BNB-USD": "#F3BA2F",
    "SOL-USD": "#14B8A6", "DOGE-USD": "#C2A633", "ADA-USD": "#3A57C2", "TRX-USD": "#E06A6A",
    "AVAX-USD": "#E8694A", "LINK-USD": "#5B7CE0",
}


def _crypto_hist_period(tickers_key: str, period: str, _bucket: int = 0) -> dict:
    """비교 차트용 — 선택 기간 일봉 종가. 공용 batch_close_history 위임."""
    return batch_close_history(tickers_key, period, _bucket)


def render(embedded: bool = False):
    if not embedded:
        inject_css()
        mark_active_nav("/market")
        st.markdown(mkt_page_header("🪙", "크립토", "시총 상위 주요 코인 Top 10 · 24시간 등락"),
                    unsafe_allow_html=True)

    bucket = live_refresh(["CRYPTO"]) if not embedded else 0
    ph = show_skeleton()
    tickers = [tk for _, tk in _CRYPTO_UNIVERSE]
    history = _crypto_history(",".join(sorted(tickers)), _bucket=bucket)
    ph.empty()

    def _series_3m(tk):
        return series_last_n(history.get(tk))

    # 현재가·1D%는 6개월 종가에서 산출(별도 시세 소스 불필요)
    scan_items, rows = [], []
    for name, tk in _CRYPTO_UNIVERSE:
        s = history.get(tk)
        price = float(s.iloc[-1]) if s is not None and not s.empty else None
        c1 = (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
              if s is not None and len(s) >= 2 and s.iloc[-2] else None)
        ind = _ind(s)
        scan_items.append({"name": name, "d1": c1, "ma20": ind["MA20 이격%"], "series": _series_3m(tk),
                           "color": _CRYPTO_COLOR.get(tk, "#9AA0AD")})  # 코인 시그니처색(꺾은선)
        rows.append({"코인": name, "현재가": price, "1D %": c1, "3M %": ind["3M %"], "추세": ind["추세"]})

    if not any(r["현재가"] is not None for r in rows):
        empty_state("크립토 데이터 준비 중")
        if not embedded:
            st.markdown(jj_footer(), unsafe_allow_html=True)
        return

    # ── 스캔 레이어(리더/부진/과열 + breadth) — 미국·한국과 동일 골격 ──
    _scan = scan_layer_html(scan_items)
    if _scan:
        st.markdown(_scan, unsafe_allow_html=True)

    # ── 주요 코인 — 52주 레인지 게이지 바(코인별 시그니처색, 표 대신) ──
    st.markdown(mkt_section_header("주요 코인", "시총 상위 6종 · 52주 범위 내 현재 위치"), unsafe_allow_html=True)
    _rb_items = []
    _ranges = fetch_52w_ranges(",".join(tk for _, tk in _CRYPTO_UNIVERSE))
    for name, tk in _CRYPTO_UNIVERSE:
        rng = _ranges.get(tk)
        if not rng:
            continue
        lo, hi, cur = rng
        _r = next((x for x in rows if x["코인"] == name), {})
        _rb_items.append({"name": name, "unit": "USD", "low": lo, "high": hi, "current": cur,
                          "d1": _r.get("1D %"), "color": _CRYPTO_COLOR.get(tk, "#9AA0AD")})
    if _rb_items:
        st.markdown(range_bar_html(_rb_items, fmt="${:,.2f}"), unsafe_allow_html=True)
        st.caption("막대 = 52주 최저~최고 · 점 = 현재가(코인 색) · 우측 라벨 = 범위 내 위치 · USD 기준")
    else:
        empty_state("코인 범위 데이터 준비 중")

    # ── 가격 추이 비교(기준=100 정규화) + 기간 라디오 — 원자재 탭과 동일 양식 ──
    st.markdown(mkt_section_header("가격 추이 비교", "주요 코인 · 기준일=100 정규화로 한눈에 비교"),
                unsafe_allow_html=True)
    _clabel, _ccode = period_radio("crypto_period")
    chist = _crypto_hist_period(",".join(sorted(tickers)), _ccode, _bucket=bucket)
    import plotly.graph_objects as go
    cfig, cplotted = go.Figure(), 0
    for name, tk in _CRYPTO_UNIVERSE:
        s = chist.get(tk)
        if s is None or s.empty or len(s) < 2 or not float(s.iloc[0]):
            continue
        cfig.add_trace(go.Scatter(
            x=s.index, y=s / float(s.iloc[0]) * 100, mode="lines", name=name,
            line=dict(color=_CRYPTO_COLOR.get(tk, "#9AA0AD"), width=2, shape="spline", smoothing=0.6),
            hovertemplate=f"{name}: %{{y:.1f}}<extra></extra>",
        ))
        cplotted += 1
    if cplotted:
        cfig.update_layout(
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
        st.plotly_chart(cfig, use_container_width=True, config={"displayModeBar": False})

    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)
