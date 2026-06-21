import html as html_lib
import math

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

import layout as L  # 반응형(뷰포트 감지 + 모바일 CSS)
from data.loader import load_market_data, load_risk_signals_cached
from src.database import DEFAULT_DB
from src.risk import compute_regime_signals


@st.cache_data(ttl=1800, show_spinner=False)
def _cached_regime_signals(fetched_at: str) -> list[dict]:
    """Cache regime-signal output keyed by market-data timestamp."""
    return compute_regime_signals(load_market_data())
from ui.components.dash_style import (
    glossary_expander,
    inject_css, show_skeleton,
    jj_footer, mark_active_nav, mkt_page_header,
)

_SIG_KOR = {
    "Risk-on / Risk-off":      "위험선호·회피",
    "Dollar Strength":         "달러 강세",
    "Rate Pressure":           "금리 부담",
    "Tech Momentum":           "AI·기술주 모멘텀",
    "Semiconductor Momentum":  "반도체 모멘텀",
    "Commodity Momentum":      "원자재 모멘텀",
    "Korea FX Risk":           "원/달러 환율",
}

_LEVEL_KOR = {
    "NEUTRAL": "중립", "MEDIUM": "중간", "HIGH": "높음", "LOW": "낮음",
    "RISING": "상승", "FALLING": "하락", "FLAT": "보합",
    "RISK-ON": "위험선호", "RISK-OFF": "위험회피",
    "BULLISH": "상승세", "BEARISH": "하락세", "STRONG": "강세", "WEAK": "약세",
}


