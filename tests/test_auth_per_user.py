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


def test_global_file_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    monkeypatch.setattr(auth, "_CREDS_FILE", tmp_path / "global_auth.json")
    acc.create_account("carol", "pw123456")
    # 계정별 없음 + 전역 파일 존재 → 폴백
    auth._CREDS_FILE.write_text('{"provider":"kis","app_key":"gk","app_secret":"gs","account_no":"9"}')
    assert auth.load_saved_credentials("carol")["app_key"] == "gk"
