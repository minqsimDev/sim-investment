"""
로컬 계정 관리.
저장 위치: ~/.siminvest_accounts.json
"""
import hashlib
import hmac
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from core.locking import file_lock

_FILE = Path.home() / ".siminvest_accounts.json"
_LOCK = Path.home() / ".siminvest_accounts.lock"


# 비밀번호 해싱 — 느린 KDF(PBKDF2-HMAC-SHA256)가 기본. 옛 계정(빠른 sha256)은
# 로그인 성공 시 자동으로 재해시(업그레이드)된다. 빠른 해시는 파일 유출 시 무차별 대입에 약함.
_PBKDF2_ROUNDS = 200_000


def _hash_legacy(pw: str, salt: str) -> str:
    """레거시 sha256(salt+pw) — 검증·하위호환 전용(신규 저장엔 안 씀)."""
    return hashlib.sha256(f"{salt}{pw}".encode()).hexdigest()


def _hash_pbkdf2(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), _PBKDF2_ROUNDS).hex()


def _new_salt() -> str:
    return os.urandom(16).hex()


def _verify_password(pw: str, acc: dict) -> bool:
    """계정의 저장 스킴(pbkdf2/레거시 sha256)에 맞춰 constant-time 검증."""
    salt = acc.get("salt", "")
    expected = acc.get("password_hash", "")
    if acc.get("hash_scheme") == "pbkdf2":
        return hmac.compare_digest(_hash_pbkdf2(pw, salt), expected)
    return hmac.compare_digest(_hash_legacy(pw, salt), expected)


def _set_password_hash(acc: dict, pw: str) -> None:
    """계정 dict 에 새 자격증명(pbkdf2 + 새 솔트) 기록."""
    salt = _new_salt()
    acc["salt"] = salt
    acc["password_hash"] = _hash_pbkdf2(pw, salt)
    acc["hash_scheme"] = "pbkdf2"


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"accounts": {}}


def _save(data: dict) -> None:
    """원자적 저장 — 임시 파일 작성 후 os.replace로 교체(쓰기 중 크래시에도 원본 보존)."""
    tmp = _FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _FILE)
    try:
        os.chmod(_FILE, 0o600)   # 비번해시·보유·텔레그램 chat_id 포함 — 소유자만 읽기
    except OSError:
        pass


@contextmanager
def _locked():
    """read-modify-write 구간 배타 잠금(공용 유틸 위임)."""
    with file_lock(_LOCK):
        yield


def create_account(username: str, password: str) -> str | None:
    """성공 시 None 반환, 실패 시 에러 메시지 반환."""
    username = username.strip()
    if not username or not password:
        return "아이디와 비밀번호를 입력해 주세요."
    if len(username) < 2:
        return "아이디는 2자 이상이어야 합니다."
    if len(password) < 8:
        return "비밀번호는 8자 이상이어야 합니다."
    with _locked():
        data = _load()
        if username in data["accounts"]:
            return "이미 사용 중인 아이디입니다."
        acc = {
            "created_at": datetime.now().isoformat(),
            "portfolios": [],
        }
        _set_password_hash(acc, password)
        data["accounts"][username] = acc
        _save(data)
    return None


def set_password(username: str, new_password: str) -> str | None:
    """기존 계정 비밀번호 변경(새 솔트 재생성). 성공 None, 실패 메시지.
    변경 시엔 8자 이상 권장(생성은 4자 허용이지만 노출 사고 대응 등 변경은 강화)."""
    username = username.strip()
    if len(new_password) < 8:
        return "비밀번호는 8자 이상으로 설정해 주세요."
    with _locked():
        data = _load()
        acc = data["accounts"].get(username)
        if not acc:
            return "계정을 찾을 수 없습니다."
        _set_password_hash(acc, new_password)
        acc["password_changed_at"] = datetime.now().isoformat()
        _save(data)
    return None


def authenticate(username: str, password: str) -> dict | None:
    """인증 성공 시 account dict 반환, 실패 시 None.
    레거시 sha256 계정은 로그인 성공 시 pbkdf2 로 자동 재해시(업그레이드)한다."""
    username = username.strip()
    acc = _load()["accounts"].get(username)
    if not acc or not _verify_password(password, acc):
        return None
    if acc.get("hash_scheme") != "pbkdf2":
        with _locked():
            data = _load()
            a2 = data["accounts"].get(username)
            if a2 and _verify_password(password, a2):   # 잠금 안에서 재확인 후 업그레이드
                _set_password_hash(a2, password)
                _save(data)
                acc = a2
    return acc


