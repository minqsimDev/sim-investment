"""
Gemini Vision으로 포트폴리오 스크린샷에서 보유 종목 파싱.
반환값은 portfolio.py의 _first() 헬퍼가 수락하는 영문 필드 + 한국어 필드 양쪽 포함.

소스: Gemini API(`GEMINI_API_KEY`, 무료 티어). 테스트 단계 무료 사용.
모델: gemini-2.5-flash-lite — 이 키 기준 무료 한도 가용(2.0-flash=0, 2.5-flash=20/일 대비 헤드룸 큼).
업로드는 이미지 N장을 단일 호출(extra_images)로 처리해 요청 수를 1로 줄인다.
정확도가 부족하면 _MODEL 을 "gemini-2.5-flash"(20/일) 또는 Anthropic Claude(히스토리에 Sonnet 4.6)로 교체.
"""
import json
import os
import re
import time

_MODEL = "gemini-2.5-flash-lite"


class VisionBusyError(RuntimeError):
    """비전 모델 과부하·일시적 사용 불가(503/429 등). 잠시 후 재시도 권장 — UI 는 '혼잡' 안내."""


_TRANSIENT_HINTS = ("503", "unavailable", "overloaded", "high demand", "429",
                    "resource_exhausted", "try again", "deadline", "timeout", "500")


def _is_transient(err: Exception) -> bool:
    s = str(err).lower()
    return any(h in s for h in _TRANSIENT_HINTS)


_PROMPT = """이 이미지(들)는 증권사 앱/HTS/MTS의 보유종목 또는 포트폴리오 화면입니다.
여러 장인 경우 모든 이미지의 종목을 합쳐서 하나의 JSON 배열로 응답하세요.
같은 종목이 여러 장에 중복되면 한 번만 포함하세요.

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
- 숫자는 쉼표·기호·통화표시 없이 순수 숫자 (예: 1526000, 12.5, -3.2)
- 평가금액과 매입금액 컬럼을 혼동하지 말 것. 손익이 마이너스면 부호(-)를 정확히 반영.
- 현금/예수금이 보이면 포함 (asset_class: "cash")
- 확인 불가능한 필드는 null"""


def _normalize(holdings: list[dict]) -> list[dict]:
    """영문 필드 → 한국어 필드 병기. portfolio.py summary stat lines 호환용."""
    out = []
    for h in holdings:
        if not isinstance(h, dict):
            continue
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
    """이미지 바이트 → 보유 종목 리스트. 여러 장 전달 시 단일 API 호출로 합산.
    extra_images: [(bytes, media_type), ...] 추가 이미지 목록."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    parts: list = [types.Part.from_bytes(data=image_bytes, mime_type=media_type)]
    for extra_bytes, extra_mt in (extra_images or []):
        parts.append(types.Part.from_bytes(data=extra_bytes, mime_type=extra_mt))
    parts.append(_PROMPT)

    # temperature=0(결정적) + json 강제(파싱 오류 제거). flash-lite 는 기본 thinking 최소라 미설정으로 충분.
    cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json")

    # 일시적 과부하(503/429 등)는 짧은 백오프로 자동 재시도 → 지속되면 VisionBusyError.
    resp = None
    for _attempt in range(3):
        try:
            resp = client.models.generate_content(model=_MODEL, contents=parts, config=cfg)
            break
        except Exception as e:  # noqa: BLE001 — 일시적/영구 구분만 하고 재던짐
            if _is_transient(e):
                if _attempt < 2:
                    time.sleep(1.5 * (_attempt + 1))
                    continue
                raise VisionBusyError(str(e)) from e
            raise

    text = (resp.text or "").strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)   # 방어적: 코드펜스가 섞이면 제거
    text = re.sub(r"\n?```$", "", text)
    holdings = json.loads(text.strip())
    if not isinstance(holdings, list):           # 드물게 {"holdings": [...]} 형태 방어
        holdings = holdings.get("holdings") or holdings.get("items") or []
    return _normalize(holdings)
