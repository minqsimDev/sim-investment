import html as html_lib

import streamlit as st

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
/* 내 포트폴리오 리스크 — 4개 카드를 한 줄에 자동 축소 배치(태블릿 2열·모바일 1열) */
.rsk-myr-grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
@media(max-width:980px){.rsk-myr-grid4{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.rsk-myr-grid4{grid-template-columns:1fr}}
/* 신호 → 내 노출 → 대응 — 표 대신 카드 형식(반응형 그리드). 심각도 = 앰버/골드/중립(빨강·파랑은 손익 전용) */
.rsk-sigcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(252px,1fr));gap:10px}
.rsk-sigcard{background:#1E2029;border:1px solid #262A33;border-left:3px solid #3A3F48;border-radius:14px;padding:13px 15px}
.rsk-sigcard.high{border-left-color:#E8883A}.rsk-sigcard.mid{border-left-color:#D9A441}.rsk-sigcard.low{border-left-color:#9AA0AD}
.rsk-sigcard-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:9px}
.rsk-sigcard-name{font-size:13px;font-weight:850;color:#E7E9EE;min-width:0}
.rsk-sev-badge{font-size:10.5px;font-weight:850;padding:2px 8px;border-radius:7px;white-space:nowrap}
.rsk-sev-badge.high{color:#E8883A;background:rgba(232,136,58,.14)}
.rsk-sev-badge.mid{color:#D9A441;background:rgba(217,164,65,.13)}
.rsk-sev-badge.low{color:#9AA0AD;background:rgba(154,160,173,.14)}
.rsk-sev-badge.na{color:#7E8694;background:rgba(14,15,19,.5)}
.rsk-sigcard-row{display:flex;gap:8px;font-size:11.5px;line-height:1.45;margin-top:5px}
.rsk-sigcard-row .k{color:#7E8694;font-weight:850;flex:0 0 40px}
.rsk-sigcard-row .v{color:#C9CEDA;font-weight:650;min-width:0}
.rsk-sigcard-row.act .v{color:#C9A24E}
/* ── Mobile ── */
@media(max-width:760px){
  .rsk-matrix-head,.rsk-impact-row.head,.rsk-impact2-row.head{display:none}
  .rsk-matrix-row{grid-template-columns:1fr;gap:6px;align-items:start}
  .rsk-impact-row,.rsk-impact2-row{grid-template-columns:1fr;gap:6px;align-items:start}
}
@media(max-width:640px){
  .rsk-card{padding:18px 16px;border-radius:18px}
}
/* 3·4. 리스크 균형 막대(4카드 압축) */
.rsk-balance{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:14px 18px;margin:0 0 14px;
  box-shadow:0 8px 22px rgba(0,0,0,.25)}
.rsk-bal-k{font-size:10px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7E8694;margin-bottom:10px}
.rsk-bal-track{display:flex;height:12px;border-radius:999px;overflow:hidden;background:#1E2029}
.rsk-bal-track i{display:block;height:100%}
.rsk-bal-track i.hi{background:#E8883A}.rsk-bal-track i.mid{background:#D9A441}.rsk-bal-track i.lo{background:#9AA0AD}
.rsk-bal-legend{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-top:11px;font-size:12px;font-weight:850;
  font-variant-numeric:tabular-nums}
.rsk-bal-legend .hi{color:#E8883A}.rsk-bal-legend .mid{color:#D9A441}.rsk-bal-legend .lo{color:#9AA0AD}
.rsk-bal-net{margin-left:auto;padding:3px 11px;border-radius:999px}
.rsk-bal-net.danger{background:rgba(232,136,58,.14);color:#E8883A}
.rsk-bal-net.warn{background:rgba(217,164,65,.13);color:#D9A441}
.rsk-bal-net.good{background:rgba(154,160,173,.14);color:#9AA0AD}
.rsk-bal-interp{font-size:11.5px;font-weight:650;color:#9AA0AD;line-height:1.55;margin-top:10px;
  padding-top:9px;border-top:1px solid #262A33}
.rsk-gauge-bridge{margin-top:9px;font-size:12px;font-weight:720;color:#9AA0AD;line-height:1.55;text-align:center;
  padding-top:9px;border-top:1px solid #262A33}
/* 점수 산식 — 주변 컴팩트 UI와 글씨 크기 통일(기본 markdown ~16px → 11.5px) */
.rsk-formula-t{font-size:10.5px;font-weight:800;color:#7E8694;letter-spacing:.04em;text-transform:uppercase;margin:12px 0 5px}
.rsk-formula{margin:0;padding-left:16px;font-weight:650;color:#9AA0AD;line-height:1.7}
.rsk-formula li{margin:2px 0;font-size:11.5px!important}   /* Streamlit 기본 li(~16px) 오버라이드 */
.rsk-formula b{color:#E7E9EE;font-weight:850;font-variant-numeric:tabular-nums}
/* 5. 매트릭스 3열 */
.rsk-m3-more{display:block;font-size:10.5px;font-weight:750;color:#7E8694;margin-top:3px;line-height:1.4}
/* 시나리오(가정) 카드 — 현황 구조카드와 구분: 파랑(=하방 충격) 좌측바 + 옅은 틴트 */
.rsk-scenario{border-left:3px solid #4D90F0;background:#15181F}
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
        f'<span class="rsk-bal-net {net_cls}">{net_dir}</span>'  # 산수(위험N−완충N=±net)는 점수 산식에만(중복 제거)
        '</div>'
    )
    return (
        '<div class="rsk-balance">'
        '<div class="rsk-bal-k">리스크 균형</div>'
        + bar + legend
        + f'<div class="rsk-bal-interp">{_escape(interp)}</div>'
        '</div>'
    )


def _matrix_rows(signals: list[dict], exposure_map: dict, dim_map: dict) -> list[dict]:
    """신호 → 내 노출 → 대응 행 산출 — 같은 노출 차원(dim) 신호는 1행 통합(중복 제거).
    예) 위험선호·금리·AI 3신호 → '성장주 70%' 한 줄. 매트릭스 카드·오늘 할 일 체크가 공유."""
    order = {"high": 0, "mid": 1, "low": 2, "na": 3}
    sorted_sigs = sorted(signals, key=lambda x: (order.get(x.get("col"), 9), x.get("signal", "")))
    rows, seen_dims = [], set()
    for s in sorted_sigs:
        name = _SIG_KOR.get(s.get("signal"), s.get("signal", ""))
        dim = dim_map.get(name)
        if dim:
            if dim in seen_dims:
                continue
            seen_dims.add(dim)
            members = [m for m in sorted_sigs
                       if dim_map.get(_SIG_KOR.get(m.get("signal"), m.get("signal", ""))) == dim]
            lead = members[0]
            col = lead.get("col", "na")
            names = list(dict.fromkeys(
                _SIG_KOR.get(m.get("signal"), m.get("signal", "")) for m in members))
            others = names[1:]
            name_html = _escape(names[0]) + (
                f'<span class="rsk-m3-more">관련 {_escape(" · ".join(others))}</span>'
                if others else "")
            expo = exposure_map.get(names[0], "직접 연결 낮음")
            action = _action_for_signal(lead.get("signal", ""), col)
        else:
            col = s.get("col", "na")
            name_html = _escape(name)
            expo = "직접 연결 낮음"
            action = _action_for_signal(s.get("signal", ""), col)
        rows.append({"name_html": name_html, "col": col, "expo": expo, "action": action})
    return rows


def _signal_cards_html(rows: list[dict]) -> str:
    """매트릭스 행 → 카드. 심각도 라벨 col 기준(위험/주의/완충), 색 앰버/골드/중립(빨강·파랑은 손익 전용)."""
    cards = []
    for r in rows:
        col = r["col"]
        c = col if col in ("high", "mid", "low") else "na"
        sev_label = {"high": "위험", "mid": "주의", "low": "완충"}.get(col, "중립")
        cards.append(
            f'<div class="rsk-sigcard {c}">'
            f'<div class="rsk-sigcard-top"><span class="rsk-sigcard-name">{r["name_html"]}</span>'
            f'<span class="rsk-sev-badge {c}">{sev_label}</span></div>'
            f'<div class="rsk-sigcard-row"><span class="k">내 노출</span><span class="v">{_escape(r["expo"])}</span></div>'
            f'<div class="rsk-sigcard-row act"><span class="k">대응</span><span class="v">▸ {_escape(r["action"])}</span></div>'
            f'</div>'
        )
    return '<div class="rsk-sigcards">' + "".join(cards) + '</div>'


def _quant_risk_score(holdings: list[dict], mkt_raw: float) -> tuple[int, dict | None]:
    """β·HHI 기반 정량 종합 리스크(0-100). 보유 미연결이면 시장 국면만.

    표준 분해를 따른다 — 총위험 = 체계적(시장) + 비체계적(집중):
    - 시장 리스크(체계적) = 시장 국면 점수 × 내 베타 노출(β=1→그대로, 고β→증폭)
    - 집중 리스크(비체계적) = HHI(허핀달) 또는 단일명 노출 중 큰 쪽(단일종목 꼬리위험 보존)
    - 종합 = 집중 0.5 + 시장 0.5 (가중은 본 앱 기준·조정 가능)
    """
    from core.pb import portfolio_risk_metrics
    def _c(x: float) -> float:
        return max(0.0, min(100.0, x))
    m = portfolio_risk_metrics(holdings)
    if not m:
        return int(round(_c(mkt_raw))), None
    conc_hhi = _c((m["hhi"] - 0.10) / 0.40 * 100)            # HHI 0.10(≈10종목)→0 · 0.50(≈2종목)→100
    conc_single = _c((m["top_w"] * 100 - 10) / 40 * 100)     # 단일명 10%→0 · 50%→100 (꼬리위험)
    conc_score = max(conc_hhi, conc_single)
    beta_factor = max(0.6, min(1.6, m["beta_p"]))
    market_score = _c(mkt_raw * (0.4 + 0.6 * beta_factor))   # β1→×1.0 · β1.5→×1.3 · β0.6→×0.76
    W_CONC, W_MKT = 0.5, 0.5
    score = int(round(_c(W_CONC * conc_score + W_MKT * market_score)))
    return score, {**m, "conc_score": conc_score, "conc_hhi": conc_hhi,
                   "conc_single": conc_single, "market_score": market_score}


def _my_portfolio_risk_html(holdings: list[dict], is_guest: bool, metrics: dict | None = None) -> str:
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
    # 시장 민감도 — 정량 표준 지표(β = CAPM, σ = 체계적 변동성 추정). 호출부의 risk_parts 재사용(중복계산 제거).
    _m = metrics
    if _m is None:
        from core.pb import portfolio_risk_metrics
        _m = portfolio_risk_metrics(holdings)
    if _m:
        _beta_sev = "danger" if _m["beta_p"] >= 1.5 else ("warn" if _m["beta_p"] >= 1.2 else "")
        _beta_body = (f'추정 연변동성 ~{_m["sigma_p"]:.0f}% · '
                      + ("시장보다 크게 출렁 — 하락장 충격 큼" if _m["beta_p"] >= 1.2
                         else "시장과 비슷하거나 둔감"))
        cards += _card("시장 민감도 β", f'{_m["beta_p"]:.2f}', _beta_body, _beta_sev)
    sub = "샘플 포트폴리오 기준 (로그인 시 내 보유 자동 전환)" if is_guest else "내 보유에서 자동 산출"
    return (
        '<div class="rsk-card">'
        f'<div class="rsk-card-title">내 포트폴리오 리스크 <span class="rsk-myr-sub">{_escape(sub)}</span></div>'
        f'<div class="rsk-myr-grid4">{cards}</div>'   # 4카드 한 줄(집중·상위3·USD·β) 자동 축소
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
        '<div class="rsk-card rsk-scenario">'   # 가정(what-if) 카드 — 현황 구조카드와 시각 구분(파랑 좌측바)
        '<div class="rsk-card-title">⚡ 만약 이렇게 되면? '
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
            '<div class="rsk-card-title">오늘 할 일 체크</div>',  # 저장 안내는 하단 '완료 N/3' 줄과 중복이라 제거
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

    # 상단 '리스크 모니터링' 배너 제거 — 제목은 네비와 중복, 부제는 아래 점수·신호가 대신 설명.
    # (불필요 요소 제거 + 상단 여백 축소로 핵심 콘텐츠를 위로)

    # 보유 자동 주입(로그인=내 보유 / 게스트·미연결=샘플)
    holdings, _is_guest, _impact_total = _my_holdings_for_impact()

    # 토글 폐지 — '시장 원인 → 내 노출 → 대응' 단일 서사로 통합. 순수 시장 국면(게이지·산식)은
    # 하단 접힘 '근거'로 강등(광범위 시장 조망은 시장 페이지 담당). 종합점수는 시장+집중 혼합값.

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
    mkt_raw = (n_high * 100 + n_mid * 55 + n_low * 10) / total   # 시장 국면 점수(0-100, 신호 가중평균)
    # 종합 리스크 = β·HHI 기반 정량(집중 0.5 + 시장 0.5). 보유 미연결이면 시장만.
    score, risk_parts = _quant_risk_score(holdings, mkt_raw)

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
    # 신호→내 노출→대응 행 1회 산출 — 매트릭스 카드와 '오늘 할 일 체크'가 공유(동일 액션).
    _mrows = _matrix_rows(signals_with_na, exposure_map, dim_map)

    def _regime_detail_block():
        # 시장 국면 '근거' — 심각도 분포 + 해석 한 줄 + 점수 산식. 게이지·대응모드는 상단 점수 배너와
        # 중복이라 제거(2026-06-25, plotly도 제외해 경량화). 점수의 '왜'는 산식이 담당.
        st.markdown(_severity_block_html(high_sigs, mid_sigs, low_sigs), unsafe_allow_html=True)
        _net = n_high - n_low
        _sign = "+" if _net > 0 else ""
        _net_word = "위험 우위" if _net > 0 else ("완충 우위" if _net < 0 else "균형")
        p = risk_parts
        if p:
            _bridge = (f"내 집중(HHI {p['hhi']:.2f}·유효 {p['eff_n']:.1f}종목)과 "
                       f"시장 민감도(β {p['beta_p']:.2f})를 반영한 종합 위험은 {tone_label}입니다.")
        else:
            _bridge = f"보유 미연결 — 시장 국면만 반영해 {tone_label}입니다."
        with st.container(border=True):
            st.markdown(f'<div class="rsk-gauge-bridge">{_escape(_bridge)}</div>',
                        unsafe_allow_html=True)
            # A3: 점수 산식 — 블랙박스 아님. 표준 분해(체계적 시장 + 비체계적 집중)를 단계별 공개.
            # 컴팩트 HTML로 렌더(기본 markdown은 ~16px라 주변과 안 맞음). 값은 숫자라 escape 불필요.
            _mkt = (f"시장 국면(원지표) = (위험 {n_high}×100 + 주의 {n_mid}×55 + 완충 {n_low}×10) ÷ {total} "
                    f"= <b>{mkt_raw:.0f}</b> · 방향성 {_sign}{_net}({_net_word})")
            if p:
                _msig = (p['sigma_p'] / p['beta_p']) if p['beta_p'] else 18.0   # 시장 σ 가정 역산
                _lines = [
                    _mkt,
                    f"시장 리스크(체계적) = 시장국면 × 내 베타노출(β {p['beta_p']:.2f}) = <b>{p['market_score']:.0f}</b>",
                    f"집중 리스크(비체계적) = HHI {p['hhi']:.2f}(유효 {p['eff_n']:.1f}종목)·최대 "
                    f"{p['top_w'] * 100:.0f}% → <b>{p['conc_score']:.0f}</b>",
                    f"종합 = 집중 {p['conc_score']:.0f}×0.5 + 시장 {p['market_score']:.0f}×0.5 "
                    f"= <b>{score} / 100</b> ({tone_label})",
                    f"추정 연변동성(σ) ≈ β {p['beta_p']:.2f} × 시장 {_msig:.0f}% = <b>{p['sigma_p']:.0f}%</b> "
                    f"· 구간 0–39 안정·40–69 주의·70+ 위험",
                    "지표: 베타(CAPM)·HHI(허핀달)=표준 정의 · 점수화·가중 0.5/0.5=본 앱 기준(조정 가능)",
                ]
            else:
                _lines = [
                    _mkt,
                    f"보유 미연결 → 종합 = 시장 점수 = <b>{score} / 100</b>",
                    f"구간: 0–39 안정 · 40–69 주의 · 70+ 위험 → 현재 <b>{score} ({tone_label})</b>",
                ]
            st.markdown(
                '<div class="rsk-formula-t">점수 산식 — 체계적(β·시장) + 비체계적(HHI 집중)</div>'
                '<ul class="rsk-formula">' + "".join(f"<li>{ln}</li>" for ln in _lines) + "</ul>",
                unsafe_allow_html=True,
            )

    # ── 단일 통합 흐름: [종합점수 아코디언 → 신호×내노출×대응 카드] → 내 집중·환율 → 시나리오 → 오늘 할 일 → (접힘)시장 국면 근거 ──
    # 종합 리스크를 아코디언 헤더로 — 클릭하면 신호→내 노출→대응 카드가 접힘/펼침(기본 펼침).
    _tone_color = {"risk": "red", "warn": "orange", "good": "green"}.get(tone, "orange")
    with st.expander(
        f":{_tone_color}[**종합 리스크 {score}/100 · {tone_label}**]  ·  대응 — {summary_short}",
        expanded=True,
    ):
        st.markdown(_signal_cards_html(_mrows), unsafe_allow_html=True)
    st.markdown(_my_portfolio_risk_html(holdings, _is_guest, risk_parts), unsafe_allow_html=True)
    st.markdown(_scenario_card_html(holdings, _impact_total), unsafe_allow_html=True)  # A2 시나리오
    # 오늘 할 일 체크 = 매트릭스의 구체 대응(위험·주의 신호만, 완충은 행동 불필요), 중복 액션 제거.
    _todo = list(dict.fromkeys(r["action"] for r in _mrows if r["col"] in ("high", "mid")))
    _render_action_checklist(_todo, _is_guest)  # B4 — 매트릭스 대응을 체크/메모로 추적
    # '내 보유·오늘' 스냅샷 제거(2026-06-25) — 당일 손익은 전체현황 히어로·포트폴리오와 중복, 리스크 관련성 약함.
    with st.expander("시장 국면 근거 (심각도 · 점수 산식)", expanded=False):
        _regime_detail_block()

    _telegram_settings()
    glossary_expander("β", "집중도", "감지 임계값")
    st.markdown(jj_footer(), unsafe_allow_html=True)
