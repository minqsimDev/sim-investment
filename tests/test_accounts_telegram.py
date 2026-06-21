import core.accounts as acc


def test_users_with_telegram(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    acc.create_account("alice", "pw123456")
    acc.create_account("bob", "pw123456")
    acc.set_setting("alice", "telegram_chat_id", 7766)
    subs = acc.users_with_telegram()
    assert ("alice", 7766) in subs
    assert all(u != "bob" for u, _ in subs)
