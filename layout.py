"""
layout.py — SIM INVESTMENT 반응형 레이아웃 헬퍼
siminvest_theme.py 와 짝으로 사용. 모바일/데스크탑 분기를 이 한 곳에서 관리한다.

설계 원칙
- 색 컨벤션(상승=빨강, 하락=파랑)은 siminvest_theme 에서 강제 → 여기서는 '레이아웃'만 담당.
- 뷰포트 폭은 세션에 1회만 캐시. 매 rerun 마다 JS 왕복하지 않는다.
- 폭 감지 실패(JS 미수신/미설치) 시 데스크탑으로 폴백 → 첫 페인트가 깨지지 않게.
- 진짜 교체가 필요한 것(표→카드, 트리맵→리스트)은 Python 분기,
  단순 재스타일(칩 가로 스크롤·여백·폰트)은 CSS 미디어쿼리로 처리.

의존성(선택): streamlit-js-eval
    pip install streamlit-js-eval
    미설치 시에도 동작하며, 항상 데스크탑으로 간주한다.
"""

from __future__ import annotations

import streamlit as st

MOBILE_BREAKPOINT = 768  # px

# --- 색 토큰: siminvest_theme 를 단일 출처로 사용 ---
# 상승/하락/브랜드 색은 siminvest_theme 에서 가져와 코드베이스 전체와 일치시킨다.
# (단독 실행·경로 문제 등으로 import 실패 시에도 동일 hex 로 폴백해 색 컨벤션을 유지.)
try:
    from siminvest_theme import UP, DOWN, GOLD
except Exception:
    UP = "#F25560"    # 상승 (한국식 빨강)
    DOWN = "#4D90F0"  # 하락 (한국식 파랑)
    GOLD = "#D9A441"  # 브랜드 액센트
FLAT = "#9AA0AD"  # 보합 / 중립 (siminvest_theme 의 .sv-metric 라벨 톤과 정렬; 테마에 별도 토큰 없음)
BASE = "#0E0F13"  # 다크 베이스 (config.toml backgroundColor)


# ──────────────────────────────────────────────────────────────
# 1. 뷰포트 감지
# ──────────────────────────────────────────────────────────────
def _detect_width():
    """streamlit-js-eval 로 window.innerWidth 를 받아온다. 미설치/미수신 시 None."""
    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError:
        return None
    w = streamlit_js_eval(js_expressions="window.innerWidth", key="siminvest_vw")
    try:
        return int(w)
    except (TypeError, ValueError):
        return None


def viewport_width(default: int = 1200) -> int:
    """
    세션 캐시된 뷰포트 폭(px). 최초 1회만 JS 감지, 이후 캐시 사용.
    ⚠️ 페이지 최상단에서 한 번 호출해두면, 무거운 렌더 전에 폭이 확정돼 깜빡임이 준다.
    """
    if "siminvest_vw_px" in st.session_state:
        return st.session_state["siminvest_vw_px"]
    w = _detect_width()
    if w:
        st.session_state["siminvest_vw_px"] = w
        return w
    # JS 가 아직 안 돌아온 첫 rerun: 캐시하지 않고 default 로 폴백
    return default


def is_mobile(breakpoint: int = MOBILE_BREAKPOINT) -> bool:
    return viewport_width() < breakpoint


