# 텔레그램 QR 온보딩 + 유저별 위험 알림 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 신규/기존 SIM 유저가 앱에서 QR을 스캔해 텔레그램을 연결하고, 본인 포트폴리오 기준 개인화 위험 알림을 받게 한다.

**Architecture:** 단기 nonce 딥링크(QR) → 폰 스캔으로 봇에 `/start <nonce>` → 연결화면 온디맨드 폴링(`getUpdates`)이 nonce→username 해소 후 유저 계정 설정에 chat_id 저장 → `run()`이 연결된 유저별로 시장위험+보유급락 평가·발송. 공개 서버/웹훅 없음(폴링).

**Tech Stack:** Python 3.12, Streamlit 1.37.1 호환, `requests`, `qrcode[pil]`(QR 생성), `pyzbar`(테스트 디코딩), pytest.

## Global Constraints
- 시세·주문 아님 — 텔레그램은 알림 전용. 봇 토큰은 `.env`만(`TELEGRAM_BOT_TOKEN`).
- 상태 파일: 봇 상태 `~/.siminvest_alerts.json`, 계정 `~/.siminvest_accounts.json`(`core.accounts`).
- 외부 발송/네트워크는 테스트에서 **모킹**(실 텔레그램 호출 금지).
- 면책 유지: 알림은 "참고 정보·판단은 직접"(권유 아님).
- 폴링 유지 — 코드에서 setWebhook 호출 금지(getUpdates와 상호배타).
- Streamlit 1.37.1 호환 API만 사용.

---

### Task 1: 의존성 + nonce 발급/해소 (`core/telegram_link.py`)

**Files:**
- Modify: `requirements.txt`
- Create: `core/telegram_link.py`
- Test: `tests/test_telegram_link.py`

**Interfaces:**
- Produces: `issue_link(username: str, bot_username: str = "sim_investment_bot") -> tuple[str, bytes]` (deeplink, qr_png) · `resolve_nonce(nonce: str) -> str | None` · `consume_nonce(nonce: str) -> None`
- Consumes: 없음(상태 파일 직접).

- [ ] **Step 1: 의존성 추가** — `requirements.txt`에 추가:
```
qrcode[pil]>=7.4
pyzbar>=0.1.9
```
설치: `.venv/bin/pip install "qrcode[pil]>=7.4" "pyzbar>=0.1.9"`
(pyzbar는 시스템 zbar 필요 시 `brew install zbar`)

- [ ] **Step 2: 실패 테스트 작성** — `tests/test_telegram_link.py`:
```python
import time
import core.telegram_link as tl


def test_issue_and_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    link, png = tl.issue_link("alice")
    assert "t.me/sim_investment_bot?start=" in link
    nonce = link.split("start=")[1]
    assert tl.resolve_nonce(nonce) == "alice"


def test_nonce_expires(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    monkeypatch.setattr(tl, "_TTL", -1)  # 즉시 만료
    link, _ = tl.issue_link("bob")
    nonce = link.split("start=")[1]
    assert tl.resolve_nonce(nonce) is None


def test_consume_is_one_time(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    link, _ = tl.issue_link("carol")
    nonce = link.split("start=")[1]
    tl.consume_nonce(nonce)
    assert tl.resolve_nonce(nonce) is None
```

- [ ] **Step 3: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_link.py -q` · Expected: FAIL (module/함수 없음)

- [ ] **Step 4: 구현** — `core/telegram_link.py`:
```python
"""텔레그램 온보딩용 단기 nonce 딥링크 + QR. 폴링 등록기와 같은 상태 파일을 공유."""
import io
import json
import os
import secrets
import time
from pathlib import Path

_STATE = Path.home() / ".siminvest_alerts.json"
_TTL = 600  # nonce 유효(초)


def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    tmp = _STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _STATE)


def _qr_png(data: str) -> bytes:
    import qrcode
    buf = io.BytesIO()
    qrcode.make(data).save(buf, format="PNG")
    return buf.getvalue()


