"""
Gemini Flash Vision API로 포트폴리오 스크린샷에서 보유 종목 파싱.
반환값은 portfolio.py의 _first() 헬퍼가 수락하는 영문 필드 + 한국어 필드 양쪽 포함.
"""
import json
import os
import re

_MODEL = "gemini-2.5-flash"

_PROMPT = """이 이미지(들)는 증권사 앱/HTS/MTS의 보유종목 또는 포트폴리오 화면입니다.
여러 장인 경우 모든 이미지의 종목을 합산해서 하나의 JSON 배열로 응답하세요.

화면에 보이는 보유 종목을 모두 추출해 JSON 배열로만 응답하세요 (설명·마크다운 없이):

[
  {
    "name": "종목명",
    "ticker": "종목코드 (한국주식: XXXXXX.KS, 미국주식/ETF: TICKER, 모를 경우 null)",
    "shares": 보유수량_숫자_또는_null,
    "avg_price": 평균단가_숫자_또는_null,
    "current_price": 현재가_숫자_또는_null,
    "eval_amount": 평가금액_숫자_또는_null,
    "purchase_amount": 매입금액_숫자_또는_null,
    "profit_loss": 평가손익_숫자_또는_null,
    "profit_loss_pct": 손익률_숫자_또는_null,
    "asset_class": "kr_stock | us_stock | etf | crypto | cash | other"
  }
]

규칙:
- 숫자는 쉼표·기호 없이 순수 숫자 (예: 1526000, 12.5)
- 현금/예수금이 보이면 포함 (asset_class: "cash")
- 확인 불가능한 필드는 null"""


def _normalize(holdings: list[dict]) -> list[dict]:
    """영문 필드 → 한국어 필드 병기. portfolio.py summary stat lines 호환용."""
    out = []
    for h in holdings:
        n = dict(h)
        if n.get("eval_amount") is not None:
            n.setdefault("평가금액", n["eval_amount"])
        if n.get("purchase_amount") is not None:
            n.setdefault("매입금액", n["purchase_amount"])
        if n.get("profit_loss") is not None:
            n.setdefault("평가손익", n["profit_loss"])
        if n.get("profit_loss_pct") is not None:
            n.setdefault("수익률", n["profit_loss_pct"])
        if n.get("shares") is not None:
            n.setdefault("보유수량", n["shares"])
        if n.get("avg_price") is not None:
            n.setdefault("평균단가", n["avg_price"])
        if n.get("current_price") is not None:
            n.setdefault("현재가", n["current_price"])
        out.append(n)
    return out


def parse_portfolio_image(
    image_bytes: bytes,
    media_type: str = "image/png",
    extra_images: list[tuple[bytes, str]] | None = None,
) -> list[dict]:
    """
    이미지 바이트 → 보유 종목 리스트. 여러 장 전달 시 단일 API 호출로 합산.
    extra_images: [(bytes, media_type), ...] 추가 이미지 목록
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    parts: list = []
    parts.append(types.Part.from_bytes(data=image_bytes, mime_type=media_type))
    for extra_bytes, extra_mt in (extra_images or []):
        parts.append(types.Part.from_bytes(data=extra_bytes, mime_type=extra_mt))
    parts.append(_PROMPT)

    resp = client.models.generate_content(model=_MODEL, contents=parts)
    text = resp.text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    holdings = json.loads(text.strip())
    return _normalize(holdings)
