"""지시서 2장 — 토스 시세 커버리지 검증.

SIM 이 보여주는 전 자산을 토스 시세 API로 호출해 O/X·지연 표를 출력한다.
결과로 '전부 토스 일원화' vs '토스 우선 + yfinance 폴백' 을 판단한다.

실행: .venv/bin/python verify_toss_coverage.py
"""
import sys
from datetime import datetime, timezone

import yaml
from dotenv import load_dotenv

load_dotenv()
from data.providers.toss_provider import TossClient  # noqa: E402


# ── yfinance 심볼 → 토스 심볼 매핑 ──────────────────────────────────────────
def to_toss_symbol(yf_ticker: str) -> str | None:
    """토스 /prices 로 조회 가능한 심볼로 변환. 불가하면 None."""
    t = yf_ticker
    if t.endswith(".KS"):
        return t[:-3]                 # 005930.KS -> 005930, 0053L0.KS -> 0053L0
    if t.endswith("=F"):
        return None                   # 선물 — 토스 미지원
    if t.endswith("=X"):
        return None                   # 환율 — 별도 endpoint
    if t.endswith("-USD"):
        return None                   # 크립토 — 토스 범위 밖
    if t.startswith("^") or t == "DX-Y.NYB":
        return None                   # 지수 — 토스 미지원
    return t                          # 미국 티커 그대로


def build_universe(cfg: dict) -> list[dict]:
    """(group, label, yf, kind, toss) 행 목록. kind: price|fx|none."""
    rows: list[dict] = []

    def add_price(group, label, yf):
        rows.append({"group": group, "label": label, "yf": yf,
                     "kind": "price", "toss": to_toss_symbol(yf)})

    for e in cfg.get("my_etfs", []):
        add_price("국내 ETF(보유)", e["name"], e["ticker"])
    for e in cfg.get("benchmark_etfs", []):
        add_price("미국 ETF(벤치마크)", e["name"], e["ticker"])
    # 지시서 2-1 에 명시됐으나 yaml 에 없는 KWEB 추가
    rows.append({"group": "미국 ETF(벤치마크)", "label": "중국인터넷 ETF (KWEB)",
                 "yf": "KWEB", "kind": "price", "toss": "KWEB"})
    for s in cfg.get("us_stocks", []):
        add_price("미국 개별주", s["name"], s["ticker"])
    for s in cfg.get("kr_stocks", []):
        add_price("국내 개별주", s["name"], s["ticker"])
    for name, tk in cfg.get("commodities", {}).items():
        rows.append({"group": "원자재(선물)", "label": name, "yf": tk,
                     "kind": "price", "toss": to_toss_symbol(tk)})
    fx_map = {  # yaml key -> (base, quote) for toss exchange-rate
        "usd_krw": ("USD", "KRW"), "jpy_krw": ("JPY", "KRW"),
        "eur_krw": ("EUR", "KRW"), "usd_jpy": ("USD", "JPY"), "dxy": None,
    }
    for key, node in cfg.get("fx", {}).items():
        rows.append({"group": "환율", "label": node["ticker"], "yf": node["ticker"],
                     "kind": "fx", "fx": fx_map.get(key)})
    return rows


def fmt_delay(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts)
        age = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
    except Exception:
        return ts
    if age < 120:
        return "실시간(<2분)"
    if age < 3600:
        return f"{int(age // 60)}분 전"
    if age < 86400:
        return f"{age / 3600:.1f}시간 전"
    return f"{age / 86400:.1f}일 전"


def main():
    with open("config/assets.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    rows = build_universe(cfg)

    client = TossClient()

    # 가격 심볼 일괄 조회(배치)
    price_syms = sorted({r["toss"] for r in rows if r["kind"] == "price" and r["toss"]})
    print(f"토스 /prices 배치 조회: {len(price_syms)} 심볼 …")
    prices = client.get_prices(price_syms)

    # 결과 채우기
    for r in rows:
        if r["kind"] == "price":
            if not r["toss"]:
                r["ok"], r["note"], r["delay"] = False, "토스 심볼 없음", "—"
            else:
                p = prices.get(r["toss"])
                r["ok"] = p is not None
                r["delay"] = fmt_delay(p["timestamp"]) if p else "—"
                r["note"] = f"{p['lastPrice']} {p['currency']}" if p else "응답 없음"
        else:  # fx
            if not r.get("fx"):
                r["ok"], r["note"], r["delay"] = False, "토스 환율 미지원(지수/비KRW·USD)", "—"
            else:
                base, quote = r["fx"]
                fx = client.get_exchange_rate(base, quote)
                r["ok"] = fx is not None
                r["delay"] = fmt_delay(fx["timestamp"]) if fx else "—"
                r["note"] = f"{fx['rate']} ({base}/{quote})" if fx else f"{base}/{quote} 미지원"

    # ── 표 출력 ────────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"{'심볼(yf)':<14}{'토스':<10}{'O/X':<5}{'지연':<14}비고")
    print("=" * 78)
    order = ["국내 개별주", "국내 ETF(보유)", "미국 개별주", "미국 ETF(벤치마크)",
             "원자재(선물)", "환율"]
    totals = {}
    for g in order:
        grp = [r for r in rows if r["group"] == g]
        if not grp:
            continue
        ok = sum(r["ok"] for r in grp)
        totals[g] = (ok, len(grp))
        print(f"\n── {g}  ({ok}/{len(grp)}) " + "─" * (60 - len(g)))
        for r in grp:
            mark = "O" if r["ok"] else "X"
            print(f"{r['yf']:<14}{str(r.get('toss') or '-'):<10}{mark:<5}{r['delay']:<14}{r['note']}")

    # ── 요약·분기 ──────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("자산군별 커버리지 요약")
    print("=" * 78)
    tot_ok = tot_all = 0
    for g in order:
        if g in totals:
            ok, n = totals[g]
            tot_ok += ok
            tot_all += n
            print(f"  {g:<20} {ok}/{n}")
    print(f"  {'─'*20} {'─'*8}")
    print(f"  {'전체':<20} {tot_ok}/{tot_all}")
    if client.last_rate_headers:
        print(f"\n  Rate limit 헤더(마지막 응답): {client.last_rate_headers}")
    print("\n  ※ 지연 등급은 호출 시점 기준. 장 마감/주말이면 timestamp 가 직전 종가라 오래된 값으로 보일 수 있음.")


if __name__ == "__main__":
    sys.exit(main())
