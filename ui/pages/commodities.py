"""
Commodities — live prices + DB technical indicators.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

import layout as L  # 모바일 분기(산점도→리스트)
from data.loader import load_market_data
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.dash_style import (
    data_source_note,
    empty_state,
    inject_css, jj_footer, mark_active_nav, numeric, show_skeleton,
    mkt_page_header, mkt_section_header, mkt_stats_chips, period_radio,
)
from ui.components.scan_layer import scan_layer_html
from ui.components.slim_table import slim_table
from ui.components.range_bar import range_bar_html

# (한글명, 단위, 그룹, 티커)
_META = {
    "gold":        ("금",       "$/oz",    "귀금속"),
    "silver":      ("은",       "$/oz",    "귀금속"),
    "copper":      ("구리",     "$/lb",    "산업금속"),
    "wti_crude":   ("WTI 원유", "$/bbl",   "에너지"),
    "brent_crude": ("브렌트",   "$/bbl",   "에너지"),
    "natural_gas": ("천연가스", "$/MMBtu", "에너지"),
}
# ④ 원자재별 시그니처 색(라인, 저알파 그라데이션 채움) — 종목마다 고유색
_COMM_COLOR = {
    "gold":        ("#D9A441", "rgba(217,164,65,0.10)"),   # 골드
    "silver":      ("#B6BCC8", "rgba(182,188,200,0.10)"),  # 실버
    "copper":      ("#B87333", "rgba(184,115,51,0.12)"),   # 코퍼
    "wti_crude":   ("#6E7B4E", "rgba(110,123,78,0.12)"),   # 원유 다크올리브
    "brent_crude": ("#4F7A6B", "rgba(79,122,107,0.12)"),   # 브렌트 틸
    "natural_gas": ("#5A8FB0", "rgba(90,143,176,0.12)"),   # 천연가스 블루
}
_COMM_COLOR_DEFAULT = ("#D9A441", "rgba(217,164,65,0.08)")


_PCODE_BARS = {"1mo": 22, "3mo": 64, "6mo": 127}   # 슬라이스용(거래일) · 1y/5y=전체


def _slice_period(s, pcode: str):
    n = _PCODE_BARS.get(pcode)
    return s.iloc[-n:] if (n and len(s) > n) else s


@st.cache_data(ttl=900, show_spinner=False)
def _comm_bundle(tickers_key: str) -> dict:
    """원자재 1년치 종가 1회 배치 → {ticker: Close Series}. 스캔·추이·52주 공통
    (이전엔 원자재마다 _chart 를 따로 받아 콜드 진입이 길었음)."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return {}
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period="1y", interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return {}
    if raw is None or getattr(raw, "empty", True):
        return {}
    out, multi = {}, len(tickers) > 1
    for tk in tickers:
        try:
            c = raw["Close"][tk] if multi else raw["Close"]
            if hasattr(c, "columns"):
                c = c.iloc[:, 0]
            c = c.dropna()
            if not c.empty:
                out[tk] = c
        except Exception:
            pass
    return out


def _comm_spark(closes: dict, tk: str, pcode: str = "3mo") -> list:
    s = closes.get(tk)
    if s is None or getattr(s, "empty", True):
        return []
    return [float(v) for v in _slice_period(s.dropna(), pcode).tolist()]


def _cb_df(closes: dict, tk: str, pcode: str = "3mo") -> pd.DataFrame:
    """번들 종가 → df(Date, Close) (비율 차트 merge 용)."""
    s = closes.get(tk)
    if s is None or getattr(s, "empty", True):
        return pd.DataFrame()
    df = _slice_period(s.dropna(), pcode).reset_index()
    df.columns = ["Date", "Close"]
    return df




