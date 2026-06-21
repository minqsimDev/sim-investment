import core.accounts as acc
import core.auth as auth


def test_per_user_credentials_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    monkeypatch.setattr(auth, "_CREDS_FILE", tmp_path / "global_auth.json")  # 전역 폴백 경로 격리
    acc.create_account("alice", "pw123456")
    acc.create_account("bob", "pw123456")

    auth.save_credentials("alice", "kis", "ak", "as", "111")
    assert auth.load_saved_credentials("alice")["app_key"] == "ak"
    assert auth.load_saved_credentials("bob") is None        # 격리


def test_global_fallback_only_without_username(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    monkeypatch.setattr(auth, "_CREDS_FILE", tmp_path / "global_auth.json")
    acc.create_account("carol", "pw123456")
    auth._CREDS_FILE.write_text('{"provider":"kis","app_key":"gk","app_secret":"gs","account_no":"9"}')

    # username 줬는데 그 계정에 creds 없음 → 전역으로 새지 않음(격리)
    assert auth.load_saved_credentials("carol") is None
    # username 없을 때만 전역 레거시 폴백(단일소유 호환)
    assert auth.load_saved_credentials()["app_key"] == "gk"


def test_delete_keeps_global_for_others(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    monkeypatch.setattr(auth, "_CREDS_FILE", tmp_path / "global_auth.json")
    acc.create_account("dave", "pw123456")
    auth._CREDS_FILE.write_text('{"provider":"kis","app_key":"gk","app_secret":"gs","account_no":"9"}')
    auth.save_credentials("dave", "kis", "dk", "ds", "1")

    auth.delete_saved_credentials("dave")          # 유저 것만 삭제
    assert auth.load_saved_credentials("dave") is None
    assert auth._CREDS_FILE.exists()                # 공용 전역 파일 보존
