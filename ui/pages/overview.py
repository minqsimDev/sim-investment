"""
전체 현황 — '내 관점' 4단 다이제스트(한 줄 진단 · 오늘 할 일 · 시장 다이제스트).
게스트=core.pb 공유 샘플 / 로그인=실계좌(소스만 교체). 시장 상세는 '시장' 탭.
"""
from __future__ import annotations

import html as _html
import pandas as pd
import streamlit as st

import layout as L  # 반응형(뷰포트 감지 + 모바일 CSS)
from data.loader import load_market_data
from src.risk import compute_regime_signals
from ui.components.dash_style import (
    glossary_expander,
    inject_css, numeric, show_skeleton,
    mark_active_nav, mkt_page_header, jj_footer, mkt_stats_chips,
)

# ── Colors ────────────────────────────────────────────────────────────────────

# ── Bar chart / ranking assets ────────────────────────────────────────────────

# ── Normalized line chart assets ──────────────────────────────────────────────
# Quiet Terminal: 카테고리 라인은 무채색 그레이 램프 + 골드(강조)만 사용

# ── Group heatmap (used in tabs) ──────────────────────────────────────────────

# ── Market movers thresholds (for 주요변동 tab) ───────────────────────────────

# ── CSS ───────────────────────────────────────────────────────────────────────
_OV_CSS = """<style>
/* 골드 CTA 링크 — 오늘 할 일·시장 다이제스트·포트폴리오 링크 공용 */
.ov-risk-link{display:inline-flex;align-items:center;justify-content:center;
  padding:11px 14px;border-radius:14px;background:rgba(217,164,65,0.10);
  border:1px solid rgba(217,164,65,0.42);color:#D9A441!important;font-size:13px;font-weight:850;
  text-decoration:none!important;transition:background .15s,border-color .15s}
.ov-risk-link:hover{background:rgba(217,164,65,0.18);border-color:#D9A441}
.ov-cta-r{text-align:right;margin-top:12px}   /* → 더보기 링크 우측 정렬(인라인 플렉스 링크를 우측으로) */
</style>"""

# ── Cached loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _cached_regime_signals(fetched_at: str) -> list[dict]:
    """Cache the regime-signal computation keyed by the market data timestamp.
    Avoids recomputing identical signals on every Streamlit rerun within the cache window.
    """
    # Pull cached market data and compute. The TTL aligns with load_market_data (30 min).
    return compute_regime_signals(load_market_data())

# ── Value helpers ──────────────────────────────────────────────────────────────

# ── HTML builders ──────────────────────────────────────────────────────────────

# 종목별 고유색 — 차분하게 채도 낮춘 자산군별 팔레트(차트 시리즈 공용)

# ── Summary text ───────────────────────────────────────────────────────────────

# ── Portfolio impact bullets ───────────────────────────────────────────────────

def _compass_model(sig_map: dict, btc_chg: float | None, kweb_chg: float | None) -> tuple[str, str, int, str]:
    score = 0

    def _col(key: str) -> str:
        return sig_map.get(key, {}).get("col", "na")

    for key, weight in [("Semiconductor Momentum", 2), ("Tech Momentum", 2)]:
        col = _col(key)
        if col == "low":
            score += weight
        elif col == "high":
            score -= weight

    for key, weight in [("Rate Pressure", 2), ("Dollar Strength", 1), ("Korea FX Risk", 1)]:
        col = _col(key)
        if col == "high":
            score -= weight
        elif col == "low":
            score += 1

    if btc_chg is not None:
        if btc_chg > 2:
            score += 1
        elif btc_chg < -2:
            score -= 1
    if kweb_chg is not None:
        if kweb_chg > 1.5:
            score += 1
        elif kweb_chg < -1.5:
            score -= 1

    angle = max(-42, min(42, score * 9))
    if score >= 3:
        return "우상향 유지", "AI·반도체 중심의 위험선호가 우세합니다. 금리와 달러 변화만 계속 점검하세요.", angle, "good"
    if score <= -3:
        return "방어 모드", "금리·달러·위험회피 압력이 커졌습니다. 변동성 큰 자산군의 움직임을 먼저 확인하세요.", angle, "risk"
    return "혼조 구간", "방향성은 아직 중립입니다. 강한 자산과 약한 자산이 갈리는지 확인하세요.", angle, "watch"

