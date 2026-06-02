import yaml
from pathlib import Path

REQUIRED_KEYS = ["user", "my_etfs", "benchmark_etfs", "us_stocks", "commodities", "fx", "macro"]

CONFIG_PATH = Path(__file__).parent.parent / "config" / "assets.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError("Config file is empty.")

    missing = [k for k in REQUIRED_KEYS if k not in config]
    if missing:
        raise KeyError(f"Config missing required keys: {missing}")

    return config
