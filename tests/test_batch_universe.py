"""배치 스냅샷 유니버스 — 전 계정 보유 포함 + 크립토 -USD 보정 + 현금 제외."""
import json
from pathlib import Path

import core.accounts as accounts
from data.fetcher import universe_tickers, _config_tickers
from core.config_loader import load_config


def _write_accounts(tmp_path: Path) -> Path:
    f = tmp_path / "acc.json"
    f.write_text(json.dumps({"accounts": {
        "alice": {"portfolios": [{"name": "p1", "holdings": [
            {"ticker": "BTC", "asset_class": "crypto"},      # → BTC-USD
            {"ticker": "AAPL", "asset_class": "us_stock"},
            {"ticker": "KRW", "asset_class": "cash"},        # 제외
        ]}]},
        "bob": {"portfolios": [{"name": "p2", "holdings": [
            {"ticker": "aapl", "asset_class": "us_stock"},   # 중복(대문자화)
            {"ticker": "005930.KS", "asset_class": "kr_stock"},
        ]}]},
    }}), encoding="utf-8")
    return f


def test_all_holding_tickers_maps_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "_FILE", _write_accounts(tmp_path))
    out = accounts.all_holding_tickers()
    assert set(out) == {"BTC-USD", "AAPL", "005930.KS"}   # 크립토 -USD, 현금 제외, 중복 제거


def test_all_holding_tickers_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "_FILE", tmp_path / "nope.json")
    assert accounts.all_holding_tickers() == []


def test_universe_includes_config_and_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "_FILE", _write_accounts(tmp_path))
    cfg_tks = set(_config_tickers(load_config()))
    uni = set(universe_tickers(include_accounts=True))
    assert cfg_tks <= uni                  # config 전부 포함
    assert {"BTC-USD", "005930.KS"} <= uni  # 계정 보유도 포함
    assert {"IEF", "SHY", "LQD", "HYG"} <= uni  # 채권 ETF(고정 표시)도 DB 적재 대상
    assert len(uni) == len(set(uni))        # 중복 없음
