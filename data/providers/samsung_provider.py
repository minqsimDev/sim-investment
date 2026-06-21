"""
삼성증권 mPOP Open API 프로바이더.

개발자 포털: https://openapi.samsungpop.com
- App Key / App Secret 은 포털 앱 등록 후 발급
- 계좌번호: 숫자 (예: 1234567890)

아래 BASE_URL, 엔드포인트, 응답 필드명은 삼성증권 Open API 공식 문서를 기준으로
작성됐습니다. 포털에서 최신 스펙을 확인 후 필요 시 수정하세요.
"""

import requests
from .brokerage_base import BrokerageProvider, BrokerageAuthError, BrokerageAPIError


class SamsungProvider(BrokerageProvider):
    BASE_URL = "https://openapi.samsungpop.com"  # 포털 확인 후 수정

    def __init__(self, app_key: str, app_secret: str, account_no: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no.replace("-", "")

    # ── 토큰 발급 ──────────────────────────────────────────────────────────────

    def fetch_token(self) -> str:
        url = f"{self.BASE_URL}/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
        except requests.Timeout:
            raise BrokerageAuthError("서버 연결 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")
        except requests.RequestException as e:
            raise BrokerageAuthError(f"네트워크 오류: {e}")

        if resp.status_code == 401:
            raise BrokerageAuthError("앱 키 또는 시크릿이 올바르지 않습니다.")
        if not resp.ok:
            raise BrokerageAuthError(f"토큰 발급 실패 (HTTP {resp.status_code}). 포털에서 앱 키를 확인해 주세요.")

        data = resp.json()
        token = data.get("access_token") or data.get("token")
        if not token:
            raise BrokerageAuthError("토큰 응답 형식을 알 수 없습니다. 삼성증권 Open API 문서를 확인해 주세요.")
        return token

    # ── 잔고 조회 ──────────────────────────────────────────────────────────────

    def fetch_holdings(self, token: str) -> dict:
        # TODO: 삼성증권 잔고 조회 엔드포인트 확인 후 수정
        url = f"{self.BASE_URL}/trading/inquire-balance"
        headers = {
            "Authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "Content-Type": "application/json",
        }
        params = {
            "account_no": self.account_no,
            "tr_id": "TTTC8434R",  # TODO: 삼성 문서에서 올바른 TR ID 확인
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        except requests.Timeout:
            raise BrokerageAPIError("잔고 조회 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")
        except requests.RequestException as e:
            raise BrokerageAPIError(f"네트워크 오류: {e}")

        if resp.status_code == 401:
            raise BrokerageAPIError("인증이 만료되었습니다. 다시 로그인해 주세요.")
        if not resp.ok:
            raise BrokerageAPIError(f"잔고 조회 실패 (HTTP {resp.status_code}).")

        body = resp.json()

        rt_cd = body.get("rt_cd") or body.get("return_code")
        if rt_cd not in (None, "0", 0):
            msg = body.get("msg1") or body.get("message") or "잔고 조회 실패"
            raise BrokerageAPIError(f"계좌번호를 확인해 주세요. ({msg})")

        items = body.get("output1") or body.get("stocks") or body.get("holdings") or []
        summary = body.get("output2") or {}

        cash_raw = summary.get("dnca_tot_amt") or summary.get("cash_balance") or 0
        cash_balance = _to_float(cash_raw)

        holdings = [self._normalize_row(row) for row in items if row]
        return {"holdings": holdings, "cash_balance": cash_balance}

    # ── 필드 정규화 ────────────────────────────────────────────────────────────

    def _normalize_row(self, row: dict) -> dict:
        """삼성증권 응답 한 행을 _normalize_holdings() 호환 형식으로 변환."""
        raw_code = row.get("pdno") or row.get("stk_code") or row.get("종목코드") or ""
        ticker = _make_ticker(raw_code)

        return {
            "ticker": ticker,
            "name": row.get("prdt_name") or row.get("stk_name") or row.get("종목명") or ticker,
            "보유수량": _to_float(row.get("hldg_qty") or row.get("보유수량")),
            "현재가": _to_float(row.get("prpr") or row.get("현재가")),
            "평균단가": _to_float(row.get("pchs_avg_pric") or row.get("평균단가")),
            "평가금액": _to_float(row.get("evlu_amt") or row.get("평가금액")),
            "매입금액": _to_float(row.get("pchs_amt") or row.get("매입금액")),
            "평가손익": _to_float(row.get("evlu_pfls_amt") or row.get("평가손익")),
            "수익률": _to_float(row.get("evlu_pfls_rt") or row.get("수익률")),
        }


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _make_ticker(code: str) -> str:
    code = str(code).strip()
    if code.isdigit() and len(code) == 6:
        return f"{code}.KS"
    return code


def _to_float(val) -> float:
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0
