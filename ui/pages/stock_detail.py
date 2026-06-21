"""개별 종목 상세 (B2) — /stock?symbol=<티커>.

가격·오늘 등락 / 6개월 추이 차트 / 내 보유(비중·평가·손익) / 1W·1M·3M·MA20·추세 /
애널리스트 목표가 / 워치리스트 별표. 종목 검색·워치리스트의 종착지.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import layout as L
from data.loader import load_market_data
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.dash_style import inject_css, mark_active_nav, empty_state, jj_footer
from siminvest_theme import UP, DOWN, GOLD
from format import currency, won

_DETAIL_CSS = """<style>
.sd-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin:8px 0 14px;flex-wrap:wrap}
.sd-id{min-width:0}
.sd-id h2{margin:0;color:#E7E9EE;font-size:24px;font-weight:950;letter-spacing:-.02em}
.sd-id .sd-meta{color:#7E8694;font-size:12px;font-weight:800;margin-top:4px}
.sd-cat{display:inline-block;font-size:10.5px;font-weight:850;color:#9AA0AD;background:#1E2029;
  border:1px solid #262A33;border-radius:999px;padding:3px 10px;margin-right:6px}
.sd-px{text-align:right}
.sd-px .v{font-size:26px;font-weight:950;color:#E7E9EE;font-variant-numeric:tabular-nums;line-height:1}
.sd-px .d{font-size:13px;font-weight:900;margin-top:4px;font-variant-numeric:tabular-nums}
.sd-px .d.up{color:#F25560}.sd-px .d.down{color:#4D90F0}
.sd-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:0 0 14px}
@media(max-width:760px){.sd-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.sd-cell{background:#16181F;border:1px solid #262A33;border-radius:12px;padding:11px 12px}
.sd-cell .k{font-size:10px;font-weight:850;color:#7E8694;text-transform:uppercase;letter-spacing:.04em}
.sd-cell .v{font-size:16px;font-weight:900;color:#E7E9EE;font-variant-numeric:tabular-nums;margin-top:4px}
.sd-cell .v.up{color:#F25560}.sd-cell .v.down{color:#4D90F0}
.sd-card{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:16px 18px;margin:0 0 14px}
.sd-card .t{font-size:13px;font-weight:900;color:#E7E9EE;margin-bottom:10px}
.sd-hold{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
@media(max-width:760px){.sd-hold{grid-template-columns:repeat(2,minmax(0,1fr))}}
.sd-hold .k{font-size:10px;font-weight:850;color:#7E8694}
.sd-hold .v{font-size:17px;font-weight:900;color:#E7E9EE;font-variant-numeric:tabular-nums;margin-top:3px}
.sd-hold .v.up{color:#F25560}.sd-hold .v.down{color:#4D90F0}
.sd-back{display:inline-flex;align-items:center;gap:4px;color:#9AA0AD;font-size:12px;font-weight:850;
  text-decoration:none;margin:2px 0 10px}
.sd-back:hover{color:#E7E9EE}
.sd-star{font-size:12px;font-weight:850;text-decoration:none;border-radius:999px;padding:5px 12px;
  border:1px solid rgba(217,164,65,.34);background:rgba(217,164,65,.10);color:#D9A441;white-space:nowrap}
.sd-star.on{background:rgba(217,164,65,.2);border-color:#D9A441}
</style>"""

_CAT_OF = {  # 시장 데이터 테이블 → 카테고리 라벨
    "us_stocks": "미국주식", "kr_stocks": "국내주식", "my_etfs": "ETF",
    "benchmarks": "지수·ETF", "commodities": "원자재", "crypto": "크립토",
}


def _auth_qs() -> str:
    role = st.session_state.get("auth_role")
    if role == "guest":
        return "_auth=guest"
    u = st.session_state.get("username")
    return f"_user={u}" if u else ""


def _resolve(symbol: str, data: dict) -> dict | None:
    """심볼(표시용 단축 가능)을 시장 테이블에서 찾아 풀티커·이름·카테고리·시세 반환."""
    s = symbol.upper()
    for tbl, cat in _CAT_OF.items():
        df = data.get(tbl, pd.DataFrame())
        if df is None or df.empty or "ticker" not in df.columns:
            continue
        for _, r in df.iterrows():
            tk = str(r.get("ticker", "")).upper()
            short = tk.replace(".KS", "").replace(".KQ", "").replace("-USD", "")
            if s in (tk, short):
                return {
                    "ticker": tk, "name": str(r.get("name") or short), "category": cat,
                    "price": r.get("price"), "change_pct": r.get("change_pct"),
                    "currency": "KRW" if (cat in ("국내주식", "ETF") or tk.endswith(".KS")) else "USD",
                }
    return None


@st.cache_data(ttl=900, show_spinner=False)
def _chart(ticker: str) -> pd.DataFrame:
    try:
        from data.session import cached_download
        raw = cached_download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if raw.empty:
            return pd.DataFrame()
        c = raw["Close"]
        if hasattr(c, "columns"):
            c = c.iloc[:, 0]
        df = c.reset_index()
        df.columns = ["Date", "Close"]
        return df.dropna()
    except Exception:
        return pd.DataFrame()


def _my_holding(ticker: str, data: dict) -> dict | None:
    bh = st.session_state.get("brokerage_holdings")
    if not bh:
        return None
    try:
        from ui.pages.portfolio import _normalize_holdings, _portfolio_summary
        # 전체 시장 데이터(FX·시세) 위에 보유를 얹어야 환산·비중이 포트폴리오와 일치
        d = dict(data)
        d["holdings"] = bh
        d["cash_balance"] = st.session_state.get("brokerage_cash_balance")
        positions, meta = _normalize_holdings(d)
        _portfolio_summary(positions, meta)  # weight 부착
        short = ticker.replace(".KS", "").replace(".KQ", "").replace("-USD", "")
        for p in positions:
            if str(p.get("ticker", "")).upper() in (ticker.upper(), short):
                return p
    except Exception:
        return None
    return None


def _watchlist() -> list[str]:
    u = st.session_state.get("username")
    if u and st.session_state.get("auth_role") != "guest":
        from core.accounts import get_setting
        return get_setting(u, "watchlist", []) or []
    return st.session_state.get("_guest_watchlist", [])


def _toggle_watch(ticker: str) -> None:
    wl = list(_watchlist())
    wl = [w for w in wl if w != ticker] if ticker in wl else (wl + [ticker])
    u = st.session_state.get("username")
    if u and st.session_state.get("auth_role") != "guest":
        from core.accounts import set_setting
        set_setting(u, "watchlist", wl)
    st.session_state["_guest_watchlist"] = wl


def render() -> None:
    L.viewport_width()
    L.inject_responsive_css()
    inject_css()
    mark_active_nav("")
    st.markdown(_DETAIL_CSS, unsafe_allow_html=True)

    sfx = _auth_qs()
    qs = f"?{sfx}" if sfx else ""
    st.markdown(f'<a class="sd-back" href="/market{qs}" target="_self">← 시장으로</a>',
                unsafe_allow_html=True)

    symbol = st.query_params.get("symbol", "").strip()
    if not symbol:
        empty_state("종목을 선택하세요", "헤더의 종목 검색에서 종목을 고르면 상세가 열립니다")
        return

    data = load_market_data()
    info = _resolve(symbol, data)
    if not info:
        empty_state(f"‘{symbol}’ 종목 정보 준비 중", "시장 유니버스에 없는 종목일 수 있습니다")
        return

    ticker = info["ticker"]
    cur = info["currency"]

    # ── 헤더: 이름·카테고리·티커 + 현재가·오늘 + 워치 별표 ──
    price_html = currency(info["price"], cur) if info["price"] is not None else "—"
    chg = info["change_pct"]
    dcls = "up" if (chg or 0) >= 0 else "down"
    dtxt = f'{"+" if (chg or 0) >= 0 else ""}{chg:.2f}%' if isinstance(chg, (int, float)) else "—"
    on = ticker in _watchlist()
    star_label = "★ 워치리스트" if on else "☆ 워치리스트"
    st.markdown(
        f'<div class="sd-head"><div class="sd-id"><h2>{info["name"]}</h2>'
        f'<div class="sd-meta"><span class="sd-cat">{info["category"]}</span>{ticker}</div></div>'
        f'<div class="sd-px"><div class="v">{price_html}</div>'
        f'<div class="d {dcls}">{dtxt} <span style="color:#7E8694;font-weight:700">오늘</span></div></div></div>',
        unsafe_allow_html=True,
    )
    if st.button(star_label, key="sd_watch"):
        _toggle_watch(ticker)
        st.rerun()

    # ── 내 보유 (있으면) ──
    pos = _my_holding(ticker, data)
    if pos:
        gl = pos.get("gain_loss_pct")
        gcls = "up" if (gl or 0) >= 0 else "down"
        tcls = "up" if (pos.get("today_change_pct") or 0) >= 0 else "down"
        st.markdown(
            '<div class="sd-card"><div class="t">내 보유</div><div class="sd-hold">'
            f'<div><div class="k">비중</div><div class="v">{(pos.get("weight") or 0):.1f}%</div></div>'
            f'<div><div class="k">평가액</div><div class="v">{won(pos.get("market_value"))}</div></div>'
            f'<div><div class="k">손익률</div><div class="v {gcls}">{("+" if (gl or 0)>=0 else "")}{(gl or 0):.1f}%</div></div>'
            f'<div><div class="k">오늘</div><div class="v {tcls}">{("+" if (pos.get("today_change_pct") or 0)>=0 else "")}{(pos.get("today_change_pct") or 0):.2f}%</div></div>'
            '</div></div>', unsafe_allow_html=True)

    # ── 기간 지표 (1W·1M·3M·MA20·추세) — DB indicator_summary ──
    _render_indicators(ticker)

    # ── 6개월 추이 차트 ──
    _render_chart(ticker, info, cur)

    # ── 애널리스트 목표가 (가능 시) ──
    _render_analyst(ticker, info)

    st.markdown(jj_footer(), unsafe_allow_html=True)


def _render_indicators(ticker: str) -> None:
    db = load_latest_indicator_summary(DEFAULT_DB)
    if db is None or db.empty or "symbol" not in db.columns:
        return
    m = db[db["symbol"].astype(str).str.upper() == ticker.upper()]
    if m.empty:
        return
    r = m.iloc[0]
    trend = {"bullish": "상승", "bearish": "하락", "neutral": "보합"}.get(str(r.get("trend_status", "")), "—")

    def cell(k, v, pct=True):
        if not isinstance(v, (int, float)) or pd.isna(v):
            return f'<div class="sd-cell"><div class="k">{k}</div><div class="v">—</div></div>'
        cls = "up" if v >= 0 else "down"
        return f'<div class="sd-cell"><div class="k">{k}</div><div class="v {cls}">{v:+.2f}%</div></div>'

    tcls = "up" if trend == "상승" else ("down" if trend == "하락" else "")
    st.markdown(
        '<div class="sd-grid">'
        + cell("1주", r.get("return_1w_pct"))
        + cell("1개월", r.get("return_1m_pct"))
        + cell("3개월", r.get("return_3m_pct"))
        + cell("MA20 이격", r.get("distance_ma20_pct"))
        + f'<div class="sd-cell"><div class="k">추세</div><div class="v {tcls}">{trend}</div></div>'
        + '</div>', unsafe_allow_html=True)


def _render_chart(ticker: str, info: dict, cur: str) -> None:
    hist = _chart(ticker)
    if hist.empty:
        empty_state("차트 데이터 준비 중")
        return
    import plotly.graph_objects as go
    _dt = pd.to_datetime(hist["Date"])
    _pd_label, _pd_days = L_period()
    h = hist[_dt >= _dt.max() - pd.Timedelta(days=_pd_days)]
    if len(h) < 2:
        h = hist
    pct = (h["Close"].iloc[-1] / h["Close"].iloc[0] - 1) * 100
    color = UP if pct >= 0 else DOWN
    st.markdown(f'<div class="sd-card" style="padding-bottom:6px"><div class="t">가격 추이 '
                f'<span style="color:{color};font-size:11px">{"+" if pct>=0 else ""}{pct:.1f}% ({_pd_label})</span></div></div>',
                unsafe_allow_html=True)
    fig = go.Figure(go.Scatter(
        x=h["Date"], y=h["Close"], mode="lines",
        line=dict(color=GOLD, width=1.6), fill="tozeroy", fillcolor="rgba(217,164,65,0.06)",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
    ))
    fmt = ",.0f" if cur == "KRW" else ",.2f"
    fig.update_layout(
        height=240, margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
        xaxis=dict(showgrid=False, showline=True, linecolor="#262A33", tickfont=dict(size=9, color="#7E8694")),
        yaxis=dict(showgrid=True, gridcolor="#262A33", tickformat=fmt,
                   tickfont=dict(size=9, color="#7E8694"), side="right"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def L_period():
    """기간 토글(공통 컴포넌트 재사용) — 6개월 데이터 슬라이스."""
    from ui.components.dash_style import period_toggle
    return period_toggle("sd_period", options=("1주", "1개월", "3개월", "6개월"), default="3개월")


def _render_analyst(ticker: str, info: dict) -> None:
    if info["category"] not in ("미국주식", "국내주식"):
        return
    try:
        from src.analyst import fetch_analyst_targets
        df = fetch_analyst_targets([ticker])
        if df is None or df.empty:
            return
        r = df.iloc[0]
        tgt = r.get("target_mean") or r.get("목표가")
        up = r.get("upside_pct") or r.get("상승여력%")
        if tgt is None:
            return
        ucls = "up" if (up or 0) >= 0 else "down"
        st.markdown(
            '<div class="sd-card"><div class="t">애널리스트 목표가</div><div class="sd-hold">'
            f'<div><div class="k">평균 목표가</div><div class="v">{currency(tgt, info["currency"])}</div></div>'
            + (f'<div><div class="k">상승여력</div><div class="v {ucls}">{("+" if (up or 0)>=0 else "")}{up:.1f}%</div></div>' if isinstance(up, (int, float)) else "")
            + '</div><div style="color:#7E8694;font-size:10.5px;font-weight:700;margin-top:8px">출처 Yahoo Finance 컨센서스 · 참고용</div></div>',
            unsafe_allow_html=True)
    except Exception:
        return