# ── Chart builders ─────────────────────────────────────────────────────────────

# ── ETF impact table (for tabs) ────────────────────────────────────────────────

# ── '내 관점' 4단 다이제스트 ─────────────────────────────────────────────────────
# 게스트=core.pb 공유 샘플(테슬라 52% 집중 …), 로그인=동일 레이아웃에 실계좌로 소스만 교체.
# 시장 상세(지수·변동성·국면)는 '시장' 탭이 home — 여기선 요약 + 링크만(중복 금지).
_MY_CSS = """<style>
/* 샘플 안내 = 파랑-라임 그라데이션 알약(포트폴리오 .gp-kicker 와 동일 스타일). */
.ov-sample-mark{display:inline-block;font-size:11px;font-weight:850;color:#E7E9EE;
  background:linear-gradient(135deg,rgba(133,186,234,.25),rgba(226,235,136,.34));
  border:1px solid #262A33;border-radius:999px;padding:5px 12px;margin:2px 0 12px}
.todo-card,.digest-card{background:#16181F;border:1px solid #262A33;border-radius:18px;
  padding:16px 18px;margin:14px 0 4px;box-shadow:0 6px 18px rgba(0,0,0,.25)}
.todo-title{font-size:11px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7E8694;margin-bottom:12px}
.digest-k{font-size:11px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#9AA0AD;margin-bottom:8px}
.todo-row{display:grid;grid-template-columns:130px minmax(0,1fr) minmax(0,1.1fr);gap:12px;align-items:center;
  padding:10px 0;border-top:1px solid #21242C}
.todo-row:first-of-type{border-top:none}
.todo-sig{font-size:13px;font-weight:900;color:#E7E9EE;position:relative;padding-left:12px}
.todo-sig::before{content:"";position:absolute;left:0;top:3px;bottom:3px;width:3px;border-radius:2px}
/* 위험 강조 = 중립→골드→앰버 단계만(리스크 탭 scorebar와 동일). 빨강/파랑은 손익 전용이라 의미 충돌 회피(A+C). */
.todo-risk .todo-sig::before{background:#E8883A}.todo-warn .todo-sig::before{background:#D9A441}.todo-good .todo-sig::before{background:#9AA0AD}
/* B2: 색 막대 의미 라벨(위험/주의/양호) — 색만으로 판단 금지(A+C) */
.todo-sev{display:inline-block;margin-left:7px;font-size:11px;font-weight:850;padding:1px 6px;border-radius:6px;vertical-align:middle}
.todo-risk .todo-sev{color:#E8883A;background:rgba(232,136,58,.14)}
.todo-warn .todo-sev{color:#D9A441;background:rgba(217,164,65,.13)}
.todo-good .todo-sev{color:#9AA0AD;background:rgba(154,160,173,.14)}
.todo-expo{font-size:12px;font-weight:800;color:#C9CDD4}
.todo-act{font-size:12px;font-weight:700;color:#9AA0AD;line-height:1.5}
.digest-line{font-size:16px;font-weight:850;color:#E7E9EE;line-height:1.45}
/* 방향 칩 — 우상향=양호 초록 · 혼조=중립 · 방어=앰버(위험경고). 손익색(빨강/파랑) 미사용 */
.ov-dir-chip{display:inline-block;font-size:12px;font-weight:850;padding:2px 9px;border-radius:7px;margin-right:8px;vertical-align:middle}
.ov-dir-chip.good{color:#3FB27F;background:rgba(63,178,127,.14)}
.ov-dir-chip.watch{color:#9AA0AD;background:rgba(154,160,173,.14)}
.ov-dir-chip.risk{color:#E8883A;background:rgba(232,136,58,.14)}
.ov-mkt-chips{margin-top:13px}
/* B1: 빈 히어로 카드에 핵심 숫자 통합 — 총자산 大(30px) + 총수익·오늘 보조. 위험 카드와 같은 카드 리듬. */
.ov-hero{border:1px solid #262A33;border-radius:18px;background:#15171E;padding:18px 22px;margin:2px 0 16px}
.ov-hero-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.ov-hero-label{font-size:13px;font-weight:900;color:#E7E9EE;letter-spacing:.02em}
.ov-hero-sub{font-size:12px;font-weight:700;color:#7E8694}
/* 핵심 숫자 — 가로 한 줄(총자산 大 앵커 + 총수익·오늘). 카드 가로폭 활용 + 위계 강조. */
.ov-hero-nums{display:flex;flex-direction:row;flex-wrap:wrap;align-items:baseline;gap:6px 30px}
.ov-hn-main,.ov-hn{display:flex;align-items:baseline;gap:8px}
.ov-hn-main span,.ov-hn span{font-size:12px;font-weight:800;letter-spacing:.02em;color:#7E8694}
.ov-hn-main b{font-size:28px;font-weight:950;color:#E7E9EE;font-variant-numeric:tabular-nums;line-height:1}
.ov-hn b{font-size:18px;font-weight:900;color:#E7E9EE;font-variant-numeric:tabular-nums;line-height:1}
.ov-hn b.up{color:#F25560}.ov-hn b.down{color:#4D90F0}
/* 자산 배분 미니바 — 최대비중 골드(강조), 나머지 중립. 손익색 미사용 */
.ov-alloc{margin-top:16px;padding-top:14px;border-top:1px solid #21242C}
.ov-alloc-k,.ov-goal-k{font-size:10.5px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#7E8694}
.ov-alloc-bar{display:flex;height:10px;border-radius:999px;overflow:hidden;background:#0E0F13;margin:9px 0}
.ov-alloc-bar i{display:block;height:100%}
.ov-alloc-legend{display:flex;flex-wrap:wrap;gap:6px 15px}
.ov-alloc-lg{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:750;color:#C9CDD4;font-variant-numeric:tabular-nums}
.ov-alloc-lg i{width:8px;height:8px;border-radius:2px;flex-shrink:0}
/* 목표 진행률 — 골드 진행 바 */
.ov-goal{margin-top:14px;padding-top:13px;border-top:1px solid #21242C}
.ov-goal-row{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.ov-goal-v{font-size:12px;font-weight:850;color:#C9CDD4;font-variant-numeric:tabular-nums}
.ov-goal-track{height:6px;border-radius:999px;background:#0E0F13;overflow:hidden;margin-top:8px}
.ov-goal-track i{display:block;height:100%;background:#D9A441;border-radius:999px}
@media(max-width:760px){.todo-row{grid-template-columns:1fr;gap:3px}.ov-hn-main b{font-size:24px}
  .ov-hero-nums{gap:8px 22px}}
</style>"""

