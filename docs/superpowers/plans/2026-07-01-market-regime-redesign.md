# 시장 페이지 레짐 주역 재설계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시장 요약 화면을 "레짐 판정(오늘 시장) → 왜(근거 신호) → 시장 한눈 → 가벼운 내 노출 브리지" 내러티브로 재구성해 앱 정체성(관점·해석)을 살린다.

**Architecture:** 기존 레짐 판정 로직(`compute_regime_signals`/`_compass_model`, 현 overview.py 내부)을 공용 모듈 `ui/components/regime.py`로 추출해 overview·market 단일 출처로 공유. market `_live_section`(요약 뷰) 최상단에 레짐 헤드라인 + 근거 신호 스트립을 얹고, 하단에 로그인 전용 노출 브리지 1줄을 추가. 자산군 7탭·시장 한눈·기존 모듈은 그대로 드릴다운.

**Tech Stack:** Streamlit(HTML via st.markdown unsafe_allow_html), Python. UI 검증은 Playwright(이 코드베이스엔 UI 테스트 프레임워크 없음 → import 스모크 + Playwright 파리티 체크).

## Global Constraints

- 작업 디렉터리 `/Users/min/DEV/sim-investment`. dev 서버 `.venv/bin/python -m streamlit run app.py --server.port 8501 --server.headless true`(백그라운드, http://localhost:8501/ 200 대기 후 Playwright는 시스템 `python3`).
- 로그인 검증 토큰: `TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")`; 평문 `?_user=minqsim` 은 차단.
- **SSOT**: 레짐 판정·신호는 기존 로직 재사용만(신규 산식 금지). market 의 레짐 헤드라인은 전체현황(overview) 나침반과 **동일 판정**이어야 한다(같은 함수·같은 데이터).
- **색체계**: 레짐 방향 톤 = 중립/골드/앰버(위험경고) 3단계. **손익 빨강/파랑 미사용**. (tone 값 "good"→골드계열 양호, "watch"→중립, "risk"→앰버.)
- 시장=general 원칙: 개인화는 "노출 브리지 1줄(로그인 시만)"만. 그 이상 개인화 금지.
- 비목표: 자산군 7탭 내부 재설계, 시장 탭 가지치기.
- 비주얼 작업(Task 2)은 frontend-design 원칙 적용(의도적·정제된, 템플릿 회피).
- 커밋 말미: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. 작업 브랜치 커밋, 머지/배포는 사용자 확인 후.

---

### Task 1: 공용 레짐 모듈 추출 (`ui/components/regime.py`)

**Files:**
- Create: `ui/components/regime.py`
- Modify: `ui/pages/overview.py` (`_cached_regime_signals`:44-50, `_compass_model`:62-98 제거 → import; 호출부 350-365 는 그대로 두되 import 소스만 변경)

**Interfaces:**
- Produces:
  - `cached_regime_signals(fetched_at: str) -> list[dict]` (기존 `_cached_regime_signals` 이동, `@st.cache_data(ttl=1800)` 유지)
  - `compass_model(sig_map: dict, btc_chg, kweb_chg) -> tuple[str, str, int, str]` (기존 `_compass_model` 이동; 반환 (direction, note, angle, tone))
  - `regime_verdict(data: dict) -> dict` — 신규 편의 래퍼. 반환 `{"direction","note","tone","angle","signals","sig_map"}`. overview 350-365 배선을 그대로 담는다.

- [ ] **Step 1: 공용 모듈 생성**

Create `ui/components/regime.py`:
```python
"""시장 레짐(국면) 판정 — 전체현황 나침반·시장 페이지·리스크가 공유하는 단일 출처.
compute_regime_signals(원지표) → 신호 → compass_model(가중 스코어) → 방향/해석/톤.
"""
import pandas as pd
import streamlit as st

from data.session import load_market_data  # 기존 overview 와 동일 소스
from src.risk import compute_regime_signals


@st.cache_data(ttl=1800, show_spinner=False)
def cached_regime_signals(fetched_at: str) -> list[dict]:
    """레짐 신호 계산을 시장데이터 타임스탬프로 캐시(리런마다 재계산 방지)."""
    return compute_regime_signals(load_market_data())


def compass_model(sig_map: dict, btc_chg, kweb_chg) -> tuple[str, str, int, str]:
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


def _safe(v):
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def regime_verdict(data: dict) -> dict:
    """시장데이터 → 레짐 판정 일괄. 반환 {direction,note,tone,angle,signals,sig_map}."""
    signals = cached_regime_signals(data["fetched_at"])
    sig_map = {s["signal"]: s for s in signals}
    _bm = data.get("benchmarks", pd.DataFrame())
    _cr = data.get("crypto", pd.DataFrame())
    _bm_chg = {} if _bm.empty else dict(zip(_bm["ticker"], _bm["change_pct"]))
    _cry_chg = {} if _cr.empty else dict(zip(_cr["ticker"], _cr["change_pct"]))
    direction, note, angle, tone = compass_model(
        sig_map, _safe(_cry_chg.get("BTC-USD")), _safe(_bm_chg.get("KWEB")))
    return {"direction": direction, "note": note, "tone": tone,
            "angle": angle, "signals": signals, "sig_map": sig_map}
```

- [ ] **Step 2: overview.py 를 공용 모듈로 재배선**

`ui/pages/overview.py`:
1. `_cached_regime_signals`(44-50)·`_compass_model`(62-98) 정의 삭제.
2. 상단 import 부에 추가: `from ui.components.regime import cached_regime_signals as _cached_regime_signals, compass_model as _compass_model`.
   (기존 호출부 `_cached_regime_signals(...)`/`_compass_model(...)` 이름 그대로 동작 — 별칭으로 무변경.)
3. `from src.risk import compute_regime_signals` 가 다른 데서 안 쓰이면 제거(쓰이면 유지).

- [ ] **Step 3: import 스모크**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('ui/components/regime.py').read()); ast.parse(open('ui/pages/overview.py').read()); print('syntax OK')"
.venv/bin/python -c "from ui.components.regime import cached_regime_signals, compass_model, regime_verdict; print('exports OK')"
.venv/bin/python -c "import ui.pages.overview; print('overview import OK')"
```
Expected: `syntax OK` / `exports OK` / `overview import OK`

- [ ] **Step 4: overview 회귀 — 다이제스트 방향 동일 렌더**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto(f"http://localhost:8501/overview?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(8000)
    t=pg.inner_text("body")
    print("레짐 방향 렌더:", any(d in t for d in ["우상향 유지","방어 모드","혼조 구간"]))
    b.close()
PY
```
Expected: `레짐 방향 렌더: True`

