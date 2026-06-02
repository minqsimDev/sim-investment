import streamlit as st
import pandas as pd
from data.fetcher import fetch_all
from core.config_loader import load_config
from ui.components.dash_style import (
    inject_css, section_header, timestamp_bar,
    style_returns, numeric, csv_bytes, excel_bytes,
)

_ETF  = {"name":"종목명","ticker":"티커","category":"분류","price":"현재가",
         "change_pct":"등락률(%)","benchmark":"벤치마크","hedged":"환헤지"}
_DRV  = {"드라이버":"드라이버","구분":"구분","현재값":"현재값","등락률(%)":"등락률(%)"}


@st.cache_data(ttl=300)
def _load():
    return fetch_all()


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
