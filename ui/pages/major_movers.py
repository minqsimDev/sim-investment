"""
Major Movers & Possible Drivers — Bloomberg-lite institutional monitoring page.
Detects significant intraday moves and infers possible causes in Korean.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.loader import load_market_data
from src.database import load_latest_indicator_summary, DEFAULT_DB
from src.mover_analysis import detect_major_movers
from ui.components.dash_style import (
    inject_css, jj_footer, mark_active_nav, numeric, show_skeleton,
    mkt_page_header, mkt_section_header, bar_color, color_change,
)


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_db_summary() -> pd.DataFrame:
    return load_latest_indicator_summary(DEFAULT_DB)


# ── Styling helpers ────────────────────────────────────────────────────────────

def _color_cell(v) -> str:
    if not isinstance(v, (int, float)) or pd.isna(v) or v == 0:
        return ""
    mag = min((abs(v) / 8.0) ** 0.7, 1.0)   # 값 크기에 비례한 농도 (R7)
    a = 0.05 + mag * 0.30
    if v > 0:
        return f"background-color:rgba(242,85,96,{a:.3f});color:#F25560;font-weight:600"
    return f"background-color:rgba(77,144,240,{a:.3f});color:#4D90F0;font-weight:600"


def _build_display_df(movers: list[dict]) -> pd.DataFrame:
    """Convert mover dicts to display DataFrame with Korean column names."""
    rows = []
    for m in movers:
        chg_1w = f"{m['change_1w']:+.2f}%" if m["change_1w"] is not None else "—"
        chg_1m = f"{m['change_1m']:+.2f}%" if m["change_1m"] is not None else "—"
        rows.append({
            "자산":           m["asset"],
            "분류":           m["category"],
            "1D %":           m["change_1d"],
            "1W %":           m["change_1w"],
            "1M %":           m["change_1m"],
            "이동 유형":      m["move_type"],
            "가능한 원인":    m["possible_driver"],
            "포트폴리오 관련도": m["portfolio_relevance"],
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["자산", "분류", "1D %", "1W %", "1M %", "이동 유형", "가능한 원인", "포트폴리오 관련도"]
    )


def _build_unusual_df(movers: list[dict]) -> pd.DataFrame:
    """Build unusual-moves display DataFrame."""
    rows = []
    for m in movers:
        rows.append({
            "자산":           m["asset"],
            "분류":           m["category"],
            "이동 유형":      m["move_type"],
            "감지 이유":      f"1D {m['change_1d']:+.2f}%",
            "가능한 원인":    m["possible_driver"],
            "모니터링 포인트": ", ".join(m.get("related_indicators", [])[:4]),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["자산", "분류", "이동 유형", "감지 이유", "가능한 원인", "모니터링 포인트"]
    )


def _style_movers(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    """Apply conditional color formatting to 1D %, 1W %, 1M % columns."""
    numeric_cols = [c for c in ["1D %", "1W %", "1M %"] if c in df.columns]
    styled = df.style
    if numeric_cols:
        styled = styled.map(_color_cell, subset=numeric_cols)
    return styled


# ── 전체 탭 재구성: 요약 카드 + 행 상세 ─────────────────────────────────────────
_MV_CSS = """<style>
.mv-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:2px 0 14px}
@media(max-width:760px){.mv-cards{grid-template-columns:1fr}}
.mv-card{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:14px 16px;
  position:relative;overflow:hidden;box-shadow:0 6px 18px rgba(0,0,0,.25)}
