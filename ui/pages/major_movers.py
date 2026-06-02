"""
Major Movers & Possible Drivers — Bloomberg-lite institutional monitoring page.
Detects significant intraday moves and infers possible causes in Korean.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from data.fetcher import fetch_all
from src.database import load_latest_indicator_summary, DEFAULT_DB
from src.mover_analysis import detect_major_movers, generate_movers_narrative
from ui.components.dash_style import (
    inject_css, section_header, timestamp_bar, numeric,
)


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load_data() -> dict:
    return fetch_all()


@st.cache_data(ttl=300)
def _load_db_summary() -> pd.DataFrame:
    return load_latest_indicator_summary(DEFAULT_DB)


# ── Styling helpers ────────────────────────────────────────────────────────────

def _color_cell(v) -> str:
    if not isinstance(v, (int, float)) or pd.isna(v):
        return ""
    if v > 0.005:
        return "background-color:#F0FFF6;color:#276749;font-weight:600"
    if v < -0.005:
        return "background-color:#FFF5F5;color:#9B2335;font-weight:600"
    return ""


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


def _show_movers_table(
    title_html: str,
    movers: list[dict],
    is_unusual: bool = False,
    caption: str = "",
) -> None:
    st.markdown(title_html, unsafe_allow_html=True)

    if not movers:
        st.info("해당 기준을 충족하는 자산 없음")
        return

    if is_unusual:
        df = _build_unusual_df(movers)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        df = _build_display_df(movers)
        pct_cols = [c for c in ["1D %", "1W %", "1M %"] if c in df.columns]
        df_numeric = numeric(df, pct_cols)
        styled = _style_movers(df_numeric)
        col_config: dict = {}
        for col in pct_cols:
            col_config[col] = st.column_config.NumberColumn(format="%.2f%%")
        st.dataframe(
            styled,
            column_config=col_config,
            hide_index=True,
            use_container_width=True,
        )

    if caption:
        st.caption(caption)


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    inject_css()

    # ── Header ────────────────────────────────────────────────────────────────
    hdr_col, btn_col = st.columns([9, 1])
    hdr_col.markdown("## 주요 이동 & 원인 분석")
    hdr_col.caption("주요 급등락 종목 및 가능한 원인 분석  ·  투자 참고용, 매매 권유 아님")

    if btn_col.button("↻ 새로고침", use_container_width=True):
        _load_data.clear()
        _load_db_summary.clear()

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner(""):
        data       = _load_data()
        db_summary = _load_db_summary()

    ts = data["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

    # ── Detect movers ─────────────────────────────────────────────────────────
    movers = detect_major_movers(data, db_summary)

    gainers = movers.get("gainers", [])
    losers  = movers.get("losers",  [])
    unusual = movers.get("unusual", [])

    total = len(gainers) + len(losers)

    # ── 1. Narrative summary ──────────────────────────────────────────────────
    st.markdown(
        section_header("오늘의 주요 이동 요약", f"급등 {len(gainers)}건 · 급락 {len(losers)}건 · 이상 변동 {len(unusual)}건"),
        unsafe_allow_html=True,
    )

    if total == 0 and not unusual:
        st.info("오늘은 기준 임계값을 초과하는 주요 이동이 감지되지 않았습니다.")
    else:
        narrative = generate_movers_narrative(movers, data)
        st.markdown(narrative)

    # ── 2. Gainers table ──────────────────────────────────────────────────────
    _show_movers_table(
        title_html=section_header(
            f"급등 자산 ({len(gainers)})",
            "1D% 기준 내림차순"
        ),
        movers=gainers,
        is_unusual=False,
        caption="투자 참고용 · 매매 권유 아님",
    )

    # ── 3. Losers table ───────────────────────────────────────────────────────
    _show_movers_table(
        title_html=section_header(
            f"급락 자산 ({len(losers)})",
            "1D% 기준 오름차순"
        ),
        movers=losers,
        is_unusual=False,
        caption="투자 참고용 · 매매 권유 아님",
    )

    # ── 4. Unusual moves table ────────────────────────────────────────────────
    _show_movers_table(
        title_html=section_header(
            f"이상 변동 ({len(unusual)})",
            "변동성 대비 이탈 또는 복합 시그널"
        ),
        movers=unusual,
        is_unusual=True,
        caption="투자 참고용 · 매매 권유 아님",
    )

    # ── 5. Detection criteria legend ─────────────────────────────────────────
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
| 변동성 대비 이탈 | \|1D%\| > 2.0 × max(20일·60일 변동성 / √252 × 100) | — | — |

**보정 근거** (실현 변동성 기준 1.0–1.5σ 수준으로 임계값 재조정)
- 고변동 주식(NVDA·AMD 등) 일일 1σ ≈ 2.8–4.7%  →  구 3.0% 기준은 0.7σ 수준으로 과감지
- 천연가스 일일 1σ ≈ 4.4–6.3%  →  구 1.5% 기준은 0.4σ 이하로 사실상 무의미
- 변동성 배수 2.0× = 업계 표준 "주목할 만한 이탈" 기준 (구 1.5× ≈ 하루 13% 확률로 발동)
- FX 주간 2.5%/월간 4%: 5% KRW 주간 이동은 실질 위기 수준으로 너무 둔감

**주의 사항**
- 가능한 원인은 패턴 기반 추론이며 확정적 원인이 아닙니다.
- DB 데이터(`python main.py` 실행)가 있을 때 주간·월간·변동성 분석이 가능합니다.
- 본 페이지는 투자 참고용이며 매매 권유가 아닙니다.
        """)