def _session_suffix() -> str:
    """세션 보존(게스트/로그인) 링크 suffix."""
    role = st.session_state.get("auth_role")
    user = st.session_state.get("username", "")
    if role == "guest":
        return "?_auth=guest"
    if user:
        return f"?_user={user}"
    return ""

def _my_perspective_bundle(data: dict) -> dict:
    """4단 데이터 — 게스트=core.pb 공유 샘플(포트폴리오와 동일 데이터셋), 로그인=실계좌(소스 교체)."""
    from datetime import date as _date, timedelta as _td
    from core.pb import GUEST_SAMPLE, holdings_for_pb, pb_diagnostics, bench_returns
    from ui.pages.portfolio import _journey_get
    bh = st.session_state.get("brokerage_holdings")
    positions, total, cash, is_guest, uname = None, 0.0, 0.0, True, None
    summary = None
    if bh:
        try:
            from ui.pages.portfolio import _normalize_holdings, _portfolio_summary
            _d = dict(data)
            _d["holdings"] = bh
            _d["cash_balance"] = st.session_state.get("brokerage_cash_balance")
            positions, meta = _normalize_holdings(_d)
            summary = _portfolio_summary(positions, meta)  # 각 position에 weight(%) 부착
            total = summary.get("total_market_value") or 0
            cash = summary.get("cash_balance") or 0
            is_guest, uname = False, st.session_state.get("username")
        except Exception:
            positions = None
    if not positions:  # 게스트/미연결 → 공유 샘플(별도 샘플 만들지 않음)
        positions, total, cash, is_guest = GUEST_SAMPLE, 700_000_000, 70_000_000, True
    # A2 단일 출처 — 포트폴리오와 동일 함수로 계산(총수익·KOSPI 대비·벤치마크 값 화면 간 일치)
    from ui.pages.portfolio import _account_diag
    holdings = holdings_for_pb(positions)
    _b = _account_diag(positions, total, cash, uname, is_guest)
    diag, bench = _b["diag"], _b["bench"]
    # 히어로 핵심 숫자 — 총자산은 항상, 오늘 손익은 실계좌(summary) 있을 때만
    today_amt = summary.get("today_change_amount") if summary else None
    today_pct = summary.get("today_change_pct") if summary else None
    # 목표 진행률(여정) — 사용자가 '직접 설정한' 목표가 있을 때만 표시(기본값이면 숨김).
    # _journey_get 을 sentinel(None)로 호출 → DB/세션에 설정값이 없으면 None → progress=None(미표시).
    from ui.pages.portfolio import _estimate_start_value
    _target_raw = _journey_get("target_value", uname, is_guest, None)
    target, progress = 0, None
    if _target_raw is not None:
        target = int(_target_raw)
        start = _estimate_start_value(positions, total)
        if target > start:
            progress = max(0.0, min(1.0, (total - start) / (target - start)))
        elif total >= target:
            progress = 1.0
    cash_pct = (cash / total * 100) if total else 0.0
    # 자산 배분 — 종목 고유 시그니처색(포트폴리오 집중도 바와 동일 `_stock_bar_color`). 현금 제외, 비중 내림차순.
    from ui.pages.portfolio import _stock_bar_color
    alloc = []
    for i, pos in enumerate(positions):
        if pos.get("category") == "현금" or pos.get("ticker") == "CASH":
            continue
        w = pos.get("weight") or 0
        if w <= 0:
            continue
        alloc.append({"name": pos.get("name", ""), "weight": float(w), "color": _stock_bar_color(pos, i)})
    alloc.sort(key=lambda x: x["weight"], reverse=True)
    return {"diag": diag, "bench": bench, "holdings": holdings, "is_guest": is_guest,
            "total": total, "today_amt": today_amt, "today_pct": today_pct,
            "cash_pct": cash_pct, "target": target, "progress": progress, "alloc": alloc}

