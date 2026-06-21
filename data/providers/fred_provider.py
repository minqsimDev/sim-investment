import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from fredapi import Fred
from .base import BaseProvider
from data.session import _cache_key, _load, _save

load_dotenv()

_FRED_TTL = 3600  # 1 hour — FRED macro data changes slowly


class FredProvider(BaseProvider):

    def __init__(self):
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            raise EnvironmentError("FRED_API_KEY not set. Add it to your .env file.")
        self.fred = Fred(api_key=api_key)

    def fetch_series(self, series_id: str) -> dict | None:
        key = _cache_key("fred", series_id)
        cached = _load(key, _FRED_TTL)
        if cached is not None:
            return cached
        try:
            series = self.fred.get_series(series_id).dropna()
            if series.empty:
                return None
            import pandas as pd
            latest_date = series.index[-1]
            # 1년 전 관측치(YoY 산출용 — CPI/PCE 등). 빈도 무관하게 날짜 기준으로 탐색
            ya = series[series.index <= latest_date - pd.DateOffset(years=1)]
            result = {
                "value": round(float(series.iloc[-1]), 4),
                "date": str(latest_date.date()),
                # 직전 관측치(전월 대비 증감 산출용 — 비농업 고용 등)
                "prev_value": round(float(series.iloc[-2]), 4) if len(series) >= 2 else None,
                # 1년 전 관측치(YoY 산출용 — 물가지수 등)
                "year_ago_value": round(float(ya.iloc[-1]), 4) if not ya.empty else None,
            }
            _save(key, result)
            return result
        except Exception:
            return None

    def fetch_series_bulk(self, series_map: dict[str, str]) -> dict[str, dict | None]:
        def _fetch(item):
            key, sid = item
            return key, self.fetch_series(sid)
        with ThreadPoolExecutor(max_workers=min(len(series_map), 8)) as ex:
            return dict(ex.map(_fetch, series_map.items()))
