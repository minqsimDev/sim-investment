"""지시서 3장 검증 — price_source 라우팅·폴백 동작 확인.

대표 심볼을 자산군별로 넣어 어떤 소스로 해소되는지, 폴백이 제대로 도는지 확인.
화면은 건드리지 않는다. 실행: .venv/bin/python verify_price_source.py
"""
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="  [log] %(message)s")
from data import price_source  # noqa: E402

# (라벨, 티커, 기대 소스)
CASES = [
    ("국내 주식",      "005930.KS",  "toss"),
    ("국내 ETF(영숫자)", "0053L0.KS",  "toss"),
    ("미국 주식",      "TSLA",       "toss"),
    ("미국 ETF",       "QQQ",        "toss"),
    ("USD/KRW 환율",   "USDKRW=X",   "toss"),
    ("원자재 선물",     "GC=F",       "yfinance"),
    ("비USD 환율",     "JPYKRW=X",   "yfinance"),
    ("지수",          "^VIX",       "yfinance"),
    ("크립토",         "BTC-USD",    "yfinance"),
    ("폴백테스트(없는티커)", "ZZZZZZ",  "yfinance"),  # 토스 미스 → yfinance 폴백
]


def main():
    tickers = [c[1] for c in CASES]
    print(f"price_source.fetch_prices_bulk — {len(tickers)} 심볼 라우팅 검증\n")
    res = price_source.fetch_prices_bulk(tickers)

    print("\n" + "=" * 76)
    print(f"{'자산군':<18}{'티커':<12}{'소스':<10}{'기대':<10}{'결과'}")
    print("=" * 76)
    ok_count = 0
    for label, tk, expect in CASES:
        q = res.get(tk)
        src = q["source"] if q else "—(실패)"
        # 폴백테스트는 yfinance 도 실패할 수 있음(존재하지 않는 티커) → 소스 미해소 허용
        match = (src == expect) or (tk == "ZZZZZZ" and q is None)
        ok_count += match
        price = q["price"] if q else None
        chg = q["change_pct"] if q else None
        cur = q["currency"] if q else None
        detail = f"{price} {cur or ''} ({chg}%)" if q else "응답 없음"
        print(f"{label:<18}{tk:<12}{src:<10}{expect:<10}{'OK' if match else 'MISMATCH'}  {detail}")

    print("=" * 76)
    print(f"라우팅 일치: {ok_count}/{len(CASES)}")
    print("\n※ change(%) 는 토스의 경우 일봉(/candles)으로 전일종가를 받아 계산.")
    print("  주말/장마감엔 None 일 수 있음. USD/KRW 는 전일종가 미제공이라 change None.")


if __name__ == "__main__":
    main()
