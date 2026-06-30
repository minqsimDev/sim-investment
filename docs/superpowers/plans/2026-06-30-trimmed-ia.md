# 트림된 IA 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 네비를 전체현황·시장·포트폴리오 3개로 줄이고, 리스크를 포트폴리오 서브탭으로 흡수해 중복을 제거한다.

**Architecture:** `risk_signals.render()` 본문을 재사용 함수 `render_risk_body()`로 추출 → 포트폴리오의 서브탭(segmented control)과 `/risk` 라우트가 동일 함수를 호출(중복 0). 네비는 `app.py`(st.navigation 목록)와 `dash_style.py`(비주얼 핀 + 숨은 page_link + JS 브리지 인덱스) 두 곳을 함께 3개 기준으로 갱신. `/home`·`/risk`는 라우트로 남겨 북마크 보호(각각 전체현황·포트폴리오 렌더).

**Tech Stack:** Streamlit(멀티페이지 st.navigation/st.Page, st.segmented_control), Python. UI 검증은 Playwright 스크립트(이 코드베이스엔 UI 테스트 프레임워크가 없어 import 스모크 + Playwright 확인을 테스트 사이클로 사용).

## Global Constraints

- 작업 디렉터리: `/Users/min/DEV/sim-investment`. dev 서버: `.venv/bin/python -m streamlit run app.py --server.port 8501`.
- 로그인 세션 복원은 서명 토큰: 검증 URL 은 `?_user=<token>`, 토큰 생성 `python -c "from core.auth_token import make_token; print(make_token('minqsim'))"`. **평문 `?_user=minqsim` 은 차단됨**(검증 시 사용 금지).
- 색 의미 고정: 빨강/파랑=손익, 주황=위험경고, 골드=강조, 초록=양호. (위험에 빨강 금지)
- 단일 출처 유지: 진단/벤치마크는 `_account_diag`(portfolio) / `_my_holdings_for_impact`(risk) 기존 경로 그대로 — 중복 계산 신설 금지.
- 손대지 않음: 레거시 라우트 스텁(/movers 등), `portfolio_guest.py`, 시장 탭 모듈 파일, 시장 9탭.
- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- 각 작업은 별도 브랜치 커밋. 머지/배포는 사용자 확인 후.

---

### Task 1: 리스크 본문을 재사용 함수로 추출 (`render_risk_body`)

**Files:**
- Modify: `ui/pages/risk_signals.py:500-635` (render() 분리)

**Interfaces:**
- Produces: `render_risk_body() -> None` — 페이지 크롬(viewport/responsive/inject_css/mark_active_nav) 없이 리스크 콘텐츠만 렌더. 세션 보유를 스스로 읽음(`_my_holdings_for_impact`). `_RISK_LOCAL_CSS` 주입 포함.
- `render() -> None` — 기존 시그니처 유지(페이지 크롬 + `render_risk_body()` 호출).

- [ ] **Step 1: 현재 `/risk` 정상 렌더 스모크(기준선)**

dev 서버 띄운 상태에서:
```bash
python -c "import ui.pages.risk_signals as r; print(hasattr(r,'render'))"
```
Expected: `True` (기준선 — 변경 전 import 정상)

- [ ] **Step 2: `render()` 를 크롬 + 본문으로 분리**

`ui/pages/risk_signals.py` 의 `def render():`(500行) 를 아래로 교체. 501~505의 페이지 크롬만 `render()` 에 남기고, 506行 이후 본문 전체를 `render_risk_body()` 로 옮긴다(본문 코드는 그대로, 들여쓰기 유지).

```python
def render():
    L.viewport_width()
    L.inject_responsive_css()
    inject_css()
    mark_active_nav("/risk")
    render_risk_body()


def render_risk_body() -> None:
    """리스크 진단 콘텐츠(페이지 크롬 없음) — /risk 라우트와 포트폴리오 '리스크 진단' 탭이 공유."""
    st.markdown(_RISK_LOCAL_CSS, unsafe_allow_html=True)
    # 보유 자동 주입(로그인=내 보유 / 게스트·미연결=샘플)
    holdings, _is_guest, _impact_total = _my_holdings_for_impact()
    # … (기존 render() 의 511行 이후 본문을 여기로 그대로 이동) …
```

