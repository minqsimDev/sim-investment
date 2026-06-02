"""
US Stocks — live prices + DB technical indicators, grouped by sector.
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

_STOCK_KOR = {
    "NVDA":  "엔비디아",
    "AMD":   "AMD",
    "AVGO":  "브로드컴",
    "MU":    "마이크론",
    "TSM":   "TSMC",
    "AAPL":  "애플",
    "MSFT":  "마이크로소프트",
    "GOOGL": "알파벳",
    "AMZN":  "아마존",
    "META":  "메타",
    "TSLA":  "테슬라",
    "PLTR":  "팔란티어",
}
_SECTOR_KOR = {
    "semiconductor": "반도체",
    "big_tech":      "빅테크",
    "ev_auto":       "전기차/자동차",
}
_BENCH_KOR = {
    "QQQ":  ("나스닥 100",   "equity_us"),
    "SPY":  ("S&P 500",     "equity_us"),
    "SOXX": ("반도체 (SOXX)", "equity_semiconductor"),
    "SMH":  ("반도체 (SMH)",  "equity_semiconductor"),
    "GLD":  ("골드 ETF",     "commodities"),
    "SLV":  ("실버 ETF",     "commodities"),
    "TLT":  ("장기채 ETF",   "bonds"),
    "KWEB": ("중국인터넷 ETF", "equity_china"),
}


@st.cache_data(ttl=300)
def _load_live():
    return fetch_all()


@st.cache_data(ttl=3600)
def _analyst_targets() -> pd.DataFrame:
    return fetch_analyst_targets(list(_STOCK_KOR.keys()))


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
    c1.markdown("## 미국 주식")
    c1.caption("미국 주식 모니터 — 투자 참고용, 매매 권유 아님")
    if c2.button("↻ 새로고침", use_container_width=True):
        _load_live.clear()

    live = _load_live()
    ts   = live["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

    # ── DB indicators ─────────────────────────────────────────────────────────
    db_df = load_latest_indicator_summary(DEFAULT_DB)

    def _dbv(df_sub: pd.DataFrame, ticker: str, col: str):
        if df_sub.empty:
            return None
        m = df_sub[df_sub["symbol"] == ticker]
        if m.empty:
            return None
        v = m.iloc[0].get(col)
        return float(v) if isinstance(v, (int, float)) else None

    def _dbstr(df_sub: pd.DataFrame, ticker: str, col: str) -> str:
        if df_sub.empty:
            return "—"
        m = df_sub[df_sub["symbol"] == ticker]
        if m.empty:
            return "—"
        return str(m.iloc[0].get(col, "—")) or "—"

    stock_db = db_df[db_df["asset_type"] == "us_stock"].copy() if not db_df.empty else pd.DataFrame()
    bench_db = db_df[db_df["asset_type"] == "benchmark"].copy() if not db_df.empty else pd.DataFrame()

    pct_cols = ["1D %", "1W %", "1M %", "3M %"]

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

    def _make_table(live_rows, db_sub, key_col="ticker") -> pd.DataFrame:
        rows = []
        for _, r in live_rows.iterrows():
            tk = r[key_col]
            rows.append({
                "현재가 (USD)": r["price"]      if isinstance(r["price"],      (int, float)) else None,
                "1D %":        r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
                "1W %":        _dbv(db_sub, tk, "return_1w_pct"),
                "1M %":        _dbv(db_sub, tk, "return_1m_pct"),
                "3M %":        _dbv(db_sub, tk, "return_3m_pct"),
                "MA20 이격%":  _dbv(db_sub, tk, "distance_ma20_pct"),
                "추세":        _TREND_MAP.get(_dbstr(db_sub, tk, "trend_status"), _dbstr(db_sub, tk, "trend_status")),
                "_ticker":    tk,
            })
        return pd.DataFrame(rows)

    def _show_table(tbl: pd.DataFrame, name_col: str):
        disp = tbl.drop(columns=["_ticker"])
        disp = numeric(disp, pct_cols + ["현재가 (USD)", "MA20 이격%"])
        styled = disp.style.map(_cell, subset=pct_cols + ["MA20 이격%"])
        if "추세" in disp.columns:
            styled = styled.map(_trend, subset=["추세"])
        cfg = {c: st.column_config.NumberColumn(format="%.2f%%")
               for c in pct_cols + ["MA20 이격%"]}
        cfg["현재가 (USD)"] = st.column_config.NumberColumn(format="%,.2f")
        st.dataframe(styled, column_config=cfg, use_container_width=True, hide_index=True)

    # ── 1. Benchmarks ─────────────────────────────────────────────────────────
    st.markdown(section_header("주요 벤치마크", "ETF 기준"), unsafe_allow_html=True)

    bench_live = live["benchmarks"].copy()
    bench_live.insert(0, "이름", bench_live["ticker"].map(
        lambda t: _BENCH_KOR.get(t, (t,))[0]
    ))
    bench_tbl = _make_table(bench_live, bench_db)
    bench_tbl.insert(0, "이름", bench_live["이름"].values)
    _show_table(bench_tbl, "이름")

    # ── 2. US Stocks by sector ────────────────────────────────────────────────
    st.markdown(section_header("미국 주식", "섹터별"), unsafe_allow_html=True)

    stocks_live = live["us_stocks"].copy()
    for sector_key, sector_kor in [("semiconductor", "반도체"), ("big_tech", "빅테크"), ("ev_auto", "전기차/자동차")]:
        sector_rows = stocks_live[stocks_live["sector"] == sector_key]
        if sector_rows.empty:
            continue
        st.markdown(
            f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:1px;color:#718096;margin:14px 0 4px">{sector_kor}</div>',
            unsafe_allow_html=True,
        )
        tbl = _make_table(sector_rows, stock_db)
        tbl.insert(0, "종목", sector_rows["ticker"].map(
            lambda t: f"{_STOCK_KOR.get(t, t)}  ({t})"
        ).values)
        _show_table(tbl, "종목")

    if not stock_db.empty:
        run_date = db_df["run_date"].max()
        st.caption(f"1W/1M/3M·추세: DB 기준 ({run_date})  ·  `python main.py` 실행 시 업데이트")

    # ── 3. Price Chart ────────────────────────────────────────────────────────
    st.markdown(section_header("가격 추이", "3개월 일별 종가"), unsafe_allow_html=True)

    opts: dict[str, str] = {}
    for _, r in live["benchmarks"].iterrows():
        label = _BENCH_KOR.get(r["ticker"], (r["ticker"],))[0]
        opts[f"{label}  ({r['ticker']})"] = r["ticker"]
    for _, r in live["us_stocks"].iterrows():
        kor = _STOCK_KOR.get(r["ticker"], r["ticker"])
        opts[f"{kor}  ({r['ticker']})"] = r["ticker"]

    col_sel, _ = st.columns([3, 7])
    with col_sel:
        sel = st.selectbox("종목", list(opts.keys()), label_visibility="collapsed",
                           key="stock_chart_sel")
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
            yaxis=dict(showgrid=True, gridcolor="#F0F4F8", tickformat="$,.2f",
                       tickfont=dict(size=9, color="#718096"), side="right"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("차트 데이터를 불러올 수 없습니다.")

    # ── 4. Return vs. Volatility Bubble Chart ────────────────────────────────
    if not stock_db.empty:
        st.markdown(section_header("리스크/수익 버블 차트",
                                   "1M 수익률 vs 20D 변동성 — 버블 크기: 3M 수익률 절대값"),
                    unsafe_allow_html=True)

        _SECTOR_COLOR = {"semiconductor": "#E07B39", "big_tech": "#4A6FA5", "ev_auto": "#38A169"}
        _SECTOR_KOR2  = {"semiconductor": "반도체", "big_tech": "빅테크", "ev_auto": "전기차/자동차"}

        bubble_rows = []
        for _, r in live["us_stocks"].iterrows():
            tk = r["ticker"]
            ret1m = _dbv(stock_db, tk, "return_1m_pct")
            vol   = _dbv(stock_db, tk, "volatility_20d_pct")
            ret3m = _dbv(stock_db, tk, "return_3m_pct")
            if ret1m is None or vol is None:
                continue
            bubble_rows.append({
                "ticker":  tk,
                "name":    _STOCK_KOR.get(tk, tk),
                "sector":  r.get("sector", ""),
                "ret1m":   ret1m,
                "vol":     vol,
                "size":    max(abs(ret3m or 0), 2),
            })

        if bubble_rows:
            bdf = pd.DataFrame(bubble_rows)
            fig_b = go.Figure()
            for sect, grp in bdf.groupby("sector"):
                fig_b.add_trace(go.Scatter(
                    x=grp["ret1m"], y=grp["vol"],
                    mode="markers+text",
                    name=_SECTOR_KOR2.get(sect, sect),
                    text=grp["name"],
                    textposition="top center",
                    textfont=dict(size=8.5, color="#4A5568"),
                    marker=dict(
                        size=grp["size"].clip(4, 30),
                        color=_SECTOR_COLOR.get(sect, "#888"),
                        opacity=0.65,
                        line=dict(width=1, color="white"),
                    ),
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "1M 수익률: %{x:.1f}%<br>"
                        "20D 변동성: %{y:.1f}%<extra></extra>"
                    ),
                ))
            fig_b.add_vline(x=0, line_width=1, line_dash="dot", line_color="#CBD5E0")
            fig_b.update_layout(
                margin=dict(l=0, r=0, t=8, b=0), height=300,
                paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
                xaxis=dict(title=dict(text="1M 수익률 (%)", font=dict(size=9)),
                           showgrid=True, gridcolor="#F0F4F8", zeroline=False,
                           ticksuffix="%", tickfont=dict(size=9, color="#718096")),
                yaxis=dict(title=dict(text="20D 변동성 (연환산 %)", font=dict(size=9)),
                           showgrid=True, gridcolor="#F0F4F8",
                           ticksuffix="%", tickfont=dict(size=9, color="#718096")),
                legend=dict(font=dict(size=9), orientation="h",
                            yanchor="bottom", y=1.01, x=0),
                hovermode="closest",
            )
            st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar": False})
            st.caption("우하단: 고수익·저변동성 (우호적) / 좌상단: 저수익·고변동성 (주의) — 투자 참고용")

    # ── 5. Analyst Price Targets ──────────────────────────────────────────────
    st.markdown(section_header("애널리스트 전망", "Yahoo Finance 컨센서스 목표가"), unsafe_allow_html=True)

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

        rows_a = []
        for _, r in analyst_df.iterrows():
            tk = r["ticker"]
            rows_a.append({
                "종목":       f"{_STOCK_KOR.get(tk, tk)}  ({tk})",
                "현재가":     r.get("현재가"),
                "목표가(평균)": r.get("목표가_평균"),
                "목표가(최고)": r.get("목표가_최고"),
                "목표가(최저)": r.get("목표가_최저"),
                "상승여력%":  r.get("상승여력%"),
                "투자의견":   r.get("투자의견") or "—",
                "애널리스트수": r.get("애널리스트수"),
            })

        atbl = pd.DataFrame(rows_a)
        price_cols = ["현재가", "목표가(평균)", "목표가(최고)", "목표가(최저)"]
        for c in price_cols:
            atbl[c] = pd.to_numeric(atbl[c], errors="coerce")
        atbl["상승여력%"] = pd.to_numeric(atbl["상승여력%"], errors="coerce")
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

    # ── FMP 개별 애널리스트 드릴다운 ─────────────────────────────────────────
    render_fmp_drilldown(list(_STOCK_KOR.keys()), _STOCK_KOR)
