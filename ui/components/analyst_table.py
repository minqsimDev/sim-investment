"""애널리스트 컨센서스 — 미국·한국 공통(네이버 단일 소스).

산점도(X=상승여력% · Y=투자의견 1~5 · 점 크기=시총) + '표로 보기' 토글.
산점도 두 축 모두 네이버가 한/미 일관 제공(의견점수=recommMean). 신뢰도 신호로 기준일 노출.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import layout as L
from ui.components.dash_style import data_source_note, empty_state
from ui.components.analyst_scatter import analyst_scatter_fig

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


def _rows(targets: pd.DataFrame, name_of: dict, price_of: dict):
    """targets + 현재가 → 표시용 row 리스트. (rows, 커버리지 보유여부)."""
    out, has_cov = [], False
    for _, r in targets.iterrows():
        tk = r["ticker"]
        tgt = r.get("목표가_평균")
        tgt = float(tgt) if pd.notna(tgt) else None
        px = price_of.get(tk)
        up = round((tgt / px - 1) * 100, 1) if (tgt and px) else None
        opinion = r.get("투자의견") or "—"
        if up is not None and up < 0 and opinion != "—":
            opinion = f"{opinion} · 목표가 하회"
        score = r.get("의견점수")
        cov = r.get("커버리지")
        if pd.notna(cov):
            has_cov = True
        out.append({
            "_tk": tk, "_name": name_of.get(tk, tk),
            "_px": px, "_tgt": tgt, "_up": up,
            "_score": float(score) if pd.notna(score) else None,
            "종목": f"{name_of.get(tk, tk)}  ({tk})",
            "현재가": px, "목표가": tgt, "상승여력%": up,
            "투자의견": opinion, "기준일": r.get("기준일") or "—", "커버리지": cov,
        })
    return out, has_cov


def _render_table(rows: list[dict], has_cov: bool, price_fmt: str) -> None:
    cols = ["종목", "현재가", "목표가", "상승여력%", "투자의견", "기준일"] + (["커버리지"] if has_cov else [])
    df = pd.DataFrame([{c: r[c] for c in cols} for r in rows])
    for c in ["현재가", "목표가", "상승여력%"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    fmt = {"현재가": price_fmt, "목표가": price_fmt, "상승여력%": "{:+.1f}%"}
    if has_cov:
        df["커버리지"] = pd.to_numeric(df["커버리지"], errors="coerce")
        fmt["커버리지"] = "{:.0f}곳"

    def _rec(v):
        return _REC_COLOR.get(str(v).split(" · ")[0], "")

    styled = (df.style
              .map(_upside_style, subset=["상승여력%"])
              .map(_rec, subset=["투자의견"])
              .format(fmt, na_rep="—"))
    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_analyst_section(targets: pd.DataFrame, name_of: dict, price_of: dict,
                           rank_of: dict | None = None, price_fmt: str = "${:,.2f}",
                           key: str = "analyst") -> None:
    """산점도(여력×의견, 점=시총) + 표 토글. targets=fetch_naver_targets 결과."""
    if targets is None or targets.empty:
        empty_state("애널리스트 컨센서스 준비 중")
        return
    rows, has_cov = _rows(targets, name_of, price_of)
    rank_of = rank_of or {}

    def _fmt_px(v):
        return price_fmt.format(v) if isinstance(v, (int, float)) else "—"

    points = []
    for d in rows:
        if d["_up"] is None or d["_score"] is None:
            continue
        points.append({
            "name": d["_name"], "x": d["_up"], "y": d["_score"], "ticker": d["_tk"],
            "rank": rank_of.get(d["_tk"]),
            "hover": (f"{d['_name']}<br>현재가 {_fmt_px(d['_px'])} · 목표가 {_fmt_px(d['_tgt'])}"
                      f"<br>상승여력 {d['_up']:+.1f}% · {d['투자의견']} · 기준일 {d['기준일']}"),
        })

    fig = analyst_scatter_fig(points) if points else None
    if fig is not None:
        def _desktop():
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                            key=f"{key}_sc")
            st.caption("X=상승여력 · Y=투자의견(1 매도~5 매수) · 점 크기=시총 · 우상단=여력 크고 의견 강함 "
                       "· 라벨은 시총 상위 5(나머지 hover)")
        _mob = pd.DataFrame([{"종목": p["name"], "상승여력": f'{p["x"]:+.1f}%'} for p in points])
        L.only_desktop(_desktop)
        L.only_mobile(lambda: L.top_movers_list(_mob, name_col="종목", change_col="상승여력"))

    if st.toggle("표로 보기", key=f"{key}_tbl", value=(fig is None)):
        _render_table(rows, has_cov, price_fmt)

    st.caption(data_source_note("네이버 금융 컨센서스", cached="24시간",
                                extra="기준일=컨센서스 갱신일 · sell-side 집계라 매수 편향이 있을 수 있음"))
