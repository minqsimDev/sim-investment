import core.accounts as acc
import src.telegram_alert as ta


def test_run_sends_per_user(tmp_path, monkeypatch):
    monkeypatch.setattr(ta, "_CFG", tmp_path / "alerts.json")
    monkeypatch.setattr(acc, "_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(acc, "_LOCK", tmp_path / "accounts.lock")
    acc.create_account("alice", "pw123456")
    acc.set_setting("alice", "telegram_chat_id", 4242)

    monkeypatch.setattr(ta, "risk_score_now", lambda: (90, 3, 1, 1))   # 시장 위험 높음
    monkeypatch.setattr(ta, "_portfolio_daily", lambda u: [{"name": "테슬라", "ticker": "TSLA", "d1": -7.0}])

    sent_to = []
    monkeypatch.setattr(ta, "send_message", lambda text, cid: sent_to.append(cid) or True)

    sent = ta.run(verbose=False)
    assert sent_to == [4242, 4242]      # 시장위험 + 보유급락 둘 다 alice에게
    assert any(s.startswith("alice:") for s in sent)