(주의: 기존 511行의 `holdings, _is_guest, _impact_total = _my_holdings_for_impact()` 가 새 본문 함수의 첫 로직이 되도록, 506~끝 본문을 통째로 `render_risk_body` 안으로 이동. `_RISK_LOCAL_CSS` 주입은 본문 함수 맨 앞으로.)

- [ ] **Step 3: import 스모크**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('ui/pages/risk_signals.py').read()); print('syntax OK')"
python -c "import ui.pages.risk_signals as r; print(callable(r.render), callable(r.render_risk_body))"
```
Expected: `syntax OK` / `True True`

- [ ] **Step 4: `/risk` 시각 회귀 확인(변경 전과 동일해야)**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto(f"http://localhost:8501/risk?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(7000)
    txt=pg.inner_text("body")
    print("리스크 콘텐츠 존재:", ("위험" in txt or "리스크" in txt) and ("벤치마크" in txt or "집중" in txt or "신호" in txt))
    b.close()
PY
```
Expected: `리스크 콘텐츠 존재: True`

- [ ] **Step 5: 커밋**

```bash
git add ui/pages/risk_signals.py
git commit -m "refactor(risk): render 본문을 render_risk_body 로 추출(재사용)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 포트폴리오에 '내 보유 / 리스크 진단' 서브탭

**Files:**
- Modify: `ui/pages/portfolio.py:2400-2423` (render 본문 — detail/업로더를 '내 보유' 탭으로, 리스크 탭 추가)

**Interfaces:**
- Consumes: `render_risk_body()` from Task 1 (`from ui.pages.risk_signals import render_risk_body`).
- 동작: `st.segmented_control("", ["내 보유","리스크 진단"], default=…)` 로 서브탭. 기본은 세션 플래그 `_pf_open_risk`(Task 3 의 /risk 스텁이 설정) 가 True 면 "리스크 진단", 아니면 "내 보유". 선택값에 따라 조건부 렌더(st.tabs 와 달리 비활성 탭 본문 미실행 → 중복 무거운 계산 회피).

- [ ] **Step 1: 서브탭 선택 + 조건부 렌더로 교체**

`ui/pages/portfolio.py` 의 `render()` 에서 `_render_portfolio_detail(...)` 호출부(2400行)부터 스크린샷 업로더 블록(~2423行)까지를 아래로 감싼다. (기존 detail/업로더 코드는 그대로 두고, 서브탭 분기 안으로 이동.)

```python
    # ── 서브탭: 내 보유 / 리스크 진단 (segmented control — 비활성 탭은 미실행) ──
    from ui.pages.risk_signals import render_risk_body
    _default_tab = "리스크 진단" if st.session_state.pop("_pf_open_risk", False) else "내 보유"
    _tab = st.segmented_control(
        "포트폴리오 보기", ["내 보유", "리스크 진단"],
        default=_default_tab, key="pf_subtab", label_visibility="collapsed",
    ) or _default_tab

    if _tab == "리스크 진단":
        render_risk_body()
    else:
        _render_portfolio_detail(
            data,
            journey={
                "progress": max(0.02, progress),
                "height": 360,
                "current_asset": current_asset,
                "target_asset": target_asset,
                "annual_growth_rate": annual_growth_rate,
            },
        )
        if brokerage_connected and st.query_params.get("pf", "") == "":
            st.markdown(
                '<div style="margin:18px 2px 8px;color:#E7E9EE;font-size:14px;font-weight:850;'
                'font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',sans-serif;">'
                '📷 스크린샷으로 보유 갱신'
                '<span style="display:block;color:#9AA0AD;font-size:12px;font-weight:650;margin-top:2px;">'
                '새 캡처를 올리면 종목·평가금액을 다시 인식해 교체해요</span></div>',
                unsafe_allow_html=True,
            )
            _render_screenshot_upload(key="screenshot_update", show_header=False)

    st.markdown(jj_footer(), unsafe_allow_html=True)
```

(기존 2400~2426 의 detail 호출·업로더·footer 를 위 블록으로 대체. footer 는 분기 밖 1회.)

- [ ] **Step 2: 구문 검사**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('ui/pages/portfolio.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 3: 서브탭 동작 시각 확인(데스크톱)**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto(f"http://localhost:8501/portfolio?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(8000)
    print("서브탭 보임:", pg.get_by_text("내 보유", exact=True).count()>0 and pg.get_by_text("리스크 진단", exact=True).count()>0)
    print("기본=내 보유(자산여정 보임):", "자산 여정" in pg.inner_text("body"))
    pg.get_by_text("리스크 진단", exact=True).first.click(); pg.wait_for_timeout(3000)
    t=pg.inner_text("body")
    print("리스크 탭 전환됨:", ("벤치마크" in t or "집중" in t or "신호" in t))
    b.close()
PY
```
Expected: 세 줄 모두 `True`