def has_account(username: str) -> bool:
    return username.strip() in _load()["accounts"]


def get_portfolios(username: str) -> list[dict]:
    return _load()["accounts"].get(username.strip(), {}).get("portfolios", [])


def all_holding_tickers() -> list[str]:
    """전 계정·전 포트폴리오 보유의 시세 조회용 티커(중복 제거, 현금 제외). 배치 스냅샷 유니버스용 —
    config 밖 계정 비주류 보유까지 DB에 적재해 마감·주말에도 현재가가 존재하게 한다.
    크립토는 -USD 보정(ui.pages.portfolio._quote_ticker 와 동일 규칙 — DB 키 정합)."""
    out: list[str] = []
    for acc in _load().get("accounts", {}).values():
        for pf in acc.get("portfolios", []):
            for h in pf.get("holdings", []):
                tk = str(h.get("ticker") or "").strip().upper()
                if not tk or tk in ("CASH", "KRW", "USD"):
                    continue
                ac = str(h.get("asset_class") or h.get("category") or "").lower()
                if "cash" in ac or "현금" in ac:
                    continue
                if ("crypto" in ac or tk.endswith("-USD")) and not tk.endswith("-USD"):
                    tk += "-USD"
                out.append(tk)
    return list(dict.fromkeys(out))


def get_setting(username: str, key: str, default=None):
    """사용자별 설정값 조회 (목표금액 등 — 새로고침에도 유지)."""
    acc = _load()["accounts"].get(username.strip())
    if not acc:
        return default
    return acc.get("settings", {}).get(key, default)


def set_setting(username: str, key: str, value) -> None:
    """사용자별 설정값 저장."""
    username = username.strip()
    with _locked():
        data = _load()
        acc = data["accounts"].get(username)
        if not acc:
            return
        acc.setdefault("settings", {})[key] = value
        _save(data)


def save_portfolio(
    username: str,
    holdings: list[dict],
    name: str = "내 포트폴리오",
    cash: float = 0.0,
) -> None:
    username = username.strip()
    with _locked():
        data = _load()
        acc = data["accounts"].get(username)
        if not acc:
            return
        portfolios = acc.setdefault("portfolios", [])
        entry = {
            "name": name,
            "holdings": holdings,
            "cash": cash,
            "updated_at": datetime.now().isoformat(),
        }
        for i, p in enumerate(portfolios):
            if p["name"] == name:
                portfolios[i] = entry
                _save(data)
                return
        portfolios.append(entry)
        _save(data)


# ── 계좌 시계열 스냅샷 (B3) ────────────────────────────────────────────────────
_SNAP_CAP = 730  # 보관 상한(약 2년치 일별)


def record_snapshot(username: str, snapshot: dict) -> None:
    """오늘 자산 스냅샷 저장 — 같은 날짜는 덮어쓰기(하루 1포인트). snapshot 에 'date'(YYYY-MM-DD) 포함."""
    username = (username or "").strip()
    date = snapshot.get("date")
    if not username or not date:
        return
    with _locked():
        data = _load()
        acc = data["accounts"].get(username)
        if not acc:
            return
        snaps = acc.setdefault("snapshots", [])
        if snaps and snaps[-1].get("date") == date:
            snaps[-1] = snapshot           # 같은 날 재방문 → 최신값으로 갱신
        else:
            snaps.append(snapshot)
        if len(snaps) > _SNAP_CAP:
            del snaps[: len(snaps) - _SNAP_CAP]
        _save(data)


def get_snapshots(username: str) -> list[dict]:
    """저장된 일별 자산 스냅샷 목록(날짜 오름차순) — record_snapshot 의 읽기 대칭."""
    username = (username or "").strip()
    if not username:
        return []
    acc = _load()["accounts"].get(username)
    return list(acc.get("snapshots") or []) if acc else []


def users_with_telegram() -> list[tuple[str, int]]:
    """telegram_chat_id 가 설정된 (username, chat_id) 목록."""
    data = _load()
    out: list[tuple[str, int]] = []
    for username, acc in data.get("accounts", {}).items():
        cid = (acc.get("settings") or {}).get("telegram_chat_id")
        if cid:
            out.append((username, cid))
    return out
