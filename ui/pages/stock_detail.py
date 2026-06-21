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
/* 종목상세는 콘텐츠가 적어 전폭(1380)이면 휑함 → 이 페이지만 폭을 좁혀 밀도를 높인다(스코프: 렌더 시에만 주입) */
[data-testid="stAppViewBlockContainer"], .block-container{max-width:960px!important}
.sd-toprow{display:flex;align-items:center;justify-content:space-between;margin:2px 0 10px;gap:12px}
.sd-topright{display:flex;align-items:center;gap:9px}
.sd-tk{font-size:12.5px;font-weight:850;font-variant-numeric:tabular-nums}
/* 헤더 카드(이름·가격) + 보유 항목 카드를 한 줄에 */
.sd-headrow{display:flex;align-items:stretch;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.sd-head{flex:1 1 300px;display:flex;align-items:center;justify-content:space-between;gap:18px;row-gap:12px;flex-wrap:wrap;
  background:#16181F;border:1px solid #262A33;border-radius:14px;padding:16px 20px}
.sd-headrow .sd-cell{flex:1 1 108px;display:flex;flex-direction:column;justify-content:center}
.sd-id{min-width:0}
.sd-id h2{margin:0;color:#E7E9EE;font-size:23px;font-weight:950;letter-spacing:-.02em}
.sd-starx{font-size:22px;line-height:1;text-decoration:none;color:#D9A441!important;flex-shrink:0;transition:color .15s}
.sd-starx.on{color:#D9A441!important}
.sd-starx:hover{color:#E7C06A!important}
.sd-chart-hd{font-size:16px;font-weight:900;color:#E7E9EE;padding-top:7px;display:flex;align-items:baseline;gap:12px}
.sd-chart-hd .p{font-size:15px;font-weight:900;font-variant-numeric:tabular-nums}
.sd-id .sd-meta{color:#7E8694;font-size:12px;font-weight:800;margin-top:6px}
.sd-cat{display:inline-block;font-size:10.5px;font-weight:850;color:#9AA0AD;background:#1E2029;
  border:1px solid #262A33;border-radius:999px;padding:3px 10px;margin-right:6px}
.sd-px{display:flex;align-items:baseline;gap:9px;flex-shrink:0}
.sd-px .v{font-size:24px;font-weight:950;color:#E7E9EE;font-variant-numeric:tabular-nums}
.sd-px .d{font-size:13px;font-weight:900;font-variant-numeric:tabular-nums}
.sd-px .d.up{color:#F25560}.sd-px .d.down{color:#4D90F0}
/* 카드 그리드(보유 항목·지표) — auto-fit로 개수에 맞춰 고르게 채움 */
.sd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;margin:0 0 14px}
@media(max-width:760px){.sd-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.sd-cell{background:#16181F;border:1px solid #262A33;border-radius:12px;padding:11px 14px}
.sd-cell .k{font-size:10px;font-weight:850;color:#7E8694;text-transform:uppercase;letter-spacing:.04em}
.sd-cell .v{font-size:20px;font-weight:900;color:#E7E9EE;font-variant-numeric:tabular-nums;margin-top:5px;text-align:right}
.sd-cell .v.up{color:#F25560}.sd-cell .v.down{color:#4D90F0}
.sd-card{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:16px 18px;margin:0 0 14px}
.sd-card .t{font-size:13px;font-weight:900;color:#E7E9EE;margin-bottom:10px}
.sd-hold{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;
  padding-top:14px;border-top:1px solid #262A33}
@media(max-width:760px){.sd-hold{grid-template-columns:repeat(2,minmax(0,1fr))}}
.sd-hold .k{font-size:10px;font-weight:850;color:#7E8694}
.sd-hold .v{font-size:17px;font-weight:900;color:#E7E9EE;font-variant-numeric:tabular-nums;margin-top:3px}
.sd-hold .v.up{color:#F25560}.sd-hold .v.down{color:#4D90F0}
.sd-back{display:inline-flex;align-items:center;gap:4px;color:#D9A441!important;font-size:12px;font-weight:850;
  text-decoration:none;margin:2px 0 10px}
.sd-back:hover{color:#E7C06A!important}
.sd-star{font-size:12px;font-weight:850;text-decoration:none;border-radius:999px;padding:5px 12px;
  border:1px solid rgba(217,164,65,.34);background:rgba(217,164,65,.10);color:#D9A441;white-space:nowrap}
.sd-star.on{background:rgba(217,164,65,.2);border-color:#D9A441}
</style>"""

_CAT_OF = {  # 시장 데이터 테이블 → 카테고리 라벨
    "us_stocks": "미국주식", "kr_stocks": "국내주식", "my_etfs": "ETF",
    "benchmarks": "지수·ETF", "commodities": "원자재", "crypto": "크립토",
}

# 카테고리 시그니처 색(포트폴리오 _CAT_COLOR와 동일 체계) — '미국주식' 등 마커 색
_CAT_SIG = {
    "미국주식": "#8A2B48", "국내주식": "#563460", "ETF": "#7E6BD6",
    "지수·ETF": "#7E6BD6", "크립토": "#F0A030", "원자재": "#9E7B3B",
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
def _chart(ticker: str, period: str = "6mo") -> pd.DataFrame:
    try:
        from data.session import cached_download
        raw = cached_download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
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


def _sig_color(ticker: str, category: str) -> str:
    """종목 고유 시그니처색 — 시장 페이지 브랜드 맵에서 조회, 없으면 골드 폴백."""
    short = ticker.replace(".KS", "").replace(".KQ", "").replace("-USD", "").upper()
    try:
        from ui.pages.us_stocks import _US_BRAND
        if short in _US_BRAND:
            return _US_BRAND[short]
    except Exception:
        pass
    try:
        from ui.pages.kr_stocks import _KR_BRAND
        if ticker in _KR_BRAND:
            return _KR_BRAND[ticker]
    except Exception:
        pass
    try:
        from ui.pages.crypto import _CRYPTO_COLOR
        if f"{short}-USD" in _CRYPTO_COLOR:
            return _CRYPTO_COLOR[f"{short}-USD"]
    except Exception:
        pass
    return GOLD


def render() -> None:
    L.viewport_width()
    L.inject_responsive_css()
    inject_css()
    mark_active_nav("")
    st.markdown(_DETAIL_CSS, unsafe_allow_html=True)

    sfx = _auth_qs()
    qs = f"?{sfx}" if sfx else ""
    symbol = st.query_params.get("symbol", "").strip()
    if not symbol:
        st.markdown(f'<a class="sd-back" href="/market{qs}" target="_self">← 시장으로</a>', unsafe_allow_html=True)
        empty_state("종목을 선택하세요", "헤더의 종목 검색에서 종목을 고르면 상세가 열립니다")
        return

    data = load_market_data()
    info = _resolve(symbol, data)
    if not info:
        st.markdown(f'<a class="sd-back" href="/market{qs}" target="_self">← 시장으로</a>', unsafe_allow_html=True)
        empty_state(f"‘{symbol}’ 종목 정보 준비 중", "시장 유니버스에 없는 종목일 수 있습니다")
        return

    ticker = info["ticker"]
    cur = info["currency"]
    sig = _sig_color(ticker, info["category"])          # 종목 고유색(티커·차트)
    catc = _CAT_SIG.get(info["category"], sig)          # 카테고리 시그니처색(미국주식 등 마커)

    # 워치리스트 토글 — 별표 링크(쿼리파라미터). 클릭당 1회·URL 정리(새로고침 재토글 방지).
    _wkey = f"_watch_done_{ticker}"
    if st.query_params.get("watch") == "1":
        if not st.session_state.get(_wkey):
            _toggle_watch(ticker)
            st.session_state[_wkey] = True
        _qp = {k: v for k, v in st.query_params.items() if k != "watch"}
        st.query_params.clear()
        st.query_params.update(_qp)
    else:
        st.session_state.pop(_wkey, None)
    on = ticker in _watchlist()
    _star_href = f"?symbol={symbol}&watch=1" + (f"&{sfx}" if sfx else "")

    # ── 상단행: 뒤로(좌) · 카테고리/티커 + 워치리스트 별표(우) ──
    st.markdown(
        f'<div class="sd-toprow"><a class="sd-back" href="/market{qs}" target="_self">← 시장으로</a>'
        f'<div class="sd-topright">'
        f'<span class="sd-cat" style="color:{catc};background:{catc}26;border-color:{catc}">{info["category"]}</span>'
        f'<span class="sd-cat" style="color:{sig};background:{sig}26;border-color:{sig};margin:0">{ticker}</span>'
        f'<a class="sd-starx {"on" if on else ""}" href="{_star_href}" target="_self" title="워치리스트">{"★" if on else "☆"}</a>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── 헤더 카드(이름·가격) + 보유 시 비중·평가액·손익률 카드를 같은 라인에 ──
    price_html = currency(info["price"], cur) if info["price"] is not None else "—"
    chg = info["change_pct"]
    dcls = "up" if (chg or 0) >= 0 else "down"
    dtxt = f'{"+" if (chg or 0) >= 0 else ""}{chg:.2f}%' if isinstance(chg, (int, float)) else "—"

    head = (
        f'<div class="sd-head"><div class="sd-id"><h2>{info["name"]}</h2></div>'
        f'<div class="sd-px"><span class="v">{price_html}</span>'
        f'<span class="d {dcls}">{dtxt} <span style="color:#7E8694;font-weight:700">오늘</span></span></div></div>'
    )
    pos = _my_holding(ticker, data)
    cells = ""
    if pos:
        gl = pos.get("gain_loss_pct"); gcls = "up" if (gl or 0) >= 0 else "down"
        def _cell(k, v, cls=""):
            return f'<div class="sd-cell"><div class="k">{k}</div><div class="v {cls}">{v}</div></div>'
        cells = (_cell("비중", f'{(pos.get("weight") or 0):.1f}%')
                 + _cell("평가액", won(pos.get("market_value")))
                 + _cell("손익률", f'{("+" if (gl or 0)>=0 else "")}{(gl or 0):.1f}%', gcls))
    st.markdown(f'<div class="sd-headrow">{head}{cells}</div>', unsafe_allow_html=True)

    # ── 전문가용 지표(변동성·52주 위치·MA 이격·모멘텀) — DB indicator_summary ──
    _render_indicators(ticker)

    # ── 6개월 추이 차트(종목 시그니처색) ──
    _render_chart(ticker, info, cur, sig)

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

    def _f(v):
        return float(v) if isinstance(v, (int, float)) and not pd.isna(v) else None

    # 52주 범위 내 위치(%) — 전문가가 즐겨 보는 기준(고점/저점 대비). 1년 일봉에서 산출.
    pos52 = None
    try:
        from ui.components.range_bar import fetch_52w_range
        rng = fetch_52w_range(ticker)
        if rng and rng[1] > rng[0]:
            pos52 = (rng[2] - rng[0]) / (rng[1] - rng[0]) * 100
    except Exception:
        pass

    def signed(k, v):  # 부호 색(이격·모멘텀)
        if v is None:
            return f'<div class="sd-cell"><div class="k">{k}</div><div class="v">—</div></div>'
        cls = "up" if v >= 0 else "down"
        return f'<div class="sd-cell"><div class="k">{k}</div><div class="v {cls}">{v:+.2f}%</div></div>'

    def neutral(k, v, fmt="{:.1f}%"):  # 무채(변동성·위치 — 방향성 없는 지표)
        if v is None:
            return f'<div class="sd-cell"><div class="k">{k}</div><div class="v">—</div></div>'
        return f'<div class="sd-cell"><div class="k">{k}</div><div class="v">{fmt.format(v)}</div></div>'

    st.markdown(
        '<div class="sd-grid">'
        + neutral("변동성 20D", _f(r.get("volatility_20d_pct")))      # 연환산 변동성(리스크)
        + neutral("52주 위치", pos52, "{:.0f}%")                      # 고점·저점 대비 현재 위치
        + signed("MA20 이격", _f(r.get("distance_ma20_pct")))        # 단기 추세 위치
        + signed("MA60 이격", _f(r.get("distance_ma60_pct")))        # 중기 추세 위치
        + signed("3M 모멘텀", _f(r.get("return_3m_pct")))            # 분기 모멘텀
        + '</div>', unsafe_allow_html=True)


def _render_chart(ticker: str, info: dict, cur: str, sig: str = GOLD) -> None:
    import plotly.graph_objects as go
    from ui.components.dash_style import period_radio
    # '가격 추이 +X%' 라벨(좌) + 기간 라디오(우, 시장 페이지와 동일·가운데 정렬) 같은 라인
    _hd, _ctrl = st.columns([1, 1.15])
    with _ctrl:
        _pd_label, _pd_code = period_radio("sd_period")   # 1M/3M/6M/1Y/5Y → yfinance 코드
    h = _chart(ticker, _pd_code)
    if h.empty:
        empty_state("차트 데이터 준비 중")
        return
    pct = (h["Close"].iloc[-1] / h["Close"].iloc[0] - 1) * 100
    color = UP if pct >= 0 else DOWN
    with _hd:
        st.markdown(f'<div class="sd-chart-hd"><span>가격 추이</span>'
                    f'<span class="p" style="color:{color}">{"+" if pct>=0 else ""}{pct:.1f}% ({_pd_label})</span></div>',
                    unsafe_allow_html=True)
    _sh = sig.lstrip("#")
    _fill = f"rgba({int(_sh[0:2],16)},{int(_sh[2:4],16)},{int(_sh[4:6],16)},0.07)"
    fig = go.Figure(go.Scatter(
        x=h["Date"], y=h["Close"], mode="lines",
        line=dict(color=sig, width=1.6), fill="tozeroy", fillcolor=_fill,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
    ))
    fmt = ",.0f" if cur == "KRW" else ",.2f"
    # y축을 데이터 범위로 — 0부터 시작하지 않아 라인이 패널을 채움(휑함 제거)
    _lo, _hi = float(h["Close"].min()), float(h["Close"].max())
    _pad = (_hi - _lo) * 0.10 or _hi * 0.02
    fig.update_layout(
        height=170, margin=dict(l=0, r=0, t=4, b=0),
        paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
        xaxis=dict(showgrid=False, showline=True, linecolor="#262A33", tickfont=dict(size=9, color="#7E8694")),
        yaxis=dict(showgrid=True, gridcolor="#262A33", tickformat=fmt, range=[_lo - _pad, _hi + _pad],
                   tickfont=dict(size=9, color="#7E8694"), side="right"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})




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