- [ ] **Step 4: 커밋**

```bash
git add ui/pages/portfolio.py
git commit -m "feat(portfolio): 내 보유/리스크 진단 서브탭(리스크 흡수)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 네비 페이지 목록 3개 + /home·/risk 흡수 (`app.py`)

**Files:**
- Modify: `ui/pages/portfolio.py` (모듈 상단 근처: `_legacy_risk` 추가 불필요 — app.py 에 정의)
- Modify: `app.py:195-230` (페이지 목록·기본 랜딩·스텁)

**Interfaces:**
- Consumes: `portfolio.render`, `overview.render` (기존).
- Produces: st.navigation 에 노출되는 페이지는 전체현황(default)·시장·포트폴리오. `/home`→overview, `/risk`→portfolio(+`_pf_open_risk` 세션 플래그).

- [ ] **Step 1: 기본 랜딩을 overview 로, /home·/risk 스텁화**

`app.py:195-213` 영역을 아래로 교체.

```python
def _home_render():
    overview.render()   # /home 은 전체현황 흡수(북마크 보호, 네비 비노출)

def _telegram_connect_render():
    if st.session_state.get("auth_role") == "guest" or not st.session_state.get("username"):
        st.info("텔레그램 위험 알림은 로그인 후 이용할 수 있어요.")
        return
    telegram_connect.render(st.session_state["username"])

def _risk_redirect():
    # /risk 북마크/딥링크 → 포트폴리오 '리스크 진단' 탭으로 흡수(네비 비노출)
    st.session_state["_pf_open_risk"] = True
    portfolio.render()

def _legacy_movers():       market.render()
def _legacy_us_stocks():    market.render()
def _legacy_kr_stocks():    market.render()
def _legacy_commodities():  market.render()
def _legacy_fx():           market.render()
```

- [ ] **Step 2: st.Page 목록 — 전체현황 default, 홈·리스크 비노출**

`app.py:215-228` 의 `_pages` 목록을 아래로 교체(네비 노출 순서 = 전체현황·시장·포트폴리오. 홈/리스크/종목/알림/레거시는 비노출 라우트).

```python
_pages = [
    st.Page(overview.render,      title="전체 현황",  url_path="overview", default=True),  # "/" 기본 랜딩
    st.Page(market.render,        title="시장",       url_path="market"),
    st.Page(portfolio.render,     title="포트폴리오", url_path="portfolio"),
    st.Page(_home_render,         title="홈",         url_path="home"),    # 비노출 — 북마크 보호(전체현황)
    st.Page(_risk_redirect,       title="리스크",     url_path="risk"),    # 비노출 — 포트폴리오 리스크 탭 흡수
    st.Page(stock_detail.render,  title="종목",       url_path="stock"),
    st.Page(_telegram_connect_render, title="알림 연결", url_path="telegram"),
    st.Page(_legacy_movers,       title="시장",       url_path="movers"),
    st.Page(_legacy_us_stocks,    title="시장",       url_path="us-stocks"),
    st.Page(_legacy_kr_stocks,    title="시장",       url_path="kr-stocks"),
    st.Page(_legacy_commodities,  title="시장",       url_path="commodities"),
    st.Page(_legacy_fx,           title="시장",       url_path="fx"),
]
```

(주의: `default=True` 가 overview 로 이동 → 기본 URL "/" 의 url_path 가 "overview" 가 아니라 default 페이지가 됨. Task 4 의 page_link `_order`/JS MAP 이 이에 맞춰 갱신되어야 함.)

- [ ] **Step 3: 구문·import 검사**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('app.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 4: 라우트 동작 확인 (default·/home·/risk)**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
def body(pg,url):
    pg.goto(url, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(7000); return pg.inner_text("body")
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    print("기본(/) = 전체현황:", "전체 현황" in body(pg,f"http://localhost:8501/?_user={T}"))
    print("/home = 전체현황:", "전체 현황" in body(pg,f"http://localhost:8501/home?_user={T}"))
    t=body(pg,f"http://localhost:8501/risk?_user={T}")
    print("/risk = 포트폴리오 리스크탭:", ("벤치마크" in t or "집중" in t or "신호" in t))
    b.close()
PY
```
Expected: 세 줄 모두 `True`

