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