_RISK_LOCAL_CSS = """<style>
/* 셸·네비·페이지 헤더는 공용(dash_style) 기준 그대로 사용 — 페이지 간 그리드 일치 */
/* ── KPI row ── */
.rsk-kpi-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:0 0 14px}
@media(max-width:860px){.rsk-kpi-row{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.rsk-kpi-row{grid-template-columns:1fr}}
.rsk-kpi{background:#16181F;border:1px solid #262A33;border-radius:20px;
  padding:18px 20px;box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-kpi-lbl{font-size:11px;font-weight:700;color:#7E8694;letter-spacing:.04em;
  text-transform:uppercase;margin-bottom:8px}
.rsk-kpi-num{font-size:34px;font-weight:900;line-height:1;color:#E7E9EE;
  font-family:'SF Mono',ui-monospace,monospace;margin-bottom:7px}
.rsk-kpi-num.danger{color:#F25560}.rsk-kpi-num.warn{color:#D9A441}.rsk-kpi-num.pos{color:#4D90F0}
.rsk-kpi-chip{display:inline-flex;align-items:center;border-radius:999px;padding:3px 10px;
  font-size:10.5px;font-weight:700;margin-bottom:6px}
.rsk-kpi-chip.danger{background:rgba(242,85,96,0.13);color:#F25560}
.rsk-kpi-chip.warn{background:rgba(217,164,65,0.13);color:#D9A441}
.rsk-kpi-chip.pos{background:rgba(77,144,240,0.13);color:#4D90F0}
.rsk-kpi-sub{font-size:11px;color:#8A999B;font-weight:600;line-height:1.4}
/* ── Action bar ── */
.rsk-action-bar{background:#1C1F27;border:1px solid #262A33;border-left:3px solid #D9A441;
  border-radius:18px;padding:14px 22px;
  display:flex;align-items:center;gap:18px;margin-bottom:16px;flex-wrap:wrap}
.rsk-action-bar-lbl{font-size:10px;font-weight:900;color:#D9A441;text-transform:uppercase;
  letter-spacing:.1em;flex-shrink:0}
.rsk-action-bar-body{flex:1;min-width:0}
.rsk-action-bar-text{font-size:13px;font-weight:700;color:#E7E9EE;line-height:1.45}
.rsk-action-bar-dot{color:#7E8694;margin:0 5px;font-size:11px}
/* ── Body 2-col (게이지 | 신호 매트릭스) ── */
.rsk-body3{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);
  gap:16px;align-items:start;margin-bottom:16px}
@media(max-width:760px){.rsk-body3{grid-template-columns:1fr}}
/* ── Cards ── */
.rsk-card{background:#16181F;border:1px solid #262A33;border-radius:20px;padding:20px;
  box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-card-title{font-size:11px;font-weight:800;color:#7E8694;letter-spacing:.05em;
  text-transform:uppercase;margin-bottom:12px}
/* 내 포트폴리오 리스크 카드 — 위험 레드 / 주의 골드 좌측 바 */
.rsk-myr-sub{font-size:10px;font-weight:700;color:#7E8694;letter-spacing:0;text-transform:none;margin-left:8px}
.rsk-myr-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
@media(max-width:760px){.rsk-myr-grid{grid-template-columns:1fr}}
.rsk-myr{background:#1E2029;border:1px solid #262A33;border-left:3px solid #3A3F48;
  border-radius:12px;padding:12px 14px}
.rsk-myr.danger{border-left-color:#F25560;background:linear-gradient(135deg,rgba(242,85,96,.08),#1E2029 60%)}
.rsk-myr.warn{border-left-color:#D9A441}
.rsk-myr-k{font-size:11px;font-weight:850;color:#9AA0AD;margin-bottom:6px}
.rsk-myr.danger .rsk-myr-k{color:#F25560}
.rsk-myr-v{font-size:22px;font-weight:950;font-variant-numeric:tabular-nums;color:#E7E9EE;line-height:1}
.rsk-myr.danger .rsk-myr-v{color:#F25560}
.rsk-myr-b{font-size:11px;font-weight:700;color:#9AA0AD;line-height:1.45;margin-top:7px}
/* ── Gauge mini-stats ── */
.rsk-mini-stats{display:flex;gap:10px;margin-top:12px;padding-top:12px;border-top:1px solid #262A33;align-items:center}
.rsk-mini-stat{font-size:10px;font-weight:700;color:#8A999B}
.rsk-mini-stat .n{font-size:16px;font-weight:900;display:block;margin-bottom:1px;font-family:'SF Mono',ui-monospace,monospace}
.rsk-mini-stat.h .n{color:#F25560}
.rsk-mini-stat.m .n{color:#D9A441}
.rsk-mini-stat.l .n{color:#4D90F0}
.rsk-mini-sep{width:1px;height:24px;background:#262A33;flex-shrink:0}
.rsk-mini-interp{font-size:11px;font-weight:800;margin-left:auto;padding:4px 10px;border-radius:8px}
/* 게이지 대응모드 칩 — 레드(=상승)·블루(=하락) 충돌 회피: 중립→골드→앰버 단계로만 위험 표현 */
.rsk-mini-interp.risk{color:#E8883A;background:rgba(232,136,58,0.14)}
.rsk-mini-interp.warn{color:#D9A441;background:rgba(217,164,65,0.13)}
.rsk-mini-interp.good{color:#9AA0AD;background:rgba(154,160,173,0.12)}
/* ── Signal groups ── */
.rsk-groups{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:stretch}
@media(max-width:760px){.rsk-groups{grid-template-columns:1fr}}
.rsk-group{min-width:0;border-radius:14px;border:1px solid #262A33;overflow:hidden;display:flex;flex-direction:column}
.rsk-group-head{display:flex;align-items:center;gap:7px;padding:9px 12px;font-size:12px;font-weight:800}
.rsk-group-cnt{margin-left:auto;font-size:10.5px;font-weight:700;opacity:.6}
.rsk-group-head.high{background:rgba(242,85,96,0.12);color:#F25560;border-bottom:1px solid rgba(242,85,96,.15)}
.rsk-group-head.mid{background:rgba(228,130,59,0.12);color:#D9A441;border-bottom:1px solid rgba(228,130,59,.15)}
.rsk-group-head.low{background:rgba(77,144,240,0.12);color:#4D90F0;border-bottom:1px solid rgba(77,144,240,.15)}
.rsk-group-head.na{background:rgba(14,15,19,0.5);color:#7E8694;border-bottom:1px solid #262A33}
.rsk-group-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.rsk-group-head.high .rsk-group-dot{background:#F25560}
.rsk-group-head.mid  .rsk-group-dot{background:#D9A441}
.rsk-group-head.low  .rsk-group-dot{background:#4D90F0}
.rsk-group-head.na   .rsk-group-dot{background:#7E8694}
.rsk-sig-list{background:#16181F;display:flex;flex-direction:column}
.rsk-sig-item{padding:10px 12px;border-top:1px solid #262A33}
.rsk-sig-list>:first-child{border-top:none}
.rsk-sig-row{display:flex;align-items:center;gap:5px;margin-bottom:3px}
.rsk-sig-name{font-size:12px;font-weight:700;color:#E7E9EE}
.rsk-sig-pin{font-size:9px;font-weight:700;color:#7E8694;border:1px solid #262A33;border-radius:4px;padding:1px 4px}
.rsk-sig-note{font-size:11px;color:#7E8694;line-height:1.5}
.rsk-sig-item.muted .rsk-sig-name{color:#8A999B}
.rsk-sig-item.muted .rsk-sig-note{color:#8A999B}
.rsk-sig-badge{margin-left:auto;font-size:10px;font-weight:800;padding:2px 8px;border-radius:5px;white-space:nowrap;flex-shrink:0}
.rsk-sig-badge.high{background:rgba(242,85,96,0.13);color:#F25560}
.rsk-sig-badge.mid{background:rgba(217,164,65,0.13);color:#D9A441}
.rsk-sig-badge.low{background:rgba(77,144,240,0.13);color:#4D90F0}
.rsk-sig-badge.na{background:rgba(14,15,19,0.5);color:#7E8694}
/* ── Signal matrix ── */
.rsk-matrix{display:grid;gap:0;border:1px solid #262A33;border-radius:16px;overflow:hidden;background:#16181F}
.rsk-matrix-head,.rsk-matrix-row{display:grid;grid-template-columns:minmax(112px,1.05fr) 76px minmax(190px,1.45fr) minmax(126px,1fr);gap:10px;align-items:center}
.rsk-matrix-head{min-height:34px;background:rgba(14,15,19,0.7);color:#7E8694;font-size:10px;font-weight:900;
  padding:0 12px;letter-spacing:.04em;text-transform:uppercase}
.rsk-matrix-row{min-height:52px;padding:8px 12px;border-top:1px solid #262A33}
.rsk-matrix-name{min-width:0;color:#E7E9EE;font-size:12px;font-weight:800}
.rsk-matrix-name small{display:block;color:#7E8694;font-size:10px;font-weight:700;margin-top:2px}
.rsk-state{justify-self:start;border-radius:999px;padding:4px 9px;font-size:10px;font-weight:800;white-space:nowrap}
.rsk-state.high{background:rgba(242,85,96,0.13);color:#F25560}.rsk-state.mid{background:rgba(217,164,65,0.13);color:#D9A441}
.rsk-state.low{background:rgba(77,144,240,0.13);color:#4D90F0}.rsk-state.na{background:rgba(14,15,19,0.5);color:#7E8694}
.rsk-matrix-copy{min-width:0;color:#9AA0AD;font-size:11px;font-weight:600;line-height:1.38}
.rsk-matrix-action{min-width:0;color:#B8BEC9;font-size:11px;font-weight:600;line-height:1.38}
.rsk-matrix-action::before{content:"▸";color:#D9A441;font-weight:800;margin-right:5px}
/* ── Portfolio impact ── */
.rsk-impact-table{display:grid;border:1px solid #262A33;border-radius:16px;overflow:hidden;background:#16181F}
.rsk-impact-row{display:grid;grid-template-columns:minmax(150px,.9fr) 110px minmax(0,1.6fr) 112px;gap:10px;align-items:center;
  min-height:50px;padding:8px 12px;border-top:1px solid #262A33}
.rsk-impact-row:first-child{border-top:none}
.rsk-impact-row.head{min-height:34px;background:rgba(14,15,19,0.7);color:#7E8694;font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}
.rsk-impact-asset{min-width:0;font-size:12px;font-weight:800;color:#E7E9EE}
.rsk-impact-asset small{display:block;color:#8A999B;font-size:10px;font-weight:700;margin-top:2px}
.rsk-impact-sens-pill{justify-self:start;border-radius:999px;padding:4px 9px;font-size:10px;font-weight:800;white-space:nowrap}
.rsk-impact-sens-pill.high{background:rgba(242,85,96,0.13);color:#F25560}
.rsk-impact-sens-pill.mid{background:rgba(217,164,65,0.13);color:#D9A441}
.rsk-impact-sens-pill.low{background:rgba(77,144,240,0.13);color:#4D90F0}
.rsk-impact-note-cell{min-width:0;font-size:11px;font-weight:600;color:#9AA0AD;line-height:1.45}
.rsk-impact-watch{font-size:11px;font-weight:800;color:#E7E9EE;line-height:1.4}
/* ── B. 신호 → 내 계좌 영향 (3열) ── */
.rsk-impact2-row{display:grid;grid-template-columns:minmax(150px,1fr) minmax(140px,1.05fr) minmax(0,1.7fr);
  gap:12px;align-items:center;min-height:52px;padding:9px 12px;border-top:1px solid #262A33}
.rsk-impact2-row:first-child{border-top:none}
.rsk-impact2-row.head{min-height:34px;background:rgba(14,15,19,0.7);color:#7E8694;font-size:10px;
  font-weight:900;text-transform:uppercase;letter-spacing:.04em}
/* ── Mobile ── */
@media(max-width:760px){
  .rsk-matrix-head,.rsk-impact-row.head,.rsk-impact2-row.head{display:none}
  .rsk-matrix-row{grid-template-columns:1fr;gap:6px;align-items:start}
  .rsk-impact-row,.rsk-impact2-row{grid-template-columns:1fr;gap:6px;align-items:start}
}
@media(max-width:640px){
  .rsk-kpi{padding:16px;border-radius:18px}
  .rsk-kpi-num{font-size:31px}
  .rsk-action-bar{padding:14px 16px;align-items:flex-start}
  .rsk-card{padding:18px 16px;border-radius:18px}
  .rsk-groups{grid-template-columns:1fr}
}
/* ── G. 처방 우선 재구성 ── */
/* 1. '오늘의 대응' 헤드라인 */
.rsk-headline{background:#1C1F27;border:1px solid #262A33;border-left:4px solid #D9A441;
  border-radius:18px;padding:18px 22px;margin:0 0 16px;box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-headline-k{font-size:10px;font-weight:900;color:#D9A441;text-transform:uppercase;
  letter-spacing:.1em;margin-bottom:9px;display:flex;align-items:center;gap:8px}
.rsk-headline-k .dot{width:6px;height:6px;border-radius:50%;background:#D9A441}
.rsk-headline-body{font-size:15.5px;font-weight:850;color:#E7E9EE;line-height:1.5}
.rsk-headline-body .sep{color:#7E8694;margin:0 7px}
.rsk-headline-cap{font-size:11.5px;font-weight:750;color:#8A999B;margin-top:10px;line-height:1.55}
.rsk-headline-cap b{color:#D9A441;font-weight:850}
/* 3·4. 리스크 균형 막대(4카드 압축) */
.rsk-balance{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:14px 18px;margin:0 0 14px;
  box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-bal-k{font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7E8694;margin-bottom:10px}
.rsk-bal-track{display:flex;height:12px;border-radius:999px;overflow:hidden;background:#1E2029}
.rsk-bal-track i{display:block;height:100%}
.rsk-bal-track i.hi{background:#F25560}.rsk-bal-track i.mid{background:#D9A441}.rsk-bal-track i.lo{background:#4D90F0}
.rsk-bal-legend{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-top:11px;font-size:12px;font-weight:850;
  font-variant-numeric:tabular-nums}
.rsk-bal-legend .hi{color:#F25560}.rsk-bal-legend .mid{color:#D9A441}.rsk-bal-legend .lo{color:#4D90F0}
.rsk-bal-net{margin-left:auto;padding:3px 11px;border-radius:999px}
.rsk-bal-net.danger{background:rgba(242,85,96,.13);color:#F25560}
.rsk-bal-net.warn{background:rgba(217,164,65,.13);color:#D9A441}
.rsk-bal-net.good{background:rgba(77,144,240,.13);color:#4D90F0}
.rsk-bal-interp{font-size:11.5px;font-weight:650;color:#9AA0AD;line-height:1.55;margin-top:10px;
  padding-top:9px;border-top:1px solid #262A33}
/* 2. 게이지 컨테이너(st.container border) 카드화 */
[data-testid="stVerticalBlockBorderWrapper"]:has(.rsk-gauge-title){
  background:#16181F!important;border:1px solid #262A33!important;border-radius:20px!important;
  box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-gauge-title{font-size:11px;font-weight:800;color:#7E8694;letter-spacing:.05em;
  text-transform:uppercase;margin:2px 0 0}
.rsk-gauge-interp{display:flex;justify-content:center;gap:9px;align-items:center;margin-top:2px}
.rsk-gauge-interp .lbl{font-size:10px;font-weight:800;color:#7E8694;text-transform:uppercase;letter-spacing:.06em}
.rsk-gauge-bridge{margin-top:9px;font-size:11px;font-weight:700;color:#8A8F9B;line-height:1.5;text-align:center;
  padding-top:9px;border-top:1px solid #262A33}
/* 5. 매트릭스 3열 */
.rsk-m3-more{font-size:10px;font-weight:800;color:#7E8694;background:rgba(100,107,121,0.14);
  border-radius:6px;padding:1px 6px}
.rsk-m3-head,.rsk-m3-row{display:grid;grid-template-columns:minmax(150px,1.05fr) minmax(150px,1.15fr) minmax(150px,1.25fr);
  gap:12px;align-items:center}
.rsk-m3-head{min-height:34px;background:rgba(14,15,19,0.7);color:#7E8694;font-size:10px;font-weight:900;
  padding:0 12px;letter-spacing:.04em;text-transform:uppercase}
.rsk-m3-row{min-height:54px;padding:9px 12px;border-top:1px solid #262A33}
.rsk-m3-name{min-width:0;color:#E7E9EE;font-size:12.5px;font-weight:800;display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.rsk-m3-expo{min-width:0;color:#C9CEDA;font-size:11.5px;font-weight:750;line-height:1.4}
.rsk-m3-action{min-width:0;color:#C9A24E;font-size:11.5px;font-weight:650;line-height:1.4}
.rsk-m3-action::before{content:"▸";color:#D9A441;font-weight:800;margin-right:5px}
@media(max-width:760px){
  .rsk-m3-head{display:none}
  .rsk-m3-row{grid-template-columns:1fr;gap:6px;align-items:start}
}
/* 내 보유·오늘 스냅샷 — 현황(중립). 시선이 '오늘의 대응'(골드)으로 흐르게 좌측바 무채색 */
.rsk-snap{background:#16181F;border:1px solid #262A33;border-left:3px solid #3A3F48;
  border-radius:18px;padding:15px 20px;margin:0 0 12px;box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-snap-k{font-size:10px;font-weight:900;color:#7E8694;text-transform:uppercase;letter-spacing:.08em;margin-bottom:9px}
.rsk-snap-tag{display:inline-block;margin-left:8px;padding:1px 7px;border-radius:999px;
  background:rgba(217,164,65,.12);border:1px solid rgba(217,164,65,.35);color:#D9A441;
  font-size:9px;font-weight:900;letter-spacing:.04em;vertical-align:middle}
.rsk-snap-body{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
.rsk-snap-flow{display:flex;align-items:baseline;gap:8px}
.rsk-snap-pct{font-size:24px;font-weight:950;font-family:'SF Mono',ui-monospace,monospace;line-height:1}
.rsk-snap-amt{font-size:14px;font-weight:800;font-variant-numeric:tabular-nums}
.rsk-snap-pct.pos,.rsk-snap-amt.pos{color:#F25560}
.rsk-snap-pct.neg,.rsk-snap-amt.neg{color:#4D90F0}
.rsk-snap-pct.flat,.rsk-snap-amt.flat{color:#9AA0AD}
.rsk-snap-sub{font-size:11px;font-weight:700;color:#7E8694;margin-left:4px}
.rsk-snap-stats{font-size:12px;font-weight:750;color:#9AA0AD;margin-left:auto;font-variant-numeric:tabular-nums}
.rsk-snap-stats .up{color:#F25560}.rsk-snap-stats .down{color:#4D90F0}
.rsk-snap-ctx{font-size:11.5px;font-weight:700;color:#8A999B;margin-top:10px;padding-top:9px;border-top:1px solid #262A33}
</style>"""


