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


def test_poll_register_dedupes_duplicate_start(tmp_path, monkeypatch):
    """같은 배치에 동일 /start 가 2건 와도 등록·환영은 1회만(중복 환영 방지)."""
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    monkeypatch.setattr(ta, "_CFG", tmp_path / "alerts.json")
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    acc.create_account("alice", "pw123456")
    link, _ = tl.issue_link("alice")
    nonce = link.split("start=")[1]

    def fake_api(method, **params):
        if method == "getUpdates":
            return [
                {"update_id": 10, "message": {"chat": {"id": 4242}, "text": f"/start {nonce}"}},
                {"update_id": 11, "message": {"chat": {"id": 4242}, "text": f"/start {nonce}"}},
            ]
        return {}
    monkeypatch.setattr(ta, "_api", fake_api)

    calls = []
    monkeypatch.setattr(ta, "send_test", lambda cid=None: calls.append(cid) or True)

    registered = ta.poll_register()
    assert registered == [("alice", 4242)]   # 중복 /start 여도 1건만
    assert calls == [4242]                     # 환영 1번만
