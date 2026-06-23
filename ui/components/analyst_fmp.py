"""
FMP analyst price target trend component.
Shows period-over-period target trend (1M / 1Q / 1Y) + consensus for each ticker.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from src.analyst import fetch_fmp_target_trends_bulk, fmp_available
from ui.components.dash_style import show_skeleton, empty_state, data_source_note


@st.cache_data(ttl=86400, show_spinner=False)   # 목표가 추이는 일 단위 안정 → 24h 캐시
def _fmp_trends_cached(tickers_key: str) -> dict:
    tickers = tickers_key.split(",")
    return fetch_fmp_target_trends_bulk(tickers)


def _arrow(a, b) -> str:
    """Return colored arrow comparing two values (a = recent, b = older)."""
    if a is None or b is None:
        return ""
    if a > b * 1.01:
        return " ▲"
    if a < b * 0.99:
        return " ▼"
    return " ─"


def _fmt(v, fmt="$,.2f") -> str:
    if v is None:
        return "—"
    try:
        return f"${v:,.2f}"
    except (TypeError, ValueError):
        return "—"


def _upside_style(v):
    if not isinstance(v, (int, float)) or pd.isna(v):
        return ""
    if v >= 10:
        return "background-color:rgba(242,85,96,0.13);color:#F25560;font-weight:600"
    if v <= -5:
        return "background-color:rgba(77,144,240,0.13);color:#4D90F0;font-weight:600"
    return ""


def _trend_style(v):
    """Color the trend direction cell."""
    if not isinstance(v, str):
        return ""
    if "▲" in v:
        return "color:#F25560;font-weight:700"
    if "▼" in v:
        return "color:#4D90F0;font-weight:700"
    return "color:#7E8694"


def render_fmp_drilldown(
    tickers: list[str],
    ticker_labels: dict[str, str],
    section_title: str = "증권사 컨센서스 목표가 추이",
) -> None:
    """
    Renders an expander showing FMP period-over-period price target trends.
    Columns: 종목, 컨센서스, 중앙값, 최고, 최저, 1M평균, 1Q평균, 1Y평균, 추이, 참여수(1M)
    """
    with st.expander(f"{section_title} (FMP)", expanded=False):
        if not fmp_available():
            st.info(
                "Financial Modeling Prep API 키를 `.env` 파일에 추가하면 "
                "기간별 목표가 추이와 중앙값을 볼 수 있습니다.\n\n"
                "```\nFMP_API_KEY=여기에_키_입력\n```\n\n"
                "무료 키 발급: https://financialmodelingprep.com/developer/docs"
            )
            return

        _ph = show_skeleton()
        cache_key = ",".join(tickers)
        trends = _fmp_trends_cached(cache_key)
        _ph.empty()

        rows = []
        for tk in tickers:
            t = trends.get(tk)
            if not t:
                continue

            consensus   = t.get("consensus")
            m1          = t.get("lastMonth_avg")
            q1          = t.get("lastQuarter_avg")
            y1          = t.get("lastYear_avg")
            m1_count    = t.get("lastMonth_count")

            # Trend: compare most recent (1M) vs prior (1Q)
            trend_str = ""
            if m1 and q1:
                arrow = _arrow(m1, q1)
                pct = (m1 - q1) / q1 * 100 if q1 else 0
                trend_str = f"{arrow} {pct:+.1f}%"

            rows.append({
                "종목":        f"{ticker_labels.get(tk, tk)} ({tk})",
                "컨센서스":    consensus,
                "중앙값":      t.get("median"),
                "최고":        t.get("high"),
                "최저":        t.get("low"),
                "1M 평균":     m1,
                "1Q 평균":     q1,
                "1Y 평균":     y1,
                "목표가 추이":  trend_str,
                "참여(1M)":    m1_count,
            })

        if not rows:
            empty_state("애널리스트 목표가 준비 중")
            return

        df = pd.DataFrame(rows)
        price_cols = ["컨센서스", "중앙값", "최고", "최저", "1M 평균", "1Q 평균", "1Y 평균"]
        for c in price_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        if "참여(1M)" in df.columns:
            df["참여(1M)"] = pd.to_numeric(df["참여(1M)"], errors="coerce")

        afmt = {c: "${:,.2f}" for c in price_cols}
        if "참여(1M)" in df.columns:
            afmt["참여(1M)"] = "{:.0f}명"
        styled = df.style.map(_trend_style, subset=["목표가 추이"]).format(afmt, na_rep="—")

        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption(data_source_note("Financial Modeling Prep", cached="1시간",
                                    extra="추이 = 최근 1개월 평균 vs 직전 분기 평균"))
