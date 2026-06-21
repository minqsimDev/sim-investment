"""
증권사 MTS 스크린샷을 Claude Vision API로 파싱해 보유 종목 데이터를 추출한다.

ANTHROPIC_API_KEY 환경 변수가 설정돼 있어야 한다.
"""

import anthropic
import base64
import json
import re

_PROMPT = """이 이미지는 증권사 MTS 앱의 보유 종목 화면입니다.
이미지에서 보유 종목 정보를 정확히 추출해서 JSON으로 반환해 주세요.

반환 형식:
{
  "holdings": [
    {
      "ticker": "종목코드 (한국 6자리 숫자 → 예: 005930.KS, 미국 → NVDA, 코인 → BTC-USD)",
      "name": "종목명",
      "보유수량": 수량(숫자),
      "현재가": 현재가(숫자),
      "평균단가": 평균매입단가(숫자),
      "평가금액": 평가금액(숫자),
      "매입금액": 매입금액(숫자, 없으면 보유수량×평균단가),
      "평가손익": 평가손익(숫자, 음수 가능),
      "수익률": 수익률(숫자, % 기호 제외, 음수 가능)
    }
  ],
  "cash_balance": 예수금또는현금잔고(숫자, 없으면 0),
  "brokerage": "증권사명"
}

주의:
- 숫자에서 쉼표·원기호(₩)·달러($)·% 제거 후 숫자만
- 한국 주식 종목코드 6자리 숫자 뒤에 .KS 붙이기
- 읽을 수 없는 필드는 0으로 처리
- JSON만 반환, 설명 없이"""


def extract_holdings_from_image(image_bytes: bytes, mime_type: str = "image/png") -> dict:
    """
    증권사 MTS 스크린샷을 Claude Vision으로 파싱.

    Returns:
        {"holdings": list[dict], "cash_balance": float, "_debug": dict}

    Raises:
        ValueError: JSON 파싱 실패 시
    """
    client = anthropic.Anthropic()
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime_type, "data": image_data},
                },
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"이미지 파싱 실패: {e}\n\n원본 응답:\n{raw[:500]}")

    holdings = parsed.get("holdings", [])
    cash_balance = float(parsed.get("cash_balance") or 0)

    return {
        "holdings": holdings,
        "cash_balance": cash_balance,
        "_debug": {
            "source": "screenshot",
            "brokerage": parsed.get("brokerage", ""),
            "raw_count": len(holdings),
        },
    }