def _cta(text: str, href: str) -> str:
    """카드 하단 우측 '더보기' 링크 — 3개 카드(포트폴리오·리스크·시장)는 동등한 형제라 동일 골드 알약."""
    return (f'<div class="ov-cta-r"><a class="ov-risk-link" href="{href}" target="_self" '
            f'style="display:inline-flex">{text} &rarr;</a></div>')

def _alloc_bar_html(alloc: list[dict], cash_pct: float) -> str:
    """히어로 — 자산 배분 미니바(내 쏠림 한눈에). 각 종목=고유 시그니처색(애플 회색·MS 파랑·NVDA 초록·
    BTC 주황 …, 포트폴리오 집중도 바와 동일). 상위 4개 + 기타(중립) + 현금(중립)으로 100% 스택."""
    if not alloc and cash_pct <= 0.1:
        return ""
    top, rest = alloc[:4], alloc[4:]
    rest_w = sum(a["weight"] for a in rest)
    bar, legend = "", ""
    for a in top:
        bar += f'<i style="width:{a["weight"]:.1f}%;background:{a["color"]}"></i>'
        legend += (f'<span class="ov-alloc-lg"><i style="background:{a["color"]}"></i>'
                   f'{_html.escape(a["name"])} {a["weight"]:.0f}%</span>')
    if rest_w > 0.1:
        bar += f'<i style="width:{rest_w:.1f}%;background:#3A3F48"></i>'
        legend += '<span class="ov-alloc-lg"><i style="background:#3A3F48"></i>기타 ' + f'{rest_w:.0f}%</span>'
    if cash_pct > 0.1:
        bar += f'<i style="width:{cash_pct:.1f}%;background:#2A2E37"></i>'
        legend += '<span class="ov-alloc-lg"><i style="background:#2A2E37"></i>현금 ' + f'{cash_pct:.0f}%</span>'
    return ('<div class="ov-alloc"><div class="ov-alloc-k">자산 배분 — 내 쏠림</div>'
            f'<div class="ov-alloc-bar">{bar}</div>'
            f'<div class="ov-alloc-legend">{legend}</div></div>')