# ──────────────────────────────────────────────────────────────
# 2. 반응형 CSS (재스타일 전용)
# ──────────────────────────────────────────────────────────────
def inject_responsive_css(breakpoint: int = MOBILE_BREAKPOINT) -> None:
    """페이지당 1회 호출. 칩 가로 스크롤·여백·폰트·카드 스타일을 주입한다."""
    st.markdown(
        f"""
        <style>
          /* CSS/JS 주입으로 생긴 빈(0높이) 블록이 세로 flex gap 을 먹어 콘텐츠 사이 공백이
             쌓이는 것을 방지(데스크탑·모바일 공통). style:only-child 만 골라 '스타일+본문'
             혼합 마크다운(예: 카드 상세)은 건드리지 않는다.
             (display:none 이어도 <style> 규칙은 전역 적용되어 무해) */
          [data-testid=stElementContainer]:empty,
          [data-testid=stElementContainer]:has(> [data-testid=stMarkdown] [data-testid=stMarkdownContainer] > style:only-child) {{ display: none !important; }}
          /* 폭 감지용 streamlit_js_eval 컴포넌트: 보이는 26px 블록 + flex gap 으로 공백을 만든다.
             폭 측정은 유지(width:100%)하되 흐름에서 빼고(absolute) 높이 0 으로 접어 공백 제거. */
          [data-testid=stElementContainer]:has(iframe[src*="streamlit_js_eval"]) {{
            position: absolute !important; width: 100% !important; height: 0 !important;
            overflow: hidden !important; margin: 0 !important; padding: 0 !important; pointer-events: none !important;
          }}
          /* ── 모바일 ── */
          @media (max-width: {breakpoint}px) {{
            .block-container {{ padding: 0.75rem 0.75rem 4.75rem !important; }}
            .siminvest-desktop-only {{ display: none !important; }}
            h1 {{ font-size: 1.5rem !important; }}
            h2 {{ font-size: 1.2rem !important; }}
            .siminvest-chiprow {{
              overflow-x: auto; flex-wrap: nowrap !important;
              -webkit-overflow-scrolling: touch;
            }}
            .siminvest-chiprow::-webkit-scrollbar {{ display: none; }}
          }}
          /* ── 데스크탑 ── */
          @media (min-width: {breakpoint + 1}px) {{
            .siminvest-mobile-only {{ display: none !important; }}
          }}

          .siminvest-chiprow {{ display: flex; gap: .5rem; padding-bottom: .25rem; }}
          .siminvest-chip {{
            flex: 0 0 auto; padding: .35rem .7rem; border-radius: 999px;
            background: rgba(255,255,255,.05); font-size: .8rem; white-space: nowrap;
          }}

          .siminvest-card {{
            border: 1px solid rgba(255,255,255,.08); border-radius: 14px;
            padding: .85rem 1rem; margin-bottom: .6rem; background: rgba(255,255,255,.02);
          }}
          .siminvest-card .row {{
            display: flex; justify-content: space-between; align-items: baseline; gap: .75rem;
          }}
          .siminvest-card .name {{ font-weight: 700; font-size: 1rem; }}
          .siminvest-card .sub {{ color: {FLAT}; font-size: .78rem; margin-top: .1rem; }}
          .siminvest-card .price {{ font-weight: 700; font-variant-numeric: tabular-nums; }}
          .siminvest-card .chg {{
            font-weight: 600; font-size: .85rem; font-variant-numeric: tabular-nums;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# 3. 등락 색 (한국식: 상승 빨강 / 하락 파랑)
# ──────────────────────────────────────────────────────────────
def _sign(v) -> int:
    """문자열('+81.0%','−1.90%') 또는 숫자에서 부호 추출 → 1 / -1 / 0."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return 1 if v > 0 else (-1 if v < 0 else 0)
    s = str(v).strip()
    if s.startswith("-") or s.startswith("−"):  # 일반 하이픈 + 유니코드 마이너스
        return -1
    if s.startswith("+"):
        return 1
    try:
        f = float(s.replace("%", "").replace(",", "").replace("+", ""))
        return 1 if f > 0 else (-1 if f < 0 else 0)
    except ValueError:
        return 0


def change_color(v) -> str:
    s = _sign(v)
    return UP if s > 0 else (DOWN if s < 0 else FLAT)


# ──────────────────────────────────────────────────────────────
# 4. 핵심: 표 ↔ 카드 전환
# ──────────────────────────────────────────────────────────────
def render_table_or_cards(
    df,
    *,
    title_col: str,
    subtitle_col: str | None = None,
    price_col: str | None = None,
    change_cols: list | None = None,
    detail_cols: list | None = None,
    breakpoint: int = MOBILE_BREAKPOINT,
    desktop_renderer=None,
):
    """
    데스크탑: 기존 표(desktop_renderer) 또는 st.dataframe.
    모바일: 종목당 카드 1장 — 제목/현재가 크게, 등락은 한국식 색, 나머지는 '상세'로 접기.

    예)
        render_table_or_cards(
            df,
            title_col="종목", subtitle_col="섹터", price_col="현재가",
            change_cols=["1D %", "3M %"],
            detail_cols=["1W %", "1M %", "MA20 이격%"],
            desktop_renderer=my_existing_styled_table,  # 기존 표 그대로 재사용 가능
        )
    """
    change_cols = change_cols or []
    detail_cols = detail_cols or []

    if not is_mobile(breakpoint):
        if desktop_renderer is not None:
            desktop_renderer(df)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
        return

    # ── 모바일 카드 ──
    for _, r in df.iterrows():
        chips = ""
        for c in change_cols:
            if c in r and r[c] is not None:
                col = change_color(r[c])
                label = c.replace(" %", "")
                chips += (
                    f'<span class="chg" style="color:{col}">{label} {r[c]}</span>'
                    "&nbsp;&nbsp;"
                )
        price_html = (
            f'<span class="price">{r[price_col]}</span>'
            if price_col and price_col in r
            else ""
        )
        sub_html = (
            f'<div class="sub">{r[subtitle_col]}</div>'
            if subtitle_col and subtitle_col in r
            else ""
        )
        st.markdown(
            f"""
            <div class="siminvest-card">
              <div class="row">
                <div><div class="name">{r[title_col]}</div>{sub_html}</div>
                <div style="text-align:right">{price_html}<div>{chips}</div></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if detail_cols:
            with st.expander("상세"):
                for c in detail_cols:
                    if c in r:
                        col = change_color(r[c]) if "%" in c else FLAT
                        st.markdown(
                            f'<span class="sub">{c}</span> · '
                            f'<span style="color:{col}">{r[c]}</span>',
                            unsafe_allow_html=True,
                        )


# ──────────────────────────────────────────────────────────────
# 5. 지표 카드 행 (st.metric 대체 — 한국식 색 강제)
# ──────────────────────────────────────────────────────────────
def _metric_card(m: dict):
    delta = m.get("delta")
    color = change_color(delta) if delta is not None else FLAT
    delta_html = (
        f'<div class="chg" style="color:{color}">{delta}</div>' if delta is not None else ""
    )
    st.markdown(
        f"""
        <div class="siminvest-card" style="margin-bottom:.5rem">
          <div class="sub">{m.get("label", "")}</div>
          <div class="price" style="font-size:1.25rem">{m.get("value", "")}</div>
          {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# 6. 가로 스크롤 칩 줄 (핵심 지표 칩 등)
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# 7. 디바이스별 분기 헬퍼 (트리맵 ↔ 리스트 등 진짜 교체용)
# ──────────────────────────────────────────────────────────────
def only_desktop(render_fn, breakpoint: int = MOBILE_BREAKPOINT):
    """데스크탑에서만 실행. 예: 트리맵/시총 히트맵."""
    if not is_mobile(breakpoint):
        render_fn()


def only_mobile(render_fn, breakpoint: int = MOBILE_BREAKPOINT):
    """모바일에서만 실행. 예: 상승/하락 상위 N개 리스트."""
    if is_mobile(breakpoint):
        render_fn()


def top_movers_list(df, *, name_col: str, change_col: str, n: int = 5):
    """
    트리맵의 모바일 대체용. 등락 상위/하위 N개를 카드 리스트로.
    """
    try:
        ranked = df.copy()
        ranked["_v"] = ranked[change_col].map(_signed_value)
        gainers = ranked.sort_values("_v", ascending=False).head(n)
        losers = ranked.sort_values("_v", ascending=True).head(n)
    except Exception:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    for title, sub in [("상승 상위", gainers), ("하락 상위", losers)]:
        st.markdown(f'<div class="sub" style="margin:.4rem 0">{title}</div>',
                    unsafe_allow_html=True)
        for _, r in sub.iterrows():
            col = change_color(r[change_col])
            st.markdown(
                f"""
                <div class="siminvest-card" style="padding:.6rem .9rem">
                  <div class="row">
                    <span class="name" style="font-size:.95rem">{r[name_col]}</span>
                    <span class="chg" style="color:{col}">{r[change_col]}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _signed_value(v) -> float:
    try:
        return float(str(v).replace("%", "").replace(",", "")
                     .replace("+", "").replace("−", "-"))
    except ValueError:
        return 0.0


# ──────────────────────────────────────────────────────────────
# 8. (선택) 모바일 하단 고정 탭바
# ──────────────────────────────────────────────────────────────