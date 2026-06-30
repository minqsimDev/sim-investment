"""
Vision으로 포트폴리오 스크린샷에서 보유 종목 파싱.
반환값은 portfolio.py의 _first() 헬퍼가 수락하는 영문 필드 + 한국어 필드 양쪽 포함.

라우팅(키 접두사로 자동 분기):
- ANTHROPIC_API_KEY 가 실제 키(sk-ant-…)면 **Claude Sonnet 4.6**(주력) — 표·한글·소수점
  인식이 가장 정확하고 일일 한도가 넉넉. 비전이 약한 크립토 카드형 화면도 강함.
- 없으면 **gemini-2.5-flash**(기본 폴백, 무료 20/일) 로 자동 전환.
  → 지금은 Gemini로 돌고, .env 에 실제 Anthropic 키만 넣으면 Claude로 자동 승격.

업로드는 이미지 N장을 단일 호출(extra_images)로 처리해 요청 수를 1로 줄인다.
"""
import base64
import json
import os
import re
import time

_CLAUDE_MODEL = "claude-sonnet-4-6"
_GEMINI_MODEL = "gemini-2.5-flash"


class VisionBusyError(RuntimeError):
    """비전 모델 과부하·일시적 사용 불가(503/429/529 등). 잠시 후 재시도 권장 — UI 는 '혼잡' 안내."""


_TRANSIENT_HINTS = ("503", "529", "unavailable", "overloaded", "high demand", "429",
                    "resource_exhausted", "rate limit", "try again", "deadline", "timeout", "500")


def _is_transient(err: Exception) -> bool:
    s = str(err).lower()
    return any(h in s for h in _TRANSIENT_HINTS)


def _has_claude_key() -> bool:
    """실제 Anthropic 키(sk-ant-…)가 있을 때만 Claude 경로. 플레이스홀더는 무시."""
    return (os.getenv("ANTHROPIC_API_KEY") or "").startswith("sk-ant-")


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
    "asset_class": "kr_stock | us_stock | etf | crypto | cash | other",
    "currency": "KRW | USD — 화면에 표시된 통화($면 USD, 원/₩면 KRW)"
  }
]

규칙(특히 숫자 정확도가 중요):
- **소수점(.)을 반드시 보존하라. 천단위 쉼표(,)만 제거하고 소수점은 절대 지우거나 무시하지 말 것.**
  예) "$4,500.00" → 4500.00,  "1,234.56" → 1234.56,  "152.30" → 152.30,  "12.5%" → 12.5
  소수점을 천단위 구분으로 착각해 "4,500.00"을 450000 처럼 만들지 말 것(자릿수가 폭증함).
- **주당 현재가(current_price)와 평균단가(avg_price)는 화면에 보이면 반드시 채워라.**
  이 값들이 평가/매입금액의 자릿수 교차검증 앵커로 쓰인다(eval≈shares×current_price).
- 통화 기호·% 기호는 제거하되 숫자 값과 소수점 자릿수는 화면 그대로.
- 금액은 화면에 보이는 숫자·통화 그대로 적고(환산하지 말 것), 통화는 currency 필드로 표기.
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


def _extract_json(text: str) -> list[dict]:
    """모델 응답 텍스트 → 보유 리스트. 코드펜스/래핑 방어."""
    text = (text or "").strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)   # 방어적: 코드펜스가 섞이면 제거
    text = re.sub(r"\n?```$", "", text)
    holdings = json.loads(text.strip())
    if not isinstance(holdings, list):           # 드물게 {"holdings": [...]} 형태 방어
        holdings = holdings.get("holdings") or holdings.get("items") or []
    return holdings


