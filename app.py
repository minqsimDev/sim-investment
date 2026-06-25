import os
from pathlib import Path
from PIL import Image
import streamlit as st
from dotenv import load_dotenv

from core.brand import APP_NAME
from siminvest_theme import theme_root_css

load_dotenv()

_icon = Image.open(Path(__file__).parent / "assets" / "intro" / "sim_heart_logo_transparent.png")

st.set_page_config(
    page_title=APP_NAME,
    page_icon=_icon,
    layout="wide",
)

# 색 토큰(:root CSS 변수) 전역 주입 — 인증 게이트보다 먼저(로그인 포함 모든 페이지가
# var(--sv-gold) 등을 쓸 수 있게). 색의 단일 출처는 siminvest_theme.py.
st.markdown(theme_root_css(), unsafe_allow_html=True)

# 문서 lang을 ko로 고정 — Streamlit 기본값 lang="en" 이면 한·중·일 공유 글자(한자 漢字)가
# macOS에서 일본어 글꼴(Hiragino)로 폴백돼 일본어처럼 보인다. ko 로 두면 한국어 글꼴로 렌더.
# st.html 은 스크립트를 실행하지 않으므로 components.html(iframe srcdoc, 동일 출처)에서 window.parent 로 부모 문서를 수정.
import streamlit.components.v1 as _components
_components.html(
    "<script>try{window.parent.document.documentElement.lang='ko';}catch(e){}</script>",
    height=0, width=0,
)


# ── Cache warming (서버 부팅 1회) ────────────────────────────────────────────────
# st.cache_resource → 프로세스당 1회만 본문 실행. 진입 경로(로그인/게스트/하드nav)와
# 무관하게 부팅 직후 백그라운드로 디스크 캐시(가격 벌크·FRED·애널리스트 타깃)를 예열해
# 첫 사용자의 콜드 스타트(~8초 네트워크 대기)를 제거한다.
@st.cache_resource(show_spinner=False)
def _warm_caches_once():
    import threading
    import time

    _WARM_INTERVAL = 1500  # 25분(<디스크 ttl 1800) 주기 재예열 → 캐시 항상 신선

    def _warm(force: bool):
        try:
            from data.fetcher import fetch_all
            fetch_all(force=force)  # 가격 벌크(+FRED) 디스크 캐시 예열 (내부 병렬)
        except Exception:
            pass
        try:
            from concurrent.futures import ThreadPoolExecutor
            from data.session import cached_ticker_info
            from data.loader import _TP_TICKERS
            with ThreadPoolExecutor(max_workers=min(len(_TP_TICKERS), 12)) as ex:
                list(ex.map(cached_ticker_info, _TP_TICKERS))  # 애널리스트 타깃가 info 예열
        except Exception:
            pass

    def _bg():
        _warm(force=False)          # 부팅 직후 1회 — 콜드 스타트 제거
        while True:                 # 이후 keep-warm: stale-while-revalidate
            time.sleep(_WARM_INTERVAL)
            _warm(force=True)       # 네트워크 강제 갱신으로 디스크를 항상 신선하게
            try:
                from data.loader import clear_market_cache
                clear_market_cache()  # st.cache_data 메모 비움 → 다음 요청은 신선한 디스크 히트(블로킹 0)
            except Exception:
                pass

    threading.Thread(target=_bg, daemon=True).start()
    return True


_warm_caches_once()

# 연결 끊김 시 뜨는 Streamlit 기본 'Connection error' 모달(영어·개발자용 문구,
# 'streamlit run yourscript.py' 등)을 한국어 안내로 교체. 인증 게이트보다 먼저 — 로그인
# 화면 포함 모든 페이지에서 끊김이 날 수 있으므로 항상 주입한다. 모달은 stApp 밖으로 portal
# 되고 버전마다 DOM 이 달라 CSS 셀렉터가 불안정 → 텍스트로 식별해 rewrite. 연결 에러 문구는
# 앱 자체 st.dialog 엔 절대 안 나오므로 오인 교체 위험 없음. (liquid_bg 와 동일한 부모 주입 패턴)
from ui.components.html_embed import embed_html as _embed_html

