"""
증권사 로그인 오케스트레이션.

로그인 흐름:
  login_with_brokerage(provider, app_key, app_secret, account_no)
    → 토큰 발급 → 잔고 조회 → 결과 반환
  실패 시 BrokerageAuthError / BrokerageAPIError (한국어 메시지)

session_state 에 저장되는 키:
  authenticated, auth_role, brokerage_provider,
  brokerage_token, brokerage_token_fetched_at,
  brokerage_holdings, brokerage_cash_balance
"""

import json
from datetime import datetime
from pathlib import Path

_CREDS_FILE = Path.home() / ".siminvest_auth.json"

from data.providers.brokerage_base import BrokerageAuthError, BrokerageAPIError  # noqa: F401
from data.providers.kiwoom_provider import KiwoomProvider
from data.providers.kis_provider import KISProvider

_PROVIDER_MAP = {
    "kiwoom": KiwoomProvider,
    "kis":    KISProvider,
}

# 실제 연동 가능한 증권사
PROVIDER_LABELS: dict[str, str] = {
    "kiwoom": "키움증권",
    "kis":    "한국투자증권",
}

# UI 표시용 전체 증권사 목록 (지원 예정 포함)
ALL_BROKERAGES: list[dict] = [
    # ── 연동 가능 ──────────────────────────────────────────────────────────────
    {
        "key": "kiwoom",
        "label": "키움증권",
        "ready": True,
        "portal_url": "https://apiportal.kiwoom.com",
        "portal_label": "apiportal.kiwoom.com",
        "steps": [
            "포털 회원가입 후 앱 등록",
            "앱 상세 페이지에서 App Key / App Secret 복사",
            "실전투자 계좌번호 10자리 준비",
        ],
        "note": "키움 REST API (Mac/Linux 지원). OpenAPI+와 별도 신청 필요.",
        "acct_format": "10자리 숫자 (하이픈 없이)",
    },
    {
        "key": "samsung",
        "label": "삼성증권",
        "ready": False,
        "portal_url": "https://www.samsungpop.com",
        "portal_label": "samsungpop.com",
        "steps": [
            "삼성증권 홈페이지 → 서비스 → mPOP Open API 신청",
            "App Key / App Secret 발급",
            "실전 계좌번호 입력",
        ],
        "note": "삼성증권 mPOP Open API — 현재 연동 준비 중입니다.",
        "acct_format": "숫자 (하이픈 없이)",
    },
    {
        "key": "kis",
        "label": "한국투자증권",
        "ready": True,
        "portal_url": "https://apiportal.koreainvestment.com",
        "portal_label": "apiportal.koreainvestment.com",
        "steps": [
            "포털 로그인 후 'API 신청' → 서비스 신청",
            "앱 Key 관리에서 App Key / App Secret 복사",
            "계좌번호 앞 8자리 + 뒤 상품코드 2자리 (총 10자리)",
        ],
        "note": "KIS Developers API (실전 계좌). TR_ID: TTTC8434R 사용.",
        "acct_format": "10자리 (앞 8자리 계좌 + 뒤 2자리 상품코드, 보통 '01')",
    },
    # ── 지원 예정 ──────────────────────────────────────────────────────────────
    {
        "key": "mirae",
        "label": "미래에셋증권",
        "ready": False,
        "portal_url": "https://securities.miraeasset.com/bbs/board/list.do?boardId=1314",
        "portal_label": "미래에셋 Open API",
        "steps": [
            "미래에셋증권 홈 → Open API 신청",
            "App Key / App Secret 발급",
            "계좌번호 입력",
        ],
        "note": "현재 연동 준비 중입니다. 곧 지원할 예정입니다.",
        "acct_format": "숫자",
    },
    {
        "key": "nh",
        "label": "NH투자증권",
        "ready": False,
        "portal_url": "https://apigw.nhqv.com",
        "portal_label": "apigw.nhqv.com",
        "steps": [
            "NH 개발자 포털 접속 후 앱 등록",
            "App Key / App Secret 발급",
            "계좌번호 입력",
        ],
        "note": "현재 연동 준비 중입니다. 곧 지원할 예정입니다.",
        "acct_format": "숫자",
    },
    {
        "key": "shinhan",
        "label": "신한투자증권",
        "ready": False,
        "portal_url": "https://openapi.shinhaninvest.com",
        "portal_label": "openapi.shinhaninvest.com",
        "steps": [
            "신한 Open API 포털 접속",
            "App Key / App Secret 발급",
            "계좌번호 입력",
        ],
        "note": "현재 연동 준비 중입니다. 곧 지원할 예정입니다.",
        "acct_format": "숫자",
    },
    {
        "key": "kb",
        "label": "KB증권",
        "ready": False,
        "portal_url": "https://openapi.kbsec.com",
        "portal_label": "openapi.kbsec.com",
        "steps": [
            "KB 개발자 포털 접속",
            "App Key / App Secret 발급",
            "계좌번호 입력",
        ],
        "note": "현재 연동 준비 중입니다. 곧 지원할 예정입니다.",
        "acct_format": "숫자",
    },
    {
        "key": "daeshin",
        "label": "대신증권",
        "ready": False,
        "portal_url": "https://www.daishin.com",
        "portal_label": "대신증권 홈",
        "steps": [
            "대신증권 OpenAPI 신청",
            "App Key / App Secret 발급",
            "계좌번호 입력",
        ],
        "note": "현재 연동 준비 중입니다. 곧 지원할 예정입니다.",
        "acct_format": "숫자",
    },
]