- [ ] **Step 5: 커밋**

```bash
git add ui/components/regime.py ui/pages/overview.py
git commit -m "refactor(regime): 레짐 판정 로직을 공용 ui/components/regime.py 로 추출(overview 재배선)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 시장 요약 — 레짐 헤드라인 + 근거 신호 스트립

**Files:**
- Modify: `ui/pages/market.py` (`_live_section`:1338~ 최상단에 삽입; `_MARKET_LOCAL_CSS` 에 스타일 추가; HTML 빌더 2개 추가)

**Interfaces:**
- Consumes: `regime_verdict(data)`(Task 1); `_SIG_KOR`(from `ui.pages.risk_signals`, 신호 영문→한글).
- Produces: `_regime_headline_html(direction, note, tone) -> str`, `_regime_signals_strip_html(signals) -> str`.

- [ ] **Step 1: HTML 빌더 2개 추가 (market.py, `_live_section` 위)**

```python
_REGIME_TONE = {"good": "rg-good", "watch": "rg-watch", "risk": "rg-risk"}


def _regime_headline_html(direction: str, note: str, tone: str) -> str:
    cls = _REGIME_TONE.get(tone, "rg-watch")
    return (
        f'<div class="rg-head {cls}">'
        f'<div class="rg-k">오늘 시장</div>'
        f'<div class="rg-dir">{direction}</div>'
        f'<div class="rg-note">{note}</div>'
        f'</div>'
    )


def _regime_signals_strip_html(signals: list[dict]) -> str:
    from ui.pages.risk_signals import _SIG_KOR
    order = {"high": 0, "mid": 1, "low": 2, "na": 3}
    lab = {"high": "위험", "mid": "주의", "low": "완충", "na": "중립"}
    sigs = sorted(signals, key=lambda s: order.get(s.get("col", "na"), 3))
    chips = "".join(
        f'<span class="rg-sig rg-{s.get("col","na")}">'
        f'{_SIG_KOR.get(s["signal"], s["signal"])} · {lab.get(s.get("col","na"),"중립")}</span>'
        for s in sigs
    )
    return f'<div class="rg-why"><div class="rg-why-k">왜 — 판정 근거</div><div class="rg-sigs">{chips}</div></div>'