def issue_link(username: str, bot_username: str = "sim_investment_bot") -> tuple[str, bytes]:
    nonce = secrets.token_urlsafe(16)
    d = _load()
    d.setdefault("pending", {})[nonce] = {"username": username, "exp": time.time() + _TTL}
    _save(d)
    link = f"https://t.me/{bot_username}?start={nonce}"
    return link, _qr_png(link)


def resolve_nonce(nonce: str) -> str | None:
    d = _load()
    rec = d.get("pending", {}).get(nonce)
    if not rec:
        return None
    if rec.get("exp", 0) < time.time():
        d["pending"].pop(nonce, None)
        _save(d)
        return None
    return rec.get("username")


def consume_nonce(nonce: str) -> None:
    d = _load()
    if d.get("pending", {}).pop(nonce, None) is not None:
        _save(d)
```

- [ ] **Step 5: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_link.py -q` · Expected: PASS

- [ ] **Step 6: 커밋**
```bash
git add requirements.txt core/telegram_link.py tests/test_telegram_link.py
git commit -m "feat(telegram): QR 온보딩 nonce 딥링크 발급/해소"
```

---

### Task 2: QR PNG 디코딩 검증 (스캔 시 올바른 딥링크)

**Files:**
- Test: `tests/test_telegram_link.py` (추가)

**Interfaces:**
- Consumes: `tl.issue_link`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_telegram_link.py`에 추가:
```python
def test_qr_decodes_to_deeplink(tmp_path, monkeypatch):
    from PIL import Image
    from pyzbar.pyzbar import decode
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    link, png = tl.issue_link("dave")
    import io
    decoded = decode(Image.open(io.BytesIO(png)))
    assert decoded and decoded[0].data.decode() == link
```

- [ ] **Step 2: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_link.py::test_qr_decodes_to_deeplink -q` · Expected: PASS (Task 1 구현으로 이미 충족)

- [ ] **Step 3: 커밋**
```bash
git add tests/test_telegram_link.py
git commit -m "test(telegram): QR PNG 디코딩→딥링크 일치 검증"
```

---

### Task 3: 계정 구독자 열거 (`core/accounts.py`)

**Files:**
- Modify: `core/accounts.py`
- Test: `tests/test_accounts_telegram.py`

**Interfaces:**
- Consumes: 기존 `set_setting(username, key, value)`, `get_setting(username, key, default)`, `create_account`.
- Produces: `users_with_telegram() -> list[tuple[str, int]]` (username, chat_id)

- [ ] **Step 1: 실패 테스트** — `tests/test_accounts_telegram.py`:
```python
import core.accounts as acc


def test_users_with_telegram(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    acc.create_account("alice", "pw123456")
    acc.create_account("bob", "pw123456")
    acc.set_setting("alice", "telegram_chat_id", 7766)
    subs = acc.users_with_telegram()
    assert ("alice", 7766) in subs
    assert all(u != "bob" for u, _ in subs)
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_accounts_telegram.py -q` · Expected: FAIL (함수 없음)

- [ ] **Step 3: 구현** — `core/accounts.py`에 추가(파일 끝, 기존 `_load()` 구조 사용. settings 위치는 기존 `get_setting` 구현과 동일 경로를 따를 것):
```python
def users_with_telegram() -> list[tuple[str, int]]:
    """telegram_chat_id 가 설정된 (username, chat_id) 목록."""
    data = _load()
    out: list[tuple[str, int]] = []
    for username, acc in data.get("accounts", {}).items():
        cid = (acc.get("settings") or {}).get("telegram_chat_id")
        if cid:
            out.append((username, cid))
    return out
```
> 구현자 주의: `get_setting`/`set_setting`이 settings를 어디에 저장하는지 먼저 확인하고(`core/accounts.py` 98–116행 부근) 동일 경로(`acc["settings"]`)를 사용할 것. 다르면 그 경로에 맞춰 위 접근을 수정.

