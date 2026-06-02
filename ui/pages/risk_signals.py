import streamlit as st
import pandas as pd

from data.fetcher import fetch_all
from src.database import load_latest_risk_signals, load_signal_history, DEFAULT_DB
from src.risk import compute_regime_signals
from ui.components.dash_style import inject_css, section_header, timestamp_bar

_SIG_KOR = {
    "Risk-on / Risk-off":      "위험선호 지수",
    "Dollar Strength":         "달러 강도",
    "Rate Pressure":           "금리 압력",
    "Tech Momentum":           "기술주 모멘텀",
    "Semiconductor Momentum":  "반도체 모멘텀",
    "Commodity Momentum":      "원자재 모멘텀",
    "Korea FX Risk":           "원화 환율 리스크",
}

_LEVEL_KOR = {
    "NEUTRAL": "중립", "MEDIUM": "중간", "HIGH": "높음", "LOW": "낮음",
    "RISING": "상승", "FALLING": "하락", "FLAT": "보합",
    "RISK-ON": "위험선호", "RISK-OFF": "위험회피",
    "BULLISH": "상승", "BEARISH": "하락", "STRONG": "강세", "WEAK": "약세",
}


@st.cache_data(ttl=300)
def _load_live():
    return fetch_all()


def render():
    inject_css()
    st.markdown("## 리스크 모니터")
    st.caption("시장 리스크 모니터링 — 투자 참고용, 매매 권유 아님")

    # Try DB first, fall back to live computation
    db_signals = load_latest_risk_signals(DEFAULT_DB)
    use_db = not db_signals.empty

    if use_db:
        run_date = db_signals["run_date"].iloc[0]
        st.markdown(timestamp_bar(run_date, note="main.py 마지막 실행 기준"), unsafe_allow_html=True)
        signals = [
            {"signal": r["signal_name"], "lv": r["level"], "col": _col_from_level(r["level"]),
             "note": r["comment"]}
            for _, r in db_signals.iterrows()
        ]
        source_note = f"DB 데이터  (run_date: {run_date})"
    else:
        with st.spinner("실시간 데이터로 신호 계산 중..."):
            data = _load_live()
        ts = data["fetched_at"][:19].replace("T", " ")
        st.markdown(timestamp_bar(ts, note="yfinance 실시간"), unsafe_allow_html=True)
        signals = compute_regime_signals(data)
        source_note = "실시간 계산 (`python main.py` 실행 후 DB에 저장됩니다)"

    st.caption(f"데이터 출처: {source_note}")
    st.markdown(section_header("시장 국면 신호"), unsafe_allow_html=True)
    st.markdown(_signals_html(signals), unsafe_allow_html=True)

    # ── Historical risk signal trend ──────────────────────────────────────────
    if use_db:
        try:
            hist = load_signal_history(limit=70, db_path=DEFAULT_DB)
            if not hist.empty and hist["run_date"].nunique() > 1:
                st.markdown(section_header("신호 이력", "최근 10회 실행 기록"), unsafe_allow_html=True)
                pivot = hist.pivot_table(index="run_date", columns="signal_name",
                                         values="level", aggfunc="last")
                pivot = pivot.sort_index(ascending=False).head(10)
                st.dataframe(pivot, use_container_width=True)
        except Exception:
            pass

    # ── Legend ────────────────────────────────────────────────────────────────
    with st.expander("신호 해석 가이드", expanded=False):
        st.markdown("""
| 색상 | 의미 |
|---|---|
| 🟢 GREEN (low/bullish/risk-on/weak) | 위험 낮음 / 우호적 환경 |
| 🟡 AMBER (medium/neutral) | 중립 / 주의 |
| 🔴 RED (high/bearish/risk-off/strong) | 위험 높음 / 주의 필요 |

**모니터링 원칙**
- 본 신호는 참고용이며 매매 권유가 아닙니다.
- 여러 신호가 동시에 RED이면 포트폴리오 전체 리스크를 점검하세요.
- 환헤지 ETF는 Korea FX Risk 신호 영향을 받지 않습니다.
        """)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _col_from_level(lv: str) -> str:
    """Map saved level string back to CSS color class."""
    lv = (lv or "").upper()
    if lv in ("HIGH", "RISK-OFF", "BEARISH", "STRONG"):
        return "high"
    if lv in ("LOW", "RISK-ON", "BULLISH", "WEAK", "FALLING"):
        return "low"
    if lv == "N/A":
        return "na"
    return "mid"


def _signals_html(signals: list[dict]) -> str:
    thead = '<thead><tr><th>신호</th><th>단계</th><th>설명</th></tr></thead>'
    rows = [
        f'<tr><td class="sig">{_SIG_KOR.get(s["signal"], s["signal"])}</td>'
        f'<td><span class="rl-{s["col"]}">{_LEVEL_KOR.get(s["lv"].upper(), s["lv"])}</span></td>'
        f'<td class="cmt">{s["note"]}</td></tr>'
        for s in signals
    ]
    return f'<div class="fin-t"><table>{thead}<tbody>{"".join(rows)}</tbody></table></div>'
