from abc import ABC, abstractmethod


class BrokerageAuthError(Exception):
    """인증 실패 (잘못된 App Key / Secret, 만료된 토큰 등)."""


class BrokerageAPIError(Exception):
    """잔고 조회 실패 (잘못된 계좌번호, 서버 오류 등)."""


class BrokerageProvider(ABC):
    """모든 증권사 프로바이더가 구현해야 하는 인터페이스."""

    @abstractmethod
    def fetch_token(self) -> str:
        """
        OAuth 액세스 토큰을 발급받아 반환한다.
        실패 시 BrokerageAuthError(한국어 메시지) 를 raise.
        """

    @abstractmethod
    def fetch_holdings(self, token: str) -> dict:
        """
        보유 종목과 예수금을 조회한다.

        반환:
            {
                "holdings": list[dict],   # _normalize_holdings() 호환 필드명
                "cash_balance": float,    # 예수금 (원화)
            }

        실패 시 BrokerageAPIError(한국어 메시지) 를 raise.
        """
