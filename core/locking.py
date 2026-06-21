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