_conn_i18n_parent = (
    "(function(){"
    "if(window.__svConnObs) return;"
    "function fix(){"
    "  document.querySelectorAll('[data-testid=\"stDialog\"] [role=\"dialog\"]').forEach(function(d){"
    "    var t=d.innerText||'';"
    "    if(!/Connection error|Streamlit server is not responding|Is Streamlit still running/.test(t)) return;"
    "    var head=d.children[0], body=d.children[1];"
    "    if(head && head.getAttribute('data-sv-i18n')!=='1'){head.textContent='연결이 잠시 끊겼어요';head.setAttribute('data-sv-i18n','1');}"
    "    if(body && body.getAttribute('data-sv-i18n')!=='1'){body.textContent='서버에 다시 연결하는 중입니다. 대개 잠시 후 자동으로 복구돼요. 계속되면 페이지를 새로고침해 주세요.';body.setAttribute('data-sv-i18n','1');}"
    "  });"
    "}"
    "window.__svConnObs=new MutationObserver(fix);"
    "window.__svConnObs.observe(document.body,{childList:true,subtree:true});"
    "fix();"
    "})();"
)
_conn_boot = (
    '<script type="text/plain" id="sv-conn-src">' + _conn_i18n_parent + "</script>"
    "<script>(function(){try{"
    "var pdoc=window.parent.document, pwin=window.parent;"
    "if(pwin.__svConnInjected) return; pwin.__svConnInjected=true;"
    "var c=document.getElementById('sv-conn-src').textContent;"
    "var s=pdoc.createElement('script'); s.textContent=c; pdoc.body.appendChild(s);"
    "}catch(e){console.error('conn-i18n',e);}})();</script>"
)
_embed_html(_conn_boot, height=0)

# ── Logout — 게스트/로그인 세션 종료 후 로그인 랜딩으로 ──────────────────────────
if st.query_params.get("logout") == "1":
    for _k in ("authenticated", "auth_role", "username", "brokerage_provider",
               "brokerage_holdings", "brokerage_cash_balance", "brokerage_token"):
        st.session_state.pop(_k, None)
    # 게스트 자동복원용 localStorage 플래그 제거(다음 탐색에서 재진입 방지)
    st.html("<script>try{window.localStorage.removeItem('siminvest_auth_role');}catch(e){}</script>")

# ── Auth ──────────────────────────────────────────────────────────────────────
_auth_param = st.query_params.get("_auth")
if _auth_param == "guest":
    st.session_state.authenticated = True
    st.session_state.auth_role = "guest"
    # _auth=guest를 URL에 유지 — nav 이동 후 세션 복원에 사용됨

# 로그인 유저 — ?_user=<username> 파라미터로 하드 nav 후 세션 복원
_url_user = st.query_params.get("_user", "").strip()
if _url_user and not st.session_state.get("authenticated"):
    from core.accounts import has_account, get_portfolios
    if has_account(_url_user):
        from ui.pages.login import _filter_valid_holdings
        _sess = {
            "authenticated": True,
            "auth_role": "user",
            "username": _url_user,
        }
        # 저장된 포트폴리오 전체 복원 — login.py 성공 경로와 동일하게
        # (브로커리지 세션을 함께 복원해야 portfolio.py가 "세션 만료"로 막지 않음)
        _ports = get_portfolios(_url_user)
        if _ports:
            _first = _ports[0]
            _sess.update({
                "brokerage_provider": "screenshot",
                "brokerage_holdings": _filter_valid_holdings(_first.get("holdings", [])),
                "brokerage_cash_balance": _first.get("cash", 0.0),
            })
        st.session_state.update(_sess)

if not st.session_state.get("authenticated", False):
    # 캐시 예열은 _warm_caches_once()가 부팅 1회 처리(진입 경로 무관) — 여기선 로그인만 렌더
    from ui.pages.login import render as _login_render
    _login_render()
    st.stop()

if st.session_state.get("auth_role") == "guest":
    st.html("""
<script>
try { window.localStorage.setItem("siminvest_auth_role", "guest"); } catch (e) {}
</script>
""")