def _col_from_level(lv: str) -> str:
    lv = (lv or "").upper()
    if lv in ("HIGH", "RISK-OFF", "BEARISH", "STRONG"):
        return "high"
    if lv in ("LOW", "RISK-ON", "BULLISH", "WEAK", "FALLING"):
        return "low"
    if lv == "N/A":
        return "na"
    return "mid"


def _escape(value) -> str:
    return html_lib.escape(str(value or ""))


def _action_for_signal(signal: str, col: str) -> str:
    if col == "na":
        return "데이터 연결 후 반영"
    actions = {
        "Risk-on / Risk-off": {
            "high": "고베타·레버리지 진입 보류",
            "mid": "지수 방향 확인 후 분할",
            "low": "핵심 성장주 비중 유지",
        },
        "Dollar Strength": {
            "high": "해외자산 신규 매수 환율 체크",
            "mid": "환율 급등락 시 분할",
            "low": "환율 부담 낮을 때 환전 검토",
        },
        "Rate Pressure": {
            "high": "장기 성장주 추격 자제",
            "mid": "금리 피크아웃 확인",
            "low": "밸류에이션 부담 완화",
        },
        "Tech Momentum": {
            "high": "기술주 비중 축소 후보 점검",
            "mid": "실적·가이던스 확인",
            "low": "주도주 추세 유지",
        },
        "Semiconductor Momentum": {
            "high": "반도체 ETF 과열 구간 확인",
            "mid": "SOX 추세 확인",
            "low": "포트폴리오 완충 신호",
        },
        "Commodity Momentum": {
            "high": "인플레·원자재 민감도 확인",
            "mid": "헤지 자산 비중 유지",
            "low": "헤지 효과 약화 점검",
        },
        "Korea FX Risk": {
            "high": "해외 ETF 일괄 매수 금지",
            "mid": "환율 구간별 분할",
            "low": "해외자산 접근 여지",
        },
    }
    return actions.get(signal, {}).get(col, "관련 자산 비중 점검")


