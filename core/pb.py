"""
PB식 리스크-우선 진단 엔진.
- pb_diagnostics(): 집중·충격·재배분·알파를 전부 자동 산출 (하드코딩 결과 금지)
- 종목 태그(섹터·베타·자산군)는 reference data(증권 마스터)로 분리
- bench_returns(): 사용자 start_date~today 동일 기간 지수 수익률
- signal_impact(): 시장 신호 → 보유 종목 노출 자동 매핑 (리스크 페이지 B)
"""
import math
from datetime import date

# ── 증권 마스터(태그) — 값은 reference data ───────────────────────────────────
# ticker(또는 base) → (sector, beta, asset_class)
_SECURITY_TAGS = {
    "TSLA": ("자동차/성장", 2.0, "미국주식"),
    "AAPL": ("빅테크", 1.2, "미국주식"),
    "MSFT": ("빅테크", 0.9, "미국주식"),
    "GOOGL": ("빅테크", 1.1, "미국주식"),
    "AMZN": ("빅테크", 1.2, "미국주식"),
    "META": ("빅테크", 1.3, "미국주식"),
    "NVDA": ("반도체", 1.7, "미국주식"),
    "AMD": ("반도체", 1.9, "미국주식"),
    "AVGO": ("반도체", 1.2, "미국주식"),
    "MU": ("반도체", 1.4, "미국주식"),
    "TSM": ("반도체", 1.2, "미국주식"),
    "ASML": ("반도체", 1.3, "미국주식"),
    "QQQ": ("지수ETF", 1.1, "미국주식"),
    "SPY": ("지수ETF", 1.0, "미국주식"),
    "005930.KS": ("반도체", 1.0, "국내주식"),
    "000660.KS": ("반도체", 1.3, "국내주식"),
    "207940.KS": ("바이오", 0.9, "국내주식"),
    "005380.KS": ("자동차", 1.1, "국내주식"),
    "035420.KS": ("인터넷", 1.0, "국내주식"),
    "051910.KS": ("이차전지", 1.2, "국내주식"),
    "BTC-USD": ("크립토", 2.5, "크립토"),
    "ETH-USD": ("크립토", 2.8, "크립토"),
    "GC=F": ("귀금속", 0.2, "원자재"),
    "SI=F": ("귀금속", 0.5, "원자재"),
    "HG=F": ("산업금속", 0.8, "원자재"),
}

# 카테고리/이름 키워드 → 기본 태그(폴백)
_FALLBACK = {
    "반도체": ("반도체", 1.6),
    "빅테크": ("빅테크", 1.2),
    "나스닥": ("성장주", 1.3),
    "테크": ("성장주", 1.3),
    "ETF": ("ETF", 1.2),
    "크립토": ("크립토", 2.0),
    "가상": ("크립토", 2.0),
    "원자재": ("원자재", 0.3),
    "금": ("귀금속", 0.2),
    "채권": ("채권", 0.2),
    "현금": ("현금", 0.0),
}


def tag_holding(name: str, ticker: str, category: str) -> tuple[str, float, str]:
    """종목 → (sector, beta, asset_class). 마스터 우선, 없으면 카테고리/이름 휴리스틱."""
    base = (ticker or "").upper()
    if base in _SECURITY_TAGS:
        return _SECURITY_TAGS[base]
    # 휴리스틱
    text = f"{name} {category}"
    for kw, (sec, beta) in _FALLBACK.items():
        if kw in text:
            ac = category or ("미국주식" if not base.endswith(".KS") else "국내주식")
            return (sec, beta, ac)
    # 통화/카테고리 기본
    ac = category or "주식"
    return ("기타", 1.1, ac)


