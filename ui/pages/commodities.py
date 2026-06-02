"""
Commodities — live prices + DB technical indicators.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

from data.fetcher import fetch_all
from src.database import load_latest_indicator_summary, DEFAULT_DB
from src.analyst import fetch_analyst_targets
from ui.components.analyst_fmp import render_fmp_drilldown
from ui.components.dash_style import (
    inject_css, section_header, timestamp_bar, numeric,
)

_COMM_STOCK_KOR = {
    "GOLD": "배릭골드",
    "NEM":  "뉴몬트",
    "FCX":  "프리포트맥모란",
    "XOM":  "엑슨모빌",
    "CVX":  "쉐브론",
    "COP":  "코노코필립스",
}
_COMM_STOCK_GROUP = {
    "GOLD": "귀금속",
    "NEM":  "귀금속",
    "FCX":  "산업금속",
    "XOM":  "에너지",
    "CVX":  "에너지",
    "COP":  "에너지",
}

# (한글명, 단위, 그룹, 티커)
_META = {
    "gold":        ("금",       "$/oz",    "귀금속"),
    "silver":      ("은",       "$/oz",    "귀금속"),
    "copper":      ("구리",     "$/lb",    "산업금속"),
    "wti_crude":   ("WTI 원유", "$/bbl",   "에너지"),
    "brent_crude": ("브렌트",   "$/bbl",   "에너지"),
    "natural_gas": ("천연가스", "$/MMBtu", "에너지"),
}


@st.cache_data(ttl=300)
def _load_live():
    return fetch_all()


@st.cache_data(ttl=3600)
def _analyst_targets() -> pd.DataFrame:
    return fetch_analyst_targets(list(_COMM_STOCK_KOR.keys()))


@st.cache_data(ttl=900)
def _chart(ticker: str) -> pd.DataFrame:
    try:
        raw = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if raw.empty:
            return pd.DataFrame()
        closes = raw["Close"]
        if hasattr(closes, "columns"):
            closes = closes.iloc[:, 0]
        df = closes.reset_index()
        df.columns = ["Date", "Close"]
        return df.dropna()
    except Exception:
        return pd.DataFrame()


def render():
    inject_css()

    c1, c2 = st.columns([9, 1])
    c1.markdown("## Commodities")
    c1.caption("원자재 시세 모니터 — 투자 참고용, 매매 권유 아님")
    if c2.button("↻ 새로고침", use_container_width=True):
        _load_live.clear()

    live = _load_live()
    ts   = live["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

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
    st.markdown(section_header("원자재 현황", "실시간 시세 · 기간별 수익률"), unsafe_allow_html=True)

    pct_cols = ["1D %", "1W %", "1M %", "3M %", "MA20 이격%"]

    def _cell(v):
        if not isinstance(v, (int, float)) or pd.isna(v): return ""
        if v > 0.3:  return "background-color:#F0FFF6;color:#276749;font-weight:600"
        if v < -0.3: return "background-color:#FFF5F5;color:#9B2335;font-weight:600"
        return ""

    _TREND_MAP = {"bullish": "상승", "bearish": "하락", "neutral": "중립"}

    def _trend(v):
        if v in ("bullish", "상승"): return "color:#276749;font-weight:700"
        if v in ("bearish", "하락"): return "color:#9B2335;font-weight:700"
        return "color:#718096"

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
        })

    for group_name in ["귀금속", "산업금속", "에너지", "기타"]:
        grp = [r for r in all_rows if r["_group"] == group_name]
        if not grp:
            continue
        st.markdown(
            f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:1px;color:#718096;margin:14px 0 4px">{group_name}</div>',
            unsafe_allow_html=True,
        )
        tbl = pd.DataFrame(grp).drop(columns=["_ticker", "_group"])
        tbl = numeric(tbl, pct_cols + ["현재가", "변동성(연)"])
        styled = tbl.style.map(_cell, subset=pct_cols)
        if "추세" in tbl.columns:
            styled = styled.map(_trend, subset=["추세"])
        cfg = {c: st.column_config.NumberColumn(format="%.2f%%") for c in pct_cols}
        cfg["현재가"]   = st.column_config.NumberColumn(format="%.4f")
        cfg["변동성(연)"] = st.column_config.NumberColumn(format="%.2f%%")
        st.dataframe(styled, column_config=cfg, use_container_width=True, hide_index=True)

    if not comm_db.empty:
        run_date = db_df["run_date"].max()
        st.caption(f"1W/1M/3M·추세: DB 기준 ({run_date})  ·  `python main.py` 실행 시 업데이트")

    # ── Price Chart ───────────────────────────────────────────────────────────
    st.markdown(section_header("가격 추이", "3개월 일별 종가"), unsafe_allow_html=True)

    opts = {}
    for _, r in live["commodities"].iterrows():
        kor, unit, _ = _META.get(r["name"], (r["name"].title(), "", ""))
        opts[f"{kor}  ({unit})"] = r["ticker"]

    col_sel, _ = st.columns([3, 7])
    with col_sel:
        sel = st.selectbox("원자재", list(opts.keys()), label_visibility="collapsed",
                           key="comm_chart_sel")
    hist = _chart(opts[sel])

    if not hist.empty:
        pct   = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        color = "#276749" if pct >= 0 else "#9B2335"
        sign  = "+" if pct >= 0 else ""
        fig = go.Figure(go.Scatter(
            x=hist["Date"], y=hist["Close"], mode="lines",
            line=dict(color="#1C2B3A", width=1.5),
            fill="tozeroy", fillcolor="rgba(28,43,58,0.05)",
        ))
        fig.update_layout(
            title=dict(
                text=f"{sel}  <span style='font-size:11px;color:{color}'>{sign}{pct:.2f}% (3M)</span>",
                font=dict(size=12, color="#2D3748"), x=0, xanchor="left",
            ),
            margin=dict(l=0, r=0, t=36, b=0), height=220,
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
            xaxis=dict(showgrid=False, showline=True, linecolor="#E2E8F0",
                       tickfont=dict(size=9, color="#718096")),
            yaxis=dict(showgrid=True, gridcolor="#F0F4F8", tickformat=",.4f",
                       tickfont=dict(size=9, color="#718096"), side="right"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("차트 데이터를 불러올 수 없습니다.")

    # ── Ratio Charts ─────────────────────────────────────────────────────────
    st.markdown(section_header("귀금속 비율 차트", "상대 강도 모니터링"), unsafe_allow_html=True)

    gld_h = _chart("GC=F")
    slv_h = _chart("SI=F")
    cop_h = _chart("HG=F")

    if not gld_h.empty and not slv_h.empty:
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            merged = gld_h.merge(slv_h, on="Date", suffixes=("_gld", "_slv")).dropna()
            if not merged.empty:
                ratio = merged["Close_gld"] / merged["Close_slv"]
                last  = ratio.iloc[-1]
                first = ratio.iloc[0]
                chg   = (last / first - 1) * 100
                color = "#276749" if chg >= 0 else "#9B2335"
                fig   = go.Figure(go.Scatter(
                    x=merged["Date"], y=ratio, mode="lines",
                    line=dict(color="#C9A84C", width=1.5),
                    fill="tozeroy", fillcolor="rgba(201,168,76,0.08)",
                    hovertemplate="%{y:.2f}<extra>금/은 비율</extra>",
                ))
                fig.update_layout(
                    title=dict(
                        text=f"금/은 비율  <span style='font-size:10px;color:{color}'>"
                             f"{'+' if chg >= 0 else ''}{chg:.1f}% (3M)</span>",
                        font=dict(size=11, color="#2D3748"), x=0, xanchor="left",
                    ),
                    margin=dict(l=0, r=0, t=32, b=0), height=180,
                    paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
                    xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#718096")),
                    yaxis=dict(showgrid=True, gridcolor="#F0F4F8",
                               tickfont=dict(size=8, color="#718096"), side="right"),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.caption("금/은 비율 상승 → 금 상대 강세 (안전자산 수요) / 하락 → 은 상대 강세 (산업금속 수요)")

        with r_col2:
            if not cop_h.empty:
                merged2 = cop_h.merge(gld_h, on="Date", suffixes=("_cop", "_gld")).dropna()
                if not merged2.empty:
                    ratio2 = merged2["Close_cop"] / merged2["Close_gld"]
                    last2  = ratio2.iloc[-1]
                    first2 = ratio2.iloc[0]
                    chg2   = (last2 / first2 - 1) * 100
                    color2 = "#276749" if chg2 >= 0 else "#9B2335"
                    fig2   = go.Figure(go.Scatter(
                        x=merged2["Date"], y=ratio2, mode="lines",
                        line=dict(color="#B87333", width=1.5),
                        fill="tozeroy", fillcolor="rgba(184,115,51,0.08)",
                        hovertemplate="%{y:.4f}<extra>구리/금 비율</extra>",
                    ))
                    fig2.update_layout(
                        title=dict(
                            text=f"구리/금 비율  <span style='font-size:10px;color:{color2}'>"
                                 f"{'+' if chg2 >= 0 else ''}{chg2:.1f}% (3M)</span>",
                            font=dict(size=11, color="#2D3748"), x=0, xanchor="left",
                        ),
                        margin=dict(l=0, r=0, t=32, b=0), height=180,
                        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
                        xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#718096")),
                        yaxis=dict(showgrid=True, gridcolor="#F0F4F8",
                                   tickfont=dict(size=8, color="#718096"), side="right"),
                        showlegend=False,
                    )
                    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
                    st.caption("구리/금 비율 상승 → 경기 낙관론 / 하락 → 경기 우려 또는 안전자산 선호")

    # ── Analyst Price Targets (관련 개별주) ───────────────────────────────────
    st.markdown(section_header("원자재 관련주 애널리스트 전망",
                               "Yahoo Finance 컨센서스 목표가 — 금광·구리·에너지 섹터"),
                unsafe_allow_html=True)

    analyst_df = _analyst_targets()

    if not analyst_df.empty:
        _REC_COLOR = {
            "강력매수": "color:#276749;font-weight:700",
            "매수":     "color:#276749;font-weight:600",
            "보유":     "color:#718096",
            "시장하회": "color:#9B2335;font-weight:600",
            "매도":     "color:#9B2335;font-weight:700",
            "강력매도": "color:#9B2335;font-weight:700",
        }

        def _rec_style(v):
            return _REC_COLOR.get(v, "")

        def _upside_style(v):
            if not isinstance(v, (int, float)) or pd.isna(v): return ""
            if v >= 10:  return "background-color:#F0FFF6;color:#276749;font-weight:600"
            if v <= -5:  return "background-color:#FFF5F5;color:#9B2335;font-weight:600"
            return ""

        for group_name in ["귀금속", "산업금속", "에너지"]:
            group_tickers = [tk for tk, g in _COMM_STOCK_GROUP.items() if g == group_name]
            grp_df = analyst_df[analyst_df["ticker"].isin(group_tickers)]
            if grp_df.empty:
                continue
            st.markdown(
                f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:#718096;margin:14px 0 4px">{group_name}</div>',
                unsafe_allow_html=True,
            )
            rows_a = []
            for _, r in grp_df.iterrows():
                tk = r["ticker"]
                rows_a.append({
                    "종목":        f"{_COMM_STOCK_KOR.get(tk, tk)}  ({tk})",
                    "현재가":      r.get("현재가"),
                    "목표가(평균)": r.get("목표가_평균"),
                    "목표가(최고)": r.get("목표가_최고"),
                    "목표가(최저)": r.get("목표가_최저"),
                    "상승여력%":   r.get("상승여력%"),
                    "투자의견":    r.get("투자의견") or "—",
                    "애널리스트수": r.get("애널리스트수"),
                })
            atbl = pd.DataFrame(rows_a)
            price_cols = ["현재가", "목표가(평균)", "목표가(최고)", "목표가(최저)"]
            for c in price_cols:
                atbl[c] = pd.to_numeric(atbl[c], errors="coerce")
            atbl["상승여력%"]   = pd.to_numeric(atbl["상승여력%"],   errors="coerce")
            atbl["애널리스트수"] = pd.to_numeric(atbl["애널리스트수"], errors="coerce")

            styled_a = (
                atbl.style
                .map(_upside_style, subset=["상승여력%"])
                .map(_rec_style,    subset=["투자의견"])
            )
            cfg_a = {c: st.column_config.NumberColumn(format="$%,.2f") for c in price_cols}
            cfg_a["상승여력%"]   = st.column_config.NumberColumn(format="%.1f%%")
            cfg_a["애널리스트수"] = st.column_config.NumberColumn(format="%d명")
            st.dataframe(styled_a, column_config=cfg_a, use_container_width=True, hide_index=True)

        st.caption("출처: Yahoo Finance 애널리스트 컨센서스 — 투자 참고용, 매매 권유 아님 · 1시간마다 업데이트")
    else:
        st.info("애널리스트 데이터를 불러올 수 없습니다.")

    render_fmp_drilldown(list(_COMM_STOCK_KOR.keys()), _COMM_STOCK_KOR, section_title="원자재 관련주 증권사별 목표가")
