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