def _goal_bar_html(target: float, progress: float) -> str:
    """히어로 — 목표 진행률 한 줄(여정). 진행 바는 골드(목표=긍정 강조)."""
    from core.journey import krw_compact
    pct = max(0.0, min(100.0, progress * 100))
    return ('<div class="ov-goal"><div class="ov-goal-row">'
            f'<span class="ov-goal-k">목표까지</span>'
            f'<span class="ov-goal-v">{krw_compact(target)} · {pct:.0f}%</span></div>'
            f'<div class="ov-goal-track"><i style="width:{pct:.1f}%"></i></div></div>')

def _todo_rows(holdings: list[dict], signals: list[dict], total: float = 0.0) -> tuple[list[dict], dict]:
    """오늘 할 일 행 산출 — 신호→내 노출, dim당 1행·최대 3줄(리스크 탭과 동일 통합). (rows, kor2eng)."""
    from core.pb import signal_impact
    from ui.pages.risk_signals import _SIG_KOR
    # 신호(영문 키)→한글 라벨 + 역매핑(대응 액션은 영문 키 기준이라 보존).
    kor2eng, sig_for_impact = {}, []
    for s in signals:
        eng = s["signal"]
        kor = _SIG_KOR.get(eng, eng)
        kor2eng[kor] = eng
        sig_for_impact.append({"signal": kor, "lv": s.get("lv"), "col": s.get("col", "na")})
    impact = signal_impact(holdings, sig_for_impact, total=total)
    order = {"high": 0, "mid": 1, "low": 2, "na": 3}
    seen, rows = set(), []
    for r in sorted(impact, key=lambda x: order.get(x.get("col"), 9)):
        if r["dim"] in seen:  # 같은 노출 차원 중복 제거(리스크 탭과 동일 통합)
            continue
        seen.add(r["dim"])
        rows.append(r)
        if len(rows) >= 3:
            break
    return rows, kor2eng

def _risk_todo_html(rows: list[dict], kor2eng: dict, footer: str = "") -> str:
    """3단 — 오늘 할 일: 신호 → 내 노출(영향 금액) → 대응(요약). 상세는 리스크 탭. rows는 _todo_rows()."""
    from ui.pages.risk_signals import _action_for_signal
    if not rows:
        return ""
    cls = {"high": "risk", "mid": "warn", "low": "good"}
    sev = {"high": "위험", "mid": "주의", "low": "양호"}   # B2: 색 막대에 라벨 부여(색만 의존 금지·A+C)
    # 3번째 칼럼 = 실제 '대응' 액션(리스크 탭과 동일 매핑) — '왜(meaning)'가 아니라 '무엇을'.
    body = "".join(
        f'<div class="todo-row todo-{cls.get(r.get("col"), "warn")}">'
        f'<div class="todo-sig">{r["signal"]}<span class="todo-sev">{sev.get(r.get("col"), "주의")}</span></div>'
        f'<div class="todo-expo">{r["exposure"]}</div>'
        f'<div class="todo-act">{_action_for_signal(kor2eng.get(r["signal"], r["signal"]), r.get("col", "na"))}</div>'
        f'</div>'
        for r in rows
    )
    return (
        f'<div class="todo-card"><div class="todo-title">오늘 할 일 — 신호 → 내 노출 → 대응</div>'
        f'{body}{footer}</div>'
    )

