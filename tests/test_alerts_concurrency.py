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