# ── B. 보유 기준 개인화: 시장 신호 → 내 계좌 영향 ─────────────────────────────
def _my_holdings_for_impact() -> tuple[list[dict], bool, float]:
    """세션 보유 → signal_impact 입력. (holdings, is_guest, total원). 게스트/미연결은 core.pb 정본 샘플."""
    bh = st.session_state.get("brokerage_holdings")
    if bh:
        try:
            from ui.pages.portfolio import _normalize_holdings, _portfolio_summary
            from core.pb import holdings_for_pb
            # 포트폴리오 페이지와 동일하게 시장데이터(fx·시세맵) 위에 보유 주입 → USD→KRW 환산 일치
            data = dict(load_market_data())
            data["holdings"] = bh
            data["cash_balance"] = st.session_state.get("brokerage_cash_balance")
            positions, meta = _normalize_holdings(data)
            summary = _portfolio_summary(positions, meta)  # 각 position에 weight(%) 부착
            holdings = holdings_for_pb(positions)
            if holdings:
                total = summary.get("total_market_value") or sum((p.get("market_value") or 0) for p in positions)
                return holdings, False, float(total or 0)
        except Exception:
            pass
    from core.pb import guest_holdings
    return guest_holdings(), True, 700_000_000.0   # 게스트 샘플 총자산(전 화면 공통)


# ── G. 처방-우선 컴포넌트 ─────────────────────────────────────────────────────
def _gauge_fig(score: int, threshold: int = 70) -> go.Figure:
    """리스크 게이지 — 청록(안전)→골드→짙은빨강 온도계 그라디언트.

    색만으로 판단하지 않도록 '위험 70' 틱 라벨 + 흰 바늘(값 위치)을 함께 둔다
    (적록색약 회피로 초록 대신 청록, 빨강은 상승색과 구분되는 짙은 톤 — siminvest_theme).
    """
    from siminvest_theme import gauge_gradient_steps
    score = max(0, min(100, score))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 40, "color": "#E7E9EE",
                         "family": "SF Mono, ui-monospace, monospace"}},
        gauge={
            "axis": {"range": [0, 100],
                     "tickvals": [0, 40, 70, 100],
                     "ticktext": ["0", "40", "위험 70", "100"],
                     "tickcolor": "#7E8694",
                     "tickfont": {"color": "#9AA0AD", "size": 10}},
            "bar": {"color": "rgba(0,0,0,0)"},                 # 기본 막대 숨김(바늘로 값 표시)
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": gauge_gradient_steps(),                   # 청록→골드→짙은빨강 그라디언트
            "threshold": {                                     # 흰 바늘 = 값 위치
                "line": {"color": "#E7E9EE", "width": 4},
                "thickness": 0.9, "value": score,
            },
        },
    ))
    fig.update_layout(
        height=190, margin=dict(l=24, r=24, t=10, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "-apple-system, 'Apple SD Gothic Neo', sans-serif"},
    )
    return fig


def _today_actions(score: int) -> list[str]:
    if score >= 70:
        return ["레버리지·고베타 자산 추가 매수 보류",
                "환율·금리 피크아웃 신호 확인 후 분할 검토",
                "금·현금성 자산 일정 비중 유지"]
    if score >= 40:
        return ["신규 매수 분할 제한",
                "고베타·레버리지 보류",
                "환율 급등락 시 분할 환전"]
    return ["핵심 비중 유지",
            "과열 종목만 부분 점검",
            "위험 신호 추가 증가 여부 모니터링"]


def _headline_action_card_html(score: int, tone_label: str, actions: list[str],
                               holdings_cap: str) -> str:
    sep = '<span class="sep">·</span>'
    body = sep.join(_escape(a) for a in actions)
    return (
        '<div class="rsk-headline">'
        '<div class="rsk-headline-k"><span class="dot"></span>오늘의 대응</div>'
        f'<div class="rsk-headline-body">{body}</div>'
        f'<div class="rsk-headline-cap">종합 <b>{score}/100 {_escape(tone_label)}</b>'
        f'{(" · 내 계좌(" + holdings_cap + ")에 직접 적용") if holdings_cap else ""}</div>'
        '</div>'
    )


