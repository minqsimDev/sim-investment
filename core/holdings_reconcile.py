"""보유 종목 금액 자릿수(소수점 유실) 결정론적 보정.

스크린샷 비전 파싱은 "$27,543.519" 를 27543519 처럼 **소수점을 잃어** 금액을 10ⁿ배로
부풀리는 일이 잦다(프롬프트로 막아도 모델이 가끔 놓침). 이 모듈은 저장 직전에 한 번
교차검증해 자릿수 오류를 바로잡는다 — 라이브 시세 의존 없이(화면 내부 정보로) 결정론적.

신뢰 순위: 보유수량(정수) > 주당가격(소수점 잘 안 틀림) > 손익률(%) ≫ 평가/매입금액.
앵커가 있으면 eval≈shares×current_price, purchase≈shares×avg_price 로 ×10ⁿ 오류를 잡고,
없으면 평가/매입의 손익률(plp) 일관성만 맞춘다. price_fn 이 주어지면(재처리/복구용)
주당가가 비어도 라이브 시세를 앵커로 쓴다.
"""
from __future__ import annotations

import math


def _num(v):
    """숫자형으로 안전 변환. 쉼표·공백·통화기호 섞인 문자열도 허용. 실패 시 None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).replace(",", "").replace("₩", "").replace("$", "").strip()
        return float(s) if s not in ("", "-", "null", "None") else None
    except (TypeError, ValueError):
        return None


def _pow10_factor(value: float, anchor: float, tol: float = 0.25):
    """value 가 anchor 의 ~10ⁿ배(n≠0)면 (10ⁿ, 나눈 뒤 잔차). 아니면 (1, inf).
    잔차 = |value/10ⁿ / anchor − 1| — 작을수록 깨끗한 자릿수 오류."""
    if not value or not anchor or value <= 0 or anchor <= 0:
        return 1.0, float("inf")
    n = round(math.log10(value / anchor))
    if n == 0:
        return 1.0, float("inf")
    k = 10.0 ** n
    return k, abs((value / k) / anchor - 1)


def _fix(value, anchor, tol: float = 0.25):
    """value 가 anchor 대비 깨끗한 10ⁿ배면 ÷10ⁿ 보정값 반환(+True). 아니면 (value, False)."""
    v = _num(value)
    a = _num(anchor)
    if v is None or a is None:
        return value, False
    k, resid = _pow10_factor(v, a, tol)
    if k != 1.0 and resid <= tol:
        return v / k, True
    return value, False


def reconcile_holding(h: dict, price_fn=None, fx: float | None = None) -> dict:
    """보유 1건의 금액 자릿수 보정(제자리 수정 후 반환).

    price_fn(ticker, asset_class) -> 주당 현재가(네이티브 통화: 미국주식·USD크립토=USD, 국내=KRW)
      또는 None. 주어지면 주당가가 비어도 앵커로 사용. fx = USD/KRW(네이티브→화면통화 비교용).
    """
    s = _num(h.get("shares") or h.get("보유수량"))
    cp = _num(h.get("current_price") or h.get("현재가"))
    ap = _num(h.get("avg_price") or h.get("평균단가"))
    plp = _num(h.get("profit_loss_pct") or h.get("수익률"))

    # 앵커 통화 정렬: 화면 금액이 USD인지 KRW인지 불확실하므로, 주당가(네이티브)에 fx 곱한
    # KRW 환산도 함께 후보로 둔다. price_fn 으로 라이브 시세를 앵커로 끌어올 수도 있다.
    if cp is None and price_fn is not None:
        try:
            cp = _num(price_fn(h.get("ticker"), h.get("asset_class")))
        except Exception:
            cp = None

    def _anchor_candidates(per_share):
        if not (s and per_share):
            return []
        native = s * per_share
        out = [native]
        if fx:
            out.append(native * fx)   # 화면이 원화 표기였을 가능성
        return out

    def _best_fix(value, per_share):
        best = (value, False, float("inf"))
        for anc in _anchor_candidates(per_share):
            nv, fixed = _fix(value, anc)
            if fixed:
                _, resid = _pow10_factor(_num(value), anc)
                if resid < best[2]:
                    best = (nv, True, resid)
        return best[0], best[1]

    fixed_any = False
    # 1) 평가금액 ↔ 수량×현재가
    new_ev, f1 = _best_fix(h.get("eval_amount") or h.get("평가금액"), cp)
    if f1:
        h["eval_amount"] = new_ev
        h["평가금액"] = new_ev
        fixed_any = True
    # 2) 매입금액 ↔ 수량×평균단가
    new_pa, f2 = _best_fix(h.get("purchase_amount") or h.get("매입금액"), ap)
    if f2:
        h["purchase_amount"] = new_pa
        h["매입금액"] = new_pa
        fixed_any = True

    # 3) 한쪽만 보정됐으면 손익률(plp)로 나머지를 맞춰 일관성 복구(plp 는 비율이라 자릿수 안전).
    ev = _num(h.get("eval_amount"))
    pa = _num(h.get("purchase_amount"))
    if plp is not None and (f1 ^ f2):
        ratio = 1 + plp / 100.0
        if f1 and ev is not None and ratio > 0.01:   # eval 보정됨 → purchase 재계산
            pa = ev / ratio
            h["purchase_amount"] = pa
            h["매입금액"] = pa
        elif f2 and pa is not None:                   # purchase 보정됨 → eval 재계산
            ev = pa * ratio
            h["eval_amount"] = ev
            h["평가금액"] = ev

    # 4) 평가손익 = 평가 − 매입 으로 동기화(둘 다 있을 때)
    if fixed_any and ev is not None and pa is not None:
        h["profit_loss"] = ev - pa
        h["평가손익"] = ev - pa

    return h


def reconcile_holdings(holdings: list[dict], price_fn=None, fx: float | None = None) -> list[dict]:
    """보유 리스트 전체의 금액 자릿수 보정. 원본을 제자리 수정하고 같은 리스트를 반환."""
    for h in holdings:
        if isinstance(h, dict):
            reconcile_holding(h, price_fn=price_fn, fx=fx)
    return holdings
