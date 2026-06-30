#!/usr/bin/env python3
"""프로덕션 계정의 보유 금액 자릿수(소수점 유실) 1회 복구.

배경: 스크린샷 비전 파싱이 '$27,543.519'를 27543519로 소수점을 놓쳐 금액을 ×10ⁿ
부풀려 저장하던 버그(PR #73에서 파서 근본 수정). 이미 저장된 기존 데이터는 자동 복구되지
않으므로 이 스크립트로 한 번 정리한다. core.holdings_reconcile + 라이브 시세 앵커 사용.

안전장치:
- 기본은 **dry-run**(미저장). 실제 반영은 --apply.
- --apply 시 파일을 먼저 백업(<파일>.bak.<timestamp>).
- 정상값·정상 KRW 보유는 건드리지 않음(idempotent — 두 번 돌려도 동일).
- core.accounts._FILE/_locked/_load/_save 를 그대로 재사용(경로·잠금·원자적 저장 일관).

실행(프로덕션, 컨테이너 안에서 — HOME=/data 가 계정 파일 경로를 잡음):
    docker compose -f deploy/docker-compose.yml exec app \
        python scripts/repair_decimal_scales.py            # dry-run(미리보기)
    docker compose -f deploy/docker-compose.yml exec app \
        python scripts/repair_decimal_scales.py --apply    # 실제 복구
옵션: --user <id> (특정 계정만)
"""
import argparse
import copy
import shutil
import sys
import time
from pathlib import Path

# 프로젝트 루트를 import 경로에 추가(스크립트 직접 실행 대비)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import accounts as acc          # noqa: E402
from core.holdings_reconcile import reconcile_holdings  # noqa: E402


def _make_price_fn():
    """ticker(+asset_class) → 주당 현재가(네이티브 통화). 실패 시 None.
    미국주식·USD크립토=USD, 국내주식=KRW. 자릿수 판정 앵커로만 쓰임."""
    from data.session import cached_download

    cache: dict = {}

    def price_fn(ticker, asset_class):
        if not ticker:
            return None
        t = str(ticker).upper()
        ac = (asset_class or "").lower()
        if ac == "crypto" or t in ("BTC", "ETH") or t.endswith("-USD"):
            t = t if t.endswith("-USD") else f"{t}-USD"
        # 국내주식(.KS/.KQ)·미국주식/ETF 는 티커 그대로
        if t in cache:
            return cache[t]
        try:
            raw = cached_download(t, period="5d", interval="1d", progress=False, auto_adjust=True)
            c = raw["Close"]
            if hasattr(c, "columns"):
                c = c.iloc[:, 0]
            cache[t] = float(c.dropna().iloc[-1])
        except Exception:
            cache[t] = None
        return cache[t]

    return price_fn


def _fmt(v):
    try:
        return f"{float(v):,.1f}"
    except (TypeError, ValueError):
        return str(v)


def main() -> int:
    ap = argparse.ArgumentParser(description="보유 금액 자릿수 유실 1회 복구")
    ap.add_argument("--apply", action="store_true", help="실제 저장(미지정 시 dry-run)")
    ap.add_argument("--user", default=None, help="특정 계정만 처리")
    args = ap.parse_args()

    try:
        from data.fx import usdkrw, FX_FALLBACK
        fx = usdkrw() or FX_FALLBACK
    except Exception:
        fx = 1450.0

    price_fn = _make_price_fn()
    print(f"계정 파일: {acc._FILE}")
    print(f"USD/KRW 앵커 환율: {fx:,.0f}")
    print(f"모드: {'APPLY(저장)' if args.apply else 'DRY-RUN(미리보기)'}\n")

    data = acc._load()
    accounts = data.get("accounts", {})
    if not accounts:
        print("계정이 없습니다.")
        return 0

    total_fixed = 0
    for uname, account in accounts.items():
        if args.user and uname != args.user:
            continue
        for pf in account.get("portfolios", []) or []:
            holdings = pf.get("holdings") or []
            if not holdings:
                continue
            before = copy.deepcopy(holdings)
            reconcile_holdings(holdings, price_fn=price_fn, fx=fx)
            diffs = [(b, a) for b, a in zip(before, holdings)
                     if b.get("eval_amount") != a.get("eval_amount")
                     or b.get("purchase_amount") != a.get("purchase_amount")]
            if diffs:
                print(f"[{uname}] '{pf.get('name', '?')}' — {len(diffs)}건 보정")
                for b, a in diffs:
                    print(f"   {a.get('name', '?'):8} 평가 {_fmt(b.get('eval_amount')):>14} → {_fmt(a.get('eval_amount')):>12}"
                          f" | 매입 {_fmt(b.get('purchase_amount')):>14} → {_fmt(a.get('purchase_amount')):>12}")
                total_fixed += len(diffs)

    print(f"\n총 {total_fixed}건 보정 대상.")
    if total_fixed == 0:
        print("복구할 데이터가 없습니다(이미 정상).")
        return 0

    if not args.apply:
        print("\nDRY-RUN — 저장하지 않았습니다. 실제 반영하려면 --apply 를 붙여 다시 실행하세요.")
        return 0

    # 백업 후 잠금 안에서 재로드→보정→저장(원자적). dry-run 이후 다른 쓰기가 있었을 수 있어 재로드.
    backup = acc._FILE.with_suffix(f".json.bak.{int(time.time())}")
    shutil.copy2(acc._FILE, backup)
    print(f"\n백업: {backup}")
    with acc._locked():
        data = acc._load()
        applied = 0
        for uname, account in data.get("accounts", {}).items():
            if args.user and uname != args.user:
                continue
            for pf in account.get("portfolios", []) or []:
                h = pf.get("holdings") or []
                if not h:
                    continue
                before = copy.deepcopy(h)
                reconcile_holdings(h, price_fn=price_fn, fx=fx)
                applied += sum(1 for b, a in zip(before, h)
                               if b.get("eval_amount") != a.get("eval_amount")
                               or b.get("purchase_amount") != a.get("purchase_amount"))
        acc._save(data)
    print(f"저장 완료 — {applied}건 보정 적용.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
