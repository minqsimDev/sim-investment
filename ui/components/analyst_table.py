"""애널리스트 컨센서스 통합 표 — 미국·한국 동일 양식(네이버 단일 소스).

컬럼: 종목 · 현재가 · 목표가 · 상승여력% · 투자의견 · 기준일 · (커버리지=KR 리포트수)
신뢰도 신호로 '기준일'(컨센서스 갱신일)을 노출한다. 상승여력은 페이지의 현재가로 계산.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components.dash_style import data_source_note, empty_state

_REC_COLOR = {
    "강력매수": "color:#F25560;font-weight:700",
    "매수":     "color:#F25560;font-weight:600",
    "보유":     "color:#7E8694",
    "시장하회": "color:#4D90F0;font-weight:600",
    "매도":     "color:#4D90F0;font-weight:700",
    "강력매도": "color:#4D90F0;font-weight:700",
}


def _upside_style(v):
    if not isinstance(v, (int, float)) or pd.isna(v):
        return ""
    if v >= 10:
        return "background-color:rgba(242,85,96,0.13);color:#F25560;font-weight:600"
    if v <= -5:
        return "background-color:rgba(77,144,240,0.13);color:#4D90F0;font-weight:600"
    return ""


def render_analyst_table(targets: pd.DataFrame, name_of: dict, price_of: dict,
                         price_fmt: str = "${:,.2f}") -> None:
    """targets(fetch_naver_targets 결과) + 현재가(price_of) → 컨센서스 표."""
    if targets is None or targets.empty:
        empty_state("애널리스트 컨센서스 준비 중")
        return

    rows, has_cov = [], False
    for _, r in targets.iterrows():
        tk = r["ticker"]
        tgt = r.get("목표가_평균")
        tgt = float(tgt) if pd.notna(tgt) else None
        px = price_of.get(tk)
        up = round((tgt / px - 1) * 100, 1) if (tgt and px) else None
        opinion = r.get("투자의견") or "—"
        # 현재가가 목표가를 웃돌면(여력<0) 매수의견과 충돌처럼 보임 → '목표가 하회' 명시
        if up is not None and up < 0 and opinion != "—":
            opinion = f"{opinion} · 목표가 하회"
        cov = r.get("커버리지")
        if pd.notna(cov):
            has_cov = True
        rows.append({
            "종목":     f"{name_of.get(tk, tk)}  ({tk})",
            "현재가":   px,
            "목표가":   tgt,
            "상승여력%": up,
            "투자의견": opinion,
            "기준일":   r.get("기준일") or "—",
            "커버리지": cov,
        })

    df = pd.DataFrame(rows)
    if not has_cov:                       # 미국 등 커버리지 없는 경우 컬럼 숨김
        df = df.drop(columns=["커버리지"])
    for c in ["현재가", "목표가", "상승여력%"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    fmt = {"현재가": price_fmt, "목표가": price_fmt, "상승여력%": "{:+.1f}%"}
    if "커버리지" in df.columns:
        df["커버리지"] = pd.to_numeric(df["커버리지"], errors="coerce")
        fmt["커버리지"] = "{:.0f}곳"

    def _rec(v):
        return _REC_COLOR.get(str(v).split(" · ")[0], "")

    styled = (df.style
              .map(_upside_style, subset=["상승여력%"])
              .map(_rec, subset=["투자의견"])
              .format(fmt, na_rep="—"))
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption(data_source_note("네이버 금융 컨센서스", cached="24시간",
                                extra="기준일=컨센서스 갱신일 · sell-side 집계라 매수 편향이 있을 수 있음"))