- [ ] **Step 5: 커밋**

```bash
git add app.py
git commit -m "feat(nav): 전체현황 기본 랜딩 + 홈/리스크 라우트 흡수(비노출)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 비주얼 네비 3개 + 숨은 page_link/JS 브리지 갱신 (`dash_style.py`)

**Files:**
- Modify: `ui/components/dash_style.py:977-982` (nav_items), `:1027` (_order), `:1053` (JS MAP)

**Interfaces:**
- Consumes: `pages`(app.py 의 st.Page 목록, url_path 로 매칭).
- 동작: 비주얼 핀 3개(전체현황·시장·포트폴리오), 숨은 page_link 순서·JS MAP 인덱스가 핀과 1:1.

- [ ] **Step 1: nav_items 3개로 (전체현황·시장·포트폴리오)**

`dash_style.py:977-982` 를 교체.

```python
    nav_items = [
        ("전체 현황",  f"/{_suffix}",            "/",          "overview"),
        ("시장",       f"/market{_suffix}",       "/market",    "market"),
        ("포트폴리오", f"/portfolio{_suffix}",    "/portfolio", "portfolio"),
    ]
```

- [ ] **Step 2: 숨은 page_link 순서 _order 갱신**

`dash_style.py:1027` 를 교체(default(전체현황)의 url_path 는 "overview", 단 "" 키로도 들어올 수 있어 둘 다 시도).

```python
        _by_path = {getattr(p, "url_path", ""): p for p in pages}
        _order = ["overview", "market", "portfolio"]   # 비주얼 핀과 동일 순서
        _cs_pages = [_by_path[u] for u in _order if u in _by_path]
```

- [ ] **Step 3: JS 브리지 MAP 갱신**

`dash_style.py:1052-1053` 의 주석·MAP 을 교체(핀 순서 [overview(0), market(1), portfolio(2)]; /home·/risk 도 매핑해 흡수).

```python
  // 숨은 page_link 순서: [overview(0), market(1), portfolio(2)].
  var MAP = {'/':0, '/overview':0, '/home':0, '/market':1, '/portfolio':2, '/risk':2};
```

- [ ] **Step 4: 구문 검사**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('ui/components/dash_style.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 5: 네비 핀 3개 + 클릭 라우팅 확인**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto(f"http://localhost:8501/?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(8000)
    pins=pg.eval_on_selector_all(".sv-nav a", "els=>els.map(e=>e.textContent.trim())")
    print("핀:", pins, "→ 3개·리스크없음:", pins==["전체 현황","시장","포트폴리오"])
    pg.get_by_text("포트폴리오", exact=True).first.click(); pg.wait_for_timeout(4000)
    print("포트폴리오 이동:", "자산 여정" in pg.inner_text("body") or "내 보유" in pg.inner_text("body"))
    b.close()
PY
```
Expected: `핀: [...] → 3개·리스크없음: True` / `포트폴리오 이동: True`

- [ ] **Step 6: 커밋**