# Global refresh via nav icon — ?refresh=1 clears all caches
if st.query_params.get("refresh") == "1":
    st.cache_data.clear()
    st.query_params.clear()  # triggers rerun automatically

# Inject CSS into document.head via JS. The top navigation lives in Streamlit's
# header area, so we keep the header available and hide only the app chrome.
st.html("""
<script>
(function(){
    var s=document.getElementById('sv-chrome-hide') || document.createElement('style');
    s.id='sv-chrome-hide';
    s.textContent=[
        '[data-testid="stStatusWidget"]{display:none!important}',
        '#MainMenu{display:none!important}',
        'footer{display:none!important}',
        '.stAppDeployButton{display:none!important}',
    ].join('');
    if(!s.parentNode){document.head.appendChild(s);}
})();
</script>
""")

# ── Pages ─────────────────────────────────────────────────────────────────────
from ui.pages import overview, portfolio, market, risk_signals, stock_detail, telegram_connect
from ui.components.dash_style import inject_shell_css, render_shell_header

# 미국주식·한국주식·원자재·FX&금리·전 자산 비교(구 '주요 이동')는 시장 페이지 내부 탭으로 통합됨.
# 홈은 "/"(default)에 서비스되지만, /overview 직접 진입 시 Streamlit "Page not found" 모달이
# 뜨므로 동일 콘텐츠를 /overview 에도 명시 등록한다.
def _home_render():
    # Liquid Ink 배경은 로그인 화면에서만 — 전체현황(홈)에선 정적 배경 유지
    overview.render()

# 구(舊) 독립 페이지 경로(/movers·/us-stocks·/kr-stocks·/commodities·/fx)는 시장 탭으로 통합되며
# 라우트가 사라져, 그 URL을 북마크/히스토리로 다시 열면 Streamlit "Page not found" 모달이 뜬다.
# → 레거시 경로를 모두 시장 페이지로 흡수해 모달이 절대 뜨지 않게 한다(커스텀 네비엔 노출 안 됨).
# 텔레그램 알림 연결(네비 비노출) — 로그인 유저만. 게스트는 안내 후 차단.
def _telegram_connect_render():
    if st.session_state.get("auth_role") == "guest" or not st.session_state.get("username"):
        st.info("텔레그램 위험 알림은 로그인 후 이용할 수 있어요.")
        return
    telegram_connect.render(st.session_state["username"])

def _legacy_movers():       market.render()
def _legacy_us_stocks():    market.render()
def _legacy_kr_stocks():    market.render()
def _legacy_commodities():  market.render()
def _legacy_fx():           market.render()

_pages = [
    st.Page(_home_render,         title="홈",         url_path="home",          default=True),  # "/"
    st.Page(overview.render,      title="전체 현황",  url_path="overview"),                       # "/overview"
    st.Page(portfolio.render,     title="포트폴리오", url_path="portfolio"),
    st.Page(market.render,        title="시장",       url_path="market"),
    st.Page(risk_signals.render,  title="리스크",     url_path="risk"),
    st.Page(stock_detail.render,  title="종목",       url_path="stock"),   # 검색·워치리스트 종착지(네비 비노출)
    st.Page(_telegram_connect_render, title="알림 연결", url_path="telegram"),  # 텔레그램 연결(네비 비노출)
    # ── 레거시 경로 흡수(네비 비노출) — 모달 방지 ──
    st.Page(_legacy_movers,       title="시장",       url_path="movers"),
    st.Page(_legacy_us_stocks,    title="시장",       url_path="us-stocks"),
    st.Page(_legacy_kr_stocks,    title="시장",       url_path="kr-stocks"),
    st.Page(_legacy_commodities,  title="시장",       url_path="commodities"),
    st.Page(_legacy_fx,           title="시장",       url_path="fx"),
]
pg = st.navigation(_pages, position="hidden")

inject_shell_css()
render_shell_header(_pages)

# 전역 종목 검색 — 헤더 바로 아래, 모든 화면 공통
from ui.components.search import render_global_search
render_global_search()

pg.run()
