"""
FX & Rates — currency pairs, yield curve, inflation, labor.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

from data.fetcher import fetch_all
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.dash_style import (
    inject_css, section_header, timestamp_bar, numeric,
)

_PAIR_LABELS = {
    "usd_krw": "USD/KRW",
    "jpy_krw": "JPY/KRW",
    "eur_krw": "EUR/KRW",
    "usd_jpy": "USD/JPY",
    "dxy":     "DXY",
}
_PAIR_NAMES = {
    "usd_krw": "달러 / 원화",
    "jpy_krw": "엔화 / 원화",
    "eur_krw": "유로 / 원화",
    "usd_jpy": "달러 / 엔화",
    "dxy":     "달러 인덱스",
}

_MAC_META = {
    "us_10y":           ("US 10Y 국채",   "%",   "금리"),
    "us_2y":            ("US 2Y 국채",    "%",   "금리"),
    "spread_10y_2y":    ("장단기 스프레드", "%",   "금리"),
    "fed_funds":        ("기준금리 (FFR)", "%",   "금리"),
    "cpi":              ("CPI",          "idx", "물가"),
    "core_cpi":         ("Core CPI",     "idx", "물가"),
    "pce":              ("PCE",          "idx", "물가"),
    "core_pce":         ("Core PCE",     "idx", "물가"),
    "unemployment":     ("실업률",        "%",   "고용"),
    "nonfarm_payrolls": ("비농업 고용",   "천명", "고용"),
}


@st.cache_data(ttl=300)
def _load_live():
    return fetch_all()


@st.cache_data(ttl=900)
def _fx_chart(ticker: str) -> pd.DataFrame:
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


_TREND_MAP = {"bullish": "상승", "bearish": "하락", "neutral": "중립"}


def render():
    inject_css()

    c1, c2 = st.columns([9, 1])
    c1.markdown("## 환율 & 금리")
    c1.caption("환율·금리 모니터 — 투자 참고용, 매매 권유 아님")
    if c2.button("↻ 새로고침", use_container_width=True):
        _load_live.clear()

    live = _load_live()
    ts = live["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

    # ── 1. FX Rates ───────────────────────────────────────────────────────────
    st.markdown(section_header("환율 현황", "실시간 환율 · 기간별 수익률"), unsafe_allow_html=True)

    db_df  = load_latest_indicator_summary(DEFAULT_DB)
    fx_db  = db_df[db_df["asset_type"] == "fx"].copy() if not db_df.empty else pd.DataFrame()

    def _db_val(ticker: str, col: str):
        if fx_db.empty:
            return None
        m = fx_db[fx_db["symbol"] == ticker]
        if m.empty:
            return None
        v = m.iloc[0].get(col)
        return float(v) if isinstance(v, (int, float)) else None

    rows = []
    for _, r in live["fx"].iterrows():
        pair   = r["pair"]
        ticker = r["ticker"]
        rows.append({
            "통화쌍": _PAIR_LABELS.get(pair, pair.upper()),
            "이름":   _PAIR_NAMES.get(pair, ""),
            "현재가": r["rate"]       if isinstance(r["rate"],       (int, float)) else None,
            "1D %":  r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
            "1W %":  _db_val(ticker, "return_1w_pct"),
            "1M %":  _db_val(ticker, "return_1m_pct"),
            "3M %":  _db_val(ticker, "return_3m_pct"),
            "추세":  _TREND_MAP.get(_db_val_str(fx_db, ticker, "trend_status"), _db_val_str(fx_db, ticker, "trend_status")),
            "_tk":   ticker,
        })

    tbl = pd.DataFrame(rows)
    pct_cols = [c for c in ["1D %", "1W %", "1M %", "3M %"] if c in tbl.columns]
    disp = numeric(tbl.drop(columns=["_tk"]), pct_cols + ["현재가"])

    def _c(v):
        if not isinstance(v, (int, float)) or pd.isna(v): return ""
        if v > 0.3:  return "background-color:#FFF5F5;color:#9B2335;font-weight:600"
        if v < -0.3: return "background-color:#F0FFF6;color:#276749;font-weight:600"
        return ""

    def _ts(v):
        if v in ("bullish", "상승"): return "color:#276749;font-weight:700"
        if v in ("bearish", "하락"): return "color:#9B2335;font-weight:700"
        return "color:#718096"

    styled = disp.style.map(_c, subset=pct_cols)
    if "추세" in disp.columns:
        styled = styled.map(_ts, subset=["추세"])

    cfg = {c: st.column_config.NumberColumn(format="%.2f%%") for c in pct_cols}
    cfg["현재가"] = st.column_config.NumberColumn(format="%.4f")
    st.dataframe(styled, column_config=cfg, use_container_width=True, hide_index=True)

    if not fx_db.empty:
        run_date = db_df["run_date"].max()
        st.caption(f"1W/1M/3M·추세: DB 기준 ({run_date})  ·  `python main.py` 실행 시 업데이트")

    # ── 2. Price Chart ────────────────────────────────────────────────────────
    st.markdown(section_header("가격 추이", "3개월 일별 종가"), unsafe_allow_html=True)

    chart_opts = {
        _PAIR_LABELS.get(r["pair"], r["pair"]): r["ticker"]
        for _, r in live["fx"].iterrows()
    }
    col_sel, _ = st.columns([3, 7])
    with col_sel:
        sel_label = st.selectbox("통화쌍", list(chart_opts.keys()), label_visibility="collapsed")
    sel_ticker = chart_opts[sel_label]

    hist = _fx_chart(sel_ticker)
    if not hist.empty:
        pct   = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        sign  = "+" if pct >= 0 else ""
        color = "#276749" if pct >= 0 else "#9B2335"
        fig = go.Figure(go.Scatter(
            x=hist["Date"], y=hist["Close"], mode="lines",
            line=dict(color="#1C2B3A", width=1.5),
            fill="tozeroy", fillcolor="rgba(28,43,58,0.05)",
        ))
        fig.update_layout(
            title=dict(
                text=(f"{sel_label}  "
                      f"<span style='font-size:11px;color:{color}'>{sign}{pct:.2f}% (3M)</span>"),
                font=dict(size=12, color="#2D3748"), x=0, xanchor="left",
            ),
            margin=dict(l=0, r=0, t=36, b=0), height=220,
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
            xaxis=dict(showgrid=False, showline=True, linecolor="#E2E8F0",
                       tickfont=dict(size=9, color="#718096")),
            yaxis=dict(showgrid=True, gridcolor="#F0F4F8", showline=True,
                       linecolor="#E2E8F0", tickformat=",.4f",
                       tickfont=dict(size=9, color="#718096"), side="right"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info(f"{sel_label} 차트 데이터를 불러올 수 없습니다.")

    # ── 2b. Dual-axis Correlation Charts ─────────────────────────────────────
    st.markdown(section_header("상관관계 차트", "주요 자산 간 동조/역행 관계"), unsafe_allow_html=True)

    @st.cache_data(ttl=900)
    def _dual_hist(t1: str, t2: str) -> tuple:
        def _dl(t):
            try:
                raw = yf.download(t, period="3mo", interval="1d",
                                  progress=False, auto_adjust=True)
                if raw.empty:
                    return pd.DataFrame()
                c = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]
                if hasattr(c, "columns"):
                    c = c.iloc[:, 0]
                df = c.reset_index()
                df.columns = ["Date", "Close"]
                return df.dropna()
            except Exception:
                return pd.DataFrame()
        return _dl(t1), _dl(t2)

    def _dual_fig(h1, h2, name1, name2, color1, color2, fmt1=",.2f", fmt2=",.2f"):
        if h1.empty or h2.empty:
            return None
        from plotly.subplots import make_subplots
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(
            x=h1["Date"], y=h1["Close"], name=name1, mode="lines",
            line=dict(color=color1, width=1.5),
            hovertemplate=f"%{{y:{fmt1}}}<extra>{name1}</extra>",
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=h2["Date"], y=h2["Close"], name=name2, mode="lines",
            line=dict(color=color2, width=1.5, dash="dot"),
            hovertemplate=f"%{{y:{fmt2}}}<extra>{name2}</extra>",
        ), secondary_y=True)
        fig.update_layout(
            margin=dict(l=0, r=0, t=8, b=0), height=180,
            paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
            legend=dict(font=dict(size=8.5), orientation="h",
                        yanchor="bottom", y=1.01, x=0,
                        bgcolor="rgba(255,255,255,0)"),
            xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#718096")),
            hovermode="x unified",
        )
        fig.update_yaxes(tickfont=dict(size=8, color=color1),
                         gridcolor="#F0F4F8", showgrid=True, secondary_y=False)
        fig.update_yaxes(tickfont=dict(size=8, color=color2),
                         showgrid=False, secondary_y=True)
        return fig

    dc1, dc2 = st.columns(2)
    with dc1:
        h_krw, h_dxy = _dual_hist("USDKRW=X", "DX-Y.NYB")
        fig = _dual_fig(h_krw, h_dxy, "USD/KRW", "DXY", "#2D3748", "#4A6FA5")
        if fig:
            st.caption("USD/KRW vs DXY — 달러 강세와 원화 약세 연동")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with dc2:
        h_qqq, h_10y = _dual_hist("QQQ", "^TNX")
        fig = _dual_fig(h_qqq, h_10y, "QQQ", "US 10Y", "#1C2B3A", "#D64E4E", ",.2f", ".2f")
        if fig:
            st.caption("QQQ vs US 10Y — 금리와 기술주 역행 관계")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    dc3, dc4 = st.columns(2)
    with dc3:
        h_gld, h_10y2 = _dual_hist("GC=F", "^TNX")
        fig = _dual_fig(h_gld, h_10y2, "Gold", "US 10Y", "#C9A84C", "#D64E4E", ",.2f", ".2f")
        if fig:
            st.caption("Gold vs US 10Y — 실질금리와 금 역행 관계")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with dc4:
        h_gld2, h_dxy2 = _dual_hist("GC=F", "DX-Y.NYB")
        fig = _dual_fig(h_gld2, h_dxy2, "Gold", "DXY", "#C9A84C", "#4A6FA5", ",.2f", ".2f")
        if fig:
            st.caption("Gold vs DXY — 달러와 금 역행 관계")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── 3. US Rates & Macro (FRED) ────────────────────────────────────────────
    st.markdown(section_header("미국 금리 & 매크로", "FRED 최신 발표치"), unsafe_allow_html=True)

    mac = live["macro"]
    if mac is None or mac.empty:
        st.info("FRED API 키를 사이드바에 입력하면 금리·물가·고용 데이터가 표시됩니다.")
        return

    groups: dict[str, list] = {}
    for _, r in mac.iterrows():
        key  = r["key"]
        label, unit, group = _MAC_META.get(key, (key, "", "기타"))
        val  = r["value"]
        date = r.get("date", "")

        if isinstance(val, (int, float)):
            if unit == "%":
                val_str = f"{val:.2f}%"
            elif unit == "천명":
                val_str = f"{val:,.0f}천명"
            else:
                val_str = f"{val:.2f}"
        else:
            val_str = "N/A"

        groups.setdefault(group, []).append({
            "지표":   label,
            "값":     val_str,
            "기준일": str(date)[:10] if date and date != "N/A" else "N/A",
        })

    for group_name, group_rows in groups.items():
        st.markdown(
            f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:1px;color:#718096;margin:14px 0 4px">{group_name}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(group_rows), use_container_width=True, hide_index=True)


def _db_val_str(fx_db: pd.DataFrame, ticker: str, col: str) -> str:
    if fx_db.empty:
        return "—"
    m = fx_db[fx_db["symbol"] == ticker]
    if m.empty:
        return "—"
    v = m.iloc[0].get(col, "—")
    return str(v) if v else "—"