def _severity_block_html(high_sigs, mid_sigs, low_sigs) -> str:
    def _tags(sigs):
        if not sigs:
            return "해당 신호 없음"
        return " · ".join(_SIG_KOR.get(s["signal"], s["signal"]) for s in sigs)

    n_high, n_mid, n_low = len(high_sigs), len(mid_sigs), len(low_sigs)
    net = n_high - n_low
    if net > 0:
        net_cls, net_dir = "danger", "위험 우위"
    elif net < 0:
        net_cls, net_dir = "good", "완충 우위"
    else:
        net_cls, net_dir = "warn", "균형"

    # 순 리스크 해석 — 완충 요인이 집중 리스크를 일부 상쇄하나 별개임을 명시
    if low_sigs:
        low_name = _SIG_KOR.get(low_sigs[0]["signal"], low_sigs[0]["signal"])
        interp = f"{low_name} 등 완충 요인이 시장 리스크를 일부 상쇄 — 단, 보유 집중 해소는 별개 과제입니다."
    elif n_high:
        interp = "완충 신호가 없어 위험 요인이 그대로 노출됩니다. 방어 비중부터 점검하세요."
    else:
        interp = "위험 신호가 제한적입니다. 핵심 비중을 유지하며 변화를 모니터링하세요."

    sign = "+" if net > 0 else ""
    total = (n_high + n_mid + n_low) or 1

    def _seg(cls, n):
        return f'<i class="{cls}" style="width:{n / total * 100:.1f}%"></i>' if n else ""

    bar = (
        '<div class="rsk-bal-track">'
        + _seg("hi", n_high) + _seg("mid", n_mid) + _seg("lo", n_low)
        + '</div>'
    )
    legend = (
        '<div class="rsk-bal-legend">'
        f'<span class="hi" title="위험: {_escape(_tags(high_sigs))}">● 위험 {n_high}</span>'
        f'<span class="mid" title="주의: {_escape(_tags(mid_sigs))}">● 주의 {n_mid}</span>'
        f'<span class="lo" title="완충: {_escape(_tags(low_sigs))}">● 완충 {n_low}</span>'
        f'<span class="rsk-bal-net {net_cls}">위험 {n_high} − 완충 {n_low} = {sign}{net} · {net_dir}</span>'
        '</div>'
    )
    return (
        '<div class="rsk-balance">'
        '<div class="rsk-bal-k">리스크 균형</div>'
        + bar + legend
        + f'<div class="rsk-bal-interp">{_escape(interp)}</div>'
        '</div>'
    )


def _signal_matrix3_html(signals: list[dict], exposure_map: dict, dim_map: dict) -> str:
    """신호 | 내 노출 | 대응 — 같은 노출 차원(dim) 신호는 1행으로 통합해 중복 노출 제거.

    예) 위험선호·금리·AI 3신호 → '성장주 70%' 한 줄 / 달러강세·원달러 → 'USD 78%' 한 줄.
    dim이 없는 신호(직접 연결 낮음)는 개별 행으로 유지.
    """
    order = {"high": 0, "mid": 1, "low": 2, "na": 3}
    eng_name = {kor: eng for eng, kor in _SIG_KOR.items()}

    def _sev(s):
        return order.get(s.get("col"), 9)

    sorted_sigs = sorted(signals, key=lambda x: (_sev(x), x.get("signal", "")))

    rows = []
    seen_dims: set[str] = set()
    for s in sorted_sigs:
        name = _SIG_KOR.get(s.get("signal"), s.get("signal", ""))
        dim = dim_map.get(name)

        if dim:
            if dim in seen_dims:
                continue
            seen_dims.add(dim)
            # 같은 dim의 신호 전부 모아 1행으로 (대표 = 최고 심각도)
            members = [m for m in sorted_sigs
                       if dim_map.get(_SIG_KOR.get(m.get("signal"), m.get("signal", ""))) == dim]
            lead = members[0]
            col = lead.get("col", "na")
            lv_kor = _LEVEL_KOR.get(str(lead.get("lv", "N/A")).upper(), str(lead.get("lv", "N/A")))
            names = [_SIG_KOR.get(m.get("signal"), m.get("signal", "")) for m in members]
            others = names[1:]
            # 같은 노출에 묶인 다른 신호를 풀어 표기 + 툴팁으로 신호명 명시
            name_html = _escape(names[0]) + (
                f' <span class="rsk-m3-more" title="같은 노출에 묶인 신호: {_escape(" · ".join(others))}">'
                f'관련 신호 +{len(others)}</span>' if others else "")
            expo = exposure_map.get(names[0], "직접 연결 낮음")
            action = _action_for_signal(lead.get("signal", ""), col)
        else:
            col = s.get("col", "na")
            lv_kor = _LEVEL_KOR.get(str(s.get("lv", "N/A")).upper(), str(s.get("lv", "N/A")))
            name_html = _escape(name)
            expo = "직접 연결 낮음"
            action = _action_for_signal(s.get("signal", ""), col)

        rows.append(
            f'<div class="rsk-m3-row">'
            f'<div class="rsk-m3-name">{name_html}'
            f'<span class="rsk-state {col}" style="display:inline-block">{_escape(lv_kor)}</span></div>'
            f'<div class="rsk-m3-expo">{_escape(expo)}</div>'
            f'<div class="rsk-m3-action">{_escape(action)}</div>'
            f'</div>'
        )
    return (
        '<div class="rsk-matrix">'
        '<div class="rsk-m3-head"><div>신호</div><div>내 노출</div><div>대응</div></div>'
        + "".join(rows)
        + '</div>'
    )


