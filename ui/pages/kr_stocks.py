"""
Korean Stocks — 코스피 시총 TOP 20 (시장 조망).
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

import layout as L  # 모바일 분기(표→카드)

from data.loader import load_market_data
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.dash_style import (
    data_source_note,
    empty_state,
    inject_css, jj_footer, mark_active_nav, numeric, show_skeleton,
    mkt_page_header, mkt_section_header, mkt_stats_chips,
)
from ui.components.scan_layer import scan_layer_html
from ui.components.slim_table import slim_table
from ui.components.range_bar import fetch_52w_range, range_bar_html
from ui.components.cap_treemap import cap_treemap
from ui.components.analyst_scatter import analyst_scatter_fig
from ui.components.live_refresh import live_refresh

_SECTOR_ORDER = ["반도체", "전자", "이차전지", "바이오", "자동차", "인터넷",
                 "금융", "화학", "철강/소재", "유틸리티", "지주/건설"]

# 한국 주식 유니버스 — '시장' 탭은 게스트도 보는 제너럴 시장 조망이므로 보유(config kr_stocks)가
# 아니라 코스피 시총 상위 ~20종을 노출(섹터 분산). 순서 = 시총 랭크. (ticker, 한글명, 섹터)
# 티커 yfinance 실검증. 현재가·1D%·기간수익률은 6개월 종가에서 산출(보유 무관).
_KR_UNIVERSE = [
    ("005930.KS", "삼성전자", "반도체"),         ("000660.KS", "SK하이닉스", "반도체"),
    ("373220.KS", "LG에너지솔루션", "이차전지"),  ("207940.KS", "삼성바이오로직스", "바이오"),
    ("005380.KS", "현대차", "자동차"),           ("000270.KS", "기아", "자동차"),
    ("068270.KS", "셀트리온", "바이오"),          ("105560.KS", "KB금융", "금융"),
    ("005490.KS", "POSCO홀딩스", "철강/소재"),    ("035420.KS", "NAVER", "인터넷"),
    ("012330.KS", "현대모비스", "자동차"),        ("055550.KS", "신한지주", "금융"),
    ("028260.KS", "삼성물산", "지주/건설"),       ("066570.KS", "LG전자", "전자"),
    ("051910.KS", "LG화학", "화학"),              ("015760.KS", "한국전력", "유틸리티"),
    ("032830.KS", "삼성생명", "금융"),            ("086790.KS", "하나금융지주", "금융"),
    ("035720.KS", "카카오", "인터넷"),            ("009150.KS", "삼성전기", "전자"),
]

# 신규 상장(데이터 누적 전) — 시총 랭킹 표와 분리해 별도 노출. (ticker, 한글명, 섹터)
# 현재 코스피 시총 상위 20종은 전부 기존 상장이라 비어 있음. 신규 IPO 발생 시 여기에 추가.
_KR_NEW_LISTINGS: list[tuple[str, str, str]] = [
]

_KOSPI_BENCH = {
    "^KS11": "KOSPI 지수",
    "^KQ11": "KOSDAQ 지수",
}

# ── 종목별 고유 시그니처 색 ─────────────────────────────────────────────────
# 기업 CI(브랜드색) 기반 — 삼성=블루, SK/LG=레드, NAVER=그린, 카카오=옐로, 현대=네이비 등.
# 한국 대형주는 블루 계열이 많아 겹치므로, 시총 랭크 순으로 배정하며 같은/근접색은 ΔE 기준으로
# 명도를 단계 조정해 구별(큰 종목이 정통 브랜드색을 유지). 게이지·스캔·비교차트에 공통 적용.
_KR_BRAND = {
    "005930.KS": "#1428A0", "000660.KS": "#EA002C", "373220.KS": "#A50034",
    "207940.KS": "#1428A0", "005380.KS": "#002C5F", "000270.KS": "#6E7B8C",
    "068270.KS": "#1A75CF", "105560.KS": "#FFB81C", "005490.KS": "#00A3E0",
    "035420.KS": "#03C75A", "012330.KS": "#002C5F", "055550.KS": "#0046FF",
    "028260.KS": "#1428A0", "066570.KS": "#A50034", "051910.KS": "#A50034",
    "015760.KS": "#0067AC", "032830.KS": "#1428A0", "086790.KS": "#008485",
    "035720.KS": "#F7C600", "009150.KS": "#1428A0",
}
_KR_BENCH_COLOR = {"^KS11": "#4D8DE8", "^KQ11": "#D9A441"}  # 지수 게이지용(종목과 무관)

# 비교차트 폴백(브랜드 미지정 종목): 무채색 계열
_LINE_COLORS = [
    "#D9A441", "#E7E9EE", "#B6BCC8", "#9AA0AD", "#7E8794",
    "#C9A24E", "#A6ACB8", "#6E7480", "#565C68", "#C2C7D0",
]


def _hex2lab(h: str):
    h = h.lstrip("#"); r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    def f(c): return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = f(r), f(g), f(b)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805; y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    x /= 0.95047; z /= 1.08883
    def g2(t): return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = g2(x), g2(y), g2(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _de(a, b):  # CIE76 색차
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def _shade(h: str, fct: float) -> str:
    h = h.lstrip("#"); r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if fct >= 1:
        r, g, b = (int(c + (255 - c) * (fct - 1)) for c in (r, g, b))
    else:
        r, g, b = (int(c * fct) for c in (r, g, b))
    return "#" + "".join(f"{max(0, min(255, c)):02X}" for c in (r, g, b))


_NUDGES = [0.6, 1.5, 0.42, 1.8, 0.32, 1.95, 0.75, 1.25, 0.5, 1.65]


def _build_kr_sig(order: list[str], thresh: float = 16.0) -> dict:
    """시총 랭크 순으로 브랜드색 배정 — 이미 놓인 색과 ΔE<thresh면 명도 단계 조정해 구별."""
    placed, out = [], {}
    for tk in order:
        base = _KR_BRAND.get(tk, "#9AA0AD")
        c = base
        for a in range(len(_NUDGES) + 1):
            lab = _hex2lab(c)
            if all(_de(lab, p) >= thresh for p in placed):
                break
            c = _shade(base, _NUDGES[min(a, len(_NUDGES) - 1)])
        placed.append(_hex2lab(c))
        out[tk] = c
    return out


_KR_SIG = _build_kr_sig([u[0] for u in _KR_UNIVERSE])


@st.cache_data(ttl=900, show_spinner=False)
def _kr_history(tickers_key: str, _bucket: int = 0) -> dict:
    """Batch 6-month daily close history for all KR stocks. _bucket=장중 캐시 버스팅 키."""
    tickers = tickers_key.split(",")
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period="6mo", interval="1d", progress=False, auto_adjust=True)
        if raw.empty:
            return {}
        result = {}
        multi = len(tickers) > 1
        for tk in tickers:
            try:
                closes = raw["Close"][tk].dropna() if multi else raw["Close"].dropna()
                if not closes.empty:
                    result[tk] = closes
            except Exception:
                pass
        return result
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def _bench_prices() -> dict:
    tickers = list(_KOSPI_BENCH.keys())
    try:
        from data.session import cached_download
        raw = cached_download(tickers, period="5d", interval="1d", progress=False, auto_adjust=True, ttl=300)
        if raw.empty:
            return {}
        results = {}
        for tk in tickers:
            try:
                closes = raw["Close"][tk].dropna() if len(tickers) > 1 else raw["Close"].dropna()
                if closes.empty:
                    continue
                price = float(closes.iloc[-1])
                prev  = float(closes.iloc[-2]) if len(closes) >= 2 else None
                results[tk] = {
                    "price":      round(price, 2),
                    "change_pct": round((price - prev) / prev * 100, 2) if prev else None,
                }
            except Exception:
                pass
        return results
    except Exception:
        return {}


def _compute_live_ind(closes: pd.Series) -> dict:
    """Compute 1W/1M/3M/MA20/trend directly from close prices."""
    def _ret(n):
        if len(closes) < n + 1:
            return None
        past = float(closes.iloc[-(n + 1)])
        now  = float(closes.iloc[-1])
        return round((now - past) / past * 100, 2) if past != 0 else None

    latest = float(closes.iloc[-1])
    ma20 = float(closes.iloc[-20:].mean()) if len(closes) >= 20 else None
    ma60 = float(closes.iloc[-60:].mean()) if len(closes) >= 60 else None

    if ma20 and ma60:
        if latest > ma20 and ma20 > ma60:   trend = "상승"
        elif latest < ma20 and ma20 < ma60: trend = "하락"
        else:                               trend = "중립"
    elif ma20:
        trend = "상승" if latest > ma20 else "하락"
    else:
        trend = "—"

    return {
        "1W %":      _ret(5),
        "1M %":      _ret(21),
        "3M %":      _ret(63),
        "MA20 이격%": round((latest - ma20) / ma20 * 100, 2) if ma20 else None,
        "추세":       trend,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _kr_analyst_targets(tickers_key: str) -> pd.DataFrame:
    """Yahoo Finance 컨센서스 목표가 — 한국(.KS) 종목. 미국 탭과 동일 소스."""
    from src.analyst import fetch_analyst_targets
    return fetch_analyst_targets([t for t in tickers_key.split(",") if t])


@st.cache_data(ttl=1800, show_spinner=False)
def _naver_consensus_cached(tickers_key: str) -> pd.DataFrame:
    """네이버 금융 컨센서스 — 코스피·코스닥 광범위(Yahoo 빈값 보강)."""
    from src.analyst_naver import fetch_naver_consensus
    return fetch_naver_consensus([t for t in tickers_key.split(",") if t])


@st.cache_data(ttl=1800, show_spinner=False)
def _naver_reports_cached(ticker: str) -> list:
    """종목별 최근 증권사 리포트(증권사·제목·날짜)."""
    from src.analyst_naver import fetch_naver_reports
    return fetch_naver_reports(ticker)


def render(embedded: bool = False):
    if not embedded:
        inject_css()
        mark_active_nav("/kr-stocks")
        st.markdown(mkt_page_header("🇰🇷", "한국주식", "코스피 시총 TOP 20 · 시총·변동성·애널리스트 한눈에"), unsafe_allow_html=True)

    bucket = live_refresh(["KR"]) if not embedded else 0
    ph = show_skeleton()
    live = load_market_data()
    _kr_history(",".join(sorted(u[0] for u in _KR_UNIVERSE + _KR_NEW_LISTINGS)), _bucket=bucket)  # 유니버스+신규상장 6개월 예열
    _bench_prices()
    load_latest_indicator_summary(DEFAULT_DB)
    ph.empty()

    # ── Stats chips ───────────────────────────────────────────────────────────
    bp = _bench_prices()
    kr_chips = []
    for lbl, tk in [("KOSPI","^KS11"),("KOSDAQ","^KQ11")]:
        r = bp.get(tk, {})
        c = r.get("change_pct")
        if c is not None:
            sign = "+" if c >= 0 else ""
            kr_chips.append({"label": lbl, "value": f"{sign}{c:.2f}%", "cls": "pos" if c>0 else ("neg" if c<0 else "neu")})
    if kr_chips:
        st.markdown(mkt_stats_chips(kr_chips), unsafe_allow_html=True)

    # ── 코스피 시총 상위 20종 유니버스에서 kr_df 구성 — 보유(config) 아님 ──────────
    all_tickers = [u[0] for u in _KR_UNIVERSE + _KR_NEW_LISTINGS]
    history = _kr_history(",".join(sorted(all_tickers)), _bucket=bucket)

    def _u_price(s):
        return float(s.iloc[-1]) if s is not None and not s.empty else None

    def _u_chg(s):  # 1D% = 최신/전일 - 1
        return (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
                if s is not None and len(s) >= 2 and s.iloc[-2] else None)

    kr_df = pd.DataFrame([
        {"ticker": tk, "name": nm, "sector": sec, "mktcap_rank": rank,
         "price": _u_price(history.get(tk)), "change_pct": _u_chg(history.get(tk))}
        for rank, (tk, nm, sec) in enumerate(_KR_UNIVERSE, 1)
    ])

    # ── DB 지표 우선, 없으면 live 계산 ───────────────────────────────────────
    db_df  = load_latest_indicator_summary(DEFAULT_DB)
    kr_db2 = db_df[db_df["asset_type"] == "kr_stock"].copy() if not db_df.empty else pd.DataFrame()
    use_db = not kr_db2.empty

    _DB_TREND = {"bullish": "상승", "bearish": "하락", "neutral": "중립"}

    def _ind(ticker: str) -> dict:
        if use_db:
            m = kr_db2[kr_db2["symbol"] == ticker]
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

    # ── 0. 30초 스캔 레이어 — 리더/러거드/과열 + breadth ─────────────────────────
    def _series_3m(tk: str) -> list[float]:
        s = history.get(tk)
        if s is None or s.empty:
            return []
        return [float(v) for v in s.iloc[-63:].tolist()]

    scan_items = []
    for _, r in kr_df.iterrows():
        tk = r["ticker"]
        ind = _ind(tk)
        scan_items.append({
            "name": r["name"],
            "d1": r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
            "ma20": ind["MA20 이격%"],
            "series": _series_3m(tk),
            "color": _KR_SIG.get(tk),  # 종목별 고유 시그니처색(겹침은 ΔE로 구별 조정)
        })
    _scan = scan_layer_html(scan_items)
    if _scan:
        st.markdown(_scan, unsafe_allow_html=True)

    # ── 1. KOSPI 벤치마크 — 게이지바(52주 범위) + 표로 보기 토글(원자재·외환과 동일 구성) ──
    st.markdown(mkt_section_header("코스피 벤치마크", "52주 범위 내 현재 위치"), unsafe_allow_html=True)
    bench = _bench_prices()
    _bench_hist = _kr_history(",".join(sorted(_KOSPI_BENCH.keys())))
    bench_rows, _rb_bench = [], []
    for tk, label in _KOSPI_BENCH.items():
        p = bench.get(tk, {})
        closes = _bench_hist.get(tk)
        bind = _compute_live_ind(closes) if closes is not None and not closes.empty else {}
        bench_rows.append({
            "지수":   label,
            "현재가": p.get("price"),
            "1D %":  p.get("change_pct"),
            "3M %":  bind.get("3M %"),
            "추세":   bind.get("추세", "—"),
        })
        rng = fetch_52w_range(tk)
        if rng:
            lo, hi, cur = rng
            _rb_bench.append({"name": label, "unit": "", "low": lo, "high": hi, "current": cur,
                              "d1": p.get("change_pct"), "color": _KR_BENCH_COLOR.get(tk)})
    if _rb_bench:
        st.markdown(range_bar_html(_rb_bench, fmt="{:,.2f}"), unsafe_allow_html=True)
        st.caption("막대 = 52주 최저~최고 · 점 = 현재가(지수색) · 우측 라벨 = 범위 내 위치")
    else:
        empty_state("벤치마크 범위 데이터 준비 중")
    if st.toggle("표로 보기", key="kr_bench_tbl", value=False):
        slim_table(bench_rows, key="kr_bench", name_key="지수",
                   price_key="현재가", price_fmt="{:,.2f}", show_conclusion=False)

    # ── 2. 시총 TOP 10 테이블 (섹터별) ──────────────────────────────────────
    _top10_sub = "시총 히트맵 · 색=1D% 등락" if embedded else "섹터별 · 시총 순위 기준"
    st.markdown(mkt_section_header("코스피 시가총액 상위", _top10_sub), unsafe_allow_html=True)

    all_rows = []
    for _, r in kr_df.iterrows():
        tk   = r["ticker"]
        rank = r.get("mktcap_rank", "—")
        ind  = _ind(tk)
        all_rows.append({
            "순위":       int(rank) if isinstance(rank, (int, float)) else "—",
            "종목":       f"{r['name']}  ({tk.replace('.KS', '')})",
            "섹터":       r.get("sector", "—"),
            "현재가 (원)": r["price"]      if isinstance(r["price"],      (int, float)) else None,
            "1D %":       r["change_pct"] if isinstance(r["change_pct"], (int, float)) else None,
            "1W %":       ind["1W %"],
            "1M %":       ind["1M %"],
            "3M %":       ind["3M %"],
            "MA20 이격%": ind["MA20 이격%"],
            "추세":        ind["추세"],
            "_ticker":    tk,
            "_name":      r["name"],
        })

    all_rows.sort(key=lambda x: x["순위"] if isinstance(x["순위"], int) else 99)

    def _render_kr_table(grp: list[dict], sort_movement: bool = False, highlight: bool = False):
        tbl = pd.DataFrame(grp).drop(columns=["_ticker", "_name"])
        tbl = numeric(tbl, pct_cols + ["현재가 (원)"])
        if sort_movement and "1D %" in tbl.columns:
            tbl = tbl.reindex(tbl["1D %"].abs().sort_values(ascending=False, na_position="last").index)
        # 모바일: 종목당 카드 (데스크탑은 아래 styled 표 유지)
        if L.is_mobile():
            disp = tbl.copy()
            for c in [x for x in pct_cols if x in disp.columns]:
                disp[c] = disp[c].map(lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) and pd.notna(v) else "—")
            if "현재가 (원)" in disp.columns:
                disp["현재가 (원)"] = disp["현재가 (원)"].map(lambda v: f"{v:,.0f}" if isinstance(v, (int, float)) and pd.notna(v) else "—")
            L.render_table_or_cards(
                disp, title_col="종목",
                price_col="현재가 (원)" if "현재가 (원)" in disp.columns else None,
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
        if "현재가 (원)" in tbl.columns:
            fmt["현재가 (원)"] = "{:,.0f}"
        styled = styled.format(fmt, na_rep="—")
        st.dataframe(styled, use_container_width=True, hide_index=True)

    if embedded:
        # 시총 히트맵 트리맵(분위기) + 표로 보기 토글 → 슬림표(정밀 비교 보존)
        # 데스크탑: 트리맵 / 모바일: 글자가 안 읽혀 상승·하락 상위 리스트로 대체
        _mv = pd.DataFrame(all_rows)
        if "1D %" in _mv.columns:
            _mv["1D %"] = _mv["1D %"].map(lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) and pd.notna(v) else "—")
        L.only_desktop(lambda: cap_treemap(all_rows, key="kr_all", name_key="종목", sector_key="섹터", rank_key="순위"))
        L.only_mobile(lambda: L.top_movers_list(_mv, name_col="종목", change_col="1D %"))
        if st.toggle("표로 보기", key="kr_all_tbl", value=False):
            _slim_rows = sorted(
                all_rows, key=lambda x: x["순위"] if isinstance(x["순위"], (int, float)) else 999)  # 시총 순위 정렬
            slim_table(_slim_rows, key="kr_all", name_key="종목",
                       price_key="현재가 (원)", price_fmt="{:,.0f}")
    else:
        for sector in _SECTOR_ORDER + ["기타"]:
            grp = [r for r in all_rows if r["섹터"] == sector]
            if not grp:
                continue
            st.markdown(
                f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:#7E8694;margin:14px 0 4px">{sector}</div>',
                unsafe_allow_html=True,
            )
            _render_kr_table(grp)

    st.caption(data_source_note("로컬 DB" if use_db else "Yahoo Finance(6개월 계산)",
                                updated=str(kr_db2["run_date"].max()) if use_db else "",
                                extra="기술지표 1W/1M/3M·추세"))

    # ── 신규 상장 (데이터 누적 전 · 시총 랭킹과 분리) — 미국 탭과 동일 처리 ──────────
    if not embedded:
        kr_new_rows = []
        for tk, nm, sec in _KR_NEW_LISTINGS:
            s = history.get(tk)
            if s is None or s.empty:
                continue
            price = float(s.iloc[-1])
            chg   = (round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
                     if len(s) >= 2 and s.iloc[-2] else None)
            since = (round((float(s.iloc[-1]) / float(s.iloc[0]) - 1) * 100, 2)
                     if len(s) >= 2 and s.iloc[0] else None)
            kr_new_rows.append({
                "종목":       f"{nm}  ({tk})",
                "섹터":       sec,
                "현재가 (원)": price,
                "1D %":       chg,
                "상장 후 %":  since,
                "데이터":     f"{len(s)}일",
            })
        if kr_new_rows:
            st.markdown(mkt_section_header("신규 상장", "데이터 누적 전 · 시총 랭킹 미반영"), unsafe_allow_html=True)
            knt = pd.DataFrame(kr_new_rows)
            _knpct = [c for c in ["1D %", "상장 후 %"] if c in knt.columns]
            knstyled = knt.style.map(_cell, subset=_knpct).format(
                {"현재가 (원)": "{:,.0f}", "1D %": "{:+.2f}%", "상장 후 %": "{:+.2f}%"}, na_rep="—")
            st.dataframe(knstyled, use_container_width=True, hide_index=True)
            st.caption("상장 초기로 1W/1M/3M·추세 등 누적 지표는 데이터가 쌓인 뒤 제공됩니다.")

    # ── 애널리스트 전망 (미국 탭과 동일 산점도) — 네이버 + Yahoo 컨센서스 병합으로 커버리지 보강 ──
    # 함수로 정의해 '맨 끝'에 렌더한다: 임베디드는 딥다이브 생략 직후, 전체 페이지는 딥다이브 뒤.
    def _render_analyst():
        st.markdown(mkt_section_header("애널리스트 전망",
                                       "컨센서스 목표가 — 네이버(코스피·코스닥) + Yahoo"),
                    unsafe_allow_html=True)

        def _an_num(v):
            try:
                f = float(v)
                return None if pd.isna(f) else f
            except (TypeError, ValueError):
                return None

        _key = ",".join(sorted(all_tickers))
        _yh = _kr_analyst_targets(_key)
        _nv = _naver_consensus_cached(_key)
        _yh_of = {r["ticker"]: r for _, r in _yh.iterrows()} if (_yh is not None and not _yh.empty) else {}
        _nv_of = {r["ticker"]: r for _, r in _nv.iterrows()} if (_nv is not None and not _nv.empty) else {}
        _nm_of = {r["_ticker"]: r["_name"] for r in all_rows}
        _rk_of = {r["_ticker"]: r["순위"] for r in all_rows}
        _px_of = {r["_ticker"]: r.get("현재가 (원)") for r in all_rows}

        points = []
        for tk in all_tickers:
            px = _an_num(_px_of.get(tk))
            nv = _nv_of.get(tk)
            yh = _yh_of.get(tk)
            # 목표가: 네이버 우선(커버리지 넓음) → 없으면 Yahoo
            tgt = _an_num(nv["목표가_평균"]) if nv is not None else None
            src = "네이버"
            if tgt is None and yh is not None:
                tgt = _an_num(yh.get("목표가_평균")); src = "Yahoo"
            if px is None or tgt is None:
                continue
            up = round((tgt / px - 1) * 100, 1)
            # 커버리지(Y): Yahoo 애널리스트수 우선 → 없으면 네이버 최근 리포트 증권사 수
            na = _an_num(yh.get("애널리스트수")) if yh is not None else None
            if na is None and nv is not None:
                na = _an_num(nv.get("리포트수"))
            if na is None:
                continue
            opinion = "—"
            if nv is not None and nv.get("투자의견") not in (None, "—"):
                opinion = nv["투자의견"]
            elif yh is not None:
                opinion = yh.get("투자의견") or "—"
            if up < 0 and opinion != "—":
                opinion = f"{opinion} · 목표가 하회"
            nm = _nm_of.get(tk, tk.replace(".KS", ""))
            points.append({
                "name": nm, "x": up, "y": na, "ticker": tk,
                "rank": _an_num(_rk_of.get(tk)),
                "hover": (f"{nm}<br>현재가 {px:,.0f}원 · 목표가 {tgt:,.0f}원"
                          f"<br>상승여력 {up:+.1f}% · 커버리지 {int(na)} · {opinion} · {src}"),
            })

        fig_kr = analyst_scatter_fig(points)
        if fig_kr is not None:
            def _desktop_sc():
                st.plotly_chart(fig_kr, use_container_width=True, config={"displayModeBar": False},
                                key="kr_analyst_sc")
                st.caption("점 크기 = 시가총액 · 우측·상단 = 목표가 여력 크고 커버리지 많음(기회) · 라벨은 시총 상위 5개(리더선), 나머지는 hover")
            # 모바일: 산점도는 라벨이 안 읽혀 상승여력 상위/하위 리스트로 대체
            _mob_pts = pd.DataFrame([{"종목": p["name"], "상승여력": f'{p["x"]:+.1f}%'} for p in points])
            L.only_desktop(_desktop_sc)
            L.only_mobile(lambda: L.top_movers_list(_mob_pts, name_col="종목", change_col="상승여력"))
            st.caption(data_source_note("네이버 금융 컨센서스 + Yahoo Finance", cached="1시간",
                                        extra="현재가는 실시간"))
        else:
            empty_state("애널리스트 컨센서스 준비 중")

        # 네이버 증권사별 최근 리포트 드릴다운 (전문 애널리스트 리서치)
        with st.expander("증권사 리포트 — 네이버 (종목 선택)"):
            _opts = {f"{r['_name']}  ({r['_ticker'].replace('.KS', '')})": r["_ticker"] for r in all_rows}
            _sel = st.selectbox("종목", list(_opts.keys()), key="kr_naver_reports_sel",
                                label_visibility="collapsed")
            _reps = _naver_reports_cached(_opts[_sel])
            if _reps:
                st.dataframe(pd.DataFrame(_reps), use_container_width=True, hide_index=True)
                st.caption("출처: 네이버 금융 리서치 · 증권사별 최근 리포트(제목·날짜)")
            else:
                st.info("최근 증권사 리포트를 찾지 못했습니다.")

    # 시장 탭(슬림): 벤치마크 + 종목 테이블 → 애널리스트 전망(맨 끝)으로 마무리. 딥다이브는 숨김.
    if embedded:
        _render_analyst()
        return

    # ── 3. 전 종목 수익률 비교 차트 (정규화) ─────────────────────────────────
    st.markdown(mkt_section_header("전 종목 수익률 비교", "3개월 · 기준일=100 정규화"), unsafe_allow_html=True)

    if history:
        fig_cmp = go.Figure()
        for i, row in enumerate(all_rows):
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
                line=dict(color=_KR_SIG.get(tk, _LINE_COLORS[i % len(_LINE_COLORS)]), width=1.5),
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

    # ── 4. 개별 종목 가격 추이 ───────────────────────────────────────────────
    st.markdown(mkt_section_header("개별 종목 가격 추이", "3개월 일별 종가"), unsafe_allow_html=True)

    opts = {
        f"{r['_name']}  ({r['_ticker'].replace('.KS', '')})": r["_ticker"]
        for r in all_rows
    }
    col_sel, _ = st.columns([3, 7])
    with col_sel:
        sel = st.selectbox("종목", list(opts.keys()), label_visibility="collapsed",
                           key="kr_chart_sel")

    sel_closes = history.get(opts[sel])
    if sel_closes is not None and not sel_closes.empty:
        cutoff = sel_closes.index[-1] - pd.DateOffset(months=3)
        s = sel_closes[sel_closes.index >= cutoff].dropna()
        if not s.empty:
            pct   = (float(s.iloc[-1]) / float(s.iloc[0]) - 1) * 100
            color = "#F25560" if pct >= 0 else "#4D90F0"   # 손익색(제목 % 텍스트)
            sign  = "+" if pct >= 0 else ""
            _sig = _KR_SIG.get(opts[sel], "#D9A441")        # 종목 시그니처색(라인·채움)
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
                yaxis=dict(showgrid=True, gridcolor="#262A33", tickformat=",",
                           tickfont=dict(size=9, color="#7E8694"), side="right"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        empty_state("차트 데이터 준비 중")

    # ── 5. 종목별 1D 등락률 바 차트 ──────────────────────────────────────────
    st.markdown(mkt_section_header("종목별 1D 등락률", "당일 변동 비교"), unsafe_allow_html=True)

    bar_rows = [r for r in all_rows if isinstance(r["1D %"], float)]
    if bar_rows:
        bar_rows.sort(key=lambda x: x["1D %"])
        labels = [r["종목"].split("  ")[0] for r in bar_rows]
        values = [r["1D %"] for r in bar_rows]
        colors = ["#F25560" if v >= 0 else "#4D90F0" for v in values]
        texts  = [f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%" for v in values]

        fig_b = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colors, marker_opacity=0.72,
            text=texts, textposition="outside",
            textfont=dict(size=9, color="#4A5568"),
            cliponaxis=False,
        ))
        fig_b.update_layout(
            margin=dict(l=0, r=60, t=8, b=0), height=300,
            paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
            xaxis=dict(showgrid=True, gridcolor="#262A33",
                       zeroline=True, zerolinecolor="#262A33", zerolinewidth=1,
                       tickformat="+.2f", ticksuffix="%",
                       tickfont=dict(size=9, color="#7E8694")),
            yaxis=dict(tickfont=dict(size=9, color="#9AA0AD"), showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar": False})

    # 전체 페이지: 딥다이브 뒤 맨 끝에 애널리스트 전망(미국 탭과 동일 위치)
    _render_analyst()

    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)
