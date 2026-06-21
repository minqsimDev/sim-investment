"""
시장 표 공용 슬림 컴포넌트 (STEP 1).
- 기본 3컬럼 지향: [이름/종목] · 현재가 · 1D% · 3M% · 추세 (+ 섹터/그룹 등 식별 컬럼)
- 우상단 '전체 컬럼 보기' 토글 → 1W·1M·MA20이격·변동성 펼침
- 행 클릭(single-row 선택) → 해당 종목 상세 칩 카드
- 히트맵은 1D%·3M% 셀에만, 값 크기 비례(상승 레드/하락 블루)
- 제목 아래 결론 한 줄 자동 생성(3M% 최상/최하 + breadth)
전 표 재사용 — 중복 구현 금지.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import layout as L  # 모바일 분기(표→카드) — 데스크탑은 기존 st.dataframe 유지

POS = "#F25560"   # 상승(레드)
NEG = "#4D90F0"   # 하락(블루)

_ALL_PCT = ["1D %", "1W %", "1M %", "3M %", "MA20 이격%"]
_EXTRA = ["1W %", "1M %", "MA20 이격%", "변동성(연)"]   # 토글/상세에서만 노출
_LEAD_OPT = ["순위", "섹터", "그룹", "단위"]             # 식별용 선행 컬럼
_HEAT = ["1D %", "3M %"]

_CSS = """<style>
.slim-detail{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  background:#16181F;border:1px solid #262A33;border-left:3px solid #D9A441;border-radius:12px;
  padding:10px 14px;margin:2px 0 10px}
