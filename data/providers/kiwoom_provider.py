"""
키움증권 REST API 프로바이더.

개발자 포털: https://apiportal.kiwoom.com / https://openapi.kiwoom.com
- App Key / App Secret 은 포털에서 앱 등록 후 발급
- 계좌번호: 10자리 숫자 (예: 1234567890)
- 모든 API 호출은 POST, api-id 헤더로 TR 코드 전달
- 잔고 조회: api-id = kt00005 (체결잔고요청)
"""

import requests
from .brokerage_base import BrokerageProvider, BrokerageAuthError, BrokerageAPIError


class KiwoomProvider(BrokerageProvider):
    BASE_URL = "https://api.kiwoom.com"

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
            "secretkey": self.app_secret,   # 키움은 secretkey (appsecret 아님)
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
            body = resp.json() if resp.content else {}
            msg = body.get("return_msg") or body.get("message") or ""
            raise BrokerageAuthError(
                f"토큰 발급 실패 (HTTP {resp.status_code}). {msg}".strip()
            )

        data = resp.json()
        rc = data.get("return_code")
        if rc not in (None, "0", 0, "200"):
            msg = data.get("return_msg") or "인증 실패"
            raise BrokerageAuthError(f"키움 인증 오류: {msg}")
        token = data.get("token") or data.get("access_token")
        if not token:
            raise BrokerageAuthError("토큰 응답 형식을 알 수 없습니다. 키움 REST API 문서를 확인해 주세요.")
        return token

    # ── 잔고 조회 ──────────────────────────────────────────────────────────────

    def fetch_holdings(self, token: str) -> dict:
        # KRX + NXT 둘 다 조회해서 합산
        all_items: list[dict] = []
        per_exchange: dict = {}
        last_data: dict = {}

        for exchange in ("KRX", "NXT"):
            d = self._fetch_raw(token, exchange)
            last_data = d
            items = self._extract_items(d)
            per_exchange[exchange] = len(items)
            all_items.extend(items)

        # 예수금: 마지막 응답의 pymn_alow_amt (출금가능금액)
        cash_raw = (
            last_data.get("pymn_alow_amt")
            or last_data.get("dnca_tot_amt")
            or 0
        )
        cash_balance = _to_float(cash_raw)
        holdings = [self._normalize_row(row) for row in all_items if row]

        _debug_snapshot = {
            "acnt_no_sent": self.account_no,          # ← 실제 전송한 계좌번호
            "return_code": last_data.get("return_code"),
            "return_msg": last_data.get("return_msg"),
            "per_exchange_counts": per_exchange,
            "total_items": len(all_items),
            "first_item": all_items[0] if all_items else None,
            "acct_evlt_amt_tot": last_data.get("evlt_amt_tot"),
            "acct_stk_buy_tot": last_data.get("stk_buy_tot_amt"),
            "acct_tot_pl": last_data.get("tot_pl_tot"),
            "cash_raw": cash_raw,
        }
        return {"holdings": holdings, "cash_balance": cash_balance, "_debug": _debug_snapshot}

    def _fetch_raw(self, token: str, exchange: str) -> dict:
        url = f"{self.BASE_URL}/api/dostk/acnt"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "kt00005",
            "cont-yn": "N",
            "next-key": "",
        }
        body = {"acnt_no": self.account_no, "dmst_stex_tp": exchange}
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=15)
        except requests.Timeout:
            raise BrokerageAPIError("잔고 조회 시간이 초과되었습니다.")
        except requests.RequestException as e:
            raise BrokerageAPIError(f"네트워크 오류: {e}")

        if resp.status_code == 401:
            raise BrokerageAPIError("인증이 만료되었습니다. 다시 로그인해 주세요.")
        if not resp.ok:
            raise BrokerageAPIError(f"잔고 조회 실패 (HTTP {resp.status_code}).")

        data = resp.json()
        rc = data.get("return_code")
        if rc not in (None, "0", 0, "200"):
            msg = data.get("return_msg") or "잔고 조회 실패"
            raise BrokerageAPIError(f"계좌번호를 확인해 주세요. ({msg})")
        return data

    @staticmethod
    def _extract_items(data: dict) -> list[dict]:
        def _as_list(v):
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                return [v]
            return []
        return (
            _as_list(data.get("entr"))
            + _as_list(data.get("entr_d1"))
            + _as_list(data.get("entr_d2"))
        )

    # ── 필드 정규화 ────────────────────────────────────────────────────────────

    def _normalize_row(self, row: dict) -> dict:
        raw_code = row.get("stk_code") or row.get("pdno") or row.get("종목코드") or ""
        ticker = _make_ticker(raw_code)
        return {
            "ticker": ticker,
            "name": row.get("stk_name") or row.get("prdt_name") or row.get("종목명") or ticker,
            "보유수량": _to_float(row.get("hldg_qty") or row.get("cncl_qty") or row.get("보유수량")),
            "현재가": _to_float(row.get("prpr") or row.get("cur_prc") or row.get("현재가")),
            "평균단가": _to_float(row.get("pchs_avg_pric") or row.get("avg_prc") or row.get("평균단가")),
            "평가금액": _to_float(row.get("evlu_amt") or row.get("eval_amt") or row.get("평가금액")),
            "매입금액": _to_float(row.get("pchs_amt") or row.get("buy_amt") or row.get("매입금액")),
            "평가손익": _to_float(row.get("evlu_pfls_amt") or row.get("pfls_amt") or row.get("평가손익")),
            "수익률": _to_float(row.get("evlu_pfls_rt") or row.get("pfls_rt") or row.get("수익률")),
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