```bash
git add ui/components/dash_style.py
git commit -m "feat(nav): 비주얼 네비 3개(전체현황·시장·포트폴리오) + 브리지 인덱스 갱신

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 전체현황 = 요약만(리스크 풀카드 없음) 확인·정리

**Files:**
- Inspect/Modify: `ui/pages/overview.py`

**Interfaces:**
- 동작: 전체현황은 `_pb_risk_summary_html`(요약 1줄)만, `_pb_risk_card_html`(풀카드) 미사용. 풀카드를 쓰고 있으면 요약으로 강등.

- [ ] **Step 1: 전체현황의 리스크 렌더 방식 점검**

```bash
cd /Users/min/DEV/sim-investment
grep -n "_pb_risk_card_html\|_pb_risk_summary_html\|pb_diagnostics" ui/pages/overview.py
```
Expected: `_pb_risk_summary_html` 만 등장(풀카드 없음) → 변경 불필요, Step 3 으로.
풀카드(`_pb_risk_card_html`)가 있으면 Step 2.

- [ ] **Step 2: (해당 시) 풀카드 → 요약 강등**

전체현황에서 `_pb_risk_card_html(...)` 호출을 `_pb_risk_summary_html(...)` 로 교체하고, '포트폴리오 리스크 진단 →' 링크(`?_user`/`_auth` suffix 포함)를 붙인다. (이미 요약이면 이 스텝 생략.)

- [ ] **Step 3: 전체현황 요약·링크 시각 확인**

```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto(f"http://localhost:8501/overview?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(7000)
    t=pg.inner_text("body")
    print("위험 요약 존재:", "집중" in t or "위험" in t)
    print("재배분 풀카드 없음(요약만):", "재배분" not in t)   # 풀카드 고유 문구
    b.close()
PY
```
Expected: `위험 요약 존재: True` / `재배분 풀카드 없음(요약만): True`

- [ ] **Step 4: 커밋 (변경 있을 때만)**

```bash
git add ui/pages/overview.py
git commit -m "refactor(overview): 리스크는 요약 1줄만(풀카드는 포트폴리오 정본)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 통합 검증 (라우팅·북마크·모바일·게스트)

**Files:** 없음(검증만)

- [ ] **Step 1: 데스크톱 전 라우트 스모크**

```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
def body(pg,u): pg.goto(u,wait_until="networkidle",timeout=60000); pg.wait_for_timeout(6000); return pg.inner_text("body")
B=f"http://localhost:8501"
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    checks={
      "/ 전체현황":("전체 현황", body(pg,f"{B}/?_user={T}")),
      "/market 시장":("시장", body(pg,f"{B}/market?_user={T}")),
      "/portfolio 내보유":("자산 여정", body(pg,f"{B}/portfolio?_user={T}")),
      "/risk→포트폴리오 리스크":("집중", body(pg,f"{B}/risk?_user={T}")),
      "/home→전체현황":("전체 현황", body(pg,f"{B}/home?_user={T}")),
    }
    for k,(needle,t) in checks.items(): print(k, needle in t)
    b.close()
PY
```
Expected: 모든 줄 `True`

- [ ] **Step 2: 모바일(390px) 네비·포트폴리오 서브탭 확인**

```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={"width":390,"height":844},is_mobile=True); pg=ctx.new_page()
    pg.goto(f"http://localhost:8501/portfolio?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(8000)
    t=pg.inner_text("body")
    print("모바일 서브탭 보임:", "내 보유" in t and "리스크 진단" in t)
    b.close()
PY
```
Expected: `모바일 서브탭 보임: True`

- [ ] **Step 3: 게스트 경로 깨지지 않음**

```bash
python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto("http://localhost:8501/?_auth=guest", wait_until="networkidle", timeout=60000); pg.wait_for_timeout=0; pg.wait_for_timeout(7000)
    t=pg.inner_text("body"); print("게스트 전체현황 렌더:", "전체 현황" in t or "시장" in t)
    b.close()
PY
```
Expected: `게스트 전체현황 렌더: True`

- [ ] **Step 4: 전체 단위 테스트 회귀 없음**

```bash
cd /Users/min/DEV/sim-investment
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```
Expected: 기존 통과 수 유지(사전 존재 실패 2건 제외 신규 실패 없음).

- [ ] **Step 5: 최종 커밋(없으면 생략) — 브랜치 정리**

검증만이면 커밋 없음. 작업 브랜치를 PR 로 올릴 준비 완료.

---

## Self-Review (작성자 점검)

- **스펙 커버리지**: 네비 3개(T3·T4) / 홈 흡수(T3) / 리스크 서브탭(T1·T2) / 정본 1곳·요약 강등(T5) / 라우트 북마크 보호(T3) / 검증(T6). 시장 9탭·레거시·게스트 비목표 = 손대지 않음(명시). ✓
- **플레이스홀더**: 각 스텝에 실제 코드/명령. 단 T1 Step2·T5 Step2 는 "기존 본문 통째 이동"·"풀카드 사용 시에만"이라 코드 전량 대신 위치·규칙 지정(기존 코드 이동/조건부라 적절). ✓
- **타입 일관성**: `render_risk_body`(T1)→T2·T3 동일 호출. `_pf_open_risk` 세션 플래그(T2 소비·T3 설정) 이름 일치. nav `_order`/MAP 인덱스(T4) ↔ st.Page url_path(T3) 정합. ✓
