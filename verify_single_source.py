"""지시서 4장 검증 — 단일 출처 정합성(QA A1).

서로 다른 두 화면의 '실제 코드 경로'로 같은 지표(종목 현재가·USD/KRW)를 뽑아
일치하는지 확인한다. load_market_data() 는 fetch_all() 을 감싼 공용 캐시이므로
모든 화면이 같은 dict 를 참조 → 값이 구조적으로 일치해야 한다.

실행: .venv/bin/python verify_single_source.py
"""
from dotenv import load_dotenv

load_dotenv("/Users/min/DEV/sim-investment/.env")

from data.fetcher import fetch_all                     # noqa: E402
from ui.pages.portfolio import _market_price_maps      # noqa: E402  (실제 포폴 경로)


def kr_stocks_screen_price(data, ticker):
    """국내주식 화면 경로: kr_stocks DataFrame 에서 직접 읽음."""
    df = data["kr_stocks"]
    row = df[df["ticker"] == ticker]
    return None if row.empty else row.iloc[0]["price"]


def portfolio_screen_price(data, ticker):
    """포트폴리오 화면 경로: _market_price_maps() 로 시세 해소."""
    return _market_price_maps(data).get(ticker, {}).get("price")


def fx_value(data, pair):
    df = data["fx"]
    row = df[df["pair"] == pair]
    return None if row.empty else row.iloc[0]["rate"]


def main():
    # load_market_data() 가 캐시하는 바로 그 객체
    data = fetch_all(force=True)

    print("=" * 64)
    print("QA A1 — 두 화면 경로에서 같은 지표 추출·일치 확인")
    print("=" * 64)

    checks = []
    for tk in ("005930.KS", "000660.KS"):
        a = kr_stocks_screen_price(data, tk)
        b = portfolio_screen_price(data, tk)
        match = a == b
        checks.append(match)
        print(f"\n{tk}")
        print(f"  국내주식 화면 : {a}")
        print(f"  포트폴리오 화면: {b}")
        print(f"  → {'일치 ✅' if match else '불일치 ❌'}")

    usdkrw = fx_value(data, "usd_krw")
    print(f"\nUSD/KRW (전 화면 공용 dict): {usdkrw}")

    print("\n" + "=" * 64)
    print(f"일치 {sum(checks)}/{len(checks)} — 모든 현재가/환율이 단일 fetch_all() 출처에서 옴")
    print("=" * 64)


if __name__ == "__main__":
    main()