.slim-detail .nm{font-size:12.5px;font-weight:900;color:#E7E9EE;margin-right:4px}
.slim-d-chip{font-size:11px;font-weight:750;color:#9AA0AD;background:#1E2029;border:1px solid #262A33;
  border-radius:999px;padding:4px 10px;font-variant-numeric:tabular-nums}
.slim-d-chip b{color:#7E8694;font-weight:850;margin-right:4px}
.slim-d-chip .pos{color:#F25560}.slim-d-chip .neg{color:#4D90F0}
</style>"""


def _heat_style(v, scale: float):
    if not isinstance(v, (int, float)) or pd.isna(v) or v == 0:
        return ""
    mag = min((abs(v) / scale) ** 0.7, 1.0)
    a = 0.05 + mag * 0.30
    if v > 0:
        return f"background-color:rgba(242,85,96,{a:.3f});color:{POS};font-weight:600"
    return f"background-color:rgba(77,144,240,{a:.3f});color:{NEG};font-weight:600"


def _trend_style(v):
    if v in ("상승", "bullish"):
        return f"color:{POS};font-weight:700"
    if v in ("하락", "bearish"):
        return f"color:{NEG};font-weight:700"
    return "color:#7E8694"


def _conclusion(df: pd.DataFrame, name_key: str) -> str:
    base = "3M %" if "3M %" in df.columns else ("1D %" if "1D %" in df.columns else None)
    if not base:
        return ""
    s = pd.to_numeric(df[base], errors="coerce")
    if s.notna().sum() == 0:
        return ""
    bcol = "1D %" if "1D %" in df.columns else base
    b = pd.to_numeric(df[bcol], errors="coerce")
    up, dn = int((b > 0).sum()), int((b < 0).sum())
    label = "3개월" if base == "3M %" else "오늘"
    ti, bi = s.idxmax(), s.idxmin()
    def _nm(i):
        return str(df.loc[i, name_key]).split("  ")[0]
    return (f"{label} 주도 {_nm(ti)} {s.loc[ti]:+.1f}% · 부진 {_nm(bi)} {s.loc[bi]:+.1f}% "
            f"· 상승 {up} · 하락 {dn}")


def _detail_card(r: pd.Series, name_key: str, price_key: str, price_fmt: str):
    name = str(r.get(name_key, "")).split("  ")[0]
    chips = []
    if price_key in r and pd.notna(r[price_key]):
        try:
            chips.append(("현재가", price_fmt.format(float(r[price_key])), ""))
        except (TypeError, ValueError):
            pass
    for c in ["1W %", "1M %", "MA20 이격%", "변동성(연)", "추세"]:
        if c not in r:
            continue
        v = r[c]
        if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
            continue
        cls = ""
        if isinstance(v, (int, float)) and c != "변동성(연)":
            cls = "pos" if v > 0 else ("neg" if v < 0 else "")
            v = f"{v:+.2f}%"
        elif c == "변동성(연)" and isinstance(v, (int, float)):
            v = f"{v:.2f}%"
        chips.append((c, v, cls))
    chips_html = "".join(
        f'<span class="slim-d-chip"><b>{c}</b><span class="{cls}">{v}</span></span>'
        for c, v, cls in chips
    )
    st.markdown(
        f'{_CSS}<div class="slim-detail"><span class="nm">{name}</span>{chips_html}</div>',
        unsafe_allow_html=True,
    )


def slim_table(rows: list[dict], *, key: str, name_key: str, price_key: str,
               price_fmt: str = "{:,.2f}", heat_scale: float = 8.0,
               show_conclusion: bool = True, col_toggle: bool = True) -> None:
    """슬림 3컬럼 표 + 전체컬럼 토글 + 행클릭 상세. 전 시장 표 공용."""
    if not rows:
        st.caption("표시할 데이터가 없습니다.")
        return
    df = pd.DataFrame(rows)
    drop = [c for c in df.columns if isinstance(c, str) and c.startswith("_")]
    df = df.drop(columns=drop, errors="ignore")

    if show_conclusion:
        c = _conclusion(df, name_key)
        if c:
            st.caption(c)

    # ── 모바일: 종목당 카드 1장 (st.dataframe 가로 스크롤 회피) ──
    # 데스크탑은 아래 기존 슬림 표(전체 컬럼 토글 + 행클릭 상세)를 그대로 사용한다.
    if L.is_mobile():
        disp = df.copy()
        for c in [x for x in _ALL_PCT if x in disp.columns]:
            disp[c] = pd.to_numeric(disp[c], errors="coerce").map(
                lambda v: f"{v:+.2f}%" if pd.notna(v) else "—")
        if price_key in disp.columns:
            disp[price_key] = pd.to_numeric(disp[price_key], errors="coerce").map(
                lambda v: price_fmt.format(v) if pd.notna(v) else "—")
        if "변동성(연)" in disp.columns:
            disp["변동성(연)"] = pd.to_numeric(disp["변동성(연)"], errors="coerce").map(
                lambda v: f"{v:.2f}%" if pd.notna(v) else "—")
        sub_col = next((c for c in ("섹터", "그룹", "단위") if c in disp.columns), None)
        L.render_table_or_cards(
            disp,
            title_col=name_key,
            subtitle_col=sub_col,
            price_col=price_key if price_key in disp.columns else None,
            change_cols=[c for c in ("1D %", "3M %") if c in disp.columns],
            detail_cols=[c for c in _EXTRA + ["추세"] if c in disp.columns],
        )
        return

    show_all = st.toggle("전체 컬럼 보기", key=f"{key}_all", value=False) if col_toggle else False

    pct_present = [c for c in _ALL_PCT if c in df.columns]
    slim_cols = [name_key]
    slim_cols += [c for c in _LEAD_OPT if c in df.columns]
    slim_cols += [c for c in [price_key, "1D %", "3M %", "추세"] if c in df.columns]
    full_cols = slim_cols + [c for c in _EXTRA if c in df.columns and c not in slim_cols]
    cols = [c for c in (full_cols if show_all else slim_cols) if c in df.columns]
    # 중복 제거(순서 보존)
    seen = set(); cols = [c for c in cols if not (c in seen or seen.add(c))]

    view = df[cols].copy()
    for c in [x for x in pct_present + [price_key, "변동성(연)"] if x in view.columns]:
        view[c] = pd.to_numeric(view[c], errors="coerce")

    styled = view.style
    heat_cols = [c for c in _HEAT if c in view.columns]
    if heat_cols:
        styled = styled.map(lambda v: _heat_style(v, heat_scale), subset=heat_cols)
    if "추세" in view.columns:
        styled = styled.map(_trend_style, subset=["추세"])
    fmt = {c: "{:+.2f}%" for c in pct_present if c in view.columns}
    if price_key in view.columns:
        fmt[price_key] = price_fmt
    if "변동성(연)" in view.columns:
        fmt["변동성(연)"] = "{:.2f}%"
    styled = styled.format(fmt, na_rep="—")

    event = st.dataframe(
        styled, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key=f"{key}_df",
    )
    try:
        sel = event.selection.rows
    except Exception:
        sel = []
    if sel:
        _detail_card(df.iloc[sel[0]], name_key, price_key, price_fmt)
