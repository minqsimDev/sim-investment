"""
장중 자동 새로고침 — 상태 배지 + 60초 주기 리런 + 캐시 버스팅 버킷.

사용:
    bucket = live_refresh(["US"])           # 페이지 상단에서 호출(배지 렌더 + 자동 갱신 가동)
    df = _some_price_fetcher(key, _bucket=bucket)   # 캐시 키에 bucket을 끼워 장중 60초마다 자연 만료

주의: yfinance는 ~15분 지연 소스라 '틱 단위 실시간'이 아니라 '소스가 주는 한 가장 최신'을 자동 유지한다.
"""
from __future__ import annotations

import streamlit as st

from core.market_hours import any_open, live_bucket

_REFRESH_SEC = 60

_BADGE_CSS = """<style>
.lv-badge{display:inline-flex;align-items:center;gap:7px;padding:4px 11px;border-radius:999px;
  font-size:11px;font-weight:800;letter-spacing:.2px;margin:0 0 10px}
.lv-badge.open{background:rgba(38,194,129,.12);border:1px solid rgba(38,194,129,.35);color:#3DD68C}
.lv-badge.closed{background:#16181F;border:1px solid #262A33;color:#9AA0AD}
.lv-dot{width:7px;height:7px;border-radius:50%}
.lv-badge.open .lv-dot{background:#3DD68C;box-shadow:0 0 0 0 rgba(61,214,140,.6);animation:lv-pulse 1.8s infinite}
.lv-badge.closed .lv-dot{background:#5A5F68}
@keyframes lv-pulse{0%{box-shadow:0 0 0 0 rgba(61,214,140,.5)}70%{box-shadow:0 0 0 6px rgba(61,214,140,0)}100%{box-shadow:0 0 0 0 rgba(61,214,140,0)}}
</style>"""


@st.fragment(run_every=_REFRESH_SEC)
def _auto_tick(markets: list[str]) -> None:
    """장중이면 60초마다 전체 리런을 트리거(만료된 시세 캐시 재조회). 장마감이면 무동작.

    주의: run_every 프래그먼트는 '첫 렌더에서도 즉시 1회 실행'된다. 무조건 st.rerun()을 부르면
    즉시 리런 → 또 즉시 실행 → 무한 루프(화면 안 뜸)가 된다. 따라서 시간 버킷이 실제로
    바뀌었을 때(=60초가 지난 재실행 시점)에만 전체 리런한다.
    """
    if not any_open(markets):
        return
    key = "_live_tick_" + "_".join(markets)
    cur = live_bucket(markets)
    prev = st.session_state.get(key)
    st.session_state[key] = cur
    if prev is not None and cur != prev:
        st.rerun()  # 버킷 진행 → 전체 리런(시세 재조회). 첫 실행(prev=None)은 기록만 하고 통과.


def live_badge_html(markets: list[str], label: str | None = None, compact: bool = False) -> str:
    """상태 배지 HTML 문자열만 반환(렌더 안 함) — 다른 헤더에 끼워 넣을 때 사용.
    compact=True 면 축약('장중 · 60초'), 상세는 title 툴팁으로."""
    name = label or " · ".join(markets)
    if any_open(markets):
        if compact:
            return (f'{_BADGE_CSS}<span class="lv-badge open" title="{name} · {_REFRESH_SEC}초 자동 갱신 · yfinance ~15분 지연">'
                    f'<span class="lv-dot"></span>장중 · {_REFRESH_SEC}초</span>')
        return (f'{_BADGE_CSS}<span class="lv-badge open"><span class="lv-dot"></span>'
                f'장중 · {name} · {_REFRESH_SEC}초 자동 갱신 <span style="opacity:.6">(yfinance ~15분 지연)</span></span>')
    if compact:
        return (f'{_BADGE_CSS}<span class="lv-badge closed" title="{name} · 수동 갱신">'
                f'<span class="lv-dot"></span>장마감</span>')
    return (f'{_BADGE_CSS}<span class="lv-badge closed"><span class="lv-dot"></span>'
            f'장마감 · {name} · 수동 갱신</span>')


def live_refresh(markets: list[str], *, label: str | None = None, render: bool = True) -> int:
    """장중 자동 갱신 가동 + (render=True면) 상태 배지 렌더. 캐시 버스팅용 bucket(int) 반환."""
    if render:
        st.markdown(live_badge_html(markets, label), unsafe_allow_html=True)
    _auto_tick(markets)
    return live_bucket(markets)
