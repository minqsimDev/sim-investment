"""게스트 둘러보기 포트폴리오 뷰 — portfolio.py에서 분리.
portfolio 정의 함수(_pb_risk_card_html 등)는 순환 import 회피 위해 함수 내부에서 지연 import.
"""
from __future__ import annotations

import math
from datetime import date as _date, timedelta

import streamlit as st

from format import won, currency as _cur
from core.journey import pct_weight
from core.pb import GUEST_SAMPLE as _GUEST_PORTFOLIO, holdings_for_pb, pb_diagnostics
from data.session import cached_download
from ui.components.dash_style import inject_css, jj_footer, mark_active_nav
from ui.pages.portfolio_css import _PORT_CSS, _PB_CSS
from ui.pages.portfolio_format import _money, _escape, _krw_short


_GUEST_CATEGORIES = {
    "미국 빅테크": ["NVDA", "MSFT", "AAPL", "META", "AMZN"],
    "반도체":      ["NVDA", "AMD", "AVGO", "TSM", "MU"],
    "국내 대형주": ["005930.KS", "000660.KS", "005380.KS", "035420.KS", "051910.KS"],
    "가상자산":    ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "원자재":      ["GC=F", "SI=F", "HG=F", "CL=F", "NG=F"],
}

_GUEST_TICKER_NAMES = {
    "NVDA": "엔비디아", "MSFT": "마이크로소프트", "AAPL": "애플",
    "TSLA": "테슬라", "META": "메타", "AMZN": "아마존", "AMD": "AMD", "AVGO": "브로드컴",
    "TSM": "TSMC", "MU": "마이크론", "GOOGL": "알파벳",
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차",
    "035420.KS": "NAVER", "051910.KS": "LG화학",
    "BTC-USD": "비트코인", "ETH-USD": "이더리움", "SOL-USD": "솔라나",
    "BNB-USD": "바이낸스", "XRP-USD": "리플",
    "GC=F": "금", "SI=F": "은", "HG=F": "구리", "CL=F": "WTI", "NG=F": "천연가스",
}

# 게스트 샘플 보유 = core.pb 정본(포트폴리오·리스크 동일 스토리). 테슬라 52% 집중 → '위험'.
from core.pb import GUEST_SAMPLE as _GUEST_PORTFOLIO


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_guest_quotes(tickers: tuple[str, ...]) -> dict:
    """게스트 샘플 보유 현재가·1D% — 시세 SSOT(price_source.fetch_prices_bulk) 경유."""
    from data.price_source import fetch_prices_bulk
    result = {}
    for tk, q in fetch_prices_bulk(list(tickers)).items():
        if q and q.get("price") is not None and q.get("change_pct") is not None:
            result[tk] = {"price": float(q["price"]), "chg": float(q["change_pct"])}
    return result


def _guest_change(chg: float | None) -> tuple[str, str]:
    if chg is None:
        return "대기", "flat"
    if chg > 0.05:
        return f"+{chg:.2f}%", "pos"
    if chg < -0.05:
        return f"{chg:.2f}%", "neg"
    return f"{chg:.2f}%", "flat"


def _guest_portfolio_positions(total_asset: float, quotes: dict) -> list[dict]:
    positions: list[dict] = []
    for item in _GUEST_PORTFOLIO:
        ticker = item["ticker"]
        weight = float(item["weight"])
        quote = quotes.get(ticker, {})
        chg = quote.get("chg")
        value = total_asset * weight / 100
        positions.append(
            {
                "ticker": ticker,
                "name": "현금/예수금" if ticker == "CASH" else _GUEST_TICKER_NAMES.get(ticker, ticker),
                "category": item["category"],
                "weight": weight,
                "currency": item.get("currency", "KRW"),
                "market_value": value,
                "price": quote.get("price"),
                "change_pct": chg,
                "change_amount": value * chg / 100 if chg is not None else 0,
            }
        )
    return positions