def _snapshot_data() -> dict | None:
    """내 보유 · 오늘 스냅샷 — 평가 흐름·급등/급락·최대상승·공통 성격. 보유 데이터에서 자동 산출."""
    from core.pb import tag_holding
    positions = []
    bh = st.session_state.get("brokerage_holdings")
    if bh:
        try:
            from ui.pages.portfolio import _normalize_holdings, _portfolio_summary
            data = dict(load_market_data())
            data["holdings"] = bh
            data["cash_balance"] = st.session_state.get("brokerage_cash_balance")
            positions, meta = _normalize_holdings(data)
            _portfolio_summary(positions, meta)
        except Exception:
            positions = []
    if not positions:  # 게스트/미연결 — 샘플 시세로 today 변동 산출
        try:
            from ui.pages.portfolio import _guest_portfolio_positions, _fetch_guest_quotes
            from core.pb import GUEST_SAMPLE
            current = st.session_state.get("portfolio_current_asset", 700_000_000)
            tks = tuple({it["ticker"] for it in GUEST_SAMPLE if it["ticker"] != "CASH"})
            positions = _guest_portfolio_positions(current, _fetch_guest_quotes(tks))
        except Exception:
            return None
    if not positions:
        return None

    def _chg(p):
        v = p.get("today_change_pct")
        return v if isinstance(v, (int, float)) else p.get("change_pct")
    def _amt(p):
        v = p.get("today_change_amount")
        return v if isinstance(v, (int, float)) else p.get("change_amount")

    rows = [p for p in positions if p.get("category") != "현금" and p.get("ticker") != "CASH"]
    if not rows:
        return None
    total = sum((p.get("market_value") or 0) for p in positions) or 0
    today_amt = sum((_amt(p) or 0) for p in rows)
    today_pct = (today_amt / total * 100) if total else 0
    valid = [(p, _chg(p)) for p in rows if isinstance(_chg(p), (int, float))]
    up = [p for p, c in valid if c >= 2.0]      # 급등(+2%↑)
    down = [p for p, c in valid if c <= -2.0]   # 급락(−2%↓)
    top, top_chg = (max(valid, key=lambda x: x[1]) if valid else (None, None))

    if up:
        from collections import Counter
        secs = [tag_holding(p.get("name", ""), p.get("ticker", ""), p.get("category", ""))[0] for p in up]
        top_sec = Counter(secs).most_common(1)[0][0]
        lev = any(any(k in (p.get("name") or "") for k in ("레버리지", "레버", "2X", "3X")) for p in up)
        label = top_sec + ("·레버리지 ETF" if lev else "")
        ctx = f"급등 종목 대부분 {label} — 집중도 점검으로 연결"
    elif down:
        ctx = "오늘 보유 급락 발생 — 방어 비중·집중도부터 점검"
    else:
        ctx = "오늘 보유 변동 제한적 — 집중도·환율 노출만 점검"

    return {
        "today_pct": today_pct, "today_amt": today_amt,
        "n_up": len(up), "n_down": len(down),
        "top_name": (top.get("name") if top else None), "top_chg": top_chg, "ctx": ctx,
    }


def _snapshot_card_html(s: dict, is_guest: bool = False) -> str:
    from core.journey import krw_compact
    pct = s["today_pct"]
    cls = "pos" if pct > 0.01 else ("neg" if pct < -0.01 else "flat")
    amt = s["today_amt"]
    amt_str = ("+" if amt > 0 else "") + krw_compact(amt)
    top_part = ""
    if s["top_name"] and isinstance(s["top_chg"], (int, float)):
        top_part = f' · 최대 상승 {_escape(s["top_name"])} {s["top_chg"]:+.1f}%'
    kicker = "샘플 포트폴리오 · 오늘" if is_guest else "내 보유 · 오늘"
    badge = '<span class="rsk-snap-tag">샘플</span>' if is_guest else ''
    return (
        '<div class="rsk-snap">'
        f'<div class="rsk-snap-k">{kicker}{badge}</div>'
        '<div class="rsk-snap-body">'
        f'<div class="rsk-snap-flow"><span class="rsk-snap-pct {cls}">{pct:+.2f}%</span>'
        f'<span class="rsk-snap-amt {cls}">{amt_str}</span>'
        f'<span class="rsk-snap-sub">오늘 평가 흐름</span></div>'
        f'<div class="rsk-snap-stats"><span class="up">급등 {s["n_up"]}건</span> · '
        f'<span class="down">급락 {s["n_down"]}건</span>{top_part}</div>'
        '</div>'
        f'<div class="rsk-snap-ctx">{_escape(s["ctx"])}</div>'
        '</div>'
    )


def _holdings_caption() -> str:
    """포트폴리오 데이터에서 최대 집중·USD 노출 자동 주입 (하드코딩 금지)."""
    holdings, _, _ = _my_holdings_for_impact()
    if not holdings:
        return ""
    from core.journey import pct_weight
    top = max(holdings, key=lambda h: h.get("weight", 0))
    usd_w = sum(h.get("weight", 0) for h in holdings if h.get("currency") == "USD") * 100
    return f'{top["name"]} {pct_weight(top.get("weight", 0) * 100)}%·USD {pct_weight(usd_w)}%'


def _my_portfolio_risk_html(holdings: list[dict], is_guest: bool) -> str:
    """내 포트폴리오 구조 리스크 — 단일종목 집중·상위3개·USD 노출(자동 산출).

    최우선 위험(집중 ≥50%)=레드 좌측 바, 주의(≥30%)=골드.
    """
    if not holdings:
        return (
            '<div class="rsk-card"><div class="rsk-card-title">내 포트폴리오 리스크</div>'
            '<p style="color:#9AA0AD;font-size:12px;font-weight:700;margin:6px 0 0">'
            '보유 데이터를 연결하면 집중·환율 리스크를 자동 분석합니다.</p></div>'
        )
    from core.journey import pct_weight
    srt = sorted(holdings, key=lambda h: h.get("weight", 0), reverse=True)
    top = srt[0]
    top_w = top["weight"] * 100
    top3 = sum(h["weight"] for h in srt[:3]) * 100
    usd = sum(h["weight"] for h in holdings if h.get("currency") == "USD") * 100

    def _card(title, val, body, sev):
        return (
            f'<div class="rsk-myr {sev}"><div class="rsk-myr-k">{_escape(title)}</div>'
            f'<div class="rsk-myr-v">{val}</div>'
            f'<div class="rsk-myr-b">{_escape(body)}</div></div>'
        )

    top_sev = "danger" if top_w >= 50 else ("warn" if top_w >= 30 else "")
    top_body = ("단일 종목 비중 과도 — 개별 악재 시 평가액이 크게 흔들립니다. 분할·분산 우선"
                if top_w >= 50 else
                "단일 종목 비중 높음 — 분산 점검 권장" if top_w >= 30 else "집중도 양호")
    top3_sev = "danger" if top3 >= 80 else ("warn" if top3 >= 60 else "")
    usd_sev = "warn" if usd >= 70 else ""
    cards = (
        _card(f'{top["name"]} 집중', f'{pct_weight(top_w)}%', top_body, top_sev)
        + _card("상위 3개 비중", f'{pct_weight(top3)}%', "상위 포지션 집중도 — 리밸런싱 1순위", top3_sev)
        + _card("USD 노출", f'{pct_weight(usd)}%', "원/달러 변동이 원화 평가액에 직접 반영", usd_sev)
    )
    sub = "샘플 포트폴리오 기준 (로그인 시 내 보유 자동 전환)" if is_guest else "내 보유에서 자동 산출"
    return (
        '<div class="rsk-card">'
        f'<div class="rsk-card-title">내 포트폴리오 리스크 <span class="rsk-myr-sub">{_escape(sub)}</span></div>'
        f'<div class="rsk-myr-grid">{cards}</div>'
        '</div>'
    )