# key → brokerage info 빠른 조회
BROKERAGE_BY_KEY: dict[str, dict] = {b["key"]: b for b in ALL_BROKERAGES}


def save_credentials(username, provider: str, app_key: str, app_secret: str, account_no: str) -> None:
    """계정별 저장. username 없으면(게스트) 저장하지 않는다."""
    if not username:
        return
    from core import accounts
    accounts.set_setting(username, "brokerage", {
        "provider": provider, "app_key": app_key,
        "app_secret": app_secret, "account_no": account_no,
    })


def load_saved_credentials(username=None) -> dict | None:
    """계정별 우선, 없으면 전역 파일(레거시) 폴백."""
    if username:
        from core import accounts
        data = accounts.get_setting(username, "brokerage")
        if data and all(k in data for k in ("provider", "app_key", "app_secret", "account_no")):
            return data
    try:
        data = json.loads(_CREDS_FILE.read_text())
        if all(k in data for k in ("provider", "app_key", "app_secret", "account_no")):
            return data
    except Exception:
        pass
    return None


def delete_saved_credentials(username=None) -> None:
    if username:
        from core import accounts
        accounts.set_setting(username, "brokerage", None)
    try:
        _CREDS_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def login_with_brokerage(
    provider: str,
    app_key: str,
    app_secret: str,
    account_no: str,
) -> dict:
    """
    증권사 API 인증 및 잔고 조회.

    Args:
        provider:   "kiwoom" | "samsung" | "kis"
        app_key:    증권사 앱 키
        app_secret: 증권사 앱 시크릿
        account_no: 계좌번호

    Returns:
        {
            "token":        str,
            "holdings":     list[dict],
            "cash_balance": float,
            "fetched_at":   datetime,
        }

    Raises:
        BrokerageAuthError: 인증 실패
        BrokerageAPIError:  잔고 조회 실패
        ValueError:         지원하지 않는 provider
    """
    info = BROKERAGE_BY_KEY.get(provider)
    if info and not info["ready"]:
        raise BrokerageAPIError(f"{info['label']}은 현재 연동 준비 중입니다. 곧 지원할 예정입니다.")

    if provider not in _PROVIDER_MAP:
        raise ValueError(f"지원하지 않는 증권사: {provider}")

    p = _PROVIDER_MAP[provider](app_key, app_secret, account_no)
    token = p.fetch_token()
    result = p.fetch_holdings(token)

    return {
        "token": token,
        "holdings": result.get("holdings", []),
        "cash_balance": result.get("cash_balance", 0.0),
        "fetched_at": datetime.now(),
        "_debug": result.get("_debug"),
    }