def _guest_curve_svg(today_pct: float) -> str:
    # R6: 단색 라인 — 양수=레드, 음수=블루
    line = "#F25560" if today_pct >= 0 else "#4D90F0"
    return (
        '<svg class="gp-chart-svg" viewBox="0 0 560 180" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="샘플 포트폴리오 추이">'
        '<defs>'
        '<linearGradient id="gpArea" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{line}" stop-opacity=".12"/>'
        f'<stop offset="100%" stop-color="{line}" stop-opacity="0"/></linearGradient>'
        '</defs>'
        '<path d="M24 142 C78 126 106 132 152 106 C198 78 222 96 268 74 C314 52 348 70 388 48 C430 26 478 48 536 28" '
        f'stroke="{line}" stroke-width="3" stroke-linecap="round" fill="none"/>'
        '<path d="M24 142 C78 126 106 132 152 106 C198 78 222 96 268 74 C314 52 348 70 388 48 C430 26 478 48 536 28 L536 168 L24 168 Z" '
        'fill="url(#gpArea)"/>'
        '<line x1="24" y1="168" x2="536" y2="168" stroke="#262A33" stroke-width="1"/>'
        f'<circle cx="536" cy="28" r="7" fill="#0E0F13" stroke="{line}" stroke-width="3"/>'
        '</svg>'
    )


def _guest_home_html(
    positions: list[dict],
    current_asset: float,
    target_asset: float,
    progress: float,
    diag: dict | None = None,
) -> str:
    from ui.pages.portfolio import _CONC_RAMP, _logo_html  # 순환 회피 지연 import
    today_amount = sum(p.get("change_amount") or 0 for p in positions)
    today_pct = today_amount / current_asset * 100 if current_asset else 0
    today_label = _money(today_amount, "KRW", signed=True, compact=True)
    today_pct_label = f"{today_pct:+.2f}%"
    today_cls = "pos" if today_amount > 0 else ("neg" if today_amount < 0 else "flat")
    largest = max(positions, key=lambda p: p.get("weight") or 0)
    # 상위 3개·최대비중·USD 노출은 PB 진단(diag)과 동일 소스 사용 — 화면 내 수치 불일치 방지
    _sorted = sorted(positions, key=lambda p: p.get("weight") or 0, reverse=True)
    top3_weight = sum(p.get("weight", 0) for p in _sorted[:3])
    largest_name = diag["top_name"] if diag else largest["name"]
    largest_w = diag["top_w"] * 100 if diag else (largest.get("weight") or 0)
    usd_weight = diag["usd_w"] if diag else sum(
        p.get("weight", 0) for p in positions if (p.get("currency") or "KRW") == "USD")
    allocation = []
    by_cat: dict[str, float] = {}
    for p in positions:
        by_cat[p["category"]] = by_cat.get(p["category"], 0) + p["weight"]
    # 비중 내림차순 → 최대 자산군 골드 강조, 이후 회색 차등(쏠림이 색으로 보이게)
    for idx, (cat, weight) in enumerate(sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True)):
        color = _CONC_RAMP[min(idx, len(_CONC_RAMP) - 1)]
        allocation.append(f'<i style="width:{weight:.1f}%;background:{color}" title="{_escape(cat)} {pct_weight(weight)}%"></i>')

    rows = []
    for p in positions[:5]:
        ticker = p["ticker"]
        short_ticker = ticker.replace(".KS", "").replace("-USD", "")
        chg_label, chg_cls = _guest_change(p.get("change_pct"))
        logo = _logo_html({"group": p["category"], "name": p["name"], "code": ticker})
        rows.append(
            '<div class="gp-pos-row">'
            f'{logo}'
            f'<div class="gp-pos-main"><b>{_escape(p["name"])}</b><span>{_escape(short_ticker)} · {_escape(p["category"])}</span></div>'
            f'<div class="gp-pos-val"><b>{_money(p["market_value"], "KRW", compact=True)}</b><span>{pct_weight(p["weight"])}%</span></div>'
            f'<div class="gp-pos-chg {chg_cls}">{_escape(chg_label)}</div>'
            '</div>'
        )

    return (
        '<section class="gp-home" aria-label="샘플 투자 홈">'
        '<div class="gp-home-main">'
        '<div class="gp-home-top">'
        '<span class="gp-kicker">샘플 포트폴리오</span>'
        '<div class="gp-total-label">샘플 총자산</div>'
        f'<div class="gp-total">{won(current_asset)}</div>'
        f'<div class="gp-delta {today_cls}"><b>{today_label}</b><span>{today_pct_label} 오늘</span></div>'
        '</div>'
        f'<div class="gp-chart">{_guest_curve_svg(today_pct)}</div>'
        '<div class="gp-actions">'
        '<a class="gp-action primary" href="#guest-watchlist">관심 종목</a>'
        '<a class="gp-action" href="#guest-journey">목표 여정</a>'
        '<a class="gp-action" href="/risk?_auth=guest" target="_self">리스크 보기</a>'
        '</div>'
        '</div>'
        '<aside class="gp-home-side">'
        '<div class="gp-side-head"><b>한눈에 보기</b><span>핵심 지표 요약</span></div>'
        '<div class="gp-mini-stats">'
        f'<div><span>목표 진행</span><b>{progress * 100:.1f}%</b></div>'
        f'<div><span>목표 금액</span><b>{_krw_short(target_asset)}원</b></div>'
        f'<div><span>최대 비중</span><b>{_escape(largest_name)} {pct_weight(largest_w)}%</b></div>'
        f'<div><span>상위 3개</span><b>{pct_weight(top3_weight)}%</b></div>'
        '</div>'
        '<div class="gp-alloc">' + "".join(allocation) + '</div>'
        f'<div class="gp-risk-note">USD 노출 {pct_weight(usd_weight)}% · 신규 매수 전 환율과 집중도를 먼저 확인</div>'
        '<div class="gp-pos-list">' + "".join(rows) + '</div>'
        '</aside>'
        '</section>'
    )


