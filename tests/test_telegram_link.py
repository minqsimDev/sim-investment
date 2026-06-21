import time
import core.telegram_link as tl


def test_issue_and_resolve(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    link, png = tl.issue_link("alice")
    assert "t.me/sim_investment_bot?start=" in link
    nonce = link.split("start=")[1]
    assert tl.resolve_nonce(nonce) == "alice"


def test_nonce_expires(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    monkeypatch.setattr(tl, "_TTL", -1)  # 즉시 만료
    link, _ = tl.issue_link("bob")
    nonce = link.split("start=")[1]
    assert tl.resolve_nonce(nonce) is None


def test_consume_is_one_time(tmp_path, monkeypatch):
    monkeypatch.setattr(tl, "_STATE", tmp_path / "alerts.json")
    link, _ = tl.issue_link("carol")
    nonce = link.split("start=")[1]
    tl.consume_nonce(nonce)
    assert tl.resolve_nonce(nonce) is None
