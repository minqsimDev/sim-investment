"""공용 파일 잠금 — read-modify-write 직렬화(동시 쓰기 lost-update 방지)."""
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # POSIX(mac/Linux)
except ImportError:  # pragma: no cover (Windows 폴백)
    fcntl = None


@contextmanager
def file_lock(lock_path):
    """lock_path 에 대한 배타 잠금. fcntl 미지원이면 no-op(단일 프로세스 가정).

    주의: 비재진입. 같은 프로세스가 같은 lock_path 를 중첩 획득하면 self-deadlock
    이다(별 fd 의 flock 은 서로 대기). 한 락을 쥔 채 같은 락을 다시 잡는 함수를
    호출하지 말 것 — 다른 lock_path 끼리는 안전(현재 alerts.lock↔accounts.lock 분리)."""
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
