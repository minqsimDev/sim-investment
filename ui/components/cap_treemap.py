"""
시총 히트맵 트리맵 (STEP 2) — 시장 분위기를 한눈에.
- 타일 크기 = 시총(랭크 기반 근사 100/rank), 색 = 1D% 등락(상승 레드 / 하락 블루), 섹터 그룹핑
- 타일 텍스트 = 종목명 + 1D%
- 클릭: 네이티브 드릴(섹터→종목) + 선택 시 상세 칩(있으면)
전 시장 시총표 공용(미국 전체종목·한국 시총TOP10).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 한국식 등락색 발산 스케일 (음수=블루 / 0=무채 / 양수=레드)
_SCALE = [[0.0, "#4D90F0"], [0.5, "#20242C"], [1.0, "#F25560"]]


def cap_treemap(rows: list[dict], *, key: str, name_key: str, sector_key: str,
                rank_key: str, change_key: str = "1D %", height: int = 430) -> None:
    if not rows:
        st.caption("표시할 데이터가 없습니다.")
        return
    df = pd.DataFrame(rows)
    df["_chg"] = pd.to_numeric(df.get(change_key), errors="coerce").fillna(0.0)
    df["_rank"] = pd.to_numeric(df.get(rank_key), errors="coerce")
    df["_size"] = df["_rank"].apply(lambda r: 100.0 / r if isinstance(r, (int, float)) and r > 0 else 6.0)
    df["_nm"] = df[name_key].astype(str).str.split("  ").str[0]
    df["_sec"] = df.get(sector_key, "기타").astype(str).replace("", "기타").fillna("기타")
    maxabs = max(float(df["_chg"].abs().max() or 0), 1.0)

    labels, parents, values, colors, text, cdata = ["전체"], [""], [0.0], [0.0], [""], [0.0]
    for sec in df["_sec"].unique():
        labels.append(sec); parents.append("전체"); values.append(0.0)
        colors.append(0.0); text.append(f"<b>{sec}</b>"); cdata.append(0.0)
    for _, r in df.iterrows():
        labels.append(f'{r["_nm"]}|{r["_sec"]}')   # 고유 id(섹터 결합) — 동명 충돌 방지
        parents.append(r["_sec"]); values.append(float(r["_size"]))
        colors.append(float(r["_chg"]))
        text.append(f'{r["_nm"]}<br>{r["_chg"]:+.2f}%')
        cdata.append(float(r["_chg"]))

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values, branchvalues="remainder",
        marker=dict(colors=colors, colorscale=_SCALE, cmid=0.0, cmin=-maxabs, cmax=maxabs,
                    line=dict(width=1.4, color="#0E0F13")),
        text=text, textinfo="text",
        textfont=dict(size=12, color="#E7E9EE",
                      family="-apple-system,'Apple SD Gothic Neo',sans-serif"),
        customdata=cdata,
        hovertemplate="%{text}<extra></extra>",
        tiling=dict(pad=3),
        sort=True,
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key=f"{key}_tm")
    st.caption("타일 크기 = 시총(근사) · 색 = 1D% 등락(상승 레드 / 하락 블루) · 섹터 클릭 시 확대")
