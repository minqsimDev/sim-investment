import pytest
from pathlib import Path
from core.config_loader import load_config


def test_config_loads():
    config = load_config()
    assert isinstance(config, dict)


def test_required_keys_present():
    config = load_config()
    required = ["user", "my_etfs", "benchmark_etfs", "us_stocks", "commodities", "fx", "macro"]
    for key in required:
        assert key in config, f"Missing key: {key}"


def test_my_etfs_have_drivers():
    config = load_config()
    for etf in config["my_etfs"]:
        assert "drivers" in etf, f"ETF missing drivers: {etf['name']}"
        assert len(etf["drivers"]) > 0


def test_user_settings():
    config = load_config()
    user = config["user"]
    assert user["base_currency"] == "KRW"
    assert user["timezone"] == "Asia/Seoul"


def test_fred_series_present():
    config = load_config()
    fred = config["macro"]["fred_series"]
    assert "us_10y" in fred
    assert "fed_funds" in fred
