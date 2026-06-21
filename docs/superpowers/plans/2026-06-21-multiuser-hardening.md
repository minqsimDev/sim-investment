# 멀티유저 안전 하드닝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공유 상태(alerts.json) 동시 쓰기 correctness와 증권사 자격증명 유저별 격리를 추가해 여러 사용자가 동시에 안전하게 쓰게 한다.

**Architecture:** fcntl 파일락을 공용 유틸로 추출해 alerts.json read-modify-write 전체를 직렬화(텔레그램 폴링 단일 소비자화). 증권사 자격증명은 전역 파일 → 계정별(`accounts.set_setting`, 이미 락 보호)로 이전하고 전역 파일은 읽기 폴백으로만 둔다.

**Tech Stack:** Python 3.12, Streamlit 1.37.1 호환, stdlib `fcntl`, pytest.

## Global Constraints
- 자격증명 저장 = **계정별 평문**(`accounts.json` settings). 기존 전역 `~/.siminvest_auth.json`은 **읽기 폴백만**, 강제 마이그레이션 없음. 게스트는 저장 불가.
- `alerts.json` RMW는 **단일 락 `~/.siminvest_alerts.lock`** 하에서만. load→mutate→save 전체 구간 보호.
- fcntl 미지원 시 락은 no-op(단일 프로세스 가정) — 기존 `accounts.py` 동작과 동일.
- 외부 텔레그램 호출은 테스트에서 모킹. Streamlit 1.37.1 호환 API만.
- 비포함: 배포/HTTPS/부하, 자격증명 암호화, 텔레그램 데몬.

---

### Task 1: 공용 파일락 유틸 (`core/locking.py`)

**Files:**
- Create: `core/locking.py`
- Modify: `core/accounts.py` (`_locked()`가 공용 유틸 사용)
- Test: `tests/test_locking.py`

**Interfaces:**
- Produces: `file_lock(lock_path: str | Path)` — contextmanager(배타 잠금; fcntl 없으면 no-op)

- [ ] **Step 1: 실패 테스트** — `tests/test_locking.py`:
```python
import threading
import time
from core.locking import file_lock


def test_file_lock_serializes_rmw(tmp_path):
    counter = tmp_path / "c.txt"
    counter.write_text("0")
    lock = tmp_path / "c.lock"

    def bump():
        for _ in range(25):
            with file_lock(lock):
                n = int(counter.read_text())
                time.sleep(0.001)          # 임계구역 내 컨텍스트 스위치 유도
                counter.write_text(str(n + 1))

    ts = [threading.Thread(target=bump) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert int(counter.read_text()) == 6 * 25   # 락 없으면 lost-update로 미달
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_locking.py -q` · Expected: FAIL (module 없음)

- [ ] **Step 3: 구현** — `core/locking.py`:
```python
"""공용 파일 잠금 — read-modify-write 직렬화(동시 쓰기 lost-update 방지)."""
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # POSIX(mac/Linux)
except ImportError:  # pragma: no cover (Windows 폴백)
    fcntl = None


@contextmanager
def file_lock(lock_path):
    """lock_path 에 대한 배타 잠금. fcntl 미지원이면 no-op(단일 프로세스 가정)."""
    if fcntl is None:
        yield
        return
    lf = open(Path(lock_path), "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
        lf.close()
```

- [ ] **Step 4: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_locking.py -q` · Expected: PASS

- [ ] **Step 5: accounts.py 가 공용 유틸 사용** — `core/accounts.py`의 `_locked()` 교체:
```python
from core.locking import file_lock


@contextmanager
def _locked():
    """read-modify-write 구간 배타 잠금(공용 유틸 위임)."""
    with file_lock(_LOCK):
        yield
