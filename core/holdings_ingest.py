"""
보유 인제스트 정규화 게이트 — AI 파서/외부 입력을 저장 전에 표준형으로.

반복 버그의 근본 원인 = 파서 출력(티커 형식·통화·자산군이 행마다 불안정)을 그대로 저장하고,
렌더 시점에 흩어진 보정(_holding_currency·_category_for_holding·…)으로 때우던 것.
여기서 저장 전에 한 번에 확정한다:
  ① 티커 표준화 — 6자리 코드→.KS, 크립토 심볼→-USD, 대문자
  ② 통화 확정 — 한국 상장(코드·발행사 접두)=KRW, 해외 상장=USD (파서의 currency 태그 불신)
  ③ 자산군 확정 — cash/crypto/etf/kr_stock/us_stock 재판정
  ④ 필수값 검증 — 종목명 + (평가금액>0 또는 수량×단가>0). 못 읽은 행은 조용히 버리지 않고
     사유와 함께 반환해 사용자에게 노출한다.

금액 자릿수 보정(×10ⁿ)은 core/holdings_reconcile 이 파서 직후 담당(기존 유지).
"""
import re

# 국내 ETF 발행사 접두 — 티커가 없어도 이름으로 한국 상장 판정
KR_ETF_ISSUERS = ("TIGER", "KODEX", "RISE", "PLUS", "ACE", "SOL",
                  "KIWOOM", "HANARO", "ARIRANG", "KBSTAR", "KOSEF")
# 크립토 주요 심볼 — 파서가 'BTC' 처럼 반환 시 -USD 부착(시세 형식)
_CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX",
                   "LINK", "BCH", "LTC", "DOT", "BNB"}
_CASH_TICKERS = {"CASH", "KRW", "USD"}


def _num(v):
    try:
        f = float(str(v).replace(",", "").strip())
        return f if f == f else None   # NaN 방지
    except (TypeError, ValueError):
        return None


def _first(row: dict, *keys):
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def is_kr_listed(ticker: str, name: str = "") -> bool:
    """한국 상장 여부 — .KS/.KQ 접미, 6자리 숫자 코드, 국내 ETF 발행사 접두 이름."""
    t = (ticker or "").upper().strip()
    if t.endswith(".KS") or t.endswith(".KQ") or re.fullmatch(r"\d{6}", t):
        return True
    nu = (name or "").upper()
    return bool(nu) and any(nu.startswith(p) for p in KR_ETF_ISSUERS)


def canonical_asset_class(row: dict, ticker: str, name: str) -> str:
    """자산군 확정 — 파서 태그는 참고만, 티커·이름 우선."""
    raw = str(_first(row, "asset_class", "assetType", "type", "category", "group") or "").lower()
    t = (ticker or "").upper()
    if "cash" in raw or "현금" in raw or t in _CASH_TICKERS:
        return "cash"
    if "crypto" in raw or t.endswith("-USD") or t in _CRYPTO_SYMBOLS:
        return "crypto"
    nu = (name or "").upper()
    if "ETF" in nu or any(nu.startswith(p) for p in KR_ETF_ISSUERS) \
            or ("etf" in raw and is_kr_listed(t)):
        return "etf"
    if "kr" in raw or is_kr_listed(t):
        return "kr_stock"
    if t:
        return "us_stock"
    return "other"


def canonical_ticker(ticker: str, asset_class: str) -> str:
    """티커 표준화 — 시세 조회가 되는 형식으로: 6자리→.KS, 크립토→-USD, 대문자."""
    t = (ticker or "").upper().strip()
    if not t:
        return ""
    if asset_class == "crypto" and not t.endswith("-USD"):
        return f"{t}-USD"
    if re.fullmatch(r"\d{6}", t):
        return f"{t}.KS"
    return t


def canonical_currency(ticker: str, name: str, asset_class: str) -> str:
    """통화 확정 — 파서의 currency 태그를 신뢰하지 않는다(반복 오태깅 이력).
    한국 상장·크립토(국내거래소 원화)·현금 → KRW, 그 외 해외 상장 → USD."""
    if asset_class in ("cash", "crypto") or is_kr_listed(ticker, name):
        return "KRW"
    return "USD"


def canonicalize_holdings(raw: list[dict]) -> tuple[list[dict], list[dict]]:
    """저장 전 단일 게이트. 반환: (정규화된 보유, 탈락 행 [{'name','reason'}]).

    탈락 사유는 UI 가 사용자에게 그대로 보여준다 — '조용히 사라진 종목' 금지."""
    clean: list[dict] = []
    dropped: list[dict] = []
    for row in raw or []:
        h = dict(row)
        name = str(_first(h, "name", "asset_name", "display_name") or "").strip()
        if not name:
            dropped.append({"name": "(이름 없음)", "reason": "종목명을 읽지 못함"})
            continue
        eval_amt = _num(_first(h, "eval_amount", "평가금액", "market_value"))
        qty = _num(_first(h, "shares", "보유수량", "quantity", "qty"))
        avg = _num(_first(h, "avg_price", "평균단가", "매입단가"))
        buy_amt = _num(_first(h, "purchase_amount", "매입금액"))
        if not ((eval_amt and eval_amt > 0) or (qty and qty > 0 and ((avg and avg > 0) or (buy_amt and buy_amt > 0)))):
            dropped.append({"name": name, "reason": "평가금액·수량을 읽지 못함 — 금액이 보이게 다시 캡처해 주세요"})
            continue
        tk_raw = str(_first(h, "ticker", "symbol", "code") or "").strip()
        ac = canonical_asset_class(h, tk_raw, name)
        tk = canonical_ticker(tk_raw, ac)
        h["name"] = name
        h["ticker"] = tk
        h["asset_class"] = ac
        h["currency"] = canonical_currency(tk, name, ac)
        clean.append(h)
    return clean, dropped
