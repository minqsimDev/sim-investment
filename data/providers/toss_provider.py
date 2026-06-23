"""토스증권 Open API provider — 시세·환율 조회 전용.

지시서 1장(인증·보안) 준수:
  - OAuth2 Client Credentials Grant. 토큰은 만료 전까지 재사용(캐시).
  - client_id/secret 은 .env(서버측)에서만 로드. 클라이언트 노출 금지.
  - 계좌·주문 API 는 호출하지 않는다(시세·환율만).

토스 심볼 규칙(공식 스펙):
  - KRX: 6자리 코드(예: 005930)   US: 영문 티커(예: AAPL)
  - 통화는 KRW/USD 만. 환율은 KRW↔USD 만 제공.
"""
import os
import time
import requests

from .base import BaseProvider

_BASE_URL = "https://openapi.tossinvest.com"
_TIMEOUT = 15

# /prices 배치 응답이 전일종가(기준가)를 담을 수 있는 후보 키. 있으면 종목당 캔들 호출을 생략한다.
_PREV_CLOSE_KEYS = ("base", "previousClose", "prevClose", "basePrice", "closePrice", "prevPrice")


def prev_close_from_row(row: dict) -> float | None:
    """/prices 한 행에서 전일종가를 추출. 후보 키 중 첫 숫자값을 반환, 없으면 None."""
    for k in _PREV_CLOSE_KEYS:
        v = row.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


class TossClient(BaseProvider):
    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self._client_id = client_id or os.getenv("TOSS_CLIENT_ID")
        self._client_secret = client_secret or os.getenv("TOSS_CLIENT_SECRET")
        if not self._client_id or not self._client_secret:
            raise RuntimeError("TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 가 .env 에 없습니다.")
        self._token: str | None = None
        self._token_exp: float = 0.0  # epoch seconds
        self.last_rate_headers: dict | None = None

    # ── 인증 ──────────────────────────────────────────────────────────────
    def _get_token(self) -> str:
        # 만료 60초 전부터 갱신
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = requests.post(
            f"{_BASE_URL}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_exp = time.time() + int(body.get("expires_in", 3600))
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _capture_rate_headers(self, resp: requests.Response):
        keys = ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After")
        hdr = {k: resp.headers.get(k) for k in keys if resp.headers.get(k) is not None}
        if hdr:
            self.last_rate_headers = hdr

    # ── 현재가 (배치, 최대 200) ────────────────────────────────────────────
    def get_prices(self, symbols: list[str]) -> dict[str, dict | None]:
        """symbol -> {lastPrice, currency, timestamp} or None(미커버/에러)."""
        out: dict[str, dict | None] = {s: None for s in symbols}
        if not symbols:
            return out
        for i in range(0, len(symbols), 200):
            chunk = symbols[i : i + 200]
            found = self._get_prices_chunk(chunk)
            # 배치가 통째로 실패하면 개별 호출로 정밀 판정
            if found is None:
                for s in chunk:
                    single = self._get_prices_chunk([s])
                    if single and s in single:
                        out[s] = single[s]
            else:
                out.update(found)
        return out

    def _get_prices_chunk(self, chunk: list[str]) -> dict[str, dict] | None:
        try:
            resp = requests.get(
                f"{_BASE_URL}/api/v1/prices",
                params={"symbols": ",".join(chunk)},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            self._capture_rate_headers(resp)
            if resp.status_code != 200:
                return None
            result = resp.json().get("result", [])
            return {
                row["symbol"]: {
                    "lastPrice": row.get("lastPrice"),
                    "currency": row.get("currency"),
                    "timestamp": row.get("timestamp"),
                    "prevClose": prev_close_from_row(row),   # 있으면 캔들 호출 생략(첫 로딩 단축)
                }
                for row in result
            }
        except Exception:
            return None

    # ── 일봉 캔들 ──────────────────────────────────────────────────────────
    def fetch_candles(self, symbol: str, count: int = 200,
                      before: str | None = None) -> tuple[list[dict], str | None]:
        """일봉 한 페이지. (candles 최신순, nextBefore) 반환. 실패 시 ([], None).
        before 에 직전 응답의 nextBefore 를 넘기면 더 과거 페이지 조회(페이지네이션).
        Rate Limits Group: MARKET_DATA_CHART (시세와 별도 그룹)."""
        params = {"symbol": symbol, "interval": "1d", "count": min(count, 200)}
        if before:
            params["before"] = before
        try:
            resp = requests.get(f"{_BASE_URL}/api/v1/candles", params=params,
                                headers=self._headers(), timeout=_TIMEOUT)
            self._capture_rate_headers(resp)
            if resp.status_code != 200:
                return [], None
            r = resp.json().get("result", {})
            return r.get("candles", []), r.get("nextBefore")
        except Exception:
            return [], None

    def get_daily_candles(self, symbol: str, count: int = 2) -> list[dict] | None:
        """최신순 캔들 목록(전일종가 계산용). [0]=최신일, [1]=직전일. 실패 시 None."""
        candles, _ = self.fetch_candles(symbol, count=count)
        return candles or None

    # ── 환율 (KRW↔USD 만 지원) ─────────────────────────────────────────────
    def get_exchange_rate(self, base: str, quote: str) -> dict | None:
        try:
            resp = requests.get(
                f"{_BASE_URL}/api/v1/exchange-rate",
                params={"baseCurrency": base, "quoteCurrency": quote},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            self._capture_rate_headers(resp)
            if resp.status_code != 200:
                return None
            r = resp.json().get("result", {})
            return {"rate": r.get("rate"), "timestamp": r.get("validFrom")}
        except Exception:
            return None
