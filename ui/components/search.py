"""전역 종목 검색 — 헤더 아래 어디서나 접근.

종목명/티커 부분일치(대소문자 무시) → 해당 시장 탭으로 이동.
유니버스: 보유종목 + 미국·한국·크립토·ETF·원자재·외환 전체.
라우팅은 기존 nav 와 동일하게 href(?market_tab=…) + 인증 suffix(_user/_auth)로 통일.
"""
from __future__ import annotations

import streamlit as st

# 카테고리 라벨 → market_tab slug
_CAT_SLUG = {
    "미국": "us", "한국": "kr", "크립토": "crypto",
    "ETF": "etf", "원자재": "commodities", "외환": "fx",
}

_GS_CSS = """<style>
.gs-item{display:flex;align-items:center;gap:10px;padding:9px 12px;margin:4px 0;
  background:#16181F;border:1px solid #262A33;border-radius:12px;text-decoration:none}
.gs-item:hover{border-color:#D9A441;background:#1B1E27}
.gs-item b{color:#E7E9EE;font-size:13.5px;font-weight:850;
  flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gs-item .gs-tk{flex-shrink:0}
.gs-item .gs-tk{color:#9AA0AD;font-size:11.5px;font-weight:700;
  font-variant-numeric:tabular-nums;font-family:'SF Mono',ui-monospace,monospace}
.gs-item .gs-cat{margin-left:auto;color:#7E8694;font-size:10.5px;font-weight:800;
  background:#1E2029;border:1px solid #262A33;border-radius:999px;padding:2px 9px}
.gs-watch-row{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-top:8px}
.gs-watch-k{font-size:10.5px;font-weight:850;color:#7E8694;text-transform:uppercase;letter-spacing:.04em}
.gs-watch{font-size:11.5px;font-weight:850;color:#D9A441;text-decoration:none;
  background:rgba(217,164,65,.10);border:1px solid rgba(217,164,65,.34);border-radius:999px;padding:3px 11px}
.gs-watch:hover{background:rgba(217,164,65,.2);border-color:#D9A441}
</style>"""

# 검색 바(#6): expander의 '>' 꺾쇠(펼침 메뉴처럼 보임) 대신 돋보기 아이콘 + 플레이스홀더만.
# 항상 보이는 한 줄 입력 → 접힘 details가 만들던 상단 빈 여백도 함께 제거.
_GS_BAR_CSS = """<style>
/* 검색 입력만 고유하게 타겟(aria-label). 돋보기는 래퍼 ::before로 얹는다
   (input background 는 Streamlit이 덮어써서 ::before 가 안정적). */
[data-testid="stTextInput"]:has(input[aria-label="종목 검색"]){margin:2px 0 6px}
/* 전역 .stTextInput input(15px/850!important)을 이기려면 특정성을 높인다(.stTextInput 접두) */
.stTextInput input[aria-label="종목 검색"]{padding-left:38px!important;font-size:13.5px!important;font-weight:600!important}
.stTextInput input[aria-label="종목 검색"]::placeholder{font-size:13px!important;font-weight:500!important}
[data-testid="stTextInput-RootElement"]:has(input[aria-label="종목 검색"]){position:relative}
[data-testid="stTextInput-RootElement"]:has(input[aria-label="종목 검색"])::before{
  content:"";position:absolute;left:14px;top:50%;transform:translateY(-50%);
  width:16px;height:16px;z-index:2;pointer-events:none;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239AA0AD' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m21 21-4.3-4.3'/%3E%3C/svg%3E") no-repeat center/16px}
</style>"""


