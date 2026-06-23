"""
US Stocks — live prices + DB technical indicators, grouped by sector.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

import layout as L  # 모바일 분기(표→카드)

from data.loader import (load_market_data, batch_close_history, series_last_n,
                          compute_live_indicators as _compute_live_ind)
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.analyst_table import render_analyst_table
from ui.components.range_bar import fetch_52w_ranges, range_bar_html
from ui.components.color_utils import hex_to_lab as _hex2lab, delta_e as _de, shade as _shade
from ui.components.dash_style import (
    data_source_note,
    empty_state,
    inject_css, jj_footer, mark_active_nav, numeric, show_skeleton,
    mkt_page_header, mkt_section_header, mkt_stats_chips,
)
from ui.components.scan_layer import scan_layer_html
from ui.components.slim_table import slim_table
from ui.components.cap_treemap import cap_treemap
from ui.components.live_refresh import live_refresh

# 미국 주식 유니버스 — '시장' 탭은 게스트도 보는 제너럴 시장 조망이므로 보유(config us_stocks)가
# 아니라 시총 상위 ~20종을 노출(섹터 분산). 순서 = 시총 랭크. (ticker, 한글명, 섹터)
# 티커는 yfinance 실데이터 확인됨. 현재가·1D%·기간수익률은 6개월 종가에서 산출(보유 무관).
# 시총 상위 20종(브로드 마켓 뷰) — 보유 종목 아님.
_US_UNIVERSE = [
    ("NVDA", "엔비디아", "반도체"),       ("AAPL", "애플", "빅테크"),
    ("MSFT", "마이크로소프트", "빅테크"),  ("AMZN", "아마존", "빅테크"),
    ("GOOGL", "알파벳", "빅테크"),         ("META", "메타", "빅테크"),
    ("AVGO", "브로드컴", "반도체"),        ("TSLA", "테슬라", "자동차"),
    ("BRK-B", "버크셔해서웨이", "금융"),   ("LLY", "일라이릴리", "헬스케어"),
    ("JPM", "JP모건", "금융"),             ("V", "비자", "금융"),
    ("WMT", "월마트", "소비재"),           ("XOM", "엑슨모빌", "에너지"),
    ("MA", "마스터카드", "금융"),          ("ORCL", "오라클", "빅테크"),
    ("UNH", "유나이티드헬스", "헬스케어"), ("COST", "코스트코", "소비재"),
    ("HD", "홈디포", "소비재"),            ("PG", "P&G", "소비재"),
]
# 신규 상장(데이터 누적 전) — 시총 랭킹 표와 분리해 별도 노출.
_US_NEW_LISTINGS = [
    ("SPCX", "스페이스X", "우주항공"),
]
_STOCK_KOR = {tk: nm for tk, nm, _sec in _US_UNIVERSE}
_SECTOR_ORDER = ["빅테크", "반도체", "금융", "헬스케어", "소비재", "에너지", "자동차"]
_SECTOR_KOR = {s: s for s in _SECTOR_ORDER}  # 유니버스 섹터는 이미 한글
_BENCH_KOR = {
    "QQQ":  ("나스닥 100",    "equity_us"),
    "SPY":  ("S&P 500",      "equity_us"),
    "SOXX": ("반도체 (SOXX)", "equity_semiconductor"),
    "SMH":  ("반도체 (SMH)",  "equity_semiconductor"),
    "GLD":  ("골드 ETF",      "commodities"),
    "SLV":  ("실버 ETF",      "commodities"),
    "TLT":  ("장기채 ETF",    "bonds"),
}  # ① KWEB(중국인터넷 ETF) 제거 — 미국 지수·섹터 ETF 그룹에 부적합(중국 ETF)
# ── 종목별 고유 시그니처 색 ─────────────────────────────────────────────────
# 기업 CI(브랜드색) 기반 — NVDA=그린, AMZN/HD=오렌지, MSFT/GOOGL/META=블루, TSLA/AVGO=레드 등.
# 블루·레드가 겹치므로 시총 랭크 순으로 배정하며 같은/근접색은 ΔE 기준 명도 단계 조정해 구별
# (큰 종목이 정통 브랜드색 유지). 게이지·스캔·비교차트·개별차트에 공통 적용.
_US_BRAND = {
    "NVDA": "#76B900", "AAPL": "#A2AAAD", "MSFT": "#00A4EF", "AMZN": "#FF9900",
    "GOOGL": "#4285F4", "META": "#0866FF", "AVGO": "#CC092F", "TSLA": "#E82127",
    "BRK-B": "#2C5282", "LLY": "#D52B1E", "JPM": "#117ACA", "V": "#1A1F71",
    "WMT": "#0071CE", "XOM": "#CE1126", "MA": "#F79E1B", "ORCL": "#C74634",
    "UNH": "#002677", "COST": "#005DAA", "HD": "#F96302", "PG": "#004B8D",
}
# 벤치마크 게이지색 — ETF 탭 테마색과 동일(대형=블루, 나스닥=바이올렛, 반도체=청록/짙은청록)
_US_BENCH_COLOR = {"SPY": "#3D7BE0", "QQQ": "#8A5CD6", "SOXX": "#17B0C0", "SMH": "#0D6973"}

# 비교차트 폴백(브랜드 미지정 종목): 무채색 계열
_LINE_COLORS = [
    "#D9A441", "#E7E9EE", "#B6BCC8", "#9AA0AD", "#7E8794",
    "#C9A24E", "#A6ACB8", "#6E7480", "#565C68", "#C2C7D0",
]


# 색 유틸(_hex2lab/_de/_shade)은 ui.components.color_utils 공용 모듈 사용(상단 import)


_NUDGES = [0.6, 1.5, 0.42, 1.8, 0.32, 1.95, 0.75, 1.25, 0.5, 1.65]


def _build_us_sig(order: list[str], thresh: float = 16.0) -> dict:
    """시총 랭크 순으로 브랜드색 배정 — 이미 놓인 색과 ΔE<thresh면 명도 단계 조정해 구별."""
    placed, out = [], {}
    for tk in order:
        base = _US_BRAND.get(tk, "#9AA0AD")
        c = base
        for a in range(len(_NUDGES) + 1):
            lab = _hex2lab(c)
            if all(_de(lab, p) >= thresh for p in placed):
                break
            c = _shade(base, _NUDGES[min(a, len(_NUDGES) - 1)])
        placed.append(_hex2lab(c))
        out[tk] = c
    return out


_US_SIG = _build_us_sig([u[0] for u in _US_UNIVERSE])


@st.cache_data(ttl=86400, show_spinner=False)   # 목표가는 일 단위 안정 → 24h
def _analyst_targets() -> pd.DataFrame:
    from src.analyst_naver import fetch_naver_targets   # 네이버 단일 소스(기준일 포함)
    return fetch_naver_targets(list(_STOCK_KOR.keys()))


def _us_history(tickers_key: str, _bucket: int = 0) -> dict:
    """6개월 종가 배치 — 공용 batch_close_history 위임(단일 캐시)."""
    return batch_close_history(tickers_key, "6mo", _bucket)

# _compute_live_ind 는 data.loader.compute_live_indicators 별칭(상단 import)


def render(embedded: bool = False):
    if not embedded:
        inject_css()
        mark_active_nav("/us-stocks")
        st.markdown(mkt_page_header("🇺🇸", "미국주식", "시총 상위 20종 · 시총·변동성·애널리스트 한눈에"), unsafe_allow_html=True)

    bucket = live_refresh(["US"]) if not embedded else 0
    ph = show_skeleton()
    live = load_market_data()
    _us_history(",".join(sorted(u[0] for u in _US_UNIVERSE + _US_NEW_LISTINGS)), _bucket=bucket)  # 유니버스+신규상장 6개월 예열
    load_latest_indicator_summary(DEFAULT_DB)
    ph.empty()

    # ── Stats chips ───────────────────────────────────────────────────────────
    bm = live["benchmarks"]
    def _bc(df, tk):
        r = df[df["ticker"] == tk]
        if r.empty: return None, None
        p = r.iloc[0].get("price"); c = r.iloc[0].get("change_pct")
        return (float(p) if isinstance(p, (int,float)) else None,
                float(c) if isinstance(c, (int,float)) else None)

    chips = []
    for lbl, tk, fmt in [("나스닥100","QQQ","${:,.0f}"),("S&P500","SPY","${:,.0f}"),("반도체(SOXX)","SOXX","${:,.0f}")]:
        p, c = _bc(bm, tk)
        if c is not None:
            sign = "+" if c >= 0 else ""
            chips.append({"label": lbl, "value": f"{sign}{c:.2f}%", "cls": "pos" if c>0 else ("neg" if c<0 else "neu")})
    if chips:
        st.markdown(mkt_stats_chips(chips), unsafe_allow_html=True)

    # ── 시총 상위 유니버스(20종)에서 stocks_live 구성 — 보유(config) 아님 ──────────
    all_us_tickers = [u[0] for u in _US_UNIVERSE + _US_NEW_LISTINGS]
    history = _us_history(",".join(sorted(all_us_tickers)), _bucket=bucket)

    def _u_price(s):
        return float(s.iloc[-1]) if s is not None and not s.empty else None

    def _u_chg(s):  # 1D% = 최신/전일 - 1
        return (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
                if s is not None and len(s) >= 2 and s.iloc[-2] else None)

    stocks_live = pd.DataFrame([
        {"ticker": tk, "name": nm, "sector": sec, "mktcap_rank": rank,
         "price": _u_price(history.get(tk)), "change_pct": _u_chg(history.get(tk))}
        for rank, (tk, nm, sec) in enumerate(_US_UNIVERSE, 1)
    ])
    top10 = stocks_live.copy()
    top10_tickers = top10["ticker"].tolist()

    # ── DB 지표 우선, 없으면 live 계산 ───────────────────────────────────────
    db_df    = load_latest_indicator_summary(DEFAULT_DB)
    stock_db = db_df[db_df["asset_type"] == "us_stock"].copy() if not db_df.empty else pd.DataFrame()
    bench_db = db_df[db_df["asset_type"] == "benchmark"].copy() if not db_df.empty else pd.DataFrame()
    use_db   = not stock_db.empty

    _DB_TREND = {"bullish": "상승", "bearish": "하락", "neutral": "중립"}

    def _ind(ticker: str, db_sub: pd.DataFrame) -> dict:
        if not db_sub.empty:
            m = db_sub[db_sub["symbol"] == ticker]
            if not m.empty:
                row = m.iloc[0]
                def _fv(v): return float(v) if isinstance(v, (int, float)) else None
                return {
                    "1W %":      _fv(row.get("return_1w_pct")),
                    "1M %":      _fv(row.get("return_1m_pct")),
                    "3M %":      _fv(row.get("return_3m_pct")),
                    "MA20 이격%": _fv(row.get("distance_ma20_pct")),
                    "추세":       _DB_TREND.get(str(row.get("trend_status", "")), "—"),
                }
        closes = history.get(ticker)
        if closes is not None and not closes.empty:
            return _compute_live_ind(closes)
        return {"1W %": None, "1M %": None, "3M %": None, "MA20 이격%": None, "추세": "—"}

    pct_cols = ["1D %", "1W %", "1M %", "3M %", "MA20 이격%"]

    def _cell(v):
        if not isinstance(v, (int, float)) or pd.isna(v) or v == 0: return ""
        mag = min((abs(v) / 8.0) ** 0.7, 1.0)   # 값 크기에 비례한 농도 (R7)
        a = 0.05 + mag * 0.30
        if v > 0:  return f"background-color:rgba(242,85,96,{a:.3f});color:#F25560;font-weight:600"
        return f"background-color:rgba(77,144,240,{a:.3f});color:#4D90F0;font-weight:600"

    def _trend_style(v):
        if v == "상승": return "color:#F25560;font-weight:700"
        if v == "하락": return "color:#4D90F0;font-weight:700"
        return "color:#7E8694"

    def _show_table(rows: list[dict], price_col: str = "현재가 (USD)",
                    sort_movement: bool = False, highlight: bool = False):
        tbl = pd.DataFrame(rows)
        drop = [c for c in ["_ticker", "_name"] if c in tbl.columns]
        tbl = tbl.drop(columns=drop)
        tbl = numeric(tbl, pct_cols + [price_col])
        if sort_movement and "1D %" in tbl.columns:
            tbl = tbl.reindex(tbl["1D %"].abs().sort_values(ascending=False, na_position="last").index)
        # 모바일: 종목당 카드 (데스크탑은 아래 styled 표 유지)
        if L.is_mobile():
            disp = tbl.copy()
            for c in [x for x in pct_cols if x in disp.columns]:
                disp[c] = disp[c].map(lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) and pd.notna(v) else "—")
            if price_col in disp.columns:
                disp[price_col] = disp[price_col].map(lambda v: f"${v:,.2f}" if isinstance(v, (int, float)) and pd.notna(v) else "—")
            L.render_table_or_cards(
                disp, title_col="종목",
                price_col=price_col if price_col in disp.columns else None,
                change_cols=[c for c in ("1D %", "3M %") if c in disp.columns],
                detail_cols=[c for c in ("1W %", "1M %", "MA20 이격%", "추세") if c in disp.columns],
            )
            return
        styled = tbl.style.map(_cell, subset=[c for c in pct_cols if c in tbl.columns])
        if "추세" in tbl.columns:
            styled = styled.map(_trend_style, subset=["추세"])
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
        if price_col in tbl.columns:
            fmt[price_col] = "${:,.2f}"
        styled = styled.format(fmt, na_rep="—")
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── 0. 30초 스캔 레이어 (표 위) — 리더/러거드/과열 + breadth ─────────────────
    def _series_3m(tk: str) -> list[float]:
        return series_last_n(history.get(tk))

    scan_items = []
    for _, r in stocks_live.iterrows():
        tk = r["ticker"]
        ind = _ind(tk, stock_db)
        scan_items.append({
            "name": _STOCK_KOR.get(tk, tk),
            "d1": r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
            "ma20": ind["MA20 이격%"],
            "series": _series_3m(tk),
            "color": _US_SIG.get(tk),  # 종목별 고유 시그니처색(겹침은 ΔE로 구별 조정)
        })
    _scan = scan_layer_html(scan_items)
    if _scan:
        st.markdown(_scan, unsafe_allow_html=True)

    # ── 1. 벤치마크 ──────────────────────────────────────────────────────────
    # '미국주식' 탭 벤치마크는 미국 지수·반도체만(QQQ·SPY·SOXX·SMH).
    # 금·은(원자재)·장기채(채권)·중국인터넷(KWEB)은 자산군이 달라 각 탭으로 분리 — 여기선 제외.
    # 게이지바(52주 범위·지수색) + 표로 보기 토글 — 원자재·외환과 동일 구성
    st.markdown(mkt_section_header("주요 벤치마크", "미국 지수·반도체 ETF · 52주 범위 내 현재 위치"),
                unsafe_allow_html=True)
    _US_BENCH = {tk for tk, (_nm, _cls) in _BENCH_KOR.items() if _cls in ("equity_us", "equity_semiconductor")}
    _bench_ranges = fetch_52w_ranges(",".join(sorted(_US_BENCH)))  # 52주 범위 1회 배치 다운로드
    bench_live = live["benchmarks"].copy()
    bench_rows, _rb_items = [], []
    for _, r in bench_live.iterrows():
        tk  = r["ticker"]
        if tk not in _US_BENCH:
            continue
        ind = _ind(tk, bench_db)
        bench_rows.append({
            "이름":        _BENCH_KOR.get(tk, (tk,))[0],
            "현재가 (USD)": r["price"]      if isinstance(r["price"],      (int, float)) else None,
            "1D %":        r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
            "1W %":        ind["1W %"],
            "1M %":        ind["1M %"],
            "3M %":        ind["3M %"],
            "MA20 이격%":  ind["MA20 이격%"],
            "추세":         ind["추세"],
            "_ticker":     tk,
        })
        rng = _bench_ranges.get(tk)
        if rng:
            lo, hi, cur = rng
            _rb_items.append({"name": _BENCH_KOR.get(tk, (tk,))[0], "unit": tk,
                              "low": lo, "high": hi, "current": cur,
                              "d1": r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
                              "color": _US_BENCH_COLOR.get(tk)})
    if _rb_items:
        st.markdown(range_bar_html(_rb_items, fmt="${:,.2f}"), unsafe_allow_html=True)
        st.caption("막대 = 52주 최저~최고 · 점 = 현재가(지수색) · 우측 라벨 = 범위 내 위치")
    else:
        empty_state("벤치마크 범위 데이터 준비 중")
    if st.toggle("표로 보기", key="us_bench_tbl", value=False):
        slim_table(bench_rows, key="us_bench", name_key="이름",
                   price_key="현재가 (USD)", price_fmt="${:,.2f}")

    # 시장 탭(슬림): 시총 TOP10·수익률 비교 숨김.
    if not embedded:
        # ── 2. 시가총액 TOP 10 ────────────────────────────────────────────────────
        st.markdown(mkt_section_header("시가총액 상위 종목", "섹터별 · 시총 순위 기준"), unsafe_allow_html=True)

        top10_rows = []
        for _, r in stocks_live.iterrows():
            rank = r.get("mktcap_rank")
            if not isinstance(rank, (int, float)):
                continue
            tk  = r["ticker"]
            ind = _ind(tk, stock_db)
            top10_rows.append({
                "순위":        int(rank),
                "종목":        f"{_STOCK_KOR.get(tk, tk)}  ({tk})",
                "섹터":        _SECTOR_KOR.get(r.get("sector", ""), r.get("sector", "—")),
                "현재가 (USD)": r["price"]      if isinstance(r["price"],      (int, float)) else None,
                "1D %":        r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
                "1W %":        ind["1W %"],
                "1M %":        ind["1M %"],
                "3M %":        ind["3M %"],
                "MA20 이격%":  ind["MA20 이격%"],
                "추세":         ind["추세"],
                "_ticker":     tk,
                "_name":       _STOCK_KOR.get(tk, tk),
            })

        top10_rows.sort(key=lambda x: x["순위"])

        for sector_key in _SECTOR_ORDER + [""]:
            sector_kor = _SECTOR_KOR.get(sector_key, "기타")
            grp = [r for r in top10_rows if r["섹터"] == sector_kor]
            if not grp:
                continue
            st.markdown(
                f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:#7E8694;margin:14px 0 4px">{sector_kor}</div>',
                unsafe_allow_html=True,
            )
            _show_table(grp)

        st.caption(data_source_note("로컬 DB" if use_db else "Yahoo Finance(6개월 계산)",
                                    updated=str(db_df["run_date"].max()) if use_db else "",
                                    extra="기술지표 1W/1M/3M·추세"))

        # ── 2-1. 신규 상장 (데이터 누적 전 · 시총 랭킹과 분리) ─────────────────────
        new_rows = []
        for tk, nm, sec in _US_NEW_LISTINGS:
            s = history.get(tk)
            if s is None or s.empty:
                continue
            price = float(s.iloc[-1])
            chg   = (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
                     if len(s) >= 2 and s.iloc[-2] else None)
            since = (round((float(s.iloc[-1]) / float(s.iloc[0]) - 1) * 100, 2)
                     if len(s) >= 2 and s.iloc[0] else None)
            new_rows.append({
                "종목":         f"{nm}  ({tk})",
                "섹터":         sec,
                "현재가 (USD)": price,
                "1D %":         chg,
                "상장 후 %":    since,
                "데이터":       f"{len(s)}일",
            })
        if new_rows:
            st.markdown(mkt_section_header("신규 상장", "데이터 누적 전 · 시총 랭킹 미반영"), unsafe_allow_html=True)
            nt = pd.DataFrame(new_rows)
            _npct = [c for c in ["1D %", "상장 후 %"] if c in nt.columns]
            nstyled = nt.style.map(_cell, subset=_npct).format(
                {"현재가 (USD)": "${:,.2f}", "1D %": "{:+.2f}%", "상장 후 %": "{:+.2f}%"}, na_rep="—")
            st.dataframe(nstyled, use_container_width=True, hide_index=True)
            st.caption("상장 초기로 1W/1M/3M·추세 등 누적 지표는 데이터가 쌓인 뒤 제공됩니다.")

        # ── 3. 전 종목 수익률 비교 차트 (정규화) ─────────────────────────────────
        st.markdown(mkt_section_header("주요 종목 수익률 비교", "3개월 · 기준일=100 정규화"), unsafe_allow_html=True)

        if history and top10_rows:
            fig_cmp = go.Figure()
            for i, row in enumerate(top10_rows):
                tk     = row["_ticker"]
                closes = history.get(tk)
                if closes is None or closes.empty:
                    continue
                cutoff = closes.index[-1] - pd.DateOffset(months=3)
                s = closes[closes.index >= cutoff].dropna()
                if len(s) < 2:
                    continue
                normed = s / float(s.iloc[0]) * 100
                pct_3m = float(normed.iloc[-1]) - 100
                sign   = "+" if pct_3m >= 0 else ""
                fig_cmp.add_trace(go.Scatter(
                    x=normed.index, y=normed.values,
                    mode="lines",
                    name=f"{row['_name']} ({sign}{pct_3m:.1f}%)",
                    line=dict(color=_US_SIG.get(tk, _LINE_COLORS[i % len(_LINE_COLORS)]), width=1.5),
                    hovertemplate="<b>" + row["_name"] + "</b><br>%{x|%Y-%m-%d}<br>%{y:.1f}<extra></extra>",
                ))

            fig_cmp.add_hline(y=100, line_width=1, line_dash="dot", line_color="#262A33")
            fig_cmp.update_layout(
                margin=dict(l=0, r=0, t=8, b=0), height=340,
                paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
                xaxis=dict(showgrid=False, showline=True, linecolor="#262A33",
                           tickfont=dict(size=9, color="#7E8694")),
                yaxis=dict(showgrid=True, gridcolor="#262A33",
                           tickfont=dict(size=9, color="#7E8694"), side="right"),
                legend=dict(font=dict(size=9), orientation="v",
                            x=1.02, y=1, xanchor="left",
                            bgcolor="rgba(22,24,31,0.85)", bordercolor="#262A33", borderwidth=1),
                hovermode="x unified",
            )
            st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

    # ── 4. 전체 종목 테이블 ──────────────────────────────────────────────────
    if embedded:
        # 시장 탭: 시총 히트맵 트리맵(분위기) + 표로 보기 토글 → 슬림표(정밀 비교 보존)
        st.markdown(mkt_section_header("전체 종목", "시총 히트맵 · 색=1D% 등락"), unsafe_allow_html=True)
        rows = []
        for _, r in stocks_live.iterrows():
            tk  = r["ticker"]
            ind = _ind(tk, stock_db)
            rows.append({
                "종목":        f"{_STOCK_KOR.get(tk, tk)}  ({tk})",
                "섹터":        _SECTOR_KOR.get(r.get("sector", ""), "기타"),
                "순위":        r.get("mktcap_rank"),
                "현재가 (USD)": r["price"]      if isinstance(r["price"],      (int, float)) else None,
                "1D %":        r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
                "1W %":        ind["1W %"],
                "1M %":        ind["1M %"],
                "3M %":        ind["3M %"],
                "MA20 이격%":  ind["MA20 이격%"],
                "추세":         ind["추세"],
                "_ticker":     tk,
            })
        # 데스크탑: 시총 히트맵 / 모바일: 글자가 안 읽혀 상승·하락 상위 리스트로 대체
        _mv = pd.DataFrame(rows)
        if "1D %" in _mv.columns:
            _mv["1D %"] = _mv["1D %"].map(lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) and pd.notna(v) else "—")
        L.only_desktop(lambda: cap_treemap(rows, key="us_all", name_key="종목", sector_key="섹터", rank_key="순위"))
        L.only_mobile(lambda: L.top_movers_list(_mv, name_col="종목", change_col="1D %"))
        if st.toggle("표로 보기", key="us_all_tbl", value=False):
            rows.sort(key=lambda x: x["순위"] if isinstance(x["순위"], (int, float)) else 999)  # 시총 순위 정렬
            slim_table(rows, key="us_all", name_key="종목",
                       price_key="현재가 (USD)", price_fmt="${:,.2f}")
    else:
        st.markdown(mkt_section_header("전체 종목", "섹터별"), unsafe_allow_html=True)
        for sector_key in _SECTOR_ORDER + [""]:
            sector_rows_live = stocks_live[stocks_live["sector"] == sector_key]
            if sector_rows_live.empty:
                continue
            sector_kor = _SECTOR_KOR.get(sector_key, "기타")
            st.markdown(
                f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:#7E8694;margin:14px 0 4px">{sector_kor}</div>',
                unsafe_allow_html=True,
            )
            rows = []
            for _, r in sector_rows_live.iterrows():
                tk  = r["ticker"]
                ind = _ind(tk, stock_db)
                rows.append({
                    "종목":        f"{_STOCK_KOR.get(tk, tk)}  ({tk})",
                    "현재가 (USD)": r["price"]      if isinstance(r["price"],      (int, float)) else None,
                    "1D %":        r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
                    "1W %":        ind["1W %"],
                    "1M %":        ind["1M %"],
                    "3M %":        ind["3M %"],
                    "MA20 이격%":  ind["MA20 이격%"],
                    "추세":         ind["추세"],
                    "_ticker":     tk,
                })
            _show_table(rows)

    # 시장 탭(슬림): 개별 차트·버블 숨김.
    if not embedded:
        # ── 5. 개별 가격 추이 차트 ───────────────────────────────────────────────
        st.markdown(mkt_section_header("개별 종목 가격 추이", "3개월 일별 종가"), unsafe_allow_html=True)

        chart_opts: dict[str, str] = {}
        for _, r in live["benchmarks"].iterrows():
            if r["ticker"] not in _US_BENCH:
                continue
            label = _BENCH_KOR.get(r["ticker"], (r["ticker"],))[0]
            chart_opts[f"{label}  ({r['ticker']})"] = r["ticker"]
        for _, r in stocks_live.iterrows():
            kor = _STOCK_KOR.get(r["ticker"], r["ticker"])
            chart_opts[f"{kor}  ({r['ticker']})"] = r["ticker"]

        col_sel, _ = st.columns([3, 7])
        with col_sel:
            sel = st.selectbox("종목", list(chart_opts.keys()), label_visibility="collapsed",
                               key="stock_chart_sel")

        sel_tk = chart_opts[sel]
        closes = history.get(sel_tk)
        if closes is not None and not closes.empty:
            cutoff = closes.index[-1] - pd.DateOffset(months=3)
            s = closes[closes.index >= cutoff].dropna()
            if not s.empty:
                pct   = (float(s.iloc[-1]) / float(s.iloc[0]) - 1) * 100
                color = "#F25560" if pct >= 0 else "#4D90F0"   # 손익색(제목 % 텍스트)
                sign  = "+" if pct >= 0 else ""
                _sig = _US_SIG.get(sel_tk) or _US_BENCH_COLOR.get(sel_tk) or "#D9A441"  # 종목·지수 시그니처색
                _sh = _sig.lstrip("#")
                _fillc = f"rgba({int(_sh[0:2],16)},{int(_sh[2:4],16)},{int(_sh[4:6],16)},0.06)"
                fig = go.Figure(go.Scatter(
                    x=s.index, y=s.values, mode="lines",
                    line=dict(color=_sig, width=1.5),
                    fill="tozeroy", fillcolor=_fillc,
                ))
                fig.update_layout(
                    title=dict(
                        text=f"{sel}  <span style='font-size:11px;color:{color}'>{sign}{pct:.2f}% (3M)</span>",
                        font=dict(size=12, color=_sig), x=0, xanchor="left",
                    ),
                    margin=dict(l=0, r=0, t=36, b=0), height=220,
                    paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
                    xaxis=dict(showgrid=False, showline=True, linecolor="#262A33",
                               tickfont=dict(size=9, color="#7E8694")),
                    yaxis=dict(showgrid=True, gridcolor="#262A33", tickformat="$,.2f",
                               tickfont=dict(size=9, color="#7E8694"), side="right"),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            empty_state("차트 데이터 준비 중")

        # ── 6. 리스크/수익 버블 차트 ─────────────────────────────────────────────
        if use_db:
            st.markdown(mkt_section_header("리스크/수익 버블 차트",
                                       "1M 수익률 vs 20D 변동성 — 버블 크기: 3M 수익률 절대값"),
                        unsafe_allow_html=True)

            _SECTOR_COLOR = {
                "semiconductor": "#E07B39",
                "big_tech":      "#5f7f86",
                "finance":       "#805AD5",
                "ev_auto":       "#D48C24",
            }
            bubble_rows = []
            for _, r in stocks_live.iterrows():
                tk    = r["ticker"]
                m     = stock_db[stock_db["symbol"] == tk]
                if m.empty:
                    continue
                row   = m.iloc[0]
                ret1m = row.get("return_1m_pct")
                vol   = row.get("volatility_20d_pct")
                ret3m = row.get("return_3m_pct")
                if not isinstance(ret1m, (int, float)) or not isinstance(vol, (int, float)):
                    continue
                bubble_rows.append({
                    "ticker": tk,
                    "name":   _STOCK_KOR.get(tk, tk),
                    "sector": r.get("sector", ""),
                    "ret1m":  float(ret1m),
                    "vol":    float(vol),
                    "size":   max(abs(float(ret3m)) if isinstance(ret3m, (int, float)) else 2, 2),
                })

            if bubble_rows:
                bdf = pd.DataFrame(bubble_rows)
                fig_b = go.Figure()
                for sect, grp in bdf.groupby("sector"):
                    fig_b.add_trace(go.Scatter(
                        x=grp["ret1m"], y=grp["vol"],
                        mode="markers+text",
                        name=_SECTOR_KOR.get(sect, sect),
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
                fig_b.add_vline(x=0, line_width=1, line_dash="dot", line_color="#262A33")
                fig_b.update_layout(
                    margin=dict(l=0, r=0, t=8, b=0), height=300,
                    paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
                    xaxis=dict(title=dict(text="1M 수익률 (%)", font=dict(size=9)),
                               showgrid=True, gridcolor="#262A33", zeroline=False,
                               ticksuffix="%", tickfont=dict(size=9, color="#7E8694")),
                    yaxis=dict(title=dict(text="20D 변동성 (연환산 %)", font=dict(size=9)),
                               showgrid=True, gridcolor="#262A33",
                               ticksuffix="%", tickfont=dict(size=9, color="#7E8694")),
                    legend=dict(font=dict(size=9), orientation="h",
                                yanchor="bottom", y=1.01, x=0),
                    hovermode="closest",
                )
                st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar": False})
                st.caption("우하단: 고수익·저변동성 (우호적) / 좌상단: 저수익·고변동성 (주의)")

    # ── 7. 애널리스트 전망 (네이버 컨센서스 · 지연 로딩) ──
    st.markdown(mkt_section_header("애널리스트 전망", "네이버 금융 컨센서스 목표가"), unsafe_allow_html=True)

    if not st.session_state.get("show_analyst_us"):
        if st.button("애널리스트 전망 불러오기", key="load_analyst_us", use_container_width=True):
            st.session_state["show_analyst_us"] = True
            st.rerun()
        st.caption("네이버 금융 컨센서스 · 불러오면 잠시 소요")
    else:
        _price_of = {tk: (float(s.iloc[-1]) if s is not None and not getattr(s, "empty", True) else None)
                     for tk, s in history.items()}
        render_analyst_table(_analyst_targets(), _STOCK_KOR, _price_of, price_fmt="${:,.2f}")
    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)