def holdings_for_pb(positions: list[dict]) -> list[dict]:
    """portfolio positions → pb 엔진 입력(weight 0~1, 태그 부착, 현금 제외)."""
    out = []
    for p in positions:
        if p.get("category") == "현금" or p.get("ticker") == "CASH":
            continue
        sector, beta, asset_class = tag_holding(p.get("name", ""), p.get("ticker", ""), p.get("category", ""))
        out.append({
            "name": p.get("name", ""),
            "weight": (p.get("weight", 0) or 0) / 100.0,  # 0~100 → 0~1
            "sector": sector,
            "beta": beta,
            # 리스크용 표시통화 — 미국주식은 USD(달러 노출). 저장 currency 가 불량(구 파싱 'KRW')일 수
            # 있어 asset_class 기준 판정. 평가액 환산통화와 별개(여기선 USD 노출·FX 리스크 계산용).
            "currency": "USD" if asset_class == "미국주식" else (p.get("currency") or "KRW").upper(),
            "asset_class": asset_class,
        })
    return out


def pb_diagnostics(holdings, total_value, cash, start_date, start_value,
                   bench_returns, today=None):
    """
    holdings: [{name, weight(0~1), sector, beta, currency, asset_class}, ...]
    bench_returns: {"NASDAQ100": 0.41, ...}  (같은 기간, 외부 계산)
    """
    today = today or date.today()
    _years = max((today - start_date).days / 365.25, 1e-9)

    if not holdings:
        return None
    top = max(holdings, key=lambda h: h["weight"])
    top_w = top["weight"]
    shock = -0.20 * top_w
    shock_krw = shock * total_value
    cash_pct = cash / total_value if total_value else 0
    usd_w = sum(h["weight"] for h in holdings if h["currency"] == "USD")

    level = "위험" if top_w >= 0.5 else ("주의" if top_w >= 0.3 else "양호")

    def rebalance_amount(target_w):
        return max(top_w - target_w, 0) * total_value

    my_return = (total_value / start_value) - 1 if start_value else 0
    best_bench = max(bench_returns, key=bench_returns.get) if bench_returns else None
    excess = (my_return - bench_returns[best_bench]) if best_bench else 0

    return {
        "top_name": top["name"], "top_w": top_w, "top_beta": top.get("beta", 1.0), "level": level,
        "top_cur": top.get("currency", "KRW"),
        "shock_pct": shock * 100, "shock_krw": shock_krw,
        "cash_pct": cash_pct * 100, "usd_w": usd_w * 100,
        "rebal_to_40": rebalance_amount(0.40),
        "my_return": my_return * 100,
        "excess_vs_best": excess * 100, "best_bench": best_bench,
    }


# ── 표준 정량 리스크 지표 (베타·HHI·추정 변동성) ──────────────────────────────
_MARKET_SIGMA = 18.0  # 시장 연환산 변동성 가정(%) — 체계적 σ 추정용(KOSPI/S&P 장기 실현 ~15~20% 중앙값)


def portfolio_risk_metrics(holdings: list[dict]) -> dict | None:
    """표준 정량 리스크 지표 — 보유 weight·beta에서 자동 산출.
    - beta_p = Σ wᵢβᵢ            (체계적 시장 민감도 = CAPM 베타)
    - hhi = Σ wᵢ², eff_n = 1/hhi (집중도 = 허핀달-허시먼 지수 · 유효종목수)
    - sigma_p ≈ beta_p × 시장σ   (체계적 변동성 추정, 연율%)
    - top_w                       (최대 단일종목 비중 0~1 — 단일명 꼬리위험)
    β·HHI는 표준 정의를 그대로 사용. 0~100 점수화 매핑·가중은 호출부(리스크 페이지) 책임."""
    hs = [h for h in holdings if (h.get("weight") or 0) > 0]
    if not hs:
        return None
    wsum = sum(h["weight"] for h in hs) or 1.0
    norm = [(h["weight"] / wsum, h) for h in hs]                 # β·HHI는 투자분 합=1 기준(표준)
    beta_p = sum(w * (h.get("beta") or 1.0) for w, h in norm)
    hhi = sum(w * w for w, _ in norm)
    eff_n = (1.0 / hhi) if hhi else float(len(hs))
    # 단일명 노출(top_w)은 '총액 대비'(현금 포함) — 진단카드·자산배분바와 동일 숫자 + 현금 완충 반영.
    top = max(hs, key=lambda h: h.get("weight") or 0)
    return {
        "beta_p": beta_p, "hhi": hhi, "eff_n": eff_n,
        "sigma_p": beta_p * _MARKET_SIGMA,
        "top_w": top.get("weight") or 0, "top_name": top.get("name", ""),
    }