def render(embedded: bool = False):
    if not embedded:
        inject_css()
        mark_active_nav("/commodities")
        st.markdown(mkt_page_header("🪙", "원자재", "금 · 은 · 구리 · 원유 · 농산물"), unsafe_allow_html=True)

    ph = show_skeleton()
    live = load_market_data()
    load_latest_indicator_summary(DEFAULT_DB)
    _comm_tickers = [r["ticker"] for _, r in live.get("commodities", pd.DataFrame()).iterrows() if r.get("ticker")]
    _cb = _comm_bundle(",".join(_comm_tickers))   # 원자재 1년 종가 1회 배치(스캔·추이·52주 공통)
    ph.empty()

    # ── Stats chips ───────────────────────────────────────────────────────────
    comm_df = live.get("commodities", pd.DataFrame())
    comm_chips = []
    for lbl, name in [("금","gold"),("은","silver"),("구리","copper"),("WTI 원유","oil_wti")]:
        if comm_df.empty: break
        r = comm_df[comm_df["name"] == name]
        if r.empty: continue
        c = r.iloc[0].get("change_pct")
        if c is not None and isinstance(c, (int, float)):
            sign = "+" if c >= 0 else ""
            comm_chips.append({"label": lbl, "value": f"{sign}{c:.2f}%", "cls": "pos" if c>0 else ("neg" if c<0 else "neu")})
    if comm_chips:
        st.markdown(mkt_stats_chips(comm_chips), unsafe_allow_html=True)

    # ── DB indicators ─────────────────────────────────────────────────────────
    db_df    = load_latest_indicator_summary(DEFAULT_DB)
    comm_db  = db_df[db_df["asset_type"] == "commodity"].copy() if not db_df.empty else pd.DataFrame()

    def _dbv(ticker: str, col: str):
        if comm_db.empty:
            return None
        m = comm_db[comm_db["symbol"] == ticker]
        if m.empty:
            return None
        v = m.iloc[0].get(col)
        return float(v) if isinstance(v, (int, float)) else None

    def _dbstr(ticker: str, col: str) -> str:
        if comm_db.empty:
            return "—"
        m = comm_db[comm_db["symbol"] == ticker]
        if m.empty:
            return "—"
        return str(m.iloc[0].get(col, "—")) or "—"

    # ── Build rows ────────────────────────────────────────────────────────────
    st.markdown(mkt_section_header("원자재 현황", "실시간 시세 · 기간별 수익률"), unsafe_allow_html=True)

    pct_cols = ["1D %", "1W %", "1M %", "3M %", "MA20 이격%"]

    def _cell(v):
        if not isinstance(v, (int, float)) or pd.isna(v) or v == 0: return ""
        mag = min((abs(v) / 8.0) ** 0.7, 1.0)   # 값 크기에 비례한 농도 (R7)
        a = 0.05 + mag * 0.30
        if v > 0:  return f"background-color:rgba(242,85,96,{a:.3f});color:#F25560;font-weight:600"
        return f"background-color:rgba(77,144,240,{a:.3f});color:#4D90F0;font-weight:600"

    _TREND_MAP = {"bullish": "상승", "bearish": "하락", "neutral": "중립"}

    def _trend(v):
        if v in ("bullish", "상승"): return "color:#F25560;font-weight:700"
        if v in ("bearish", "하락"): return "color:#4D90F0;font-weight:700"
        return "color:#7E8694"

    all_rows = []
    for _, r in live["commodities"].iterrows():
        key    = r["name"]
        ticker = r["ticker"]
        kor, unit, group = _META.get(key, (key.title(), "", "기타"))
        all_rows.append({
            "원자재":     kor,
            "단위":       unit,
            "현재가":     r["price"]      if isinstance(r["price"],      (int, float)) else None,
            "1D %":      r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
            "1W %":      _dbv(ticker, "return_1w_pct"),
            "1M %":      _dbv(ticker, "return_1m_pct"),
            "3M %":      _dbv(ticker, "return_3m_pct"),
            "MA20 이격%": _dbv(ticker, "distance_ma20_pct"),
            "변동성(연)": _dbv(ticker, "volatility_20d_pct"),
            "추세":       _TREND_MAP.get(_dbstr(ticker, "trend_status"), _dbstr(ticker, "trend_status")),
            "_ticker":   ticker,
            "_group":    group,
            "_key":      key,
        })

    # ── 0. 30초 스캔 레이어 — 리더/러거드/과열 + breadth (표 위) ─────────────────
    scan_items = [{
        "name": r["원자재"],
        "d1": r["1D %"],
        "ma20": r["MA20 이격%"],
        "series": _comm_spark(_cb, r["_ticker"]),
        "color": _COMM_COLOR.get(r["_key"], _COMM_COLOR_DEFAULT)[0],  # 원자재 시그니처색(꺾은선)
    } for r in all_rows]
    _scan = scan_layer_html(scan_items)
    if _scan:
        # 스캔 레이어는 섹션 헤더보다 위 — 마크다운 순서상 헤더 이후에 출력되므로 여기서 먼저
        st.markdown(_scan, unsafe_allow_html=True)

    def _render_comm_table(grp: list[dict], show_group: bool = False,
                           sort_movement: bool = False, highlight: bool = False):
        df_rows = []
        for r in grp:
            row = {k: v for k, v in r.items() if k not in ("_ticker", "_group")}
            if show_group:
                row = {"그룹": r["_group"], **row}
            df_rows.append(row)
        tbl = pd.DataFrame(df_rows)
        tbl = numeric(tbl, pct_cols + ["현재가", "변동성(연)"])
        if sort_movement and "1D %" in tbl.columns:
            tbl = tbl.reindex(tbl["1D %"].abs().sort_values(ascending=False, na_position="last").index)
        styled = tbl.style.map(_cell, subset=pct_cols)
        if "추세" in tbl.columns:
            styled = styled.map(_trend, subset=["추세"])
        if highlight and "1D %" in tbl.columns and tbl["1D %"].notna().any():
            imax, imin = tbl["1D %"].idxmax(), tbl["1D %"].idxmin()
            def _row_hl(row):
                styles = [""] * len(row)
                if row.name == imax:
                    styles[0] = "box-shadow:inset 4px 0 0 #F25560"
                elif row.name == imin:
                    styles[0] = "box-shadow:inset 4px 0 0 #4D90F0"
                return styles
            styled = styled.apply(_row_hl, axis=1)
        fmt = {c: "{:+.2f}%" for c in pct_cols if c in tbl.columns}
        if "현재가" in tbl.columns: fmt["현재가"] = "{:,.2f}"
        if "변동성(연)" in tbl.columns: fmt["변동성(연)"] = "{:.2f}%"
        styled = styled.format(fmt, na_rep="—")
        st.dataframe(styled, use_container_width=True, hide_index=True)

    if embedded:
        # 레인지 불릿 바(52주 범위 내 위치) + 표로 보기 토글 → 슬림표
        _bullet_items = []
        for r in all_rows:
            s = _cb.get(r["_ticker"])
            if s is None or getattr(s, "empty", True) or len(s.dropna()) < 2:
                continue
            s = s.dropna()
            lo, hi, cur = float(s.min()), float(s.max()), float(s.iloc[-1])
            _bullet_items.append({
                "name": r["원자재"], "unit": r.get("단위", ""),
                "low": lo, "high": hi, "current": cur,
                "d1": r.get("1D %"), "m3": r.get("3M %"),
                "color": _COMM_COLOR.get(r["_key"], _COMM_COLOR_DEFAULT)[0],  # 원자재 시그니처색
            })
        if _bullet_items:
            st.markdown(range_bar_html(_bullet_items), unsafe_allow_html=True)
            st.caption("막대 = 52주 최저~최고 · 점 = 현재가 · 우측 라벨 = 범위 내 위치")
        if st.toggle("표로 보기", key="comm_all_tbl", value=False):
            _slim_rows = []
            for r in sorted(all_rows,
                            key=lambda x: abs(x["1D %"]) if isinstance(x["1D %"], (int, float)) else -1,
                            reverse=True):
                _slim_rows.append({"그룹": r.get("_group", ""), **{k: v for k, v in r.items() if not str(k).startswith("_")}})
            slim_table(_slim_rows, key="comm_all", name_key="원자재",
                       price_key="현재가", price_fmt="{:,.2f}")
    else:
        for group_name in ["귀금속", "산업금속", "에너지", "기타"]:
            grp = [r for r in all_rows if r["_group"] == group_name]
            if not grp:
                continue
            st.markdown(
                f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:#7E8694;margin:14px 0 4px">{group_name}</div>',
                unsafe_allow_html=True,
            )
            _render_comm_table(grp)

    if not comm_db.empty:
        run_date = db_df["run_date"].max()
        st.caption(data_source_note("로컬 DB", updated=str(run_date), extra="기술지표 1W/1M/3M·추세"))


    # ⑤ 관련주 애널리스트 전망 섹션 삭제 — 시장 탭(embedded)에서도 색 입힌 가격 차트를 그대로 노출.

    # ── Price Chart — 전 원자재 비교(기준=100 정규화) + 기간 라디오 ────────────────
    st.markdown(mkt_section_header("가격 추이 비교", "전 원자재 · 기준일=100 정규화로 한눈에 비교"),
                unsafe_allow_html=True)
    _plabel, _pcode = period_radio("comm_period", periods=["1M", "3M", "6M", "1Y"])  # 번들=1년
    fig = go.Figure()
    plotted = 0
    for _, r in live["commodities"].iterrows():
        key, tk = r["name"], r["ticker"]
        kor, _u, _g = _META.get(key, (key.title(), "", ""))
        s = _cb.get(tk)
        if s is None or getattr(s, "empty", True):
            continue
        s = _slice_period(s.dropna(), _pcode)
        if len(s) < 2 or not float(s.iloc[0]):
            continue
        line_c, _f = _COMM_COLOR.get(key, _COMM_COLOR_DEFAULT)   # ④ 종목별 고유색
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values / float(s.iloc[0]) * 100, mode="lines", name=kor,
            line=dict(color=line_c, width=2, shape="spline", smoothing=0.6),  # 부드러운 곡선
            hovertemplate=f"{kor}: %{{y:.1f}}<extra></extra>",
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

    # ── Ratio Charts (심화 지표 — 기본 접힘) ──────────────────────────────────
    with st.expander("귀금속 비율 차트 — 심화 지표(상대강도·경기국면)", expanded=False):
        st.caption("가격이 아니라 '시장 심리·경기 국면'을 읽는 매크로 게이지입니다. 금속 미보유여도 위험선호·성장 기대를 가늠하는 데 씁니다.")
        gld_h = _cb_df(_cb, "GC=F")
        slv_h = _cb_df(_cb, "SI=F")
        cop_h = _cb_df(_cb, "HG=F")

        if not gld_h.empty and not slv_h.empty:
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                merged = gld_h.merge(slv_h, on="Date", suffixes=("_gld", "_slv")).dropna()
                if not merged.empty:
                    ratio = merged["Close_gld"] / merged["Close_slv"]
                    last  = ratio.iloc[-1]
                    first = ratio.iloc[0]
                    chg   = (last / first - 1) * 100
                    color = "#F25560" if chg >= 0 else "#4D90F0"
                    fig   = go.Figure(go.Scatter(
                        x=merged["Date"], y=ratio, mode="lines",
                        line=dict(color="#b8924a", width=1.5, shape="spline", smoothing=0.6),
                        fill="tozeroy", fillcolor="rgba(201,168,76,0.08)",
                        hovertemplate="%{y:.2f}<extra>금/은 비율</extra>",
                    ))
                    fig.update_layout(
                        title=dict(
                            text=f"금/은 비율  <span style='font-size:10px;color:{color}'>"
                                 f"{'+' if chg >= 0 else ''}{chg:.1f}% (3M)</span>",
                            font=dict(size=11, color="#D9A441"), x=0, xanchor="left",
                        ),
                        margin=dict(l=0, r=0, t=32, b=0), height=180,
                        paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
                        xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#7E8694")),
                        yaxis=dict(showgrid=True, gridcolor="#262A33",
                                   tickfont=dict(size=8, color="#7E8694"), side="right"),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    st.caption("비율 ↑ = 금 상대 강세(안전자산·공포) · ↓ = 은 강세(산업수요·위험선호). "
                               "역사적 평균 ~60–70, 극단에서 금↔은 상대가치 신호.")

            with r_col2:
                if not cop_h.empty:
                    merged2 = cop_h.merge(gld_h, on="Date", suffixes=("_cop", "_gld")).dropna()
                    if not merged2.empty:
                        ratio2 = merged2["Close_cop"] / merged2["Close_gld"]
                        last2  = ratio2.iloc[-1]
                        first2 = ratio2.iloc[0]
                        chg2   = (last2 / first2 - 1) * 100
                        color2 = "#F25560" if chg2 >= 0 else "#4D90F0"
                        fig2   = go.Figure(go.Scatter(
                            x=merged2["Date"], y=ratio2, mode="lines",
                            line=dict(color="#B87333", width=1.5, shape="spline", smoothing=0.6),
                            fill="tozeroy", fillcolor="rgba(184,115,51,0.08)",
                            hovertemplate="%{y:.4f}<extra>구리/금 비율</extra>",
                        ))
                        fig2.update_layout(
                            title=dict(
                                text=f"구리/금 비율  <span style='font-size:10px;color:{color2}'>"
                                     f"{'+' if chg2 >= 0 else ''}{chg2:.1f}% (3M)</span>",
                                font=dict(size=11, color="#D9A441"), x=0, xanchor="left",
                            ),
                            margin=dict(l=0, r=0, t=32, b=0), height=180,
                            paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
                            xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#7E8694")),
                            yaxis=dict(showgrid=True, gridcolor="#262A33",
                                       tickfont=dict(size=8, color="#7E8694"), side="right"),
                            showlegend=False,
                        )
                        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
                        st.caption("비율 ↑ = 경기 낙관·리스크온(금리 상승 동행) · ↓ = 둔화·안전선호. "
                                   "‘닥터 코퍼’ 기반 글로벌 경기 선행지표.")

    # ⑤ 원자재 관련주 애널리스트 전망(산점도·FMP 드릴다운) 삭제 — 원자재 탭은 시세 중심.
    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)
