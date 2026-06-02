import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from fredapi import Fred
from .base import BaseProvider

load_dotenv()


class FredProvider(BaseProvider):

    def __init__(self):
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            raise EnvironmentError("FRED_API_KEY not set. Add it to your .env file.")
        self.fred = Fred(api_key=api_key)

    def fetch_series(self, series_id: str) -> dict | None:
        try:
            series = self.fred.get_series(series_id).dropna()
            if series.empty:
                return None
            return {
                "value": round(float(series.iloc[-1]), 4),
                "date": str(series.index[-1].date()),
            }
        except Exception:
            return None

    def fetch_series_bulk(self, series_map: dict[str, str]) -> dict[str, dict | None]:
        def _fetch(item):
            key, sid = item
            return key, self.fetch_series(sid)
        with ThreadPoolExecutor(max_workers=min(len(series_map), 8)) as ex:
            return dict(ex.map(_fetch, series_map.items()))
