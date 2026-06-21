"""
FX & Rates — currency pairs, yield curve, inflation, labor.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

import layout as L  # 모바일 분기(표→카드)
from data.loader import load_market_data
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.dash_style import (
    period_radio,
    data_source_note,
    empty_state,
    inject_css, jj_footer, mark_active_nav, numeric, show_skeleton,
    mkt_page_header, mkt_section_header, mkt_stats_chips, color_change,
)
from ui.components.scan_layer import scan_layer_html
from ui.components.slim_table import slim_table
from ui.components.range_bar import fetch_52w_ranges, range_bar_html

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
# 통화쌍별 고유색(라인·스파크라인) — 서로 구분되고 손익색(빨강/파랑)과 분리
_FX_COLOR = {
    "usd_krw": "#4FA98C",   # 달러/원 — 틸그린
    "jpy_krw": "#D98C5F",   # 엔/원 — 웜오렌지
    "eur_krw": "#5B6FB5",   # 유로/원 — 인디고
    "usd_jpy": "#C99A3C",   # 달러/엔 — 앰버
    "dxy":     "#8C7BD6",   # 달러 인덱스 — 퍼플
}
_FX_COLOR_DEFAULT = "#9AA0AD"

_MAC_META = {
    "us_10y":           ("US 10Y 국채",   "%",   "금리"),
    "us_2y":            ("US 2Y 국채",    "%",   "금리"),
    "spread_10y_2y":    ("장단기 스프레드", "%",   "금리"),
    "fed_funds":        ("기준금리 (FFR)", "%",   "금리"),
    "cpi":              ("CPI (YoY)",      "yoy", "물가"),
    "core_cpi":         ("Core CPI (YoY)", "yoy", "물가"),
    "pce":              ("PCE (YoY)",      "yoy", "물가"),
    "core_pce":         ("Core PCE (YoY)", "yoy", "물가"),
    "unemployment":     ("실업률",        "%",   "고용"),
    "nonfarm_payrolls": ("비농업 고용 (전월 대비)", "mom_man", "고용"),
}


@st.cache_data(ttl=900, show_spinner=False)
def _fx_chart(ticker: str, period: str = "3mo") -> pd.DataFrame:
    try:
        from data.session import cached_download
        raw = cached_download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
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


@st.cache_data(ttl=900, show_spinner=False)
def _dual_hist(t1: str, t2: str) -> tuple:
    def _dl(t):
        try:
            from data.session import cached_download
            raw = cached_download(t, period="3mo", interval="1d",
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


def _fx_price_chart(live: dict) -> None:
    """가격 추이 비교 — 전 통화쌍을 기준일=100 정규화로 한 차트에 합쳐 비교(통화쌍 고유색·spline).
    스케일이 다른 쌍(USD/KRW~1380, JPY/KRW~9, DXY~104)을 % 변화로 한눈에 비교. 기간 토글 1개로 전체 적용."""
    st.markdown(mkt_section_header("가격 추이 비교", "전 통화쌍 · 기준일=100 정규화로 한눈에 비교"),
                unsafe_allow_html=True)
    fx_rows = list(live["fx"].iterrows())
    if not fx_rows:
        return
    _pd_label, _pd_code = period_radio("fx_period_all")
    fig = go.Figure()
    plotted = 0
    for _, r in fx_rows:
        pair, ticker = r["pair"], r["ticker"]
        label = _PAIR_LABELS.get(pair, pair.upper())
        _h = _fx_chart(ticker, period=_pd_code)
        if _h.empty or len(_h) < 2 or not _h["Close"].iloc[0]:
            continue
        color = _FX_COLOR.get(pair, _FX_COLOR_DEFAULT)
        fig.add_trace(go.Scatter(
            x=_h["Date"], y=_h["Close"] / _h["Close"].iloc[0] * 100, mode="lines", name=label,
            line=dict(color=color, width=2, shape="spline", smoothing=0.6),
            hovertemplate=f"{label}: %{{y:.1f}}<extra></extra>",
        ))
        plotted += 1
    if not plotted:
        empty_state("차트 데이터 준비 중")
        return
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


def render(embedded: bool = False, section: str = "all"):
    """section: 'all'(환율+금리) | 'fx'(환율만, 시장 '외환' 탭)."""
    if not embedded:
        inject_css()
        mark_active_nav("/fx")
        _t, _s = (("외환", "환율 · 달러지수 · 통화쌍별 등락") if section == "fx"
                  else ("FX & 금리", "환율 · 달러지수 · 미국채 수익률 · 금리 지표"))
        st.markdown(mkt_page_header("💱", _t, _s), unsafe_allow_html=True)

    ph = show_skeleton()
    live   = load_market_data()
    db_df  = load_latest_indicator_summary(DEFAULT_DB)
    _dual_hist("USDKRW=X", "DX-Y.NYB")
    _dual_hist("QQQ", "^TNX")
    _dual_hist("GC=F", "^TNX")
    _dual_hist("GC=F", "DX-Y.NYB")
    ph.empty()

    # ── Stats chips ───────────────────────────────────────────────────────────
    fx_df = live.get("fx", pd.DataFrame())
    fx_chips = []
    for lbl, pair in [("USD/KRW","usd_krw"),("달러지수","dxy"),("JPY/KRW","jpy_krw")]:
        if fx_df.empty: break
        r = fx_df[fx_df["pair"] == pair]
        if r.empty: continue
        c = r.iloc[0].get("change_pct")
        if c is not None and isinstance(c, (int, float)):
            sign = "+" if c >= 0 else ""
            fx_chips.append({"label": lbl, "value": f"{sign}{c:.2f}%", "cls": "neg" if c>0 else ("pos" if c<0 else "neu")})
    if fx_chips:
        st.markdown(mkt_stats_chips(fx_chips), unsafe_allow_html=True)

    # ── 1. FX Rates ── (원자재 탭과 동일 배치: 칩 → 스캔 → 게이지바 → 표 토글. 별도 섹션 헤더 없음)
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
            "_pair": pair,
        })

    tbl = pd.DataFrame(rows)

    # ── 0. 30초 스캔 레이어 — 가장 큰 변동 통화쌍 + breadth ─────────────────────
    scan_items = [{
        "name": r["통화쌍"],
        "d1": r["1D %"],
        "ma20": None,  # FX는 MA20 이격 미제공 → 과열 카드 생략
        "series": [float(v) for v in _fx_chart(r["_tk"])["Close"].tolist()] if not _fx_chart(r["_tk"]).empty else [],
        "color": _FX_COLOR.get(r["_pair"], _FX_COLOR_DEFAULT),  # 통화쌍 고유색(꺾은선)
    } for r in rows]
    _scan = scan_layer_html(scan_items, spark_label="3개월 추이")
    if _scan:
        st.markdown(_scan, unsafe_allow_html=True)

    # 52주 레인지 바 — 원자재 탭과 동일(막대=저~고 · 점=현재 · 라벨=범위 내 위치)
    _rb_items = []
    _ranges = fetch_52w_ranges(",".join(r["_tk"] for r in rows))
    for r in rows:
        rng = _ranges.get(r["_tk"])
        if not rng:
            continue
        lo, hi, cur = rng
        _rb_items.append({"name": r["통화쌍"], "unit": r.get("이름", ""),
                          "low": lo, "high": hi, "current": cur, "d1": r.get("1D %"),
                          "color": _FX_COLOR.get(r["_pair"], _FX_COLOR_DEFAULT)})  # 통화쌍 시그니처색
    if _rb_items:
        st.markdown(range_bar_html(_rb_items, fmt="{:,.4f}"), unsafe_allow_html=True)
        st.caption("막대 = 52주 최저~최고 · 점 = 현재가 · 우측 라벨 = 범위 내 위치")

    # 정밀 표(현재가·1D/1W/1M/3M·추세)는 토글 뒤로 — 원자재 탭과 동일(기본 접힘, 게이지바 우선)
    if st.toggle("표로 보기", key="fx_all_tbl", value=False):
        _slim_rows = sorted(
            rows, key=lambda x: abs(x["1D %"]) if isinstance(x.get("1D %"), (int, float)) else -1,
            reverse=True)
        slim_table(_slim_rows, key="fx", name_key="통화쌍",
                   price_key="현재가", price_fmt="{:,.4f}", heat_scale=3.0)

    if not fx_db.empty:
        run_date = db_df["run_date"].max()
        st.caption(data_source_note("로컬 DB", updated=str(run_date), extra="기술지표 1W/1M/3M·추세"))

    # 가격 추이 + 기간 토글(#11) — 임베디드(시장 외환 탭) 포함 항상. 상관관계 차트만 비임베디드.
    _fx_price_chart(live)

    if not embedded:
        # ── 2b. Dual-axis Correlation Charts ─────────────────────────────────────
        st.markdown(mkt_section_header("상관관계 차트", "주요 자산 간 동조/역행 관계"), unsafe_allow_html=True)

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
                paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
                legend=dict(font=dict(size=8.5), orientation="h",
                            yanchor="bottom", y=1.01, x=0,
                            bgcolor="rgba(22,24,31,0)"),
                xaxis=dict(showgrid=False, tickfont=dict(size=8, color="#7E8694")),
                hovermode="x unified",
            )
            fig.update_yaxes(tickfont=dict(size=8, color=color1),
                             gridcolor="#262A33", showgrid=True, secondary_y=False)
            fig.update_yaxes(tickfont=dict(size=8, color=color2),
                             showgrid=False, secondary_y=True)
            return fig

        dc1, dc2 = st.columns(2)
        with dc1:
            h_krw, h_dxy = _dual_hist("USDKRW=X", "DX-Y.NYB")
            fig = _dual_fig(h_krw, h_dxy, "USD/KRW", "DXY", "#D9A441", "#5f7f86")
            if fig:
                st.caption("USD/KRW vs DXY — 달러 강세와 원화 약세 연동")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with dc2:
            h_qqq, h_10y = _dual_hist("QQQ", "^TNX")
            fig = _dual_fig(h_qqq, h_10y, "QQQ", "US 10Y", "#D9A441", "#F25560", ",.2f", ".2f")
            if fig:
                st.caption("QQQ vs US 10Y — 금리와 기술주 역행 관계")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        dc3, dc4 = st.columns(2)
        with dc3:
            h_gld, h_10y2 = _dual_hist("GC=F", "^TNX")
            fig = _dual_fig(h_gld, h_10y2, "Gold", "US 10Y", "#b8924a", "#F25560", ",.2f", ".2f")
            if fig:
                st.caption("Gold vs US 10Y — 실질금리와 금 역행 관계")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with dc4:
            h_gld2, h_dxy2 = _dual_hist("GC=F", "DX-Y.NYB")
            fig = _dual_fig(h_gld2, h_dxy2, "Gold", "DXY", "#b8924a", "#5f7f86", ",.2f", ".2f")
            if fig:
                st.caption("Gold vs DXY — 달러와 금 역행 관계")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 금리·물가·고용(채권/금리)은 별도 섹션 — '외환' 탭(section='fx')에선 숨김
    if section != "fx":
        render_rates(embedded=True)

    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)


# 채권 ETF(있는 것만 표시) — ticker → 한글 라벨
_BOND_ETFS = {
    "TLT": "미국 장기국채", "IEF": "미국 중기국채", "SHY": "미국 단기국채",
    "LQD": "투자등급 회사채", "HYG": "하이일드 회사채",
}

_BND_CSS = """<style>
.bnd-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:0 0 14px}
.bnd-card{background:#16181F;border:1px solid #262A33;border-left:3px solid #3A3F48;border-radius:12px;padding:12px 14px}
.bnd-card.pos{border-left-color:#F25560}.bnd-card.neg{border-left-color:#4D90F0}.bnd-card.flat{border-left-color:#5A5F52}
.bnd-k{font-size:10px;font-weight:850;color:#9AA0AD;margin-bottom:6px}
.bnd-row{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.bnd-tk{font-size:13px;font-weight:950;color:#E7E9EE}
.bnd-px{font-size:13px;font-weight:850;color:#C9CEDA;font-variant-numeric:tabular-nums}
.bnd-pct{font-size:15px;font-weight:950;font-variant-numeric:tabular-nums;margin-top:6px}
.bnd-pct.pos{color:#F25560}.bnd-pct.neg{color:#4D90F0}.bnd-pct.flat{color:#9AA0AD}
</style>"""


@st.cache_data(ttl=900, show_spinner=False)
def _bond_etf_quotes() -> dict:
    """채권 ETF 현재가·1D% — 벤치마크 config에 없어도 직접 조회(5종 모두 표시)."""
    from data.session import cached_download
    tickers = list(_BOND_ETFS.keys())
    out: dict[str, tuple] = {}
    try:
        raw = cached_download(tickers, period="5d", interval="1d", progress=False, auto_adjust=True)
        if raw is None or raw.empty:
            return out
        close = raw["Close"]
        multi = len(tickers) > 1
        for tk in tickers:
            try:
                s = (close[tk] if multi else close).dropna()
                if s.empty:
                    continue
                price = float(s.iloc[-1])
                chg = (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
                       if len(s) >= 2 and s.iloc[-2] else None)
                out[tk] = (price, chg)
            except Exception:
                pass
    except Exception:
        return {}
    return out


def _render_bond_etfs() -> None:
    """채권 ETF 시세 카드(장·중·단기 국채 + 투자등급·하이일드 회사채). 금리와 역행하는 대표 프록시."""
    quotes = _bond_etf_quotes()
    cards = ""
    for tk, label in _BOND_ETFS.items():
        q = quotes.get(tk)
        if not q:
            continue
        price, chg = q
        cls = "pos" if (chg or 0) > 0 else ("neg" if (chg or 0) < 0 else "flat")
        pct = f"{'+' if (chg or 0) >= 0 else ''}{chg:.2f}%" if chg is not None else "—"
        cards += (
            f'<div class="bnd-card {cls}"><div class="bnd-k">{label}</div>'
            f'<div class="bnd-row"><span class="bnd-tk">{tk}</span>'
            f'<span class="bnd-px">${price:,.2f}</span></div>'
            f'<div class="bnd-pct {cls}">{pct}</div></div>'
        )
    if not cards:
        return
    st.markdown(mkt_section_header("채권 (국채·회사채 ETF)", "장·중·단기 국채 + 투자등급·하이일드 — 금리 역행 프록시"),
                unsafe_allow_html=True)
    st.markdown(_BND_CSS + f'<div class="bnd-cards">{cards}</div>', unsafe_allow_html=True)


def render_rates(embedded: bool = False):
    """채권 · 금리 — 채권 ETF + 미국 국채 수익률·물가(YoY)·고용(FRED). 시장 '채권·금리' 탭."""
    if not embedded:
        inject_css()
        mark_active_nav("/market")
        st.markdown(mkt_page_header("📉", "채권 · 금리", "미국 국채 수익률 · 물가 · 고용 (FRED)"),
                    unsafe_allow_html=True)

    live = load_market_data()

    # ── 채권 (국채 ETF) — 금리와 역행하는 대표 채권 프록시 ──
    _render_bond_etfs()

    st.markdown(mkt_section_header("미국 금리 & 매크로", "FRED 최신 발표치"), unsafe_allow_html=True)

    mac = live["macro"]
    if mac is None or mac.empty:
        st.info("FRED API 키를 사이드바에 입력하면 금리·물가·고용 데이터가 표시됩니다.")
        if not embedded:
            st.markdown(jj_footer(), unsafe_allow_html=True)
        return

    groups: dict[str, list] = {}
    for _, r in mac.iterrows():
        key  = r["key"]
        label, unit, group = _MAC_META.get(key, (key, "", "기타"))
        val  = r["value"]
        prev = r.get("prev_value")
        yago = r.get("year_ago_value")
        date = r.get("date", "")

        if isinstance(val, (int, float)):
            if unit == "%":
                val_str = f"{val:.2f}%"
            elif unit == "mom_man":
                # FRED PAYEMS는 '천명' 단위 총량 → 전월 대비 증감(만 명)으로 환산
                if isinstance(prev, (int, float)):
                    chg_man = (val - prev) / 10.0   # (천명 차) ÷ 10 = 만 명
                    val_str = f"{'+' if chg_man >= 0 else ''}{chg_man:,.1f}만 명"
                else:
                    val_str = "—"
            elif unit == "yoy":
                # 물가지수 레벨 → 전년 동월 대비 변동률(YoY %)
                if isinstance(yago, (int, float)) and yago:
                    yoy = (val / yago - 1) * 100
                    val_str = f"{'+' if yoy >= 0 else ''}{yoy:.1f}%"
                else:
                    val_str = "—"
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
            f'letter-spacing:1px;color:#7E8694;margin:14px 0 4px">{group_name}</div>',
            unsafe_allow_html=True,
        )
        _grp_df = pd.DataFrame(group_rows)
        _pct_cols = [c for c in _grp_df.columns if "%" in str(c)]
        # 모바일: 표 가로 클리핑(값·기준일 잘림) 회피 — 지표/값/기준일을 카드로
        if L.is_mobile():
            L.render_table_or_cards(_grp_df, title_col="지표", subtitle_col="기준일", price_col="값")
            continue
        # 3개 표(금리·물가·고용) 컬럼 폭을 동일 고정 → 지표/값/기준일 세로 라인이 정확히 정렬됨.
        _col_cfg = {
            "지표":   st.column_config.TextColumn("지표", width="large"),
            "값":     st.column_config.TextColumn("값", width="small"),
            "기준일": st.column_config.TextColumn("기준일", width="medium"),
        }
        if _pct_cols:
            st.dataframe(_grp_df.style.map(color_change, subset=_pct_cols),
                         use_container_width=True, hide_index=True, column_config=_col_cfg)
        else:
            st.dataframe(_grp_df, use_container_width=True, hide_index=True, column_config=_col_cfg)

    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)


def _db_val_str(fx_db: pd.DataFrame, ticker: str, col: str) -> str:
    if fx_db.empty:
        return "—"
    m = fx_db[fx_db["symbol"] == ticker]
    if m.empty:
        return "—"
    v = m.iloc[0].get(col, "—")
    return str(v) if v else "—"