def _build_claude_call(images: list[tuple[bytes, str]]):
    """Claude Sonnet 4.6 비전 호출 thunk — 클라이언트·base64 인코딩을 미리 1회만 구성."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    content: list[dict] = [
        {"type": "image",
         "source": {"type": "base64", "media_type": mt,
                    "data": base64.standard_b64encode(b).decode()}}
        for b, mt in images
    ]
    content.append({"type": "text", "text": _PROMPT})

    def _call() -> str:
        msg = client.messages.create(
            model=_CLAUDE_MODEL, max_tokens=4096, temperature=0,  # temperature=0=결정적 추출
            messages=[{"role": "user", "content": content}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    return _call


def _build_gemini_call(images: list[tuple[bytes, str]]):
    """gemini-2.5-flash 폴백(무료 20/일) 호출 thunk. thinking 기본 ON(정확도 우선)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    parts: list = [types.Part.from_bytes(data=b, mime_type=mt) for b, mt in images]
    parts.append(_PROMPT)
    cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json")

    def _call() -> str:
        return client.models.generate_content(model=_GEMINI_MODEL, contents=parts, config=cfg).text
    return _call


def _image_mime(data: bytes) -> str:
    """이미지 바이트의 매직넘버로 실제 포맷 판정. 업로드 MIME(안드로이드 '파일' 피커에서
    application/octet-stream 등으로 틀리게 옴)에 의존하지 않게 — 모바일 업로드 인식 실패의 주원인.
    Claude/Gemini 지원: png/jpeg/webp/gif. 미지원(HEIC 등)이면 ''."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return ""


def _to_supported(data: bytes) -> tuple[bytes, str]:
    """지원 포맷 + 정확한 MIME 보장. 미지원(HEIC 등)이면 Pillow로 JPEG 변환 시도, 실패 시 에러."""
    mt = _image_mime(data)
    if mt:
        return data, mt
    try:
        import io
        from PIL import Image
        try:
            import pillow_heif  # HEIC 지원(있으면)
            pillow_heif.register_heif_opener()
        except Exception:
            pass
        buf = io.BytesIO()
        Image.open(io.BytesIO(data)).convert("RGB").save(buf, format="JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        raise ValueError("지원하지 않는 이미지 형식입니다. PNG 또는 JPG 스크린샷을 사용해 주세요.") from e


def parse_portfolio_image(
    image_bytes: bytes,
    media_type: str = "image/png",
    extra_images: list[tuple[bytes, str]] | None = None,
) -> list[dict]:
    """이미지 바이트 → 보유 종목 리스트. 여러 장 전달 시 단일 API 호출로 합산.
    extra_images: [(bytes, media_type), ...] 추가 이미지 목록.
    Claude 키가 있으면 Claude(주력), 없으면 gemini-2.5-flash(폴백).
    MIME은 바이트에서 재판정(업로드 MIME 무시) — 모바일 '파일' 피커의 잘못된 MIME 대응."""
    raw = [image_bytes] + [b for b, _ in (extra_images or [])]
    images = [_to_supported(b) for b in raw]
    if _has_claude_key():
        build = _build_claude_call
    elif os.getenv("GEMINI_API_KEY"):
        build = _build_gemini_call
    else:
        raise EnvironmentError("ANTHROPIC_API_KEY(sk-ant-…) 또는 GEMINI_API_KEY 가 필요합니다.")

    call = build(images)   # 클라이언트·인코딩은 1회만 — 재시도 시 네트워크 호출만 반복
    # 일시적 과부하(503/429/529 등)는 짧은 백오프로 자동 재시도 → 지속되면 VisionBusyError.
    for _attempt in range(3):
        try:
            # 저장 직전 자릿수(소수점 유실) 결정론적 보정 — 모델이 '$27,543.519'를 27543519로
            # 부풀려 읽어도 주당가 앵커로 ×10ⁿ 오류를 잡는다(라이브 시세 불필요).
            from core.holdings_reconcile import reconcile_holdings
            return reconcile_holdings(_normalize(_extract_json(call())))
        except Exception as e:  # noqa: BLE001 — 일시적/영구 구분만 하고 재던짐
            if _is_transient(e):
                if _attempt < 2:
                    time.sleep(1.5 * (_attempt + 1))
                    continue
                raise VisionBusyError(str(e)) from e
            raise
