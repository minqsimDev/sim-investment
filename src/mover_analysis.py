"""
Major Movers & Possible Drivers analysis module.
Detects significant price movements and infers possible causes in Korean.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


# ── Thresholds (per-asset-class, validated against historical realized vol) ──
#
# Calibration basis:
#   Broad ETFs (SPY/QQQ/GLD): daily 1σ ≈ 1.0–1.4%  → 1.5% ≈ 1.1–1.5σ  (keep)
#   Sector ETFs (SOXX/AI/China): daily 1σ ≈ 1.75–2.2% → 2.5% ≈ 1.2σ
#   High-vol stocks (NVDA/AMD/TSLA/PLTR): daily 1σ ≈ 2.8–4.7% → 5.0% ≈ 1.3σ
#   Gold: daily 1σ ≈ 1.0%                             → 1.25% ≈ 1.25σ
#   Silver: daily 1σ ≈ 1.7%                           → 2.5% ≈ 1.5σ
#   Copper: daily 1σ ≈ 1.4%                           → 2.0% ≈ 1.4σ
#   WTI/Brent: daily 1σ ≈ 2.2–3.1%                   → 3.0% ≈ 1.1σ
#   Natural gas: daily 1σ ≈ 4.4–6.3%                  → 5.0% ≈ 0.9–1.1σ
#   USD/KRW: daily 1σ ≈ 0.44–0.50%                   → 0.5% ≈ 1.0–1.1σ (keep)
#   JPY crosses: daily 1σ ≈ 0.6–0.75%                → 0.7%

_THRESHOLDS = {
    "etf_broad":       1.5,   # SPY, QQQ, GLD, SLV-type
    "etf_sector":      2.5,   # SOXX, AI-tech, China, covered-call
    "benchmark":       1.5,   # benchmark catch-all
    "us_stock":        3.0,   # default individual stock
    "us_stock_hv":     5.0,   # high-vol names: NVDA, AMD, TSLA, PLTR, MU, TSM
    "commodity_gold":  1.25,
    "commodity_silver":2.5,
    "commodity_copper":2.0,
    "commodity_oil":   3.0,
    "commodity_gas":   5.0,
    "commodity":       1.5,   # fallback
    "fx_jpy":          0.7,   # JPY crosses more volatile than KRW
    "fx":              0.5,   # USD/KRW, DXY, EUR/KRW
    # Crypto: daily 1σ — BTC ~2-3%, ETH ~3-5%, SOL/others ~5-7%
    "crypto_btc":      3.0,
    "crypto_eth":      4.0,
    "crypto_hv":       5.0,   # SOL and other high-beta coins
    "crypto":          3.0,   # fallback
}

# Individual stocks with daily 1σ ≥ 3% (annualized vol ≥ 47%)
_HIGH_VOL_STOCKS = {"NVDA", "AMD", "AVGO", "TSLA", "PLTR", "MU"}

# Sector ETFs that require a higher threshold than broad ETFs
_SECTOR_ETFS = {"SOXX", "SMH", "SOXS", "KWEB", "FXI", "CQQQ", "TQQQ", "SOXL"}

# Weekly / monthly flags — differentiated by asset class
# Basis: weekly σ = daily σ × √5; monthly σ = daily σ × √21
#   Broad ETFs: weekly σ ≈ 2.2%  → 5.0% ≈ 2.3σ  (keep)
#   High-vol stocks: weekly σ ≈ 8–10% → 10% ≈ 1.0–1.3σ
#   FX: weekly σ ≈ 1.1–1.7%    → 2.5% ≈ 1.5–2.3σ  (was 5.0% — too loose)
_WEEKLY_FLAG_DEFAULT    = 5.0
_WEEKLY_FLAG_HV_STOCK   = 10.0
_WEEKLY_FLAG_FX         = 2.5
_WEEKLY_FLAG_CRYPTO_BTC = 10.0  # BTC weekly 1σ ≈ 7-8% (daily × √7)
_WEEKLY_FLAG_CRYPTO_HV  = 20.0  # ETH/SOL weekly 1σ ≈ 10-14%

_MONTHLY_FLAG_DEFAULT    = 10.0
_MONTHLY_FLAG_HV_STOCK   = 20.0
_MONTHLY_FLAG_FX         = 4.0   # 5% KRW monthly = genuine macro event
_MONTHLY_FLAG_CRYPTO_BTC = 20.0  # BTC monthly 1σ ≈ 15-20%
_MONTHLY_FLAG_CRYPTO_HV  = 40.0  # ETH/SOL monthly 1σ ≈ 25-40%

# Vol multiplier: 2.0σ is the institutional "notable deviation" standard.
# 1.5σ (old) fires ~13% of days per instrument — alert fatigue.
# 2.0σ fires ~4.6% of days (~12×/year) — meaningful signal.
_VOL_MULT = 2.0


# ── Threshold resolvers ───────────────────────────────────────────────────────

def _resolve_threshold(ticker: str, name: str, asset_cat: str) -> float:
    upper = ticker.upper()
    if asset_cat == "us_stock":
        return _THRESHOLDS["us_stock_hv"] if upper in _HIGH_VOL_STOCKS else _THRESHOLDS["us_stock"]
    if asset_cat in ("my_etf", "etf"):
        return _THRESHOLDS["etf_sector"] if upper in _SECTOR_ETFS else _THRESHOLDS["etf_broad"]
    if asset_cat == "benchmark":
        return _THRESHOLDS["etf_sector"] if upper in _SECTOR_ETFS else _THRESHOLDS["benchmark"]
    if asset_cat == "commodity":
        n = name.lower()
        if any(k in n for k in ("gold", "금")):
            return _THRESHOLDS["commodity_gold"]
        if any(k in n for k in ("silver", "은")):
            return _THRESHOLDS["commodity_silver"]
        if any(k in n for k in ("copper", "구리")):
            return _THRESHOLDS["commodity_copper"]
        if any(k in n for k in ("gas", "가스")):
            return _THRESHOLDS["commodity_gas"]
        if any(k in n for k in ("crude", "oil", "원유", "브렌트", "wti", "brent")):
            return _THRESHOLDS["commodity_oil"]
        return _THRESHOLDS["commodity"]
    if asset_cat == "fx":
        return _THRESHOLDS["fx_jpy"] if "JPY" in upper or "jpy" in ticker.lower() else _THRESHOLDS["fx"]
    if asset_cat == "crypto":
        if "BTC" in upper:
            return _THRESHOLDS["crypto_btc"]
        if "ETH" in upper:
            return _THRESHOLDS["crypto_eth"]
        return _THRESHOLDS["crypto_hv"]
    return 1.5


def _resolve_flags(ticker: str, asset_cat: str) -> tuple[float, float]:
    """Returns (weekly_flag, monthly_flag) for the given asset."""
    upper = ticker.upper()
    if asset_cat == "fx":
        return _WEEKLY_FLAG_FX, _MONTHLY_FLAG_FX
    if asset_cat == "us_stock" and upper in _HIGH_VOL_STOCKS:
        return _WEEKLY_FLAG_HV_STOCK, _MONTHLY_FLAG_HV_STOCK
    if asset_cat == "crypto":
        if "BTC" in upper:
            return _WEEKLY_FLAG_CRYPTO_BTC, _MONTHLY_FLAG_CRYPTO_BTC
        return _WEEKLY_FLAG_CRYPTO_HV, _MONTHLY_FLAG_CRYPTO_HV
    return _WEEKLY_FLAG_DEFAULT, _MONTHLY_FLAG_DEFAULT


# ── Category labels (Korean) ──────────────────────────────────────────────────

_CATEGORY_LABELS = {
    "my_etf":    "관심 ETF",   # 워치리스트(실제 보유 아님) — '직접 보유'는 세션 실보유로 판정
    "benchmark": "벤치마크",
    "us_stock":  "미국 주식",
    "commodity": "원자재",
    "fx":        "FX",
    "crypto":    "암호화폐",
}

_COMM_NAME_KOR = {
    "gold":        "금",
    "silver":      "은",
    "copper":      "구리",
    "wti_crude":   "WTI 원유",
    "brent_crude": "브렌트",
    "natural_gas": "천연가스",
}


# ── Driver inference rules ────────────────────────────────────────────────────

def _get_macro_value(data: dict, key: str) -> float | None:
    mac = data.get("macro")
    if mac is None or mac.empty:
        return None
    r = mac[mac["key"] == key]
    if r.empty:
        return None
    v = r.iloc[0]["value"]
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _get_chg(data: dict, category: str, identifier: str) -> float | None:
    """Get change_pct for a given identifier across data categories."""
    if category == "benchmarks":
        df = data.get("benchmarks", pd.DataFrame())
        if not df.empty and "ticker" in df.columns:
            r = df[df["ticker"] == identifier]
            if not r.empty:
                try:
                    return float(r.iloc[0]["change_pct"])
                except (TypeError, ValueError):
                    return None
    elif category == "commodities":
        df = data.get("commodities", pd.DataFrame())
        if not df.empty and "name" in df.columns:
            r = df[df["name"] == identifier]
            if not r.empty:
                try:
                    return float(r.iloc[0]["change_pct"])
                except (TypeError, ValueError):
                    return None
    elif category == "fx":
        df = data.get("fx", pd.DataFrame())
        if not df.empty and "pair" in df.columns:
            r = df[df["pair"] == identifier]
            if not r.empty:
                try:
                    return float(r.iloc[0]["change_pct"])
                except (TypeError, ValueError):
                    return None
    elif category == "us_stocks":
        df = data.get("us_stocks", pd.DataFrame())
        if not df.empty and "ticker" in df.columns:
            r = df[df["ticker"] == identifier]
            if not r.empty:
                try:
                    return float(r.iloc[0]["change_pct"])
                except (TypeError, ValueError):
                    return None
    return None


def _infer_driver(ticker: str, category: str, change_1d: float, data: dict) -> tuple[str, list[str]]:
    """
    Returns (possible_driver_korean, related_indicators).
    Uses hedged language per specification — never definitive.

    Threshold calibration notes:
    - us10y 4.8%: empirical break level for large-cap growth (was 4.5%, raised per 2025–26 regime)
    - us10y 4.0% for gold: nominal proxy for real yield < 0.5% (TIPS preferred but not in pipeline)
    - dxy_chg 0.5%: meaningful DXY day (was 0.3% — below DXY daily noise floor of 0.2–0.4%)
    - qqq_chg -1.0%: minimum equity decline for gold safe-haven narrative
    """
    ticker_upper = ticker.upper()
    qqq_chg  = _get_chg(data, "benchmarks", "QQQ")
    soxx_chg = _get_chg(data, "benchmarks", "SOXX")
    gold_chg = _get_chg(data, "commodities", "gold")
    slv_chg  = _get_chg(data, "commodities", "silver")
    cop_chg  = _get_chg(data, "commodities", "copper")
    oil_chg  = _get_chg(data, "commodities", "wti_crude")
    dxy_chg  = _get_chg(data, "fx", "dxy")
    krw_chg  = _get_chg(data, "fx", "usd_krw")
    us10y    = _get_macro_value(data, "us_10y")
    us2y     = _get_macro_value(data, "us_2y")

    def pos(v): return v is not None and v > 0
    def neg(v): return v is not None and v < 0

    # ── QQQ / 기술주 ────────────────────────────────────────────────────────
    if ticker_upper in ("QQQ", "TQQQ") or "나스닥" in ticker or "빅테크" in ticker or "테크" in ticker:
        if change_1d > 0:
            # 4.8% is the empirical regime boundary for growth stock pressure (2025–26)
            if (us10y is not None and us10y < 4.8) or (dxy_chg is not None and dxy_chg <= 0):
                return (
                    "금리 안정에 따른 기술주 위험선호 심리 회복 가능성",
                    ["US10Y", "DXY", "VIX"]
                )
            return (
                "위험선호 심리 개선 또는 실적 기대감 반영 가능성",
                ["US10Y", "DXY", "SPY"]
            )
        else:
            if us10y is not None and us10y > 4.8:
                return (
                    "금리 상승 압력이 성장주 밸류에이션에 부담을 줄 가능성",
                    ["US10Y", "US2Y", "DXY"]
                )
            # 2-year yield is a more sensitive Fed expectations proxy
            if us2y is not None and us2y > 4.5:
                return (
                    "연준 긴축 기대 반영, 성장주 밸류에이션 압박 가능성",
                    ["US2Y", "US10Y", "DXY"]
                )
            return (
                "위험회피 심리 또는 매크로 불확실성 반영 가능성",
                ["US10Y", "SPY", "VIX"]
            )

    # ── 반도체 ──────────────────────────────────────────────────────────────
    if ticker_upper in ("SOXX", "SMH", "NVDA", "AMD", "AVGO", "TSM", "MU") or \
       "반도체" in ticker or "AI테크" in ticker or "AI커버드" in ticker:
        if change_1d > 0:
            # Check whether rate environment supports the move
            rate_tailwind = us10y is not None and us10y < 4.8
            return (
                "반도체 업황 개선 기대 또는 AI 설비투자 관련 뉴스 반영 가능성"
                + ("  ·  금리 환경 우호적" if rate_tailwind else ""),
                ["SOXX", "NVDA", "QQQ", "US10Y"]
            )
        return (
            "반도체 수요 우려 또는 재고 조정 우려 반영 가능성"
            + ("  ·  KOSPI 반도체 동반 하락 모니터링 필요" if abs(change_1d) >= 3.0 else ""),
            ["SOXX", "QQQ", "US10Y", "US2Y"]
        )

    # ── 금 ──────────────────────────────────────────────────────────────────
    if ticker_upper in ("GLD", "GC=F", "IAU") or "금현물" in ticker or "금선물" in ticker or \
       ticker.lower() in ("gold",):
        if change_1d > 0:
            # Primary: real yield proxy (us10y < 4.0 → real yield likely low; TIPS preferred)
            # Secondary: dollar direction
            if (dxy_chg is not None and dxy_chg < 0) and (us10y is not None and us10y < 4.0):
                return (
                    "달러 약세 + 실질금리 하락 동시 작용, 금 선호 환경 가능성",
                    ["DXY", "US10Y", "VIX"]
                )
            if dxy_chg is not None and dxy_chg < 0:
                return (
                    "달러 약세에 따른 금 선호 가능성",
                    ["DXY", "US10Y"]
                )
            if us10y is not None and us10y < 4.0:
                return (
                    "실질금리 하락 기대에 따른 금 선호 가능성",
                    ["US10Y", "DXY"]
                )
            # Risk-off: equity decline ≥ 1% is the floor for safe-haven narrative
            if qqq_chg is not None and qqq_chg < -1.0:
                return (
                    "안전자산 수요 또는 위험회피 심리 반영 가능성  ·  VIX 확인 권장",
                    ["QQQ", "DXY", "US10Y", "VIX"]
                )
            # Gold rising with strong dollar / high rates → likely central bank/geopolitical demand
            return (
                "귀금속 전반 강세 또는 중앙은행 수요·지정학적 리스크 반영 가능성",
                ["DXY", "US10Y", "VIX"]
            )
        # Gold falling — could be dollar strength, rate rise, or margin-call deleveraging
        if dxy_chg is not None and dxy_chg > 0.5:
            return (
                "달러 강세에 따른 금 매도 압력 가능성",
                ["DXY", "US10Y"]
            )
        return (
            "실질금리 상승 또는 위험자산 마진콜 청산 가능성",
            ["DXY", "US10Y", "VIX"]
        )

    # ── 은 ──────────────────────────────────────────────────────────────────
    if ticker_upper in ("SLV", "SI=F") or "은선물" in ticker or ticker.lower() == "silver":
        if change_1d > 0:
            silver_outperforms = (
                slv_chg is not None and gold_chg is not None and slv_chg > gold_chg
            )
            # Copper rising together confirms industrial demand thesis
            copper_up = cop_chg is not None and cop_chg > 0
            if silver_outperforms and copper_up:
                return (
                    "귀금속 베타 확대 + 구리 동반 상승, 산업용 수요 기대 가능성",
                    ["GLD", "Copper", "DXY"]
                )
            if silver_outperforms:
                return (
                    "귀금속 베타 확대 가능성  ·  구리 방향 확인 필요",
                    ["GLD", "Copper", "DXY"]
                )
            return (
                "귀금속 전반 강세 반영 가능성",
                ["GLD", "DXY", "Copper"]
            )

    # ── 구리 ────────────────────────────────────────────────────────────────
    if ticker_upper in ("HG=F", "CPER") or "구리" in ticker or ticker.lower() == "copper":
        if change_1d > 0:
            return (
                "중국 수요 또는 글로벌 제조업 개선 기대 가능성  ·  EV·AI 인프라 공급 부족 요인도 병존",
                ["KWEB", "DXY", "글로벌 PMI"]
            )
        return (
            "중국 수요 둔화 또는 글로벌 제조업 위축 우려 반영 가능성",
            ["KWEB", "DXY"]
        )

    # ── USD/KRW ──────────────────────────────────────────────────────────────
    if ticker_upper in ("USDKRW=X", "USD/KRW") or "usd_krw" in ticker.lower() or \
       ticker == "usd_krw":
        if change_1d > 0:
            # 0.5%는 DXY 의미있는 강세 임계값 (0.3%는 일상 노이즈 수준)
            if dxy_chg is not None and dxy_chg > 0.5:
                return (
                    "달러 강세에 따른 원화 약세 압력 가능성  ·  비헤지 ETF 환손실 모니터링 필요",
                    ["DXY", "US10Y", "비헤지 ETF"]
                )
            if dxy_chg is not None and dxy_chg <= 0:
                # DXY 보합인데 원화 약세 → 국내 자본유출 또는 EM 리스크
                return (
                    "달러 인덱스 무관한 원화 약세  ·  국내 자본유출 또는 EM 리스크오프 압력 가능성",
                    ["DXY", "비헤지 ETF", "경상수지"]
                )
            return (
                "원화 약세  ·  해외 ETF 환노출 영향 점검 필요",
                ["DXY", "비헤지 ETF"]
            )
        return (
            "원화 강세  ·  비헤지 해외 ETF 환이익 가능성",
            ["DXY", "비헤지 ETF"]
        )

    # ── DXY ─────────────────────────────────────────────────────────────────
    if ticker_upper in ("DX-Y.NYB", "DXY") or ticker == "dxy":
        if change_1d > 0:
            return (
                "달러 강세  ·  원자재·이머징 자산 전반에 부담이 될 가능성",
                ["US10Y", "USD/KRW", "GLD"]
            )
        return (
            "달러 약세  ·  원자재·이머징 자산에 우호적 환경 조성 가능성",
            ["US10Y", "GLD", "Copper"]
        )

    # ── 원유 ────────────────────────────────────────────────────────────────
    if ticker_upper in ("CL=F", "BZ=F") or "원유" in ticker or "브렌트" in ticker or \
       "crude" in ticker.lower() or "brent" in ticker.lower():
        if change_1d > 0:
            return (
                "OPEC 공급 조절 또는 글로벌 수요 개선 기대 가능성  ·  에너지 수입 비용 증가로 원화 약세 압력 가능성",
                ["DXY", "USD/KRW", "글로벌 PMI"]
            )
        return (
            "수요 둔화 우려 또는 공급 확대 반영 가능성",
            ["DXY", "Copper"]
        )

    # ── 중국 관련 ────────────────────────────────────────────────────────────
    if ticker_upper in ("KWEB", "FXI", "CQQQ") or "차이나" in ticker or "중국" in ticker:
        if change_1d > 0:
            return (
                "중국 기술주 정책 지원 또는 섹터 모멘텀 반영 가능성",
                ["KWEB", "DXY", "Copper"]
            )
        return (
            "중국 규제 리스크 또는 경기 우려 반영 가능성",
            ["KWEB", "Copper", "DXY"]
        )

    # ── SPY / 대형주 ─────────────────────────────────────────────────────────
    if ticker_upper in ("SPY", "IVV", "VOO") or "S&P500" in ticker or "S&P 500" in ticker:
        if change_1d > 0:
            return (
                "광범위한 위험선호 심리 개선 또는 경제지표 호조 반영 가능성",
                ["QQQ", "US10Y", "DXY"]
            )
        return (
            "광범위한 위험회피 또는 매크로 불확실성 반영 가능성",
            ["VIX", "US10Y", "DXY"]
        )

    # ── FX 일반 ─────────────────────────────────────────────────────────────
    if category == "fx":
        if change_1d > 0:
            return (
                "달러 강세 또는 해당 통화 약세 압력 반영 가능성",
                ["DXY", "US10Y"]
            )
        return (
            "달러 약세 또는 해당 통화 강세 반영 가능성",
            ["DXY", "US10Y"]
        )

    # ── 비트코인 ─────────────────────────────────────────────────────────────────
    if "BTC" in ticker_upper or "비트코인" in ticker:
        if change_1d > 0:
            if dxy_chg is not None and dxy_chg < 0 and qqq_chg is not None and qqq_chg > 0:
                return (
                    "달러 약세 + 위험선호 동반 상승, 크립토 친화적 환경 가능성",
                    ["DXY", "QQQ", "US10Y"]
                )
            if qqq_chg is not None and qqq_chg > 0:
                return (
                    "위험선호 심리 개선에 따른 크립토 동반 상승 가능성",
                    ["QQQ", "DXY", "US10Y"]
                )
            return (
                "크립토 시장 독립 모멘텀 또는 ETF 유입 기대 가능성",
                ["DXY", "QQQ", "US10Y"]
            )
        if dxy_chg is not None and dxy_chg > 0.5:
            return (
                "달러 강세에 따른 크립토 매도 압력 가능성",
                ["DXY", "QQQ", "US10Y"]
            )
        return (
            "위험회피 심리 또는 크립토 시장 조정 압력 가능성",
            ["QQQ", "DXY", "US10Y"]
        )

    # ── 이더리움 / 솔라나 / 기타 코인 ────────────────────────────────────────────
    if "ETH" in ticker_upper or "SOL" in ticker_upper or category == "crypto":
        coin_name = "이더리움" if "ETH" in ticker_upper else ("솔라나" if "SOL" in ticker_upper else ticker)
        if change_1d > 0:
            return (
                f"비트코인 상승 연동 또는 {coin_name} 개별 네트워크 모멘텀 반영 가능성",
                ["BTC-USD", "QQQ", "DXY"]
            )
        return (
            f"비트코인 하락 연동 또는 크립토 전반 위험회피 가능성  ·  {coin_name} 고베타 특성상 낙폭 확대 유의",
            ["BTC-USD", "QQQ", "DXY"]
        )

    # ── 기본 fallback ────────────────────────────────────────────────────────
    if change_1d > 0:
        return (
            "시장 전반의 위험선호 심리 또는 개별 모멘텀 반영 가능성",
            ["QQQ", "SPY", "DXY"]
        )
    return (
        "시장 전반의 위험회피 심리 또는 개별 약세 요인 반영 가능성",
        ["QQQ", "SPY", "US10Y"]
    )


# ── Portfolio relevance ───────────────────────────────────────────────────────

def _check_portfolio_relevance(ticker: str, name: str, category: str, data: dict) -> str:
    crypto_df = data.get("crypto", pd.DataFrame())
    if not crypto_df.empty and "ticker" in crypto_df.columns:
        if ticker in crypto_df["ticker"].values:
            return "직접 보유 중"

    my_etfs_df = data.get("my_etfs", pd.DataFrame())
    if my_etfs_df.empty:
        return "해당 없음"

    if "ticker" in my_etfs_df.columns:
        if ticker in my_etfs_df["ticker"].values:
            return "직접 보유 중"

    if "benchmark" in my_etfs_df.columns:
        matching = my_etfs_df[my_etfs_df["benchmark"] == ticker]
        if not matching.empty:
            etf_names = ", ".join(matching["name"].tolist()) if "name" in matching.columns else "보유 ETF"
            return f"벤치마크 — {etf_names}"

    if "category" in my_etfs_df.columns:
        cat_map = {
            "반도체": ["반도체", "AI", "Tech"],
            "기술": ["기술", "나스닥", "빅테크", "테크"],
            "금": ["금"],
            "은": ["은"],
            "구리": ["구리"],
            "중국": ["차이나", "중국", "China"],
        }
        for key, keywords in cat_map.items():
            if any(kw in name or kw in ticker for kw in keywords):
                my_matching = my_etfs_df[
                    my_etfs_df["category"].apply(
                        lambda c: any(kw in str(c) for kw in keywords)
                    )
                ]
                if not my_matching.empty:
                    etf_names = ", ".join(my_matching["name"].tolist()[:2])
                    return f"관련 카테고리 보유 — {etf_names}"

    return "직접 관련 없음"


# ── Volatility-adjusted daily threshold ──────────────────────────────────────

def _daily_vol_threshold(vol_20d_pct: float | None, vol_60d_pct: float | None = None) -> float | None:
    """
    Returns daily vol in % from annualised vol.
    Uses max(20d, 60d) to avoid threshold suppression after volatile periods.
    """
    v20 = None
    if vol_20d_pct is not None and not math.isnan(vol_20d_pct):
        v20 = (vol_20d_pct / math.sqrt(252)) * 100

    v60 = None
    if vol_60d_pct is not None and not math.isnan(vol_60d_pct):
        v60 = (vol_60d_pct / math.sqrt(252)) * 100

    candidates = [v for v in (v20, v60) if v is not None]
    return max(candidates) if candidates else None


# ── Main detection function ───────────────────────────────────────────────────

def detect_major_movers(data: dict, db_summary: pd.DataFrame) -> dict:
    """
    Returns {"gainers": list, "losers": list, "unusual": list}.
    Each mover dict has: asset, ticker, category, change_1d, change_1w,
    change_1m, move_type, possible_driver, related_indicators, portfolio_relevance.
    """
    gainers: list[dict] = []
    losers:  list[dict] = []
    unusual: list[dict] = []

    db_lookup: dict[str, Any] = {}
    if not db_summary.empty and "symbol" in db_summary.columns:
        for _, row in db_summary.iterrows():
            db_lookup[str(row["symbol"])] = row

    def _safe_float(v) -> float | None:
        try:
            f = float(v)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    def _process_asset(ticker: str, name: str, change_pct_raw,
                       asset_cat: str, data_cat_label: str):
        change_1d = _safe_float(change_pct_raw)
        if change_1d is None:
            return

        threshold   = _resolve_threshold(ticker, name, asset_cat)
        weekly_flag, monthly_flag = _resolve_flags(ticker, asset_cat)

        db_row   = db_lookup.get(ticker)
        chg_1w   = _safe_float(db_row["return_1w_pct"])     if db_row is not None else None
        chg_1m   = _safe_float(db_row["return_1m_pct"])     if db_row is not None else None
        vol_20d  = _safe_float(db_row["volatility_20d_pct"]) if db_row is not None else None
        # vol_60d not yet in DB schema; reserved for future use
        vol_60d  = None

        move_flags = []
        is_significant = abs(change_1d) >= threshold

        if change_1d >= threshold:
            move_flags.append("일간 급등")
        elif change_1d <= -threshold:
            move_flags.append("일간 급락")

        if chg_1w is not None and abs(chg_1w) >= weekly_flag:
            move_flags.append("주간 급등/급락")

        if chg_1m is not None and abs(chg_1m) >= monthly_flag:
            move_flags.append("월간 급등/급락")

        daily_vol = _daily_vol_threshold(vol_20d, vol_60d)
        vol_breach = False
        if daily_vol is not None and daily_vol > 0:
            if abs(change_1d) > _VOL_MULT * daily_vol:
                vol_breach = True
                if "변동성 대비 이탈" not in move_flags:
                    move_flags.append("변동성 대비 이탈")

        if not move_flags and not vol_breach:
            return

        move_type = " / ".join(move_flags) if move_flags else "변동성 대비 이탈"

        driver, related = _infer_driver(ticker, asset_cat, change_1d, data)
        portfolio_rel = _check_portfolio_relevance(ticker, name, asset_cat, data)

        mover = {
            "asset":               name,
            "ticker":              ticker,
            "category":            data_cat_label,
            "change_1d":           round(change_1d, 2),
            "change_1w":           round(chg_1w, 2) if chg_1w is not None else None,
            "change_1m":           round(chg_1m, 2) if chg_1m is not None else None,
            "move_type":           move_type,
            "possible_driver":     driver,
            "related_indicators":  related,
            "portfolio_relevance": portfolio_rel,
        }

        if vol_breach and not is_significant:
            unusual.append(mover)
        elif change_1d > 0:
            gainers.append(mover)
            if vol_breach:
                unusual.append(mover)
        else:
            losers.append(mover)
            if vol_breach:
                unusual.append(mover)

    # ── Process my_etfs ───────────────────────────────────────────────────────
    my_etfs_df = data.get("my_etfs", pd.DataFrame())
    if not my_etfs_df.empty:
        for _, row in my_etfs_df.iterrows():
            _process_asset(
                ticker=str(row.get("ticker", "")),
                name=str(row.get("name", row.get("ticker", ""))),
                change_pct_raw=row.get("change_pct"),
                asset_cat="my_etf",
                data_cat_label=_CATEGORY_LABELS["my_etf"],
            )

    # ── Process benchmarks ────────────────────────────────────────────────────
    benchmarks_df = data.get("benchmarks", pd.DataFrame())
    if not benchmarks_df.empty:
        for _, row in benchmarks_df.iterrows():
            _process_asset(
                ticker=str(row.get("ticker", "")),
                name=str(row.get("name", row.get("ticker", ""))),
                change_pct_raw=row.get("change_pct"),
                asset_cat="benchmark",
                data_cat_label=_CATEGORY_LABELS["benchmark"],
            )

    # ── Process US stocks ─────────────────────────────────────────────────────
    us_stocks_df = data.get("us_stocks", pd.DataFrame())
    if not us_stocks_df.empty:
        for _, row in us_stocks_df.iterrows():
            _process_asset(
                ticker=str(row.get("ticker", "")),
                name=str(row.get("name", row.get("ticker", ""))),
                change_pct_raw=row.get("change_pct"),
                asset_cat="us_stock",
                data_cat_label=_CATEGORY_LABELS["us_stock"],
            )

    # ── Process commodities ───────────────────────────────────────────────────
    comm_df = data.get("commodities", pd.DataFrame())
    if not comm_df.empty:
        for _, row in comm_df.iterrows():
            raw_name = str(row.get("name", ""))
            _process_asset(
                ticker=str(row.get("ticker", raw_name)),
                name=_COMM_NAME_KOR.get(raw_name, raw_name),
                change_pct_raw=row.get("change_pct"),
                asset_cat="commodity",
                data_cat_label=_CATEGORY_LABELS["commodity"],
            )

    # ── Process FX ────────────────────────────────────────────────────────────
    fx_df = data.get("fx", pd.DataFrame())
    if not fx_df.empty:
        for _, row in fx_df.iterrows():
            pair = str(row.get("pair", ""))
            display_name = pair.upper().replace("_", "/")
            _process_asset(
                ticker=pair,
                name=display_name,
                change_pct_raw=row.get("change_pct"),
                asset_cat="fx",
                data_cat_label=_CATEGORY_LABELS["fx"],
            )

    # ── Process crypto ────────────────────────────────────────────────────────
    crypto_df = data.get("crypto", pd.DataFrame())
    if not crypto_df.empty:
        for _, row in crypto_df.iterrows():
            _process_asset(
                ticker=str(row.get("ticker", "")),
                name=str(row.get("name", row.get("ticker", ""))),
                change_pct_raw=row.get("change_pct"),
                asset_cat="crypto",
                data_cat_label=_CATEGORY_LABELS["crypto"],
            )

    gainers.sort(key=lambda x: x["change_1d"], reverse=True)
    losers.sort(key=lambda x: x["change_1d"])
    unusual.sort(key=lambda x: abs(x["change_1d"]), reverse=True)

    seen: set[str] = set()
    deduped_unusual = []
    for m in unusual:
        if m["ticker"] not in seen:
            seen.add(m["ticker"])
            deduped_unusual.append(m)

    return {"gainers": gainers, "losers": losers, "unusual": deduped_unusual}


# ── Narrative generation ──────────────────────────────────────────────────────

def _format_asset_line(mover: dict) -> str:
    chg = mover["change_1d"]
    sign = "+" if chg >= 0 else ""
    return f"{mover['asset']} ({sign}{chg:.2f}%)"


def _infer_common_theme(movers: dict, data: dict) -> str:
    gainers = movers.get("gainers", [])
    losers  = movers.get("losers",  [])

    dxy_chg  = _get_chg(data, "fx", "dxy")
    krw_chg  = _get_chg(data, "fx", "usd_krw")
    us10y    = _get_macro_value(data, "us_10y")

    gainer_tickers = {m["ticker"].upper() for m in gainers}
    loser_tickers  = {m["ticker"].upper() for m in losers}

    tech_up   = bool(gainer_tickers & {"QQQ", "SOXX", "TQQQ"})
    gold_up   = any("금" in m["asset"] or m["ticker"].upper() in ("GLD", "IAU") for m in gainers)
    risk_up   = bool(gainer_tickers & {"SPY", "QQQ", "SOXX"})
    risk_down = bool(loser_tickers  & {"SPY", "QQQ"})
    dxy_up    = dxy_chg is not None and dxy_chg > 0.5  # raised from 0.3

    themes = []

    if tech_up and (us10y is None or us10y < 4.8) and not risk_down:
        themes.append("금리 안정 기반 위험선호 심리 개선 흐름")
    if gold_up and (dxy_chg is None or dxy_chg < 0):
        themes.append("달러 약세에 따른 안전자산·귀금속 선호")
    if dxy_up and krw_chg is not None and krw_chg > 0:
        themes.append("달러 강세 — 원화 약세 연동 흐름")
    if risk_down and us10y is not None and us10y > 4.8:
        themes.append("금리 상승 압력에 따른 위험자산 조정 가능성")
    if not themes:
        if gainers and losers:
            themes.append("자산군 간 순환매 또는 혼조세 흐름")
        elif gainers:
            themes.append("광범위한 위험선호 흐름")
        elif losers:
            themes.append("광범위한 위험회피 흐름")
        else:
            themes.append("뚜렷한 공통 테마 미확인")

    return " / ".join(themes)


def _portfolio_impact_notes(movers: dict, data: dict) -> str:
    all_movers = movers.get("gainers", []) + movers.get("losers", []) + movers.get("unusual", [])
    relevant = [m for m in all_movers if "해당 없음" not in m["portfolio_relevance"]
                and "직접 관련 없음" not in m["portfolio_relevance"]]
    if not relevant:
        return "현재 급등락 자산 중 보유 ETF와 직접 연관된 항목 없음"

    seen: set[str] = set()
    notes = []
    for m in relevant:
        if m["ticker"] not in seen:
            seen.add(m["ticker"])
            chg = m["change_1d"]
            sign = "+" if chg >= 0 else ""
            notes.append(f"{m['asset']} ({sign}{chg:.2f}%) → {m['portfolio_relevance']}")
    return "  \n".join(notes[:4])


def _indicators_to_watch(movers: dict) -> str:
    all_movers = movers.get("gainers", []) + movers.get("losers", []) + movers.get("unusual", [])
    indicator_counts: dict[str, int] = {}
    for m in all_movers:
        for ind in m.get("related_indicators", []):
            indicator_counts[ind] = indicator_counts.get(ind, 0) + 1

    if not indicator_counts:
        return "US10Y, DXY, USD/KRW"

    sorted_indicators = sorted(indicator_counts.items(), key=lambda x: x[1], reverse=True)
    return ", ".join(ind for ind, _ in sorted_indicators[:6])