.mv-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px}
.mv-card.red::before{background:#F25560}.mv-card.blue::before{background:#4D90F0}.mv-card.gold::before{background:#D9A441}
.mv-k{font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7E8694;margin-bottom:6px}
.mv-card.red .mv-k{color:#F25560}.mv-card.blue .mv-k{color:#4D90F0}.mv-card.gold .mv-k{color:#D9A441}
.mv-v{font-size:20px;font-weight:950;color:#E7E9EE;line-height:1.1;font-variant-numeric:tabular-nums;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mv-v small{font-size:13px;font-weight:700;color:#8A999B;margin-left:2px}
/* 오늘의 톱: 긴 종목명 overflow 방지 — 이름 ellipsis + 등락률 고정 */
.mv-vflex{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.mv-vflex .mv-nm{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:15px}
.mv-pct{font-size:15px;font-weight:900;flex-shrink:0}.mv-pct.pos{color:#F25560}.mv-pct.neg{color:#4D90F0}
.mv-s{font-size:11px;font-weight:700;color:#7E8694;margin-top:5px;line-height:1.4;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mv-detail{display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:#16181F;
  border:1px solid #262A33;border-left:3px solid #D9A441;border-radius:12px;padding:10px 14px;margin:2px 0 10px}
.mv-d-nm{font-size:12.5px;font-weight:900;color:#E7E9EE;margin-right:4px}
.mv-d-chip{font-size:11px;font-weight:750;color:#9AA0AD;background:#1E2029;border:1px solid #262A33;
  border-radius:999px;padding:4px 10px;font-variant-numeric:tabular-nums}
.mv-d-chip b{color:#7E8694;font-weight:850;margin-right:4px}
.mv-d-chip .pos{color:#F25560}.mv-d-chip .neg{color:#4D90F0}
.mv-d-driver{flex-basis:100%;font-size:11.5px;font-weight:650;color:#9AA0AD;line-height:1.5;margin-top:2px}
</style>"""


def _held_tickers() -> set[str]:
    """로그인 유저의 '실제' 보유 티커 집합(세션). 크립토는 BTC↔BTC-USD 양형 포함.
    '직접 보유'는 워치리스트(my_etfs)가 아니라 이 실보유 기준이어야 함(유령 보유 방지)."""
    out: set[str] = set()
    for h in (st.session_state.get("brokerage_holdings") or []):
        tk = str(h.get("ticker") or "").upper().strip()
        if not tk:
            continue
        out.add(tk)
        out.add(tk.removesuffix("-USD"))
        if not tk.endswith("-USD"):
            out.add(f"{tk}-USD")
    return out


def _mv_held(m: dict) -> bool:
    return bool(m.get("_held"))   # render()에서 실보유 티커로 태깅(아래 _held_tickers)


def _mv_detail(m: dict) -> None:
    def _chip(label, val, cls=""):
        return f'<span class="mv-d-chip"><b>{label}</b><span class="{cls}">{val}</span></span>'
    chips = _chip("분류", m.get("category", "—"))
    w, mo = m.get("change_1w"), m.get("change_1m")
    if isinstance(w, (int, float)):
        chips += _chip("1W", f"{w:+.2f}%", "pos" if w > 0 else "neg")
    if isinstance(mo, (int, float)):
        chips += _chip("1M", f"{mo:+.2f}%", "pos" if mo > 0 else "neg")
    drv = (m.get("possible_driver") or "").strip()
    body = f'<div class="mv-d-driver">{drv}</div>' if drv else ""
    st.markdown(f'{_MV_CSS}<div class="mv-detail"><span class="mv-d-nm">{m["asset"]}</span>{chips}{body}</div>',
                unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render(embedded: bool = False) -> None:
    if not embedded:
        inject_css()
        mark_active_nav("/market")
        # ── Header ──────────────────────────────────────────────────────────────
        st.markdown(mkt_page_header("📈", "전체 — 전 자산 크로스 비교", "당일 급등락 자산 감지 · 가능한 원인 분석"), unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    ph = show_skeleton()
    data       = load_market_data()
    db_summary = _load_db_summary()
    ph.empty()

    # ── Detect movers ─────────────────────────────────────────────────────────
    movers = detect_major_movers(data, db_summary)

    gainers = movers.get("gainers", [])
    losers  = movers.get("losers",  [])
    unusual = movers.get("unusual", [])

    # '직접 보유' 태깅 — 워치리스트가 아니라 세션의 실제 보유 티커 기준(유령 보유 표시 방지)
    _held = _held_tickers()
    for _m in gainers + losers + unusual:
        _m["_held"] = str(_m.get("ticker") or "").upper().strip() in _held

    total = len(gainers) + len(losers)

    # ── 1. 요약 카드 3장 — 게스트=시장 TOP, 로그인=내 보유 ──────────────────────
    is_guest = st.session_state.get("auth_role") == "guest"
    top = max(gainers, key=lambda m: m["change_1d"]) if gainers else None
    if top:
        top_html = (f'<div class="mv-card gold"><div class="mv-k">오늘의 톱</div>'
                    f'<div class="mv-v mv-vflex"><span class="mv-nm">{top["asset"]}</span>'
                    f'<span class="mv-pct pos">+{top["change_1d"]:.2f}%</span></div>'
                    f'<div class="mv-s">최대 상승 종목</div></div>')
    else:
        top_html = ('<div class="mv-card gold"><div class="mv-k">오늘의 톱</div>'
                    '<div class="mv-v">—</div><div class="mv-s">급등 자산 없음</div></div>')

    if is_guest:
        g3 = " · ".join(m["asset"] for m in sorted(gainers, key=lambda m: m["change_1d"], reverse=True)[:3])
        l3 = " · ".join(m["asset"] for m in sorted(losers, key=lambda m: m["change_1d"])[:3])
        c1 = (f'<div class="mv-card red"><div class="mv-k">오늘 급등</div>'
              f'<div class="mv-v">{len(gainers)}<small>건</small></div>'
              f'<div class="mv-s">{g3 or "해당 없음"}</div></div>')
        c2 = (f'<div class="mv-card blue"><div class="mv-k">오늘 급락</div>'
              f'<div class="mv-v">{len(losers)}<small>건</small></div>'
              f'<div class="mv-s">{l3 or "해당 없음"}</div></div>')
    else:
        hg = [m for m in gainers if _mv_held(m)]
        hl = [m for m in losers if _mv_held(m)]
        c1 = (f'<div class="mv-card red"><div class="mv-k">내 보유 급등</div>'
              f'<div class="mv-v">{len(hg)}<small>건</small></div>'
              f'<div class="mv-s">{(" · ".join(m["asset"] for m in hg[:3])) or "해당 없음"}</div></div>')
        c2 = (f'<div class="mv-card blue"><div class="mv-k">내 보유 급락</div>'
              f'<div class="mv-v">{len(hl)}<small>건</small></div>'
              f'<div class="mv-s">{(" · ".join(m["asset"] for m in hl[:3])) or "해당 없음"}</div></div>')
    st.markdown(_MV_CSS + '<div class="mv-cards">' + c1 + c2 + top_html + '</div>',
                unsafe_allow_html=True)

    # ── 2. 다이버징 바 (급등·급락 TOP) ──────────────────────────────────────────
    if total == 0 and not unusual:
        st.info("오늘은 기준 임계값을 초과하는 주요 이동이 감지되지 않았습니다.")
    else:
        top_gainers = sorted(gainers, key=lambda x: x["change_1d"], reverse=True)[:8]
        top_losers = sorted(losers, key=lambda x: x["change_1d"])[:8]
        chart_rows = sorted(top_gainers + top_losers, key=lambda x: x["change_1d"])
        labels = [m["asset"] for m in chart_rows]
        values = [m["change_1d"] for m in chart_rows]
        max_abs = max((abs(v) for v in values), default=1) or 1
        bar_colors = []
        for v in values:
            a = 0.35 + min(abs(v) / max_abs, 1.0) * 0.55
            rgb = "242,85,96" if v >= 0 else "77,144,240"
            bar_colors.append(f"rgba({rgb},{a:.2f})")
        texts = [f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%" for v in values]
        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h", marker_color=bar_colors,
            text=texts, textposition="outside", textfont=dict(size=9, color="#9AA0AD"),
            cliponaxis=False,
        ))
        fig.update_layout(
            margin=dict(l=0, r=70, t=6, b=2),   # 상단 잘림/빈 공간 정리
            height=min(520, max(200, len(chart_rows) * 28 + 36)),
            paper_bgcolor="rgba(22,24,31,0.97)", plot_bgcolor="#0E0F13",
            xaxis=dict(showgrid=True, gridcolor="#262A33", zeroline=True,
                       zerolinecolor="#3A4150", zerolinewidth=2,
                       tickformat="+.1f", ticksuffix="%", tickfont=dict(size=9, color="#7E8694")),
            yaxis=dict(tickfont=dict(size=10, color="#E7E9EE"), showgrid=False, automargin=True),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── 3. 단일 슬림 표 — 게스트=TOP 10, 로그인=내 보유 강조 ───────────────────
    mv = gainers + losers
    if mv:
        show_all = st.toggle("전체 보기", key="mv_all", value=False)
        if is_guest:
            # 게스트: 내 종목 개념 없음 → 변동 큰 순 TOP만(보유 컬럼·강조 없음)
            mv_sorted = sorted(mv, key=lambda m: -abs(m["change_1d"]))
            display = mv_sorted if show_all else mv_sorted[:10]
            df = numeric(pd.DataFrame([{"자산": m["asset"], "1D %": m["change_1d"],
                                        "분류": m.get("category", "—")} for m in display]), ["1D %"])
            sty = (df.style.map(_color_cell, subset=["1D %"])
                   .format({"1D %": "{:+.2f}%"}, na_rep="—"))
            cap = f"기본 노출 = 변동 큰 순 상위 10개 · 전체 {len(mv)}건은 '전체 보기' · 행 클릭 시 1W·1M·원인"
        else:
            mv_sorted = sorted(mv, key=lambda m: (0 if _mv_held(m) else 1, -abs(m["change_1d"])))
            held_rows = [m for m in mv_sorted if _mv_held(m)]
            rest_rows = [m for m in mv_sorted if not _mv_held(m)]
            display = mv_sorted if show_all else (held_rows + rest_rows[:10])
            df = numeric(pd.DataFrame([{
                "자산": m["asset"], "1D %": m["change_1d"], "분류": m.get("category", "—"),
                "보유": "● 직접 보유" if _mv_held(m) else "",
            } for m in display]), ["1D %"])
            held_pos = [i for i, m in enumerate(display) if _mv_held(m)]
            def _row_gold(row):
                return ["box-shadow:inset 4px 0 0 #D9A441" if (row.name in held_pos and i == 0) else ""
                        for i in range(len(row))]
            sty = (df.style
                   .map(_color_cell, subset=["1D %"])
                   .apply(_row_gold, axis=1)
                   .map(lambda v: "color:#D9A441;font-weight:800" if v else "", subset=["보유"])
                   .format({"1D %": "{:+.2f}%"}, na_rep="—"))
            cap = f"기본 노출 = 내 보유 + 상위 10개 · 전체 {len(mv)}건은 '전체 보기' · 행 클릭 시 1W·1M·원인"
        ev = st.dataframe(sty, use_container_width=True, hide_index=True,
                          on_select="rerun", selection_mode="single-row", key="mv_df")
        try:
            sel = ev.selection.rows
        except Exception:
            sel = []
        if sel:
            _mv_detail(display[sel[0]])
        st.caption(cap)

    # ── 4. Detection criteria legend ─────────────────────────────────────────
    with st.expander("감지 기준 보기", expanded=False):
        st.markdown(r"""
| 자산 유형 | 일간 임계값 | 주간 플래그 | 월간 플래그 |
|---|---|---|---|
| 광역 ETF (SPY·QQQ·GLD 등) | \|1D%\| ≥ 1.5% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| 섹터 ETF (SOXX·AI·China 등) | \|1D%\| ≥ 2.5% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| 미국 주식 (일반) | \|1D%\| ≥ 3.0% | \|1W%\| ≥ 7.5% | \|1M%\| ≥ 15% |
| 고변동 주식 (NVDA·AMD·TSLA·PLTR 등) | \|1D%\| ≥ 5.0% | \|1W%\| ≥ 10% | \|1M%\| ≥ 20% |
| 금 | \|1D%\| ≥ 1.25% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| 은 | \|1D%\| ≥ 2.5% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| 구리 | \|1D%\| ≥ 2.0% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| WTI/브렌트 원유 | \|1D%\| ≥ 3.0% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| 천연가스 | \|1D%\| ≥ 5.0% | \|1W%\| ≥ 5% | \|1M%\| ≥ 10% |
| USD/KRW · DXY | \|1D%\| ≥ 0.5% | \|1W%\| ≥ 2.5% | \|1M%\| ≥ 4% |
| JPY 통화쌍 | \|1D%\| ≥ 0.7% | \|1W%\| ≥ 2.5% | \|1M%\| ≥ 4% |
| 비트코인 (BTC) | \|1D%\| ≥ 3.0% | \|1W%\| ≥ 10% | \|1M%\| ≥ 20% |
| 이더리움 (ETH) | \|1D%\| ≥ 4.0% | \|1W%\| ≥ 15% | \|1M%\| ≥ 30% |
| 솔라나 등 고변동 코인 | \|1D%\| ≥ 5.0% | \|1W%\| ≥ 20% | \|1M%\| ≥ 40% |
| 변동성 대비 이탈 | \|1D%\| > 2.0 × max(20일·60일 변동성 / √252 × 100) | — | — |

**보정 근거** (실현 변동성 기준 1.0–1.5σ 수준으로 임계값 재조정)
- 고변동 주식(NVDA·AMD 등) 일일 1σ ≈ 2.8–4.7%  →  구 3.0% 기준은 0.7σ 수준으로 과감지
- 천연가스 일일 1σ ≈ 4.4–6.3%  →  구 1.5% 기준은 0.4σ 이하로 사실상 무의미
- 변동성 배수 2.0× = 업계 표준 "주목할 만한 이탈" 기준 (구 1.5× ≈ 하루 13% 확률로 발동)
- FX 주간 2.5%/월간 4%: 5% KRW 주간 이동은 실질 위기 수준으로 너무 둔감

**주의 사항**
- 가능한 원인은 패턴 기반 추론이며 확정적 원인이 아닙니다.
- DB 데이터(`python main.py` 실행)가 있을 때 주간·월간·변동성 분석이 가능합니다.
        """)

    # disclaimer는 페이지 하단 1회만 (표마다 반복 제거)
    st.caption("데이터는 실시간이 아닐 수 있습니다")
    if not embedded:
        st.markdown(jj_footer(), unsafe_allow_html=True)