def _render_watchlist(auth: str) -> None:
    """워치리스트 빠른 이동 — 종목 상세로 바로 가는 별표 칩(검색 비었을 때)."""
    u = st.session_state.get("username")
    if u and st.session_state.get("auth_role") != "guest":
        from core.accounts import get_setting
        wl = get_setting(u, "watchlist", []) or []
    else:
        wl = st.session_state.get("_guest_watchlist", [])
    if not wl:
        return
    amp = f"&{auth}" if auth else ""
    pills = "".join(
        f'<a class="gs-watch" href="/stock?symbol={tk}{amp}" target="_self">★ {tk}</a>'
        for tk in wl[:12]
    )
    st.markdown(_GS_CSS + f'<div class="gs-watch-row"><span class="gs-watch-k">워치리스트</span>{pills}</div>',
                unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _build_universe() -> list[tuple[str, str, str]]:
    """(표시명, 티커, 카테고리) 리스트. 시장 페이지의 정적 유니버스 상수를 모은다(프로세스당 1회)."""
    items: list[tuple[str, str, str]] = []
    try:
        from ui.pages.us_stocks import _US_UNIVERSE
        items += [(nm, tk, "미국") for tk, nm, _ in _US_UNIVERSE]
    except Exception:
        pass
    try:
        from ui.pages.kr_stocks import _KR_UNIVERSE
        items += [(nm, tk.replace(".KS", ""), "한국") for tk, nm, _ in _KR_UNIVERSE]
    except Exception:
        pass
    try:
        from ui.pages.etf import _KR_ETF_UNIVERSE
        items += [(nm, tk.replace(".KS", ""), "ETF") for _, nm, tk in _KR_ETF_UNIVERSE]
    except Exception:
        pass
    try:
        from ui.pages.crypto import _CRYPTO_UNIVERSE
        items += [(nm, tk.replace("-USD", ""), "크립토") for nm, tk in _CRYPTO_UNIVERSE]
    except Exception:
        pass
    try:
        from ui.pages.commodities import _META   # {key: (한글명, 단위, 그룹)} — 티커 없이 key만
        items += [(nm, key, "원자재") for key, (nm, _u, _g) in _META.items()]
    except Exception:
        pass
    try:
        from ui.pages.fx_rates import _PAIR_LABELS, _PAIR_NAMES
        items += [(_PAIR_NAMES.get(k, lbl), lbl, "외환") for k, lbl in _PAIR_LABELS.items()]
    except Exception:
        pass
    return items


def _auth_qs() -> str:
    """현재 세션의 인증 쿼리스트링(앞 구분자 없음). 게스트/로그인 세션 유지용."""
    role = st.session_state.get("auth_role")
    if role == "guest":
        return "_auth=guest"
    user = st.session_state.get("username")
    return f"_user={user}" if user else ""


def render_global_search() -> None:
    """헤더 바로 아래에 1회 호출(app.py). 모든 화면에서 동일하게 노출.
    돋보기 검색 바(꺾쇠 없음) — 입력 시 결과, 비었을 땐 워치리스트만(여백 최소화)."""
    auth = _auth_qs()
    st.markdown(_GS_BAR_CSS, unsafe_allow_html=True)
    q = st.text_input(
        "종목 검색", key="global_search_q",
        placeholder="내 보유·주요 종목 검색 (예: 테슬라, 삼성전자, 금)",
        label_visibility="collapsed",
    )
    q = (q or "").strip()
    if not q:
        _render_watchlist(auth)   # 워치리스트 빠른 이동(있을 때만 렌더 → 비었으면 여백 0)
        return

    ql = q.lower()
    results = [it for it in _build_universe()
               if ql in it[0].lower() or ql in it[1].lower()]
    shown = {tk.lower() for _, tk, _ in results}
    # 보유종목 — 시장 유니버스에 없는 티커만 추가(중복 방지). 매칭 시 포트폴리오로 이동.
    for h in st.session_state.get("brokerage_holdings", []) or []:
        tk = str(h.get("ticker") or h.get("symbol") or h.get("code") or "").strip()
        nm = str(h.get("name") or h.get("asset_name") or h.get("display_name") or tk).strip()
        disp = tk.replace(".KS", "").replace("-USD", "")
        if not (nm or disp):
            continue
        if (ql in nm.lower() or ql in disp.lower()) and disp.lower() not in shown:
            results.append((nm, disp, "보유"))
            shown.add(disp.lower())
    if not results:
        st.caption(f"‘{q}’ 검색 결과가 없습니다 — 내 보유·주요 종목만 검색됩니다.")
        return

    amp = f"&{auth}" if auth else ""
    links = []
    for name, tk, cat in results[:12]:
        # 외환·원자재는 개별 종목 상세가 없어 해당 시장 탭으로, 나머지는 종목 상세 페이지로
        if cat == "외환":
            href = f"/market?market_tab=fx{amp}"
        elif cat == "원자재":
            href = f"/market?market_tab=commodities{amp}"
        else:
            href = f"/stock?symbol={tk}{amp}"
        links.append(
            f'<a class="gs-item" href="{href}" target="_self">'
            f'<b>{name}</b> <span class="gs-tk">{tk}</span>'
            f'<span class="gs-cat">{cat}</span></a>'
        )
    st.markdown(_GS_CSS + "".join(links), unsafe_allow_html=True)
    if len(results) > 12:
        st.caption(f"외 {len(results) - 12}건 — 검색어를 좁혀보세요.")
