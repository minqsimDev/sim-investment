"""로그인 무차별 대입 방어 테스트."""
import time

import core.login_guard as lg


def setup_function(_):
    lg._fails.clear()
    lg._locked_until.clear()


def test_not_locked_below_threshold():
    for _ in range(lg._MAX_FAILS - 1):
        assert lg.record_failure("u") == 0
    assert lg.check_locked("u") == 0


def test_locks_at_threshold():
    lock = 0
    for _ in range(lg._MAX_FAILS):
        lock = lg.record_failure("u")
    assert lock > 0
    assert lg.check_locked("u") > 0


def test_success_resets():
    for _ in range(lg._MAX_FAILS - 1):
        lg.record_failure("u")
    lg.record_success("u")
    assert lg.check_locked("u") == 0
    assert lg._fails.get("u") in (None, [])


def test_case_insensitive_key():
    for _ in range(lg._MAX_FAILS):
        lg.record_failure("User")
    assert lg.check_locked("user") > 0   # 대소문자 무관 동일 계정


def test_lockout_expires(monkeypatch):
    base = time.time()
    monkeypatch.setattr(lg.time, "time", lambda: base)
    for _ in range(lg._MAX_FAILS):
        lg.record_failure("u")
    assert lg.check_locked("u") > 0
    monkeypatch.setattr(lg.time, "time", lambda: base + lg._LOCKOUT + 1)
    assert lg.check_locked("u") == 0


def test_window_prunes_old_failures(monkeypatch):
    base = time.time()
    monkeypatch.setattr(lg.time, "time", lambda: base)
    for _ in range(lg._MAX_FAILS - 1):
        lg.record_failure("u")
    # 윈도가 지나면 옛 실패는 만료 → 다시 1회부터 카운트(잠금 안 됨)
    monkeypatch.setattr(lg.time, "time", lambda: base + lg._WINDOW + 1)
    assert lg.record_failure("u") == 0
    assert lg.check_locked("u") == 0