# ── 벤치마크 동일 기간 수익률 ────────────────────────────────────────────────
_BENCH_TICKERS = {"NASDAQ100": "QQQ", "S&P500": "SPY", "KOSPI": "^KS11"}


def bench_returns(start_date: date, today=None) -> dict:
    """start_date~today 동일 기간 지수 수익률(소수). 실패 종목은 제외."""
    from datetime import timedelta
    today = today or date.today()
    out = {}
    try:
        from data.session import cached_download
    except Exception:
        return out
    start = (start_date - timedelta(days=4)).isoformat()
    for label, tk in _BENCH_TICKERS.items():
        try:
            raw = cached_download(tk, start=start, interval="1d", progress=False, auto_adjust=True)
            if raw is None or raw.empty:
                continue
            c = raw["Close"]
            if hasattr(c, "columns"):
                c = c.iloc[:, 0]
            c = c.dropna()
            if len(c) >= 2 and c.iloc[0]:
                out[label] = float(c.iloc[-1] / c.iloc[0] - 1)
        except Exception:
            continue
    return out


# ── 시장 신호 → 보유 노출 매핑 (리스크 B) ─────────────────────────────────────
# 신호 → 노출 '차원(dim)'. 같은 dim 신호는 호출부(리스크 매트릭스)에서 1행으로 통합
# → 같은 노출(예: USD 78%·성장주 70%)이 신호 이름만 바꿔 반복되는 중복을 제거.
_SIGNAL_DIM = {
    "위험선호·회피":     "growth",
    "금리 부담":         "growth",
    "AI·기술주 모멘텀":  "growth",
    "달러 강세":         "fx",
    "원/달러 환율":      "fx",
    "반도체 모멘텀":     "semi",
    "원자재 모멘텀":     "commodity",
}


def scenario_drawdown(holdings: list[dict], total: float, market_move_pct: float = -10.0) -> dict:
    """주식 시장이 market_move_pct% 움직일 때 β가중 예상 평가액 변화. {pct, krw}.
    추정: 원자재는 시장(주식)과 상관 낮다고 보고 제외, 나머지는 종목 β로 환산."""
    if not holdings:
        return {"pct": 0.0, "krw": 0.0}
    beta_w = sum((h.get("weight") or 0) * (h.get("beta") or 1.0)
                 for h in holdings if h.get("asset_class") != "원자재")
    pct = beta_w * market_move_pct
    return {"pct": pct, "krw": (total or 0.0) * pct / 100.0}


def fx_scenario(holdings: list[dict], total: float, fx_move_pct: float = -5.0) -> dict:
    """원/달러가 fx_move_pct% 움직일 때(− = 원화 강세) USD 보유 평가액 변화(원). 추정."""
    if not holdings:
        return {"pct": 0.0, "krw": 0.0}
    usd_w = sum((h.get("weight") or 0) for h in holdings if (h.get("currency") or "").upper() == "USD")
    pct = usd_w * fx_move_pct
    return {"pct": pct, "krw": (total or 0.0) * pct / 100.0}


def impact_krw(total: float, exposure_pct: float, move_pct: float = 1.0) -> float:
    """노출 자산이 move_pct% 움직일 때 내 평가액에 미치는 영향(원).
    exposure_pct·move_pct 는 퍼센트 단위. 추정치(상관·헤지 무시한 단순 환산)."""
    return (total or 0.0) * (exposure_pct / 100.0) * (move_pct / 100.0)


def friction_krw(amount: float, is_us: bool = False) -> float:
    """매도 시 거래 마찰비용(원) 개략 추정.
    국내 ≈ 0.20%(증권거래세 0.18% + 위탁수수료 ~0.015%),
    해외 ≈ 0.45%(수수료 ~0.2% + 환전 스프레드 ~0.25%).
    해외주식 양도소득세(차익의 22%, 연 250만원 공제)는 실현손익에 따라 변동이 커 별도.
    정확치가 아닌 참고용 추정값."""
    rate = 0.0045 if is_us else 0.0020
    return max(0.0, (amount or 0.0)) * rate


