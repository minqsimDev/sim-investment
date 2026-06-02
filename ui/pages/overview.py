import streamlit as st
import pandas as pd
from data.fetcher import fetch_all
from ui.components.dash_style import (
    inject_css, metric_strip, section_header, timestamp_bar,
    style_returns, numeric, csv_bytes, excel_bytes,
)

# ── Column maps ───────────────────────────────────────────────────────────────
_ETF = {"name":"종목명","ticker":"티커","price":"현재가","change":"전일대비",
        "change_pct":"등락률(%)","benchmark":"벤치마크","hedged":"환헤지"}
_BENCH = {"ticker":"티커","name":"종목명","price":"현재가","change_pct":"등락률(%)"}
_STOCK = {"ticker":"티커","name":"종목명","sector":"섹터","price":"현재가","change_pct":"등락률(%)"}
_COMM  = {"name":"원자재","price":"현재가","change_pct":"등락률(%)"}
_FX    = {"pair":"통화쌍","rate":"환율","change_pct":"등락률(%)","priority":"중요도"}
_MAC   = {"key":"지표","series_id":"FRED코드","value":"값","date":"기준일"}


@st.cache_data(ttl=300)
def _load():
    return fetch_all()


def render():
    inject_css()

    # ── Header bar ───────────────────────────────────────────────────────────
    c1, c2 = st.columns([9, 1])
    c1.markdown("## 투자 모니터링")
    c1.caption("본 데이터는 투자 참고용이며 매매 권유가 아닙니다.")
    if c2.button("↻ 새로고침", use_container_width=True):
        st.cache_data.clear()

    with st.spinner(""):
        data = _load()

    ts = data["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

    fx   = data["fx"]
    comm = data["commodities"]
    mac  = data["macro"]

    # ── Metric strip 1: FX & 귀금속 ──────────────────────────────────────────
    usd_krw, uc = _fx(fx, "usd_krw")
    dxy,     dc = _fx(fx, "dxy")
    gold,    gc = _comm(comm, "gold")
    silver,  sc = _comm(comm, "silver")
    copper,  cc = _comm(comm, "copper")
    wti,     wc = _comm(comm, "wti_crude")

    st.markdown(metric_strip([
        {"label": "USD / KRW",    "value": _v(usd_krw, 1), **_d(uc)},
        {"label": "DXY",          "value": _v(dxy,     2), **_d(dc)},
        {"label": "금  $/oz",     "value": _v(gold,    0), **_d(gc)},
        {"label": "은  $/oz",     "value": _v(silver,  2), **_d(sc)},
        {"label": "구리 $/lb",    "value": _v(copper,  3), **_d(cc)},
        {"label": "WTI $/bbl",    "value": _v(wti,     2), **_d(wc)},
    ]), unsafe_allow_html=True)

    # ── Metric strip 2: 금리 ─────────────────────────────────────────────────
    us10y  = _macro(mac, "us_10y")
    us2y   = _macro(mac, "us_2y")
    spread = _macro(mac, "spread_10y_2y")
    ff     = _macro(mac, "fed_funds")
    cpi    = _macro(mac, "cpi")
    unrate = _macro(mac, "unemployment")

    st.markdown(metric_strip([
        {"label": "미국 10년물",   "value": _rate(us10y),  "delta": None, "positive": None},
        {"label": "미국 2년물",    "value": _rate(us2y),   "delta": None, "positive": None},
        {"label": "장단기 스프레드","value": _rate(spread), "delta": None, "positive": None},
        {"label": "기준금리",      "value": _rate(ff),     "delta": None, "positive": None},
        {"label": "CPI",          "value": _rate(cpi),    "delta": None, "positive": None},
        {"label": "실업률",        "value": _rate(unrate), "delta": None, "positive": None},
    ]), unsafe_allow_html=True)

    # ── 보유 ETF ──────────────────────────────────────────────────────────────
    st.markdown(section_header("보유 ETF"), unsafe_allow_html=True)

    etf_df = _prep(data["my_etfs"], list(_ETF), _ETF, ["change_pct", "change", "price"])
    etf_styled = style_returns(etf_df, "등락률(%)")

    col_etf, col_etf_dl = st.columns([9, 1])
    with col_etf:
        st.dataframe(
            etf_styled,
            column_config=_cfg({
                "현재가":    ("number", "%,.0f"),
                "전일대비":  ("number", "%+,.0f"),
                "등락률(%)": ("number", "%.2f%%"),
            }),
            use_container_width=True, hide_index=True,
        )
    with col_etf_dl:
        today = ts[:10]
        raw = data["my_etfs"].rename(columns=_ETF)
        st.download_button("↓ CSV",   csv_bytes(raw),   f"etf_{today}.csv",  "text/csv",            use_container_width=True)
        st.download_button("↓ Excel", excel_bytes({"보유ETF": raw}), f"etf_{today}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    # ── 시장 현황 ─────────────────────────────────────────────────────────────
    st.markdown(section_header("시장 현황"), unsafe_allow_html=True)
    cb, cs = st.columns(2)

    with cb:
        st.markdown('<div style="font-size:10px;color:#718096;font-weight:600;margin-bottom:4px">벤치마크 ETF</div>', unsafe_allow_html=True)
        b_df = _prep(data["benchmarks"], list(_BENCH), _BENCH, ["change_pct", "price"])
        st.dataframe(
            style_returns(b_df, "등락률(%)"),
            column_config=_cfg({"현재가": ("number", "%,.2f"), "등락률(%)": ("number", "%.2f%%")}),
            use_container_width=True, hide_index=True,
        )

    with cs:
        st.markdown('<div style="font-size:10px;color:#718096;font-weight:600;margin-bottom:4px">미국 주식</div>', unsafe_allow_html=True)
        s_df = _prep(data["us_stocks"], list(_STOCK), _STOCK, ["change_pct", "price"])
        st.dataframe(
            style_returns(s_df, "등락률(%)"),
            column_config=_cfg({"현재가": ("number", "%,.2f"), "등락률(%)": ("number", "%.2f%%")}),
            use_container_width=True, hide_index=True,
        )

    # ── 원자재 & 환율 ─────────────────────────────────────────────────────────
    st.markdown(section_header("원자재 & 환율"), unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)

    with cc1:
        st.markdown('<div style="font-size:10px;color:#718096;font-weight:600;margin-bottom:4px">원자재</div>', unsafe_allow_html=True)
        co_df = _prep(comm, list(_COMM), _COMM, ["change_pct", "price"])
        st.dataframe(
            style_returns(co_df, "등락률(%)"),
            column_config=_cfg({"현재가": ("number", "%,.3f"), "등락률(%)": ("number", "%.2f%%")}),
            use_container_width=True, hide_index=True,
        )

    with cc2:
        st.markdown('<div style="font-size:10px;color:#718096;font-weight:600;margin-bottom:4px">환율</div>', unsafe_allow_html=True)
        fx_df = _prep(fx, list(_FX), _FX, ["change_pct", "rate"])
        st.dataframe(
            style_returns(fx_df, "등락률(%)"),
            column_config=_cfg({"환율": ("number", "%,.3f"), "등락률(%)": ("number", "%.2f%%")}),
            use_container_width=True, hide_index=True,
        )

    # ── 매크로 지표 ───────────────────────────────────────────────────────────
    st.markdown(section_header("매크로 지표 (FRED)"), unsafe_allow_html=True)
    if mac is None or mac.empty:
        st.info("FRED API 키를 사이드바에 입력하면 금리 · CPI · 고용 데이터가 활성화됩니다.")
    else:
        m_df = mac.rename(columns=_MAC)
        st.dataframe(m_df, column_config=_cfg({"값": ("number", "%.4f")}),
                     use_container_width=True, hide_index=True)

    # ── 전체 내보내기 ─────────────────────────────────────────────────────────
    st.markdown(section_header("데이터 내보내기"), unsafe_allow_html=True)
    dl1, dl2, _ = st.columns([1, 1, 6])
    all_sheets = {
        "보유ETF":      data["my_etfs"].rename(columns=_ETF),
        "벤치마크":     data["benchmarks"].rename(columns=_BENCH),
        "미국주식":     data["us_stocks"].rename(columns=_STOCK),
        "원자재":       comm.rename(columns=_COMM),
        "환율":         fx.rename(columns=_FX),
    }
    if mac is not None and not mac.empty:
        all_sheets["매크로"] = mac.rename(columns=_MAC)

    dl1.download_button("↓ 전체 Excel", excel_bytes(all_sheets),
                        f"sinvest_{today}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
    dl2.download_button("↓ 전체 CSV (ETF)",
                        csv_bytes(all_sheets["보유ETF"]), f"sinvest_etf_{today}.csv",
                        "text/csv", use_container_width=True)


# ── helpers ──────────────────────────────────────────────────────────────────

def _prep(df: pd.DataFrame, cols: list, rename: dict, num_cols: list) -> pd.DataFrame:
    from ui.components.dash_style import numeric
    out = df[cols].copy().rename(columns=rename)
    kr_nums = [rename.get(c, c) for c in num_cols]
    return numeric(out, kr_nums)

def _cfg(spec: dict) -> dict:
    cfg = {}
    for col, (kind, fmt) in spec.items():
        if kind == "number":
            cfg[col] = st.column_config.NumberColumn(col, format=fmt)
    return cfg

def _fx(df, pair):
    r = df[df["pair"] == pair]
    if r.empty: return "N/A", None
    return r.iloc[0]["rate"], r.iloc[0]["change_pct"]

def _comm(df, name):
    r = df[df["name"] == name]
    if r.empty: return "N/A", None
    return r.iloc[0]["price"], r.iloc[0]["change_pct"]

def _macro(df, key):
    if df is None or df.empty: return "N/A"
    r = df[df["key"] == key]
    return r.iloc[0]["value"] if not r.empty else "N/A"

def _v(val, d=2):
    if val == "N/A" or not isinstance(val, (int, float)): return "N/A"
    return f"{val:,.{d}f}"

def _rate(val):
    if val == "N/A" or not isinstance(val, (int, float)): return "N/A"
    return f"{val:.2f}%"

def _d(val):
    if val is None or val == "N/A" or not isinstance(val, (int, float)):
        return {"delta": None, "positive": None}
    sign = "+" if val >= 0 else ""
    return {"delta": f"{sign}{val:.2f}%", "positive": val > 0}
