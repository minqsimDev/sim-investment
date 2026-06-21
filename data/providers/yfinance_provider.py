import yfinance as yf
from .base import BaseProvider
from data.session import cached_download


class YFinanceProvider(BaseProvider):

    def fetch_prices_bulk(self, tickers: list[str], force: bool = False) -> dict[str, dict | None]:
        if not tickers:
            return {}

        try:
            raw = cached_download(
                tickers,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=True,
                threads=True,
                timeout=20,
                # force=True → ttl 0으로 디스크 캐시 우회(백그라운드 keep-warm 갱신용)
                ttl=0 if force else 1800,  # 30 min — matches Streamlit cache TTL so restarts hit disk cache
            )
        except Exception:
            return {t: None for t in tickers}

        multi = len(tickers) > 1
        results = {}

        for ticker in tickers:
            try:
                closes = raw["Close"][ticker].dropna() if multi else raw["Close"].dropna()

                if closes.empty:
                    results[ticker] = None
                    continue

                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else None
                change = round(price - prev, 4) if prev is not None else None
                change_pct = round((price - prev) / prev * 100, 2) if prev is not None else None

                results[ticker] = {
                    "price": round(price, 4),
                    "prev_close": round(prev, 4) if prev is not None else None,
                    "change": change,
                    "change_pct": change_pct,
                }
            except Exception:
                results[ticker] = None

        return results