def _scenario_card_html(holdings: list[dict], total: float) -> str:
    """만약 이렇게 되면? — 현 보유 기준 스트레스 시나리오 예상 영향(추정, A2 시간축 해석)."""
    if not holdings or not total:
        return ""
    from core.pb import scenario_drawdown, fx_scenario
    from core.journey import krw_compact
    top = max(holdings, key=lambda h: h.get("weight", 0))
    top_w = top.get("weight") or 0
    rows = [
        ("시장(주식) −10%", scenario_drawdown(holdings, total, -10.0), "β가중 동반 하락 가정"),
        (f'{top.get("name", "최대 종목")} −20%',
         {"pct": -top_w * 20, "krw": total * (-top_w * 20) / 100}, "최대 종목 단일 충격"),
        ("원/달러 −5% (원화 강세)", fx_scenario(holdings, total, -5.0), "USD 보유 환손실"),
    ]
    cells = ""
    for title, r, body in rows:
        v = f'{r["pct"]:+.1f}% · {krw_compact(r["krw"])}'
        cells += (f'<div class="rsk-myr"><div class="rsk-myr-k">{_escape(title)}</div>'
                  f'<div class="rsk-myr-v" style="color:#4D90F0">{v}</div>'
                  f'<div class="rsk-myr-b">{_escape(body)}</div></div>')
    return (
        '<div class="rsk-card">'
        '<div class="rsk-card-title">만약 이렇게 되면? '
        '<span class="rsk-myr-sub">현 보유 기준 예상 낙폭 · 추정(상관·헤지 단순화)</span></div>'
        f'<div class="rsk-myr-grid">{cells}</div></div>'
    )


def _render_action_checklist(actions: list[str], is_guest: bool) -> None:
    """B4 — '그래서 지금 뭘?' 대응 액션을 체크/메모로 남긴다. 로그인=계정 영속, 게스트=세션."""
    if not actions:
        return
    username = st.session_state.get("username")
    persist = bool(username) and not is_guest
    if persist:
        from core.accounts import get_setting
        log = dict(get_setting(username, "action_log", {}) or {})
    else:
        log = dict(st.session_state.get("_action_log", {}))

    with st.container(border=True):
        st.markdown(
            '<div class="rsk-card-title">오늘 할 일 체크 '
            '<span class="rsk-myr-sub">조언 → 행동 · 체크·메모는 저장됩니다</span></div>',
            unsafe_allow_html=True)
        done_ct, changed = 0, False
        for i, act in enumerate(actions):
            e = log.get(act, {})
            done = st.checkbox(act, value=bool(e.get("done")), key=f"rsk_act_{i}")
            memo = st.text_input(
                "메모", value=e.get("memo", ""), key=f"rsk_actmemo_{i}",
                placeholder="메모(선택) — 예: 환율 1,500 이하일 때 분할 매수", label_visibility="collapsed")
            done_ct += 1 if done else 0
            new_e = {"done": done, "memo": memo}
            if new_e != {"done": bool(e.get("done")), "memo": e.get("memo", "")}:
                if done or memo:
                    log[act] = new_e
                else:
                    log.pop(act, None)
                changed = True
        st.caption(f"완료 {done_ct} / {len(actions)}" + ("" if persist else " · 로그인 시 저장됩니다"))
    if changed:
        if persist:
            from core.accounts import set_setting
            set_setting(username, "action_log", log)
        else:
            st.session_state["_action_log"] = log


def _telegram_settings():
    """📲 텔레그램 위험 알림 — 연결·규칙·테스트 (성장_로드맵 C). 최상위 expander(중첩 금지)."""
    from src import telegram_alert as tg
    with st.expander("📲 텔레그램으로 위험 알림 받기", expanded=False):
        if not tg.is_configured():
            st.warning("봇 토큰 미설정 — `.env`에 `TELEGRAM_BOT_TOKEN` 추가 후 앱을 재시작하세요.")
            return
        cfg = tg.load_cfg()
        cid = cfg.get("chat_id")
        st.caption("위험 발생 시 텔레그램으로 알림을 받습니다. 평가·발송은 데이터 갱신(main.py) 시 수행됩니다.")
        if cid:
            st.success(f"연결됨 · chat_id `{cid}`")
        else:
            st.info("연결: 텔레그램에서 **@sim_investment_bot** 검색 → **/start** 전송 → 아래 '연결' 클릭")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("연결 / 갱신", key="tg_connect", use_container_width=True):
                try:
                    new = tg.connect()
                    if new:
                        st.success(f"연결됨 · chat_id `{new}`")
                    else:
                        st.warning("수신 메시지 없음 — 봇에 /start 를 먼저 보내세요.")
                except Exception as e:
                    st.error(f"연결 실패: {e}")
        with c2:
            if st.button("테스트 전송", key="tg_test", disabled=not cid, use_container_width=True):
                try:
                    if tg.send_test():
                        st.success("전송 성공")
                    else:
                        st.error("전송 실패")
                except Exception as e:
                    st.error(f"전송 실패: {e}")

        st.markdown("**알림 규칙**")
        r = cfg["rules"]
        e1 = st.toggle(f"종합 위험 점수 {r['risk_score']['threshold']} 이상",
                       value=r["risk_score"]["enabled"], key="tg_r1")
        e2 = st.toggle(f"보유 종목 일일 {r['holding_drop']['threshold']:+.0f}% 이하",
                       value=r["holding_drop"]["enabled"], key="tg_r2")
        if e1 != r["risk_score"]["enabled"] or e2 != r["holding_drop"]["enabled"]:
            r["risk_score"]["enabled"], r["holding_drop"]["enabled"] = e1, e2
            tg.save_cfg(cfg)
        st.caption("보유 급락 규칙은 증권사 연동 시 동작 · 같은 알림은 12시간 쿨다운.")


