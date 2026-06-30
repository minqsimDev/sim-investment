"""로그인 무차별 대입(brute-force) 방어 — 아이디별 연속 실패 시 짧은 잠금.

인메모리(프로세스 수명). 로그인은 app 컨테이너 단일 프로세스에서만 처리되므로 충분하다.
재시작 시 초기화되지만 공격자가 재시작을 강제할 수 없어 억제 효과는 유지된다.
아이디 기반 잠금은 표적 DoS(남의 계정 잠그기) 여지가 있어 잠금 시간을 짧게(기본 5분) 둔다.
"""
import time

_MAX_FAILS = 5      # 윈도 내 허용 실패 횟수
_WINDOW = 600.0     # 실패 집계 윈도(초) = 10분
_LOCKOUT = 300.0    # 임계 초과 시 잠금(초) = 5분

_fails: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}


def _key(username: str) -> str:
    return (username or "").strip().lower()


def check_locked(username: str) -> int:
    """잠겨 있으면 남은 잠금 초(>0), 아니면 0."""
    rem = _locked_until.get(_key(username), 0.0) - time.time()
    return int(rem) + 1 if rem > 0 else 0


def record_failure(username: str) -> int:
    """실패 1건 기록. 윈도 내 임계 초과 시 잠금 설정. 잠금됐으면 잠금 초, 아니면 0."""
    k = _key(username)
    now = time.time()
    arr = [t for t in _fails.get(k, []) if now - t < _WINDOW]
    arr.append(now)
    _fails[k] = arr
    if len(arr) >= _MAX_FAILS:
        _locked_until[k] = now + _LOCKOUT
        _fails[k] = []
        return int(_LOCKOUT)
    return 0


def record_success(username: str) -> None:
    """성공 시 해당 아이디의 실패·잠금 기록 초기화."""
    k = _key(username)
    _fails.pop(k, None)
    _locked_until.pop(k, None)