def _market_pulse_chips(data: dict) -> str:
    """시장 펄스 — 핵심 지표 1D% 미니 칩(시장 페이지 '오늘의 핵심 지표'와 동일 컴포넌트·소스).
    풀 지표는 시장 페이지 담당, 여기선 5개 요약만(다이제스트)."""
    def _chg(key, col, val):
        df = data.get(key)
        if not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
            return None
        r = df[df[col] == val]
        if r.empty:
            return None
        c = r.iloc[0].get("change_pct")
        return float(c) if isinstance(c, (int, float)) and not pd.isna(c) else None
    specs = [("나스닥100", "benchmarks", "ticker", "QQQ"), ("S&P500", "benchmarks", "ticker", "SPY"),
             ("반도체", "benchmarks", "ticker", "SOXX"), ("USD/KRW", "fx", "pair", "usd_krw"),
             ("비트코인", "crypto", "ticker", "BTC-USD")]
    items = []
    for label, key, col, val in specs:
        c = _chg(key, col, val)
        if c is None:
            continue
        sign = "+" if c >= 0 else ""
        items.append({"label": label, "value": f"{sign}{c:.2f}%",
                      "cls": "pos" if c > 0 else ("neg" if c < 0 else "neu")})
    return f'<div class="ov-mkt-chips">{mkt_stats_chips(items)}</div>' if items else ""

def _market_digest_html(direction: str, note: str, tone: str, chips: str, footer: str = "") -> str:
    """4단 — 시장 다이제스트: 방향 칩(색 배지) + 한 줄 + 핵심 지표 펄스 칩 + 시장 탭 링크."""
    tcls = tone if tone in ("good", "risk", "watch") else "watch"
    return (
        f'<div class="digest-card"><div class="digest-k">시장 다이제스트</div>'
        f'<div class="digest-line"><span class="ov-dir-chip {tcls}">{direction}</span>{note}</div>'
        f'{chips}{footer}</div>'
    )

# ── Main render ────────────────────────────────────────────────────────────────