```

- [ ] **Step 2: `_live_section` 최상단에서 레짐 블록 렌더**

`_live_section`(market.py) 에서 `data = _fd.result()` 로 `data` 가 확정된 직후(펄스/시장한눈 섹션보다 위)에 삽입:
```python
    from ui.components.regime import regime_verdict
    _rg = regime_verdict(data)
    st.markdown(_regime_headline_html(_rg["direction"], _rg["note"], _rg["tone"]), unsafe_allow_html=True)
    st.markdown(_regime_signals_strip_html(_rg["signals"]), unsafe_allow_html=True)
```
(기존 "오늘의 핵심 지표"·"시장 한눈"·"테마별 시장 동향" 은 그 아래로 그대로.)

- [ ] **Step 3: CSS 추가 (`_MARKET_LOCAL_CSS`)**

`_MARKET_LOCAL_CSS` 문자열의 닫는 `</style>` 직전에 삽입(값은 색체계 준수 — 골드 #D9A441 / 앰버 #E8883A / 중립 회색):
```css
.rg-head{border:1px solid #262A33;border-radius:16px;padding:16px 18px;margin:2px 0 10px;background:#16181F}
.rg-head .rg-k{font-size:11px;font-weight:800;color:#7E8694;letter-spacing:.04em}
.rg-head .rg-dir{font-size:26px;font-weight:950;letter-spacing:-.02em;margin:2px 0 4px}
.rg-head .rg-note{font-size:13px;font-weight:650;color:#9AA0AD;line-height:1.5}
.rg-good .rg-dir{color:#3DD68C}.rg-watch .rg-dir{color:#C9CDD6}.rg-risk .rg-dir{color:#E8883A}
.rg-good{border-color:rgba(61,214,140,.34)}.rg-risk{border-color:rgba(232,136,58,.40)}
.rg-why{margin:0 0 14px}
.rg-why-k{font-size:11px;font-weight:800;color:#7E8694;margin:0 0 6px}
.rg-sigs{display:flex;flex-wrap:wrap;gap:6px}
.rg-sig{font-size:11.5px;font-weight:800;padding:4px 10px;border-radius:999px;border:1px solid #262A33;color:#9AA0AD;background:rgba(255,255,255,.04)}
.rg-high{color:#E8883A;border-color:rgba(232,136,58,.38);background:rgba(232,136,58,.10)}
.rg-mid{color:#D9A441;border-color:rgba(217,164,65,.34);background:rgba(217,164,65,.10)}
.rg-low{color:#9AA0AD}
@media(max-width:768px){.rg-head .rg-dir{font-size:22px}}
```

- [ ] **Step 4: 구문 검사**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('ui/pages/market.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 5: 파리티 검증 — 시장 레짐 == 전체현황 방향, 근거 칩 존재**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys, re
from playwright.sync_api import sync_playwright
T=sys.argv[1]; B="http://localhost:8501"
DIRS=["우상향 유지","방어 모드","혼조 구간"]
def dir_of(pg,url):
    pg.goto(url, wait_until="networkidle", timeout=60000); pg.wait_for_timeout=0; pg.wait_for_timeout(8000)
    t=pg.inner_text("body"); return next((d for d in DIRS if d in t), None), t
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    ov,_=dir_of(pg,f"{B}/overview?_user={T}")
    mk,mt=dir_of(pg,f"{B}/market?_user={T}")
    print("전체현황 방향:", ov, "| 시장 방향:", mk, "| 일치:", ov==mk and ov is not None)
    print("오늘 시장 헤드라인:", "오늘 시장" in mt)
    print("근거 신호(왜) 스트립:", "판정 근거" in mt)
    b.close()
PY
```
Expected: `일치: True` / `오늘 시장 헤드라인: True` / `근거 신호(왜) 스트립: True`

- [ ] **Step 6: 커밋**

```bash
git add ui/pages/market.py
git commit -m "feat(market): 요약 최상단 레짐 헤드라인 + 근거 신호 스트립(전체현황 나침반과 동일 판정)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 가벼운 내 노출 브리지 (로그인 전용 1줄)

**Files:**
- Modify: `ui/pages/market.py` (`_live_section` 하단; `_MARKET_LOCAL_CSS` 스타일; HTML 빌더 1개)

**Interfaces:**
- Consumes: `_market_suffix()`(기존, 세션 토큰 suffix); `st.session_state`.
- Produces: `_exposure_bridge_html(suffix: str) -> str` (비로그인/게스트면 빈 문자열).

- [ ] **Step 1: 브리지 빌더 추가 (market.py)**

```python
def _exposure_bridge_html(suffix: str) -> str:
    """이 국면이 내 노출에 뭘 의미? — 로그인 시만 노출되는 가벼운 링크 1줄(시장=general 유지)."""
    import streamlit as st
    if st.session_state.get("auth_role") == "guest" or not st.session_state.get("username"):
        return ""
    href = f"/risk{suffix}"
    return (
        f'<a class="rg-bridge" href="{href}" target="_self">'
        f'이 국면에서 내 노출은? · 리스크 진단 →</a>'
    )
```
(`/risk` 는 네비 브리지가 포트폴리오 리스크 탭으로 흡수 — 클라이언트사이드.)

- [ ] **Step 2: `_live_section` 끝에서 렌더**

`_live_section` 의 마지막(테마별 시장 동향 섹션 뒤, 함수 반환 직전)에:
```python
    st.markdown(_exposure_bridge_html(suffix), unsafe_allow_html=True)
```

- [ ] **Step 3: CSS 추가 (`_MARKET_LOCAL_CSS`, </style> 직전)**

```css
.rg-bridge{display:inline-flex;align-items:center;margin:8px 0 2px;padding:8px 14px;border-radius:999px;
  font-size:12.5px;font-weight:800;color:#D9A441;background:rgba(217,164,65,.10);
  border:1px solid rgba(217,164,65,.40);text-decoration:none}
.rg-bridge:hover{background:rgba(217,164,65,.18);border-color:#D9A441}
```

- [ ] **Step 4: 구문 검사**

```bash
cd /Users/min/DEV/sim-investment
python -c "import ast; ast.parse(open('ui/pages/market.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

- [ ] **Step 5: 검증 — 로그인 노출/게스트 미노출 + 리스크 탭 이동**

dev 서버 재시작 후:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]; B="http://localhost:8501"
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page()
    pg.goto(f"{B}/market?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(8000)
    print("로그인 브리지 노출:", "내 노출은?" in pg.inner_text("body"))
    pg2=b.new_page()
    pg2.goto(f"{B}/market?_auth=guest", wait_until="networkidle", timeout=60000); pg2.wait_for_timeout(8000)
    print("게스트 브리지 미노출:", "내 노출은?" not in pg2.inner_text("body"))
    b.close()
PY
```
Expected: `로그인 브리지 노출: True` / `게스트 브리지 미노출: True`

- [ ] **Step 6: 커밋**

```bash
git add ui/pages/market.py
git commit -m "feat(market): 로그인 전용 '내 노출' 브리지 1줄(→리스크 탭). 시장=general 유지

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 통합 검증

**Files:** 없음(검증만)

- [ ] **Step 1: 전체 흐름 + 모바일 + 전체 테스트**

dev 서버 실행 상태에서:
```bash
TOKEN=$(.venv/bin/python -c "from core.auth_token import make_token; print(make_token('minqsim'))")
python3 - "$TOKEN" <<'PY'
import sys
from playwright.sync_api import sync_playwright
T=sys.argv[1]; B="http://localhost:8501"
with sync_playwright() as pw:
    b=pw.chromium.launch()
    pg=b.new_page(); pg.goto(f"{B}/market?_user={T}", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(8000)
    t=pg.inner_text("body")
    print("데스크톱 순서(헤드라인·근거·시장한눈):", all(k in t for k in ["오늘 시장","판정 근거","시장 한눈"]))
    ctx=b.new_context(viewport={"width":390,"height":844}, is_mobile=True); m=ctx.new_page()
    m.goto(f"{B}/market?_user={T}", wait_until="networkidle", timeout=60000); m.wait_for_timeout(8000)
    print("모바일 레짐 헤드라인:", "오늘 시장" in m.inner_text("body"))
    b.close()
PY
```
Expected: 두 줄 모두 `True`

- [ ] **Step 2: pytest 회귀**

```bash
cd /Users/min/DEV/sim-investment
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -4
```
Expected: 기존 통과 유지, 사전 존재 2건(vision_parser/deprecated_streamlit) 외 신규 실패 없음.

---

## Self-Review (작성자 점검)

- **스펙 커버리지**: 레짐 헤드라인(T2) / 근거 신호(T2) / 시장 한눈(기존 유지) / 노출 브리지(T3) / 공용 레짐 추출·SSOT(T1) / 색 톤(T2 CSS) / general 원칙·브리지 로그인전용(T3). 비목표(자산탭 내부·가지치기)=손대지 않음. ✓
- **플레이스홀더**: 각 스텝 실제 코드/명령 포함. ✓
- **타입 일관성**: `regime_verdict`(T1)→T2 `_rg["direction"/"note"/"tone"/"signals"]` 사용 일치. `compass_model` 반환 (direction,note,angle,tone) 일치. `_exposure_bridge_html(suffix)`(T3)↔`_market_suffix()` suffix 일치. `_SIG_KOR` overview 와 동일 출처. ✓