def _render_guest_portfolio():
    # 순환 import 회피 — 호출 시점(portfolio 완전 로드 후) 지연 import
    from ui.pages.portfolio import (_get_bench_returns, _journey_get,
                                    _benchmark_compare_html, _pb_risk_card_html,
                                    _render_asset_journey)
    from ui.components.dash_style import inject_css

    inject_css()
    mark_active_nav("/portfolio")
    st.markdown(_PORT_CSS, unsafe_allow_html=True)
    st.markdown("""<style>
.gp-home{display:grid;grid-template-columns:minmax(0,1.18fr) minmax(330px,.82fr);gap:12px;margin:10px 0 16px}
.gp-home-main,.gp-home-side{background:#16181F;border:1px solid #262A33;border-radius:18px;box-shadow:0 16px 36px rgba(0,0,0,0.30)}
.gp-home-main{position:relative;overflow:hidden;padding:20px 22px 18px;min-height:386px;display:flex;flex-direction:column}
.gp-home-main{background:#16181F}
.gp-home-side{background:#16181F}
.gp-home-top{position:relative;z-index:1}
/* 샘플 표기 — 파랑-라임 그라데이션 알약(전체현황 .ov-sample-mark 와 동일 스타일) */
.gp-kicker{display:inline-flex;border:1px solid #262A33;background:linear-gradient(135deg,rgba(133,186,234,.25),rgba(226,235,136,.34));color:#E7E9EE;border-radius:999px;padding:6px 10px;font-size:10px;font-weight:950;margin-bottom:14px}
.gp-total-label{font-size:12px;color:#9AA0AD;font-weight:900;margin-bottom:5px}
.gp-total{color:#E7E9EE;font-size:40px;font-weight:950;line-height:1.05;font-variant-numeric:tabular-nums}
.gp-delta{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;font-weight:900}
.gp-delta b{font-variant-numeric:tabular-nums}.gp-delta span{color:#9AA0AD;font-size:12px}
.gp-delta.pos,.gp-pos-chg.pos{color:#F25560}.gp-delta.neg,.gp-pos-chg.neg{color:#4D90F0}.gp-delta.flat,.gp-pos-chg.flat{color:#9AA0AD}
.gp-chart{margin:auto -6px 8px}.gp-chart-svg{display:block;width:100%;height:auto;min-height:170px}
.gp-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:auto}
.gp-action{display:inline-flex;align-items:center;justify-content:center;min-height:38px;border-radius:999px;border:1px solid #262A33;color:#E7E9EE;background:rgba(255,255,255,0.04);padding:0 14px;font-size:12px;font-weight:950;text-decoration:none}
.gp-action.primary{background:#D9A441;color:#0E0F13;border-color:transparent;box-shadow:0 10px 22px rgba(0,0,0,0.30)}
.gp-home-side{padding:16px;min-width:0}
.gp-side-head{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin-bottom:12px}
.gp-side-head b{color:#E7E9EE;font-size:15px;font-weight:950}
.gp-side-head span{color:#9AA0AD;font-size:10px;font-weight:850;text-align:right}
.gp-mini-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:10px}
.gp-mini-stats div{border:1px solid #262A33;background:#1E2029;border-radius:12px;padding:10px;min-width:0}
.gp-mini-stats span{display:block;color:#9AA0AD;font-size:10px;font-weight:900;margin-bottom:4px}
.gp-mini-stats b{display:block;color:#E7E9EE;font-size:13px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gp-alloc{display:flex;height:10px;border-radius:999px;overflow:hidden;background:#1E2029;margin:8px 0}
.gp-alloc i{display:block;height:100%;min-width:3px}
.gp-risk-note{color:#E7E9EE;background:linear-gradient(135deg,rgba(133,186,234,.16),rgba(226,235,136,.22));border:1px solid #262A33;border-radius:12px;padding:9px 10px;font-size:11px;font-weight:800;line-height:1.45;margin-bottom:10px}
.gp-pos-list{display:grid;gap:7px}
.gp-pos-row{display:grid;grid-template-columns:32px minmax(0,1fr) auto auto;gap:8px;align-items:center;border:1px solid #262A33;border-radius:12px;background:rgba(22,24,31,0.84);padding:8px}
.gp-pos-row .hold-logo{width:32px;height:32px;flex-basis:32px}
.gp-pos-main{min-width:0}.gp-pos-main b{display:block;color:#E7E9EE;font-size:12px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gp-pos-main span{display:block;color:#9AA0AD;font-size:10px;font-weight:850;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gp-pos-val{text-align:right}.gp-pos-val b{display:block;color:#E7E9EE;font-size:11px;font-weight:950;white-space:nowrap}
.gp-pos-val span{display:block;color:#9AA0AD;font-size:10px;font-weight:850;margin-top:2px}
.gp-pos-chg{font-size:11px;font-weight:950;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.gp-header{padding:22px 0 8px;margin-bottom:4px}
.gp-header h2{font-size:22px;font-weight:950;color:#E7E9EE;margin:0;letter-spacing:0}
.gp-header p{font-size:13px;color:#9AA0AD;margin:4px 0 0;font-weight:600}
.gp-section{margin:18px 0 6px}
.gp-section-title{font-size:15px;font-weight:800;color:#E7E9EE;margin:0 0 10px;letter-spacing:0}
.gp-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px}
.gp-card{background:#16181F;border:1px solid #262A33;border-radius:16px;padding:14px 16px;
  box-shadow:0 7px 18px rgba(0,0,0,0.30)}
.gp-card-name{font-size:12px;color:#9AA0AD;font-weight:700;margin:0 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gp-card-ticker{font-size:11px;color:#7E8694;font-weight:600;margin:0 0 8px;font-family:monospace}
.gp-card-price{font-size:16px;font-weight:900;color:#E7E9EE;font-family:'SF Mono',monospace;
  font-variant-numeric:tabular-nums;margin:0 0 4px}
.gp-card-chg{font-size:12px;font-weight:800;font-family:'SF Mono',monospace}
.gp-card-chg.pos{color:#F25560}.gp-card-chg.neg{color:#4D90F0}.gp-card-chg.flat{color:#9AA0AD}
.gp-badge{display:inline-block;background:rgba(217,164,65,0.15);color:#D9A441;font-size:10px;font-weight:700;
  padding:3px 8px;border-radius:999px;margin-bottom:6px}
@media(max-width:1080px){.gp-home{grid-template-columns:1fr}.gp-home-main{min-height:330px}}
@media(max-width:900px){.gp-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){
  .gp-home{gap:10px;margin-top:6px}.gp-home-main,.gp-home-side{border-radius:16px}
  .gp-home-main{padding:16px;min-height:0}.gp-total{font-size:31px}
  .gp-chart-svg{min-height:132px}.gp-actions{display:grid;grid-template-columns:1fr 1fr}.gp-action{min-height:36px}
  .gp-mini-stats{grid-template-columns:1fr 1fr}.gp-pos-row{grid-template-columns:32px minmax(0,1fr) auto}.gp-pos-chg{grid-column:2/-1;text-align:left}
  .gp-grid{grid-template-columns:1fr}
}
</style>""", unsafe_allow_html=True)

    current_asset = st.session_state.get("portfolio_current_asset", 700_000_000)
    target_asset = st.session_state.get("portfolio_target_asset", 1_500_000_000)
    annual_growth_rate = st.session_state.get("portfolio_annual_growth_rate", 0.20)
    progress = min(1.0, max(0.0, current_asset / max(1, target_asset)))
    all_tickers = tuple({tk for tks in _GUEST_CATEGORIES.values() for tk in tks if tk != "CASH"})
    quotes = _fetch_guest_quotes(all_tickers)
    guest_positions = _guest_portfolio_positions(current_asset, quotes)

    # ── PB 리스크-우선 진단 + 벤치마크 (샘플) — 실사용자 경로와 동일 컴포넌트 재사용 ──
    st.markdown(_PB_CSS, unsafe_allow_html=True)
    from datetime import date as _date
    from core.pb import holdings_for_pb, pb_diagnostics
    _uname = st.session_state.get("username")
    _cash = next((p["market_value"] for p in guest_positions if p.get("category") == "현금"), 0) or 0
    _sval = float(_journey_get("start_value", _uname, True, max(1.0, current_asset * 0.62)))
    _sd_raw = _journey_get("start_date", _uname, True, (_date.today() - timedelta(days=730)).isoformat())
    _start = _date.fromisoformat(_sd_raw) if isinstance(_sd_raw, str) else _sd_raw
    _bench = _get_bench_returns(_sd_raw if isinstance(_sd_raw, str) else _sd_raw.isoformat())
    _diag = pb_diagnostics(holdings_for_pb(guest_positions), current_asset, _cash, _start, _sval, _bench)
    if _diag:
        # 진단부 위 '샘플 포트폴리오' 인라인 마커 제거 — 홈 히어로 .gp-kicker 가 동일 표기 담당(페이지당 1회).
        st.markdown(_pb_risk_card_html(_diag), unsafe_allow_html=True)
        _bm = _benchmark_compare_html(_diag, _bench)
        if _bm:
            st.markdown(_bm, unsafe_allow_html=True)

    st.markdown(_guest_home_html(guest_positions, current_asset, target_asset, progress, _diag), unsafe_allow_html=True)

    st.markdown('<div id="guest-journey"></div>', unsafe_allow_html=True)
    _render_asset_journey(current_asset, is_guest=True)

    st.markdown("""
<div id="guest-watchlist" class="gp-header">
  <h2>관심 종목 샘플</h2>
  <p>실계좌를 연결하면 이 영역은 내 보유 종목과 관심 종목 중심으로 바뀝니다. 카테고리별 주요 종목은 아래에서 펼쳐 볼 수 있습니다.</p>
</div>""", unsafe_allow_html=True)

    with st.expander("관심 종목 샘플 펼치기 (카테고리별 주요 종목)", expanded=False):
        for category, tickers in _GUEST_CATEGORIES.items():
            st.markdown(f'<div class="gp-section"><div class="gp-section-title">{category}</div></div>', unsafe_allow_html=True)
            cards = []
            for tk in tickers:
                q = quotes.get(tk, {})
                price = q.get("price")
                chg = q.get("chg")
                name = _GUEST_TICKER_NAMES.get(tk, tk)
                short_tk = tk.replace(".KS", "").replace("-USD", "")

                if price is None:
                    price_str = "—"
                    chg_str, chg_cls = "—", "flat"
                else:
                    price_str = _cur(price, "KRW") if tk.endswith(".KS") else _cur(price, "USD")
                    if chg is None:
                        chg_str, chg_cls = "—", "flat"
                    elif chg > 0.05:
                        chg_str, chg_cls = f"+{chg:.2f}%", "pos"
                    elif chg < -0.05:
                        chg_str, chg_cls = f"{chg:.2f}%", "neg"
                    else:
                        chg_str, chg_cls = f"{chg:.2f}%", "flat"

                cards.append(
                    f'<div class="gp-card">'
                    f'<div class="gp-badge">TOP5</div>'
                    f'<div class="gp-card-name">{name}</div>'
                    f'<div class="gp-card-ticker">{short_tk}</div>'
                    f'<div class="gp-card-price">{price_str}</div>'
                    f'<div class="gp-card-chg {chg_cls}">{chg_str}</div>'
                    f'</div>'
                )
            st.markdown('<div class="gp-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)

    st.markdown("""
<div style="margin-top:24px;padding:16px 20px;background:#16181F;border:1px solid #262A33;
  border-radius:16px;font-size:13px;color:#9AA0AD;text-align:center;">
  실계좌 연동을 위해 <strong style="color:#E7E9EE;">로그인 → 계좌연동</strong>을 진행해 주세요.
</div>""", unsafe_allow_html=True)
    st.markdown(jj_footer(), unsafe_allow_html=True)