def render():
    L.viewport_width()          # 폭 먼저 확정 → 모바일 리플로우 최소화
    L.inject_responsive_css()   # 페이지당 1회
    inject_css()
    mark_active_nav("/")
    st.markdown(_OV_CSS, unsafe_allow_html=True)
    st.markdown(_MY_CSS, unsafe_allow_html=True)
    # B1: 빈 히어로 제거 — 핵심 숫자 통합 히어로를 데이터 로드 후 한 번에 렌더(아래)
    ph = show_skeleton()
    data = load_market_data()
    ph.empty()

    # 시장 신호(시장 다이제스트·오늘 할 일용) — 시장 데이터에서 산출
    signals = _cached_regime_signals(data["fetched_at"])
    sig_map = {s["signal"]: s for s in signals}

    def _safe(v):
        try:
            f = float(v)
            return None if pd.isna(f) else f
        except (TypeError, ValueError):
            return None

    _bm = data.get("benchmarks", pd.DataFrame())
    _cr = data.get("crypto", pd.DataFrame())
    _bm_chg = {} if _bm.empty else dict(zip(_bm["ticker"], _bm["change_pct"]))
    _cry_chg = {} if _cr.empty else dict(zip(_cr["ticker"], _cr["change_pct"]))
    btc_chg, kweb_chg = _safe(_cry_chg.get("BTC-USD")), _safe(_bm_chg.get("KWEB"))
    direction, compass_note, _, _dir_tone = _compass_model(sig_map, btc_chg, kweb_chg)

    # ── 내 관점 데이터(게스트=공유 샘플 / 로그인=실계좌, 소스만 교체) ──
    bundle = _my_perspective_bundle(data)
    _diag, _bench, _holdings, _is_guest = (
        bundle["diag"], bundle["bench"], bundle["holdings"], bundle["is_guest"])
    _suf = _session_suffix()

    # 히어로 핵심 숫자 한 줄 — 총자산 · 총수익 · (실계좌면) 오늘 손익. 첫 스크롤 전 가치 전달.
    from core.journey import krw_compact
    _total, _today_amt, _today_pct = bundle.get("total"), bundle.get("today_amt"), bundle.get("today_pct")
    _my_ret = _diag.get("my_return") if _diag else None
    _hs = []
    if _total:
        _hs.append(("총자산", krw_compact(_total), ""))
    if _my_ret is not None:
        _hs.append(("총수익", f"{_my_ret:+.1f}%", "up" if _my_ret >= 0 else "down"))
    if _today_amt is not None and _today_pct is not None:
        if abs(_today_pct) < 0.005:           # 반올림 0.00% → '−0' 처럼 깨져 보이는 것 방지
            _hs.append(("오늘", "보합", ""))
        else:
            _sgn = "+" if _today_amt >= 0 else ""
            _hs.append(("오늘", f"{_sgn}{krw_compact(_today_amt)} ({_today_pct:+.2f}%)",
                        "up" if _today_amt >= 0 else "down"))
    # B1: 히어로 카드에 통합 — 총자산 大 + 총수익·오늘 보조 (빈 히어로 카드 + 떠다니던 숫자 합침)
    _main = _hs[0] if _hs else None
    _nums = (f'<div class="ov-hn-main"><span>{_main[0]}</span><b>{_main[1]}</b></div>' if _main else "")
    _nums += "".join(f'<div class="ov-hn"><span>{l}</span><b class="{c}">{v}</b></div>' for l, v, c in _hs[1:])
    # 부제 = 아래 카드 제목 복붙(중복) 대신 실제 메타(갱신 시각). fetched_at=isoformat → HH:MM.
    _fa = str(data.get("fetched_at") or "")
    _upd = f'<span class="ov-hero-sub">갱신 {_fa[11:16]}</span>' if len(_fa) >= 16 else ""
    # 자산 배분 미니바(내 쏠림) + 목표 진행률 — 히어로 빈 공간을 '내 계좌 파생 정보'로 채움
    _alloc = _alloc_bar_html(bundle.get("alloc", []), bundle.get("cash_pct", 0.0))
    _prog = bundle.get("progress")
    _goal = _goal_bar_html(bundle.get("target", 0), _prog) if (_prog is not None and bundle.get("target")) else ""
    st.markdown(
        '<div class="ov-hero"><div class="ov-hero-head">'
        '<span class="ov-hero-label">전체 현황</span>'
        f'{_upd}'
        f'</div><div class="ov-hero-nums">{_nums}</div>'
        f'{_alloc}{_goal}</div>',
        unsafe_allow_html=True,
    )

    # 샘플 마커(상시) — 문구는 '샘플 포트폴리오'로 통일(포트폴리오와 동일). 면책(매매 권유 아님)은 하단 푸터가 담당.
    if _is_guest:
        st.markdown('<div class="ov-sample-mark">샘플 포트폴리오</div>', unsafe_allow_html=True)

    from ui.pages.portfolio import _pb_risk_summary_html, _PB_CSS
    st.markdown(_PB_CSS, unsafe_allow_html=True)

    # 더보기 CTA — 포트폴리오·리스크·시장은 동등한 형제 섹션이라 동일한 골드 알약으로 통일.
    _rows, _kor2eng = _todo_rows(_holdings, signals, _total or 0.0)

    if _diag:
        # 1단 — 한 줄 진단(요약). 풀 카드(지표 그리드·재배분·벤치마크)는 포트폴리오/리스크에서만 — 100% 복제 제거.
        # 상세 링크는 카드 '안쪽 하단·우측'에(밖에 떠다니지 않게). 풀 상세는 포트폴리오 탭.
        _detail_link = _cta("내 포트폴리오 — 벤치마크 · 보유 · 리밸런싱", f"/portfolio{_suf}")
        st.markdown(_pb_risk_summary_html(_diag, footer=_detail_link), unsafe_allow_html=True)

    # 2단 — 오늘 할 일(신호 → 내 노출 → 대응 3줄), 상세는 리스크 탭
    _todo = _risk_todo_html(_rows, _kor2eng,
                            footer=_cta("리스크 — 신호 · 내 노출 · 대응", f"/risk{_suf}"))
    if _todo:
        st.markdown(_todo, unsafe_allow_html=True)

    # 3단 — 시장 다이제스트(방향 칩 + 한 줄 + 핵심 지표 펄스 칩 + 시장 탭 링크)
    st.markdown(_market_digest_html(direction, compass_note, _dir_tone, _market_pulse_chips(data),
                                    footer=_cta("시장 — 지수 · 환율 · 변동성", f"/market{_suf}")),
                unsafe_allow_html=True)

    glossary_expander("β", "추세", "breadth", "집중도")
    st.markdown(jj_footer(), unsafe_allow_html=True)