def render():
    L.viewport_width()          # 폭 먼저 확정 → 모바일 리플로우 최소화
    L.inject_responsive_css()   # 페이지당 1회
    inject_css()
    mark_active_nav("/risk")
    st.markdown(_RISK_LOCAL_CSS, unsafe_allow_html=True)

    st.markdown(
        mkt_page_header(
            "🛡",
            "리스크 모니터링",
            "내 포트폴리오 집중·환율 리스크 · 시장 국면(달러·금리·환율·모멘텀)",
        ),
        unsafe_allow_html=True,
    )

    # 보유 자동 주입(로그인=내 보유 / 게스트·미연결=샘플)
    holdings, _is_guest, _impact_total = _my_holdings_for_impact()

    # ── 리스크 보기 세그먼트 (로그인=내 포트폴리오 / 게스트=시장 기본) ──────────────
    view = st.radio(
        "리스크 보기", ["내 포트폴리오 리스크", "시장 리스크"],
        index=(1 if _is_guest else 0), key="risk_view_mode",
        label_visibility="collapsed", horizontal=True,
    ) or ("시장 리스크" if _is_guest else "내 포트폴리오 리스크")

    # ── 시장 신호 로드 + 점수 ────────────────────────────────────────────────────
    db_signals = load_risk_signals_cached(DEFAULT_DB)
    use_db = not db_signals.empty
    if use_db:
        signals = [
            {"signal": r["signal_name"], "lv": r["level"],
             "col": _col_from_level(r["level"]), "note": r["comment"]}
            for _, r in db_signals.iterrows()
        ]
    else:
        ph = show_skeleton()
        data = load_market_data()
        ph.empty()
        signals = _cached_regime_signals(data["fetched_at"])

    signals_with_na = signals
    total  = len(signals) or 1
    n_high = sum(1 for s in signals if s["col"] == "high")
    n_mid  = sum(1 for s in signals if s["col"] == "mid")
    n_low  = sum(1 for s in signals if s["col"] == "low")
    raw    = (n_high * 100 + n_mid * 55 + n_low * 10) / total
    score  = int(round(max(0, min(100, raw))))

    threshold = 70
    if score >= threshold:
        tone, tone_label = "risk", "위험 구간"
    elif score >= 40:
        tone, tone_label = "warn", "주의 구간"
    else:
        tone, tone_label = "good", "안정 구간"
    summary_short = "방어 우선" if score >= threshold else ("선별 대응" if score >= 40 else "비중 유지")

    high_sigs = [s for s in signals if s["col"] == "high"]
    mid_sigs  = [s for s in signals if s["col"] == "mid"]
    low_sigs  = [s for s in signals if s["col"] == "low"]

    sig_for_impact = [
        {"signal": _SIG_KOR.get(s["signal"], s["signal"]),
         "lv": s.get("lv"), "col": s.get("col", "na")}
        for s in signals_with_na
    ]
    from core.pb import signal_impact
    _impact = signal_impact(holdings, sig_for_impact, total=_impact_total)
    exposure_map = {r["signal"]: r["exposure"] for r in _impact}
    dim_map = {r["signal"]: r["dim"] for r in _impact}
    holdings_cap = _holdings_caption()

    def _market_block(formula_collapsible: bool = True):
        # '오늘의 대응' 헤드라인 → 심각도 균형 막대 → 게이지 | 신호 매트릭스
        # formula_collapsible=False: 상위 expander 안에서 호출될 때(중첩 금지) 점수 산식을 인라인 렌더
        st.markdown(
            _headline_action_card_html(score, tone_label, _today_actions(score), holdings_cap),
            unsafe_allow_html=True,
        )
        st.markdown(_severity_block_html(high_sigs, mid_sigs, low_sigs), unsafe_allow_html=True)
        gauge_col, matrix_col = st.columns([0.95, 1.65], gap="medium")
        with gauge_col:
            with st.container(border=True):
                st.markdown('<p class="rsk-gauge-title">종합 리스크 게이지</p>', unsafe_allow_html=True)
                st.plotly_chart(_gauge_fig(score, threshold), use_container_width=True,
                                config={"displayModeBar": False})
                st.markdown(
                    f'<div class="rsk-gauge-interp"><span class="lbl">대응 모드</span>'
                    f'<span class="rsk-mini-interp {tone}" style="margin-left:0">{summary_short}</span></div>',
                    unsafe_allow_html=True,
                )
                _net = n_high - n_low
                _sign = "+" if _net > 0 else ""
                _net_word = "위험 우위" if _net > 0 else ("완충 우위" if _net < 0 else "균형")
                _bridge = (
                    f"방향성은 {_sign}{_net}({_net_word})이나, 보유 집중으로 게이지는 {score}({tone_label})입니다."
                    if tone != "good" else
                    f"방향성 {_sign}{_net}({_net_word}) · 보유 집중도 제한적 — 게이지 {score}({tone_label})."
                )
                st.markdown(f'<div class="rsk-gauge-bridge">{_escape(_bridge)}</div>',
                            unsafe_allow_html=True)
                # A3: 점수 산식 — 블랙박스 점수가 아니라 납득 가능하게.
                # 상위 expander 안(내 포트폴리오 뷰)에선 중첩 금지라 인라인으로 렌더.
                _formula_md = (
                    f"- 신호 집계: 위험 **{n_high}** · 주의 **{n_mid}** · 완충 **{n_low}** (전체 {total}개)\n"
                    f"- 게이지 점수 = (위험 {n_high}×100 + 주의 {n_mid}×55 + 완충 {n_low}×10) ÷ {total} "
                    f"= {raw:.0f} → **{score} / 100**\n"
                    f"- 방향성 = 위험 {n_high} − 완충 {n_low} = **{_sign}{_net}** ({_net_word})\n"
                    f"- 구간: 0–39 안정 · 40–69 주의 · 70+ 위험 → 현재 **{score} ({tone_label})**"
                )
                if formula_collapsible:
                    with st.expander("점수 산식 보기", expanded=False):
                        st.markdown(_formula_md)
                else:
                    st.caption("점수 산식")
                    st.markdown(_formula_md)
        with matrix_col:
            st.markdown(
                '<div class="rsk-card" style="display:flex;flex-direction:column">'
                '<div class="rsk-card-title">신호 → 내 노출 → 대응</div>'
                + _signal_matrix3_html(signals_with_na, exposure_map, dim_map)
                + '</div>',
                unsafe_allow_html=True,
            )

    if view == "내 포트폴리오 리스크":
        st.markdown(_my_portfolio_risk_html(holdings, _is_guest), unsafe_allow_html=True)
        st.markdown(_scenario_card_html(holdings, _impact_total), unsafe_allow_html=True)  # A2 시나리오
        _render_action_checklist(_today_actions(score), _is_guest)  # B4 액션 체크/메모
        _snap = _snapshot_data()
        if _snap:
            st.markdown(_snapshot_card_html(_snap, _is_guest), unsafe_allow_html=True)
        with st.expander("시장 리스크 함께 보기 (국면·금리·환율·모멘텀)", expanded=False):
            _market_block(formula_collapsible=False)  # 상위 expander 중첩 금지 → 인라인
    else:
        _market_block()

    _telegram_settings()
    glossary_expander("β", "집중도", "감지 임계값")
    st.markdown(jj_footer(), unsafe_allow_html=True)
