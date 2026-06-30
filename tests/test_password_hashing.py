"""비밀번호 해싱(pbkdf2) + 레거시 자동 승격 테스트. 임시 HOME 으로 격리."""
import json
import os
from pathlib import Path

import pytest

import core.accounts as acc


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    # accounts 모듈은 import 시점에 _FILE 을 고정하므로 테스트용으로 재지정
    monkeypatch.setattr(acc, "_FILE", tmp_path / ".siminvest_accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / ".siminvest_accounts.lock")
    return tmp_path


def _read(home):
    return json.loads((acc._FILE).read_text())["accounts"]


def test_new_account_uses_pbkdf2_and_min_length(tmp_home):
    assert acc.create_account("user", "short") == "비밀번호는 8자 이상이어야 합니다."
    assert acc.create_account("user", "longenough") is None
    rec = _read(tmp_home)["user"]
    assert rec["hash_scheme"] == "pbkdf2"
    assert acc.authenticate("user", "longenough") is not None
    assert acc.authenticate("user", "wrongpass") is None


def test_legacy_sha256_verifies_and_upgrades(tmp_home):
    salt = acc._new_salt()
    acc._save({"accounts": {"old": {
        "password_hash": acc._hash_legacy("oldpass12", salt), "salt": salt,
        "created_at": "x", "portfolios": [],   # hash_scheme 없음 = 레거시
    }}})
    assert acc.authenticate("old", "nope") is None
    assert acc.authenticate("old", "oldpass12") is not None
    rec = _read(tmp_home)["old"]
    assert rec["hash_scheme"] == "pbkdf2"             # 승격됨
    assert acc.authenticate("old", "oldpass12") is not None
    assert acc.authenticate("old", "oldpass12X") is None


def test_set_password_uses_pbkdf2(tmp_home):
    acc.create_account("user", "longenough")
    assert acc.set_password("user", "short") == "비밀번호는 8자 이상으로 설정해 주세요."
    assert acc.set_password("user", "brandnew9") is None
    rec = _read(tmp_home)["user"]
    assert rec["hash_scheme"] == "pbkdf2" and "password_changed_at" in rec
    assert acc.authenticate("user", "brandnew9") is not None
    assert acc.authenticate("user", "longenough") is None