```
> 기존 `import fcntl`/`@contextmanager def _locked()` 본문을 위로 대체. `from contextlib import contextmanager` 는 유지(다른 데서 안 쓰면 _locked 정의에 필요). `_LOCK` 상수는 그대로.

- [ ] **Step 6: 계정 회귀 확인** — Run: `.venv/bin/python -m pytest tests/test_accounts_telegram.py -q` · Expected: PASS

- [ ] **Step 7: 커밋**
```bash
git add core/locking.py core/accounts.py tests/test_locking.py
git commit -m "feat(locking): 공용 file_lock 유틸 추출 + accounts 적용"
```

---

### Task 2: alerts.json 동시성 (`core/telegram_link.py`, `src/telegram_alert.py`)

**Files:**
- Modify: `core/telegram_link.py` (RMW를 락으로)
- Modify: `src/telegram_alert.py` (`poll_register` 락 + load-merge-save 유지)
- Test: `tests/test_alerts_concurrency.py`

**Interfaces:**
- Consumes: `core.locking.file_lock`
- Produces: 동작 동일(시그니처 불변), 동시 안전성만 추가. `_LOCK_FILE = ~/.siminvest_alerts.lock`

- [ ] **Step 1: 실패 테스트** — `tests/test_alerts_concurrency.py`:
```python
import threading
import core.telegram_link as tl