- [ ] **Step 4: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_accounts_telegram.py -q` · Expected: PASS

- [ ] **Step 5: 커밋**
```bash
git add core/accounts.py tests/test_accounts_telegram.py
git commit -m "feat(accounts): 텔레그램 구독자(users_with_telegram) 열거"
```

---

### Task 4: 폴링 등록기 (`src/telegram_alert.py: poll_register`)

**Files:**
- Modify: `src/telegram_alert.py`
- Test: `tests/test_telegram_onboarding.py`

**Interfaces:**
- Consumes: `core.telegram_link.resolve_nonce/consume_nonce`, `core.accounts.set_setting`, 기존 `load_cfg/save_cfg/_api/send_test`.
- Produces: `poll_register() -> list[tuple[str, int]]` (등록된 username, chat_id)

- [ ] **Step 1: 실패 테스트** — `tests/test_telegram_onboarding.py`:
```python
import core.telegram_link as tl
import core.accounts as acc
import src.telegram_alert as ta


def test_poll_register_links_account(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    monkeypatch.setattr(ta, "_CFG", tmp_path / "alerts.json")
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    acc.create_account("alice", "pw123456")
    link, _ = tl.issue_link("alice")
    nonce = link.split("start=")[1]

    # getUpdates / sendMessage 모킹
    def fake_api(method, **params):
        if method == "getUpdates":
            return [{"update_id": 10, "message": {"chat": {"id": 4242}, "text": f"/start {nonce}"}}]
        return {}
    monkeypatch.setattr(ta, "_api", fake_api)

    registered = ta.poll_register()
    assert ("alice", 4242) in registered
    assert acc.get_setting("alice", "telegram_chat_id") == 4242
    assert tl.resolve_nonce(nonce) is None  # 소비됨
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_onboarding.py -q` · Expected: FAIL

- [ ] **Step 3: 구현** — `src/telegram_alert.py`에 추가:
```python
def poll_register() -> list[tuple[str, int]]:
    """getUpdates 로 /start <nonce> 를 받아 유저 계정에 chat_id 저장. 등록 목록 반환."""
    from core.telegram_link import resolve_nonce, consume_nonce
    from core import accounts

    cfg = load_cfg()
    offset = cfg.get("update_offset")
    updates = _api("getUpdates", offset=offset, timeout=0)
    registered: list[tuple[str, int]] = []
    for u in updates:
        cfg["update_offset"] = u.get("update_id", 0) + 1
        msg = u.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid and text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                username = resolve_nonce(parts[1].strip())
                if username:
                    accounts.set_setting(username, "telegram_chat_id", cid)
                    consume_nonce(parts[1].strip())
                    try:
                        send_test(cid)
                    except Exception:
                        pass
                    registered.append((username, cid))
    save_cfg(cfg)
    return registered
```

- [ ] **Step 4: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_onboarding.py -q` · Expected: PASS

- [ ] **Step 5: 커밋**
```bash
git add src/telegram_alert.py tests/test_telegram_onboarding.py
git commit -m "feat(telegram): 폴링 등록기 poll_register(/start nonce→계정 chat_id)"
```

---

### Task 5: 유저별 알림 (`src/telegram_alert.py: run` 개편)

**Files:**
- Modify: `src/telegram_alert.py`
- Test: `tests/test_telegram_peruser.py`

**Interfaces:**
- Consumes: `core.accounts.users_with_telegram`, `core.accounts.get_portfolios`, 기존 `risk_score_now`, `_daily_change`, `send_message`, `_cooldown_ok`.
- Produces: 개편된 `run(verbose=True) -> list[str]` — 연결된 유저별로 평가·발송. 발송 키 형식 `"{username}:{rule}"`.

- [ ] **Step 1: 실패 테스트** — `tests/test_telegram_peruser.py`:
```python
import core.accounts as acc
import src.telegram_alert as ta


def test_run_sends_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(ta, "_CFG", tmp_path / "alerts.json")
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    acc.create_account("alice", "pw123456")
    acc.set_setting("alice", "telegram_chat_id", 4242)

    monkeypatch.setattr(ta, "risk_score_now", lambda: (90, 3, 1, 1))   # 시장 위험 높음
    monkeypatch.setattr(ta, "_portfolio_daily", lambda u: [{"name": "테슬라", "ticker": "TSLA", "d1": -7.0}])

    sent_to = []
    monkeypatch.setattr(ta, "send_message", lambda text, cid: sent_to.append(cid) or True)

    sent = ta.run(verbose=False)
    assert sent_to == [4242, 4242]      # 시장위험 + 보유급락 둘 다 alice에게
    assert any(s.startswith("alice:") for s in sent)
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_peruser.py -q` · Expected: FAIL

- [ ] **Step 3: 구현** — `src/telegram_alert.py`:
  (a) 유저 포트폴리오 보유 일일% 헬퍼 추가:
```python
def _portfolio_daily(username: str) -> list[dict]:
    """유저의 저장 포트폴리오 보유 종목 → [{name, ticker, d1}]. 일일%는 지표 DB/시세에서."""
    from core import accounts
    tickers, names = [], {}
    for p in accounts.get_portfolios(username):
        for h in (p.get("holdings") or []):
            tk = h.get("ticker")
            if tk:
                tickers.append(tk)
                names[tk] = h.get("name") or tk
    if not tickers:
        return []
    d1 = _daily_change(list(dict.fromkeys(tickers)))
    return [{"name": names[tk], "ticker": tk, "d1": d1[tk]} for tk in d1]
```
  (b) `run()`을 유저 순회로 교체:
```python
def run(verbose: bool = True) -> list[str]:
    """연결된 유저별로 시장위험 + 본인 보유급락 평가·발송. 반환=발송 키 목록."""
    from core import accounts
    from datetime import datetime, timezone
    cfg = load_cfg()
    now = datetime.now(timezone.utc)
    rules = cfg.get("rules", _DEFAULT_CFG["rules"])
    cfg.setdefault("last_sent", {})
    sent: list[str] = []

    score, nh, nm, nl = risk_score_now() if rules.get("risk_score", {}).get("enabled") else (0, 0, 0, 0)

    for username, cid in accounts.users_with_telegram():
        # 규칙 ①: 시장 종합 위험(공통 점수, 쿨다운은 유저별)
        r1 = rules.get("risk_score", {})
        if r1.get("enabled") and score >= r1.get("threshold", 80):
            key = f"{username}:risk_score"
            if _cooldown_ok(cfg, key, now):
                msg = (f"⚠️ *종합 위험 {score}*  ·  방어 우선 구간\n\n"
                       f"시장 국면 신호가 위험 쪽으로 기울었어요.\n"
                       f"`위험 {nh}   주의 {nm}   완충 {nl}`\n\n"
                       f"› 점검 포인트 — 보유 비중과 헤지 여부{_ALERT_SIGN}")
                if send_message(msg, cid):
                    cfg["last_sent"][key] = now.isoformat()
                    sent.append(key)
        # 규칙 ②: 본인 보유 종목 급락
        r2 = rules.get("holding_drop", {})
        if r2.get("enabled"):
            thr = r2.get("threshold", -5.0)
            for h in _portfolio_daily(username):
                if h["d1"] <= thr:
                    key = f"{username}:holding_drop:{h['ticker']}"
                    if _cooldown_ok(cfg, key, now):
                        msg = (f"🔻 *{h['name']}*  {h['d1']:+.1f}%  ·  보유 종목 급락\n\n"
                               f"오늘 하루 큰 폭으로 내렸어요.  _(경보 기준 {thr:+.0f}%)_\n\n"
                               f"› 점검 포인트 — 비중과 추가 하방 위험{_ALERT_SIGN}")
                        if send_message(msg, cid):
                            cfg["last_sent"][key] = now.isoformat()
                            sent.append(key)
    save_cfg(cfg)
    if verbose:
        print(f"[telegram] 발송 {len(sent)}건: {sent}")
    return sent
```
> 기존 단일 chat_id 기반 `run()`/`_holdings_daily()`는 위로 대체. `_holdings_daily`가 다른 곳에서 안 쓰이면 제거.

- [ ] **Step 4: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_telegram_peruser.py -q` · Expected: PASS

- [ ] **Step 5: 커밋**
```bash
git add src/telegram_alert.py tests/test_telegram_peruser.py
git commit -m "feat(telegram): 유저별 개인화 알림(run 개편: 시장위험+본인 보유급락)"
```

---

### Task 6: 앱 연결 화면 (QR + 온디맨드 폴링)

**Files:**
- Create: `ui/pages/telegram_connect.py`
- Modify: 진입점(설정/계정 메뉴) — 기존 nav 구조에 맞춰 링크 추가(예: `app.py` 또는 설정 페이지)
- Test: `tests/test_telegram_connect_ui.py` (렌더 호출이 예외 없이 도는지 스모크)

**Interfaces:**
- Consumes: `core.telegram_link.issue_link`, `src.telegram_alert.poll_register`, 세션의 로그인 username.
- Produces: `render(username: str) -> None`

- [ ] **Step 1: 구현** — `ui/pages/telegram_connect.py`:
```python
"""텔레그램 알림 연결 화면 — QR 표시 + 온디맨드 폴링으로 자동 등록."""
import streamlit as st

from core.telegram_link import issue_link
from src.telegram_alert import poll_register
from core import accounts

_POLL_SEC = 3


def render(username: str) -> None:
    st.subheader("텔레그램 위험 알림 연결")
    if accounts.get_setting(username, "telegram_chat_id"):
        st.success("연결됨 ✅  시장·보유 위험 신호가 있을 때 텔레그램으로 전해드려요.")
        return

    if st.session_state.get("_tg_link_user") != username:
        link, png = issue_link(username)
        st.session_state["_tg_link"] = link
        st.session_state["_tg_qr"] = png
        st.session_state["_tg_link_user"] = username

    st.image(st.session_state["_tg_qr"], width=220, caption="텔레그램 앱으로 QR 스캔")
    st.caption(f"또는 링크로 열기: {st.session_state['_tg_link']}")
    _await_scan(username)


@st.fragment(run_every=_POLL_SEC)
def _await_scan(username: str) -> None:
    """스캔될 때까지 몇 초마다 getUpdates 폴링. 등록되면 리런해 '연결됨' 표시."""
    try:
        regs = poll_register()
    except Exception:
        regs = []
    if any(u == username for u, _ in regs) or accounts.get_setting(username, "telegram_chat_id"):
        st.rerun()
```

- [ ] **Step 2: 진입점 연결** — 로그인된 유저의 설정/계정 영역에서 `telegram_connect.render(username)` 호출하도록 한 줄 추가(기존 nav 패턴 확인 후 적용).

- [ ] **Step 3: 스모크 테스트** — `tests/test_telegram_connect_ui.py`:
```python
def test_render_importable():
    import ui.pages.telegram_connect as tc
    assert hasattr(tc, "render")
```
Run: `.venv/bin/python -m pytest tests/test_telegram_connect_ui.py -q` · Expected: PASS

- [ ] **Step 4: 커밋**
```bash
git add ui/pages/telegram_connect.py tests/test_telegram_connect_ui.py app.py
git commit -m "feat(telegram): QR 연결 화면 + 온디맨드 폴링 등록"
```

---

### Task 7: 전체 회귀 + 앱 헬스 체크

**Files:** 없음(검증).

- [ ] **Step 1: 전체 테스트** — Run: `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_risk_ui.py`
  Expected: 신규 텔레그램 테스트 PASS. (기존 `test_portfolio_ui.py` 1건은 선존재 실패 — 본 작업과 무관, 그대로 둠)

- [ ] **Step 2: 앱 구동 스모크** — Run: `.venv/bin/streamlit run app.py --server.headless true --server.port 8599 &` 후 `curl -sSf http://localhost:8599/_stcore/health` 가 `ok` 인지 확인. 종료.

- [ ] **Step 3: 화면 확인(가능 시)** — Playwright로 `http://localhost:8599` 로드 → 로그인/게스트 진입 → 주요 페이지(시장·포트폴리오) 렌더 및 텔레그램 연결 화면 QR 표시 스크린샷. 콘솔 에러 없는지.

- [ ] **Step 4: 커밋(있으면)** — 수정 발생 시 커밋. 없으면 생략.

---

## 자동화 한계 (명시)
- **실제 폰 QR 스캔→`/start` 왕복**은 사람이 필요(에이전트는 폰 없음). 에이전트는 QR 디코딩 + `getUpdates` 모킹으로 등록 로직을 검증하고, 실스캔 1회는 사용자가 봇 `@sim_investment_bot`로 확인.
