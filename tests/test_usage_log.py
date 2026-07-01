"""사용 이벤트 로그 집계·안전성 테스트."""
import json

import core.usage_log as ul


def test_summarize_counts_views_and_unique_users(tmp_path):
    p = tmp_path / "u.jsonl"
    recs = [
        {"page": "market", "tab": "us", "uid": "u_a"},
        {"page": "market", "tab": "us", "uid": "u_b"},
        {"page": "market", "tab": "us", "uid": "u_a"},   # 같은 uid 재방문 → views+1, uniq 그대로
        {"page": "market", "tab": "rates", "uid": "u_a"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    s = ul.summarize(p)
    assert s[("market", "us")]["views"] == 3
    assert len(s[("market", "us")]["users"]) == 2
    assert s[("market", "rates")]["views"] == 1
    assert len(s[("market", "rates")]["users"]) == 1


def test_summarize_missing_file_is_empty(tmp_path):
    assert ul.summarize(tmp_path / "nope.jsonl") == {}


def test_summarize_skips_corrupt_lines(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text('{"page":"market","tab":"kr","uid":"u_a"}\nNOT JSON\n\n', encoding="utf-8")
    s = ul.summarize(p)
    assert s[("market", "kr")]["views"] == 1


def test_append_writes_line_with_timestamp(tmp_path, monkeypatch):
    f = tmp_path / "u.jsonl"
    monkeypatch.setattr(ul, "_FILE", f)
    monkeypatch.setattr(ul, "_LOCK", tmp_path / "u.lock")
    ul._append({"event": "tab_view", "page": "market", "tab": "etf", "uid": "u_x"})
    rec = json.loads(f.read_text().strip())
    assert rec["page"] == "market" and rec["tab"] == "etf" and "ts" in rec


def test_log_tab_view_no_streamlit_is_safe(monkeypatch, tmp_path):
    # streamlit 세션이 없어도(테스트 환경) 예외 없이 no-op/best-effort 여야 한다
    monkeypatch.setattr(ul, "_FILE", tmp_path / "u.jsonl")
    monkeypatch.setattr(ul, "_LOCK", tmp_path / "u.lock")
    ul.log_tab_view("market", "us")   # must not raise