def account_greed(holdings: list[dict], total: float = 0.0, cash: float = 0.0) -> dict | None:
    """내 계좌 '탐욕 지수'(0~100, 높을수록 탐욕적·공격적).

    리스크 게이지(위험도)와 입력은 일부 겹치되 역할이 다르다 — 이건 '심리 쏠림(공격성)'의 거울.
    입력 4종(집중도·현금 방어력·고베타/레버리지·단일통화 쏠림)을 0~100으로 정규화 후 가중 평균.
    가중치·구간 컷오프는 검증된 표준 공식이 아니라 본 앱이 정한 출발점이며, 산출 근거를 펼쳐 공개한다.
    """
    if not holdings:
        return None
    top_w    = max((h["weight"] for h in holdings), default=0.0)            # 최대 종목 비중 0~1
    pbeta    = sum(h["weight"] * (h.get("beta") or 1.0) for h in holdings)  # 가중 평균 베타
    usd_w    = sum(h["weight"] for h in holdings if h.get("currency") == "USD")
    cash_pct = (cash / total) if total else 0.0

    def _c(x): return max(0.0, min(100.0, x))
    # A3 컷오프 튜닝 — 흔한 집중 계좌가 100에 포화되지 않게 헤드룸 부여(집중 80%·USD 95%에서 만점).
    s_conc = _c(top_w / 0.80 * 100)                  # 최대 종목 80%+ → 100 (40%≈50, 63%≈79)
    s_cash = _c((1 - cash_pct / 0.25) * 100)         # 현금 0% → 100, 25%+ → 0 (완만한 경사)
    s_beta = _c((pbeta - 0.9) / (1.8 - 0.9) * 100)   # 가중 β 0.9 → 0, 1.8+ → 100
    s_fx   = _c(usd_w / 0.95 * 100)                  # USD 95%+ → 100 (87.5%≈92)

    comps = [
        {"key": "conc", "name": "집중도",         "raw": f"최대 종목 {top_w * 100:.0f}%",
         "norm": s_conc, "weight": 35, "note": "한 종목 비중이 클수록 탐욕(분산이 아니라 베팅)"},
        {"key": "cash", "name": "현금 방어력",     "raw": f"현금 {cash_pct * 100:.0f}%",
         "norm": s_cash, "weight": 30, "note": "현금이 적을수록 탐욕(하락 완충 부족)"},
        {"key": "beta", "name": "고베타·레버리지", "raw": f"가중 β {pbeta:.2f}",
         "norm": s_beta, "weight": 20, "note": "변동성 큰 자산이 많을수록 탐욕"},
        {"key": "fx",   "name": "통화 쏠림",       "raw": f"USD {usd_w * 100:.0f}%",
         "norm": s_fx,  "weight": 15, "note": "단일 통화 노출이 클수록 탐욕"},
    ]
    score = round(sum(c["norm"] * c["weight"] for c in comps) / 100)
    for c in comps:
        c["contrib"] = round(c["norm"] * c["weight"] / 100, 1)   # 총점 기여분(합 = score)

    if   score < 25: band, label, interp = "ext_fear",  "극단적 공포", "과도하게 방어적 — 기회비용 점검"
    elif score < 45: band, label, interp = "fear",      "공포",       "보수적 — 방어 우위"
    elif score < 55: band, label, interp = "neutral",   "중립",       "균형 — 쏠림 적음"
    elif score < 75: band, label, interp = "greed",     "탐욕",       "공격적 — 집중·현금 부족 점검 권장"
    else:            band, label, interp = "ext_greed", "극단적 탐욕", "과열 — 분산·현금 완충 점검 권장"

    return {"score": score, "band": band, "label": label, "interp": interp, "components": comps}


