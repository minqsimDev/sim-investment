"""보유 포트폴리오 히트맵(트리맵) — 내 비중·내 손익 한눈에.

타일 크기 = 평가금액(=비중), 색 = 수익률(이익 레드 / 손실 블루), 자산군 그룹.
시장용 cap_treemap(시총 랭크 100/rank 근사)과 달리 **값-비례** 크기라 개인 포트폴리오에 맞다.
보유 전종목을 타일로 깐다(평가금액>0). 색은 [[project_simvest_color_system]] 준수(빨강=이익/파랑=손실).
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# 한국식 발산 스케일: 음수(손실)=블루 / 0=무채 / 양수(이익)=레드
_SCALE = [[0.0, "#4D90F0"], [0.5, "#20242C"], [1.0, "#F25560"]]


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def portfolio_treemap(rows: list[dict], *, key: str = "pf",
                      name_key: str = "name", value_key: str = "market_value",
                      change_key: str = "gain_loss_pct", group_key: str = "category",
                      height: int = 420) -> None:
    """rows = 보유 종목 dict 리스트. 평가금액 있는 종목만 타일."""
    pts = []
    for r in rows or []:
        v = _f(r.get(value_key))
        if v is None or v <= 0:
            continue
        chg = _f(r.get(change_key)) or 0.0
        nm = str(r.get(name_key) or r.get("ticker") or "—").split("  ")[0]
        grp = (str(r.get(group_key) or "").strip() or "기타")
        pts.append((nm, grp, v, chg))
    if not pts:
        st.caption("표시할 보유 종목이 없습니다.")
        return

    maxabs = max((abs(c) for *_, c in pts), default=1.0) or 1.0
    labels, parents, values, colors, text = ["전체"], [""], [0.0], [0.0], [""]
    for g in dict.fromkeys(g for _, g, _, _ in pts):   # 자산군 노드(입력 순서 보존)
        labels.append(g); parents.append("전체"); values.append(0.0); colors.append(0.0)
        text.append(f"<b>{g}</b>")
    for nm, grp, v, chg in pts:
        labels.append(f"{nm}|{grp}")                   # 고유 id(자산군 결합) — 동명 충돌 방지
        parents.append(grp); values.append(v); colors.append(chg)
        text.append(f"{nm}<br>{chg:+.1f}%")

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values, branchvalues="remainder",
        marker=dict(colors=colors, colorscale=_SCALE, cmid=0.0, cmin=-maxabs, cmax=maxabs,
                    line=dict(width=1.4, color="#0E0F13")),
        text=text, textinfo="text",
        textfont=dict(size=12, color="#E7E9EE",
                      family="-apple-system,'Apple SD Gothic Neo',sans-serif"),
        hovertemplate="%{text}<extra></extra>",
        tiling=dict(pad=3), sort=True,
    ))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key=f"{key}_pftm")
    st.caption("타일 크기 = 평가금액(비중) · 색 = 수익률(이익 레드 / 손실 블루) · 자산군 클릭 시 확대")