def test_concurrent_issue_link_no_lost_update(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    monkeypatch.setattr(tl, "_LOCK_FILE", tmp_path / "alerts.lock")

    def issue(i):
        tl.issue_link(f"user{i}")

    ts = [threading.Thread(target=issue, args=(i,)) for i in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]

    import json
    pending = json.loads((tmp_path / "alerts.json").read_text()).get("pending", {})
    assert len(pending) == 12   # 락 없으면 동시 쓰기로 일부 유실
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_alerts_concurrency.py -q` · Expected: FAIL (`_LOCK_FILE` 없음 또는 유실로 12 미만)

- [ ] **Step 3: telegram_link RMW 락 적용** — `core/telegram_link.py` 수정:
  (a) 상단에 락 경로 + import:
```python
from core.locking import file_lock

_STATE = Path.home() / ".siminvest_alerts.json"
_LOCK_FILE = Path.home() / ".siminvest_alerts.lock"
_TTL = 600
```
  (b) `issue_link` 의 RMW를 락으로:
```python
def issue_link(username: str, bot_username: str = "sim_investment_bot") -> tuple[str, bytes]:
    nonce = secrets.token_urlsafe(16)
    with file_lock(_LOCK_FILE):
        d = _load()
        d.setdefault("pending", {})[nonce] = {"username": username, "exp": time.time() + _TTL}
        _save(d)
    link = f"https://t.me/{bot_username}?start={nonce}"
    return link, _qr_png(link)
```
  (c) `resolve_nonce`(만료 삭제가 RMW) 와 `consume_nonce` 도 락으로:
```python
def resolve_nonce(nonce: str) -> str | None:
    with file_lock(_LOCK_FILE):
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
    with file_lock(_LOCK_FILE):
        d = _load()
        if d.get("pending", {}).pop(nonce, None) is not None:
            _save(d)
```

- [ ] **Step 4: telegram_alert poll_register 락 적용** — `src/telegram_alert.py`:
  (a) import 추가: `import time`, `from core.locking import file_lock`, 그리고 `_LOCK_FILE = Path.home() / ".siminvest_alerts.lock"` (모듈 상단, `_CFG` 옆).
  (b) `poll_register()` 전체 RMW를 락으로 감싼다. resolve/consume_nonce 가 같은 락을 재진입하지 않도록, poll_register 안에서는 nonce 매핑을 **락 안에서 cfg.pending 직접 처리**한다:
```python
def poll_register() -> list[tuple[str, int]]:
    """getUpdates 로 /start <nonce> 수신 → 계정 chat_id 저장. 락으로 단일 소비자 직렬화."""
    from core import accounts

    registered: list[tuple[str, int]] = []
    with file_lock(_LOCK_FILE):
        cfg = load_cfg()
        pending = cfg.get("pending", {})
        offset = cfg.get("update_offset")
        updates = _api("getUpdates", offset=offset, timeout=0)
        seen: set[str] = set()
        welcomes: list[int] = []
        for u in updates:
            cfg["update_offset"] = u.get("update_id", 0) + 1
            msg = u.get("message") or {}
            text = (msg.get("text") or "").strip()
            cid = (msg.get("chat") or {}).get("id")
            if cid and text.startswith("/start"):
                parts = text.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip() not in seen:
                    nonce = parts[1].strip()
                    rec = pending.get(nonce)
                    if rec and rec.get("exp", 0) >= time.time():
                        username = rec["username"]
                        seen.add(nonce)
                        pending.pop(nonce, None)
                        accounts.set_setting(username, "telegram_chat_id", cid)
                        registered.append((username, cid))
                        welcomes.append(cid)
        cfg["pending"] = pending
        save_cfg(cfg)
    # 환영 발송은 락 밖에서(네트워크 I/O를 임계구역에서 분리)
    for cid in welcomes:
        try:
            send_test(cid)
        except Exception:
            pass
    return registered
```
> 주의: 이 버전은 nonce 검증·소비를 cfg.pending 안에서 직접 하므로 `resolve_nonce`/`consume_nonce` 를 호출하지 않는다(같은 락 재진입 회피). `load_cfg`/`save_cfg` 는 `pending` 등 미지 키를 보존해야 한다(기존 load_cfg 의 `else: cfg[k]=v` 병합이 이를 보장 — 확인할 것).

- [ ] **Step 5: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_alerts_concurrency.py tests/test_telegram_onboarding.py -q` · Expected: PASS (동시성 + 기존 등록 테스트)

- [ ] **Step 6: 커밋**
```bash
git add core/telegram_link.py src/telegram_alert.py tests/test_alerts_concurrency.py
git commit -m "fix(telegram): alerts.json RMW 파일락 + 폴링 단일소비자 직렬화"
```

---

### Task 3: 증권사 자격증명 유저별 (`core/auth.py`)

**Files:**
- Modify: `core/auth.py` (save/load/delete 에 username)
- Test: `tests/test_auth_per_user.py`

**Interfaces:**
- Consumes: `core.accounts.set_setting/get_setting`
- Produces: `save_credentials(username, provider, app_key, app_secret, account_no)` · `load_saved_credentials(username=None) -> dict|None` · `delete_saved_credentials(username=None)`

- [ ] **Step 1: 실패 테스트** — `tests/test_auth_per_user.py`:
```python
import core.accounts as acc
import core.auth as auth


def test_per_user_credentials_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    monkeypatch.setattr(auth, "_CREDS_FILE", tmp_path / "global_auth.json")  # 전역 폴백 경로 격리
    acc.create_account("alice", "pw123456")
    acc.create_account("bob", "pw123456")

    auth.save_credentials("alice", "kis", "ak", "as", "111")
    assert auth.load_saved_credentials("alice")["app_key"] == "ak"
    assert auth.load_saved_credentials("bob") is None        # 격리

def test_global_file_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    monkeypatch.setattr(auth, "_CREDS_FILE", tmp_path / "global_auth.json")
    acc.create_account("carol", "pw123456")
    # 계정별 없음 + 전역 파일 존재 → 폴백
    auth._CREDS_FILE.write_text('{"provider":"kis","app_key":"gk","app_secret":"gs","account_no":"9"}')
    assert auth.load_saved_credentials("carol")["app_key"] == "gk"
```

- [ ] **Step 2: 실패 확인** — Run: `.venv/bin/python -m pytest tests/test_auth_per_user.py -q` · Expected: FAIL (시그니처 불일치)

- [ ] **Step 3: 구현** — `core/auth.py` 의 save/load/delete 교체:
```python
def save_credentials(username, provider: str, app_key: str, app_secret: str, account_no: str) -> None:
    """계정별 저장. username 없으면(게스트) 저장하지 않는다."""
    if not username:
        return
    from core import accounts
    accounts.set_setting(username, "brokerage", {
        "provider": provider, "app_key": app_key,
        "app_secret": app_secret, "account_no": account_no,
    })


def load_saved_credentials(username=None) -> dict | None:
    """계정별 우선, 없으면 전역 파일(레거시) 폴백."""
    if username:
        from core import accounts
        data = accounts.get_setting(username, "brokerage")
        if data and all(k in data for k in ("provider", "app_key", "app_secret", "account_no")):
            return data
    try:
        data = json.loads(_CREDS_FILE.read_text())
        if all(k in data for k in ("provider", "app_key", "app_secret", "account_no")):
            return data
    except Exception:
        pass
    return None


def delete_saved_credentials(username=None) -> None:
    if username:
        from core import accounts
        accounts.set_setting(username, "brokerage", None)
    try:
        _CREDS_FILE.unlink(missing_ok=True)
    except Exception:
        pass
```

- [ ] **Step 4: 통과 확인** — Run: `.venv/bin/python -m pytest tests/test_auth_per_user.py -q` · Expected: PASS

- [ ] **Step 5: 호출부 username 전달** — 다음 명령으로 호출처를 찾아 username 인자를 넘기도록 수정:
```bash
grep -rn "save_credentials(\|load_saved_credentials(\|delete_saved_credentials(" ui/ core/ src/ app.py | grep -v "def "
```
각 호출부에서 세션 username(`st.session_state.get("username")`)을 첫 인자로 전달. 게스트(username None)는 save 무시·load는 전역 폴백. 수정 후 해당 페이지가 import 되는지 스모크:
```bash
.venv/bin/python -c "import ui.pages.login, ui.pages.portfolio"
```

- [ ] **Step 6: 커밋**
```bash
git add core/auth.py tests/test_auth_per_user.py ui/ app.py
git commit -m "feat(auth): 증권사 자격증명 유저별 분리(+전역 읽기 폴백)"
```

---

### Task 4: 연결 화면 성공 판정 단순화 (`ui/pages/telegram_connect.py`)

**Files:**
- Modify: `ui/pages/telegram_connect.py:30-36`

- [ ] **Step 1: 수정** — 폴링 직렬화로 다른 세션이 내 `/start`를 소비할 수 있으므로, 성공 판정을 **계정 chat_id 존재만**으로 단순화(자기 poll 결과 의존 제거):
```python
@st.fragment(run_every=_POLL_SEC)
def _await_scan(username: str) -> None:
    """스캔될 때까지 폴링. 누구 세션이 소비하든 내 계정에 chat_id 가 생기면 성공."""
    try:
        poll_register()
    except Exception:
        pass
    if accounts.get_setting(username, "telegram_chat_id"):
        st.rerun()
```

- [ ] **Step 2: 스모크** — Run: `.venv/bin/python -c "import ui.pages.telegram_connect"` · Expected: 에러 없음

- [ ] **Step 3: 커밋**
```bash
git add ui/pages/telegram_connect.py
git commit -m "refactor(telegram): 연결 성공 판정을 계정 chat_id 존재로 단순화"
```

---

### Task 5: 전체 회귀 + 동시성·런타임 검증

**Files:** 없음(검증).

- [ ] **Step 1: 전체 테스트** — Run: `DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest tests/ -q --ignore=tests/test_risk_ui.py`
  Expected: 신규(locking·alerts_concurrency·auth_per_user) PASS. 선존재 1 fail(`test_portfolio_ui` 마크업)은 무관 — 그대로.

- [ ] **Step 2: 실런타임 1.37.1 로드** — Run:
```bash
/opt/anaconda3/bin/python -c "import core.locking, core.auth, core.telegram_link, src.telegram_alert, ui.pages.telegram_connect; print('1.37.1 load OK')"
```
  Expected: `1.37.1 load OK`

- [ ] **Step 3: 커밋(있으면)** — 수정 발생 시만.

---

## 자동화 한계 (명시)
- 동시성은 **스레드 기반 테스트**로 검증(같은 프로세스, 별 open() 으로 flock 직렬화 확인). 실제 다중 프로세스/배포 부하 테스트는 범위 밖.
- 텔레그램 외부 전송은 모킹. 실제 다중 유저 동시 QR 스캔은 사람 손이 필요(후속 수동 확인).
