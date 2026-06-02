import streamlit as st
import pandas as pd
from data.fetcher import fetch_all
from core.config_loader import load_config
from src.analyst import fetch_analyst_targets
from ui.components.analyst_fmp import render_fmp_drilldown
from ui.components.dash_style import (
    inject_css, section_header, timestamp_bar,
    style_returns, numeric, csv_bytes, excel_bytes,
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

_ETF  = {"name":"종목명","ticker":"티커","category":"분류","price":"현재가",
         "change_pct":"등락률(%)","benchmark":"벤치마크","hedged":"환헤지"}
_DRV  = {"드라이버":"드라이버","구분":"구분","현재값":"현재값","등락률(%)":"등락률(%)"}


@st.cache_data(ttl=300)
def _load():
    return fetch_all()


@st.cache_data(ttl=3600)
def _analyst_targets() -> pd.DataFrame:
    return fetch_analyst_targets(list(_STOCK_KOR.keys()))


def render():
    inject_css()

    c1, c2 = st.columns([9, 1])
    c1.markdown("## 보유 포트폴리오")
    c1.caption("투자 참고용 데이터입니다. 매매 권유가 아닙니다.")
    if c2.button("↻ 새로고침", use_container_width=True):
        st.cache_data.clear()

    with st.spinner(""):
        data = _load()
    config = load_config()

    ts = data["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

    etfs    = data["my_etfs"]
    benches = data["benchmarks"]

    # ── 보유 ETF 현황 ─────────────────────────────────────────────────────────
    st.markdown(section_header("보유 ETF 현황"), unsafe_allow_html=True)

    cols = ["name", "ticker", "category", "price", "change_pct", "benchmark", "hedged"]
    etf_df = etfs[cols].copy().rename(columns=_ETF)
    etf_df = numeric(etf_df, ["현재가", "등락률(%)"])

    col_t, col_dl = st.columns([9, 1])
    with col_t:
        st.dataframe(
            style_returns(etf_df, "등락률(%)"),
            column_config={
                "현재가":    st.column_config.NumberColumn("현재가",    format="%,.0f"),
                "등락률(%)": st.column_config.NumberColumn("등락률(%)", format="%.2f%%"),
            },
            use_container_width=True, hide_index=True,
        )
    with col_dl:
        st.download_button("↓ CSV",   csv_bytes(etf_df),
                           f"portfolio_{ts[:10]}.csv", "text/csv", use_container_width=True)
        st.download_button("↓ Excel", excel_bytes({"포트폴리오": etf_df}),
                           f"portfolio_{ts[:10]}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    # ── 벤치마크 비교 ─────────────────────────────────────────────────────────
    st.markdown(section_header("내 ETF vs 벤치마크"), unsafe_allow_html=True)

    rows = []
    for _, etf in etfs.iterrows():
        bm  = etf["benchmark"]
        b_r = benches[benches["ticker"] == bm]
        b_c = b_r.iloc[0]["change_pct"] if not b_r.empty else None
        my  = etf["change_pct"]
        diff = round(my - b_c, 2) if isinstance(my, float) and isinstance(b_c, float) else None
        rows.append({
            "종목명":           etf["name"],
            "내 ETF 등락률(%)": my   if isinstance(my, float)  else None,
            "벤치마크":         bm,
            "벤치마크 등락률(%)":b_c  if isinstance(b_c, float) else None,
            "초과 수익률(%)":   diff,
        })

    cmp = pd.DataFrame(rows)
    cmp = numeric(cmp, ["내 ETF 등락률(%)", "벤치마크 등락률(%)", "초과 수익률(%)"])
    cmp_styled = cmp.style\
        .map(_ret_style, subset=["내 ETF 등락률(%)", "벤치마크 등락률(%)"])\
        .map(_alpha_style, subset=["초과 수익률(%)"])

    st.dataframe(
        cmp_styled,
        column_config={
            "내 ETF 등락률(%)":  st.column_config.NumberColumn(format="%.2f%%"),
            "벤치마크 등락률(%)": st.column_config.NumberColumn(format="%.2f%%"),
            "초과 수익률(%)":    st.column_config.NumberColumn(format="%.2f%%"),
        },
        use_container_width=True, hide_index=True,
    )

    # ── 드라이버 분석 ─────────────────────────────────────────────────────────
    st.markdown(section_header("ETF별 드라이버 현황",
                               "각 ETF의 주요 영향 요인 오늘 성과"), unsafe_allow_html=True)

    for cfg_etf in config["my_etfs"]:
        name    = cfg_etf["name"]
        drivers = cfg_etf.get("drivers", [])
        if not drivers:
            continue
        with st.expander(f"{name}  —  드라이버 {len(drivers)}개", expanded=False):
            drv_rows = []
            for drv in drivers:
                res = _lookup(drv, data)
                drv_rows.append({
                    "드라이버":   drv,
                    "구분":       res.get("source", "N/A") if res else "N/A",
                    "현재값":     res.get("value",  "N/A") if res else "N/A",
                    "등락률(%)":  res.get("change_pct", None) if res else None,
                })
            drv_df = pd.DataFrame(drv_rows)
            drv_df = numeric(drv_df, ["등락률(%)"])
            st.dataframe(
                style_returns(drv_df, "등락률(%)"),
                column_config={"등락률(%)": st.column_config.NumberColumn(format="%.2f%%")},
                use_container_width=True, hide_index=True,
            )


    # ── 애널리스트 전망 ────────────────────────────────────────────────────────
    st.markdown(section_header("보유 ETF 주요 편입 종목 애널리스트 전망",
                               "Yahoo Finance 컨센서스 목표가 — 나스닥·반도체·빅테크 ETF 편입 종목"),
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

        rows_a = []
        for _, r in analyst_df.iterrows():
            tk = r["ticker"]
            rows_a.append({
                "종목":        f"{_STOCK_KOR.get(tk, tk)}  ({tk})",
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

    render_fmp_drilldown(list(_STOCK_KOR.keys()), _STOCK_KOR, section_title="주요 편입 종목 증권사별 목표가")


# ── Style helpers ─────────────────────────────────────────────────────────────

def _ret_style(v):
    if not isinstance(v, (int, float)) or pd.isna(v): return ""
    if v > 0.005:  return "background-color:#F0FFF6;color:#276749;font-weight:600"
    if v < -0.005: return "background-color:#FFF5F5;color:#9B2335;font-weight:600"
    return ""

def _alpha_style(v):
    if not isinstance(v, (int, float)) or pd.isna(v): return ""
    if v > 0.1:  return "color:#276749;font-weight:700"
    if v < -0.1: return "color:#9B2335;font-weight:700"
    return "color:#718096"


# ── Driver lookup ─────────────────────────────────────────────────────────────

_MACRO_MAP = {"US10Y": "us_10y", "US 10Y": "us_10y", "US2Y": "us_2y", "US 2Y": "us_2y"}

def _lookup(driver: str, data: dict) -> dict | None:
    for _, r in data["commodities"].iterrows():
        if driver.lower() == r["name"].lower():
            return {"source": "원자재", "value": _f(r["price"]), "change_pct": r["change_pct"]}

    for _, r in data["fx"].iterrows():
        if driver.upper() in (r["pair"].upper(), "DXY") and (driver.upper() != "DXY" or r["pair"] == "dxy"):
            return {"source": "환율",   "value": _f(r["rate"]),  "change_pct": r["change_pct"]}
        if driver.upper().replace("/","_").replace(" ","_") == r["pair"].upper():
            return {"source": "환율",   "value": _f(r["rate"]),  "change_pct": r["change_pct"]}

    for _, r in data["us_stocks"].iterrows():
        if driver.upper() == str(r["ticker"]).upper():
            return {"source": "미국주식", "value": _f(r["price"]), "change_pct": r["change_pct"]}

    for _, r in data["benchmarks"].iterrows():
        if driver.upper() == str(r["ticker"]).upper():
            return {"source": "벤치마크", "value": _f(r["price"]), "change_pct": r["change_pct"]}

    mac = data["macro"]
    if mac is not None and not mac.empty:
        key = _MACRO_MAP.get(driver)
        if key:
            row = mac[mac["key"] == key]
            if not row.empty:
                return {"source": "매크로", "value": f"{row.iloc[0]['value']}%", "change_pct": None}
    return None

def _f(v):
    if not isinstance(v, (int, float)): return "N/A"
    return f"{v:,.2f}"