def signal_impact(holdings: list[dict], signals: list[dict], total: float = 0.0) -> list[dict]:
    """
    각 시장 신호를 보유 종목 태그로 자동 연결. 노출은 보유 데이터에서 실측(.1f).
    total(원)을 주면 노출을 '내 계좌 영향 금액(1%당 약 ○○)'으로 번역해 exposure 텍스트에 덧붙인다.
    같은 노출 차원(dim)을 공유하는 신호는 동일 exposure·dim을 가지며, 호출부에서 1행 통합.
    return: [{signal, dim, level, col, exposure, meaning}]
    """
    if not holdings:
        return []
    usd_w   = sum(h["weight"] for h in holdings if h["currency"] == "USD") * 100
    top     = max(holdings, key=lambda h: h["weight"])
    top_w   = top["weight"] * 100
    semi_w  = sum(h["weight"] for h in holdings if "반도체" in h["sector"]) * 100
    growth_w = sum(h["weight"] for h in holdings if h["beta"] >= 1.2) * 100
    comm_w  = sum(h["weight"] for h in holdings
                  if h["asset_class"] == "원자재" or h["sector"] in ("귀금속", "산업금속")) * 100

    # 비중(%)은 반올림 정수 기본(유의미할 때만 1자리) — 전 화면 공통 포맷
    from core.journey import pct_weight as _pw, krw_compact as _kc

    def _imp(expo_pct: float) -> str:
        """노출을 '1%당 약 ○○' 영향 금액으로 번역(total 있을 때만)."""
        if not total or expo_pct <= 0:
            return ""
        return f" · 1%당 약 {_kc(impact_krw(total, expo_pct, 1.0))}"

    # dim별 '서로 다른 고유 노출'(실측값) + 의미 — dim당 단 하나
    dim_expo = {
        "growth": (
            f"성장주 {_pw(growth_w)}% · 최대 {top['name']} {_pw(top_w)}%(β{top['beta']:.1f}){_imp(growth_w)}",
            "위험선호·금리·기술 신호가 모두 이 성장주 집중에 작용",
        ),
        "fx": (
            f"USD {_pw(usd_w)}% · 환헤지 0%{_imp(usd_w)}",
            "달러 방향이 평가금액과 신규 해외매수 부담에 직접 작용",
        ),
        "semi": (
            f"반도체 {_pw(semi_w)}%{_imp(semi_w)}" if semi_w > 0 else "반도체 직접 노출 없음",
            "반도체 사이클이 이 비중에 직접 연동" if semi_w > 0 else "반도체 신호의 직접 영향 제한적",
        ),
        "commodity": (
            f"원자재 {_pw(comm_w)}%{_imp(comm_w)}" if comm_w > 0 else "원자재 노출 없음",
            "원자재는 주식과 상관이 낮아 분산 효과" if comm_w > 0 else "원자재 분산 효과 제한적",
        ),
    }

    out = []
    for s in signals:
        key = s.get("signal", "")
        dim = _SIGNAL_DIM.get(key)
        if not dim:
            continue
        exposure, meaning = dim_expo[dim]
        out.append({
            "signal": key,
            "dim": dim,
            "level": s.get("lv", s.get("col", "")),
            "col": s.get("col", "na"),
            "exposure": exposure,
            "meaning": meaning,
        })
    return out


# ── 게스트 샘플 포트폴리오 (정본) ────────────────────────────────────────────
# 포트폴리오·리스크 페이지가 동일 샘플을 공유 → 게스트가 두 페이지에서 같은 스토리.
# 테슬라 52% 집중(>=50%) → PB level "위험". USD 노출 52+18+8 = 78%.
GUEST_SAMPLE = [  # name, ticker, category, weight(0~100), currency
    {"name": "테슬라",     "ticker": "TSLA",      "category": "미국주식", "weight": 52.0, "currency": "USD"},
    {"name": "엔비디아",   "ticker": "NVDA",      "category": "미국주식", "weight": 18.0, "currency": "USD"},
    {"name": "삼성전자",   "ticker": "005930.KS", "category": "국내주식", "weight": 12.0, "currency": "KRW"},
    {"name": "금",         "ticker": "GC=F",      "category": "원자재",   "weight": 8.0,  "currency": "USD"},
    {"name": "현금/예수금", "ticker": "CASH",      "category": "현금",     "weight": 10.0, "currency": "KRW"},
]


def guest_holdings() -> list[dict]:
    """게스트 샘플 → pb 엔진/signal_impact 입력(현금 제외, 태그 부착)."""
    return holdings_for_pb(GUEST_SAMPLE)
