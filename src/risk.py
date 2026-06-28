"""
Market regime signal computation.
Used by risk_signals.py (live display) and main.py (DB storage).

모멘텀 신호(Risk-on/off·Tech·Semi·Commodity·Korea FX)는 1일 변동% 대신 **20거래일(1개월) 추세**로
산출한다 → 장마감·주말에도 신호가 죽지 않고 하루 노이즈에 덜 흔들린다. 추세는 price_history(DB) 종가
기반(_fetch_regime_closes → batch_close_history). DB 히스토리가 없으면 1일 변동%로 폴백.
레벨 기반(Dollar=DXY 레벨, Rate=US10Y 레벨)은 원래 1D 의존이 아니라 그대로 둔다.
"""
import pandas as pd


def _fetch_regime_closes(data: dict) -> dict:
    """추세 산출용 3개월 종가 — 벤치마크·원자재·환율 티커를 DB-우선(batch_close_history)으로.
    키는 compute_regime_signals 가 쓰는 키로 정규화(벤치=ticker, 원자재=name, 환율=pair)."""
    want: dict[str, str] = {}
    bm = data.get("benchmarks")
    if bm is not None and not bm.empty and "ticker" in bm:
        for _, r in bm.iterrows():
            t = str(r.get("ticker") or "")
            if t and t != "N/A":
                want[t] = t
    comm = data.get("commodities")
    if comm is not None and not comm.empty and "ticker" in comm:
        for _, r in comm.iterrows():
            t = str(r.get("ticker") or "")
            if t and t != "N/A":
                want[str(r.get("name"))] = t
    fxd = data.get("fx")
    if fxd is not None and not fxd.empty and "ticker" in fxd:
        for _, r in fxd.iterrows():
            t = str(r.get("ticker") or "")
            if t and t != "N/A":
                want[str(r.get("pair"))] = t
    if not want:
        return {}
    try:
        from data.loader import batch_close_history
        hist = batch_close_history(",".join(dict.fromkeys(want.values())), "3mo")
    except Exception:
        return {}
    return {k: hist.get(tk) for k, tk in want.items() if hist.get(tk) is not None}


def compute_regime_signals(data: dict, closes: dict | None = None) -> list[dict]:
    """
    Returns list of signal dicts with keys: signal, lv (level label), col (low/mid/high/na), note, score.
    closes: {key: Close Series} (추세용). None 이면 DB에서 조회. 빈 dict 면 1D 변동%로 폴백.
    """
    bm   = data.get("benchmarks",  pd.DataFrame())
    comm = data.get("commodities", pd.DataFrame())
    fxd  = data.get("fx",          pd.DataFrame())
    mac  = data.get("macro",       pd.DataFrame())
    if closes is None:
        closes = _fetch_regime_closes(data)
    closes = closes or {}

    def _bc(t):
        r = bm[bm["ticker"] == t] if not bm.empty else pd.DataFrame()
        v = r.iloc[0]["change_pct"] if not r.empty else None
        return float(v) if isinstance(v, (int, float)) else None

    def _cc(n):
        r = comm[comm["name"] == n] if not comm.empty else pd.DataFrame()
        v = r.iloc[0]["change_pct"] if not r.empty else None
        return float(v) if isinstance(v, (int, float)) else None

    def _fv(p, col):
        r = fxd[fxd["pair"] == p] if not fxd.empty else pd.DataFrame()
        v = r.iloc[0][col] if not r.empty else None
        return float(v) if isinstance(v, (int, float)) else None

    def _mv(k):
        if mac is None or (hasattr(mac, "empty") and mac.empty): return None
        r = mac[mac["key"] == k]
        v = r.iloc[0]["value"] if not r.empty else None
        return float(v) if isinstance(v, (int, float)) else None

    def _ret20(key):
        """최근 20거래일 수익률(%) — 종가 부족(<21)·없음이면 None."""
        s = closes.get(key)
        if s is None:
            return None
        try:
            s = s.dropna()
        except Exception:
            return None
        if len(s) < 21:
            return None
        p0 = float(s.iloc[-21])
        return (float(s.iloc[-1]) - p0) / p0 * 100 if p0 else None

    def _clamp(v, lo=0, hi=100):
        return max(lo, min(hi, v))

    def _sig(signal, lv, col, note, score=50):
        return {"signal": signal, "lv": lv, "col": col, "note": note, "score": round(_clamp(score))}

    def _trend(key, d1, t_thr, d_thr, pos, neg, mid):
        """(값, 레벨, 색, 기준라벨, 임계값) — 추세 우선, 없으면 1D 폴백. pos/neg/mid=(label,col)."""
        v, thr, basis = _ret20(key), t_thr, "1개월"
        if v is None:
            v, thr, basis = d1, d_thr, "1D"
        if v is None:
            return None, "N/A", "na", None, t_thr
        lv, col = (pos if v > thr else neg if v < -thr else mid)
        return v, lv, col, basis, thr

    out = []

    # ── Risk sentiment (SPY 추세) ───────────────────────────────────────────────
    v, lv, col, basis, thr = _trend("SPY", _bc("SPY"), 2.0, 0.5,
                                    ("RISK-ON", "low"), ("RISK-OFF", "high"), ("NEUTRAL", "mid"))
    if v is None:
        note, score = "데이터 없음", 50
    else:
        note = f"SPY {basis} {v:+.2f}%"
        tlt_c = _bc("TLT")
        if tlt_c is not None: note += f"  ·  TLT 1D {tlt_c:+.2f}%"
        if lv == "RISK-ON":    note += "  — 위험선호 우세"
        elif lv == "RISK-OFF": note += "  — 안전자산 선호"
        score = _clamp(50 + v / (2 * thr) * 50)
    out.append(_sig("Risk-on / Risk-off", lv, col, note, score))

    # ── Dollar strength (DXY 레벨 — 추세 무관) ──────────────────────────────────
    dxy_v, dxy_c = _fv("dxy", "rate"), _fv("dxy", "change_pct")
    if dxy_v is not None:
        if dxy_v > 103:   lv, col = "STRONG",  "high"
        elif dxy_v > 98:  lv, col = "NEUTRAL", "mid"
        else:              lv, col = "WEAK",    "low"
        note = f"DXY {dxy_v:.2f}"
        if dxy_c is not None: note += f"  (1D {dxy_c:+.2f}%)"
        if dxy_v > 103:   note += "  — 강달러: EM 헤드윈드"
        elif dxy_v < 98:  note += "  — 약달러: EM 우호적"
        score = _clamp((dxy_v - 90) / 20 * 100)
    else:
        lv, col, note, score = "N/A", "na", "데이터 없음", 50
    out.append(_sig("Dollar Strength", lv, col, note, score))

    # ── Rate pressure (US 10Y 레벨, FRED — 추세 무관) ───────────────────────────
    us10y = _mv("us_10y")
    if us10y is not None:
        if us10y > 4.5:   lv, col = "HIGH",   "high"
        elif us10y > 3.5: lv, col = "MEDIUM", "mid"
        else:              lv, col = "LOW",    "low"
        tail = ("고금리: 성장주 밸류에이션 압박" if us10y > 4.5
                else "저금리: 성장주 우호" if us10y <= 3.5 else "중립적 수준")
        note, score = f"US 10Y {us10y:.2f}%  — {tail}", _clamp((us10y - 1.0) / 5.0 * 100)
    else:
        lv, col, note, score = "N/A", "na", "FRED 데이터 없음", 50
    out.append(_sig("Rate Pressure", lv, col, note, score))

    # ── Tech momentum (QQQ 추세) ────────────────────────────────────────────────
    v, lv, col, basis, thr = _trend("QQQ", _bc("QQQ"), 3.0, 1.0,
                                    ("BULLISH", "low"), ("BEARISH", "high"), ("NEUTRAL", "mid"))
    note = f"QQQ {basis} {v:+.2f}%" if v is not None else "데이터 없음"
    out.append(_sig("Tech Momentum", lv, col, note, 50 if v is None else _clamp(50 + v / (2 * thr) * 50)))

    # ── Semiconductor momentum (SOXX 추세) ──────────────────────────────────────
    v, lv, col, basis, thr = _trend("SOXX", _bc("SOXX"), 5.0, 1.5,
                                    ("BULLISH", "low"), ("BEARISH", "high"), ("NEUTRAL", "mid"))
    note = f"SOXX {basis} {v:+.2f}%" if v is not None else "데이터 없음"
    out.append(_sig("Semiconductor Momentum", lv, col, note, 50 if v is None else _clamp(50 + v / (2 * thr) * 50)))

    # ── Commodity momentum (금·은·동 추세 평균) ─────────────────────────────────
    parts, basis = [], "1개월"
    for nm in ("gold", "silver", "copper"):
        t = _ret20(nm)
        if t is not None:
            parts.append((nm, t))
    if not parts:                       # 추세 없으면 1D 폴백
        basis = "1D"
        parts = [(nm, _cc(nm)) for nm in ("gold", "silver", "copper") if _cc(nm) is not None]
    if parts:
        avg = sum(v for _, v in parts) / len(parts)
        thr = 3.0 if basis == "1개월" else 0.5
        if avg > thr:    lv, col = "RISING",  "mid"
        elif avg < -thr: lv, col = "FALLING", "low"
        else:             lv, col = "FLAT",    "mid"
        names = {"gold": "Gold", "silver": "Silver", "copper": "Copper"}
        note = f"{basis} " + "  ·  ".join(f"{names[n]} {v:+.1f}%" for n, v in parts)
        score = _clamp(50 + avg / (2 * thr) * 50)
    else:
        lv, col, note, score = "N/A", "na", "데이터 없음", 50
    out.append(_sig("Commodity Momentum", lv, col, note, score))

    # ── Korea FX risk (USD/KRW 추세) ────────────────────────────────────────────
    krw_v = _fv("usd_krw", "rate")
    v, lv, col, basis, thr = _trend("usd_krw", _fv("usd_krw", "change_pct"), 1.5, 0.5,
                                    ("HIGH", "high"), ("LOW", "low"), ("MEDIUM", "mid"))
    if v is None:
        note, score = "데이터 없음", 50
    else:
        tail = ("원화 약세: 비헤지 ETF 환손실" if lv == "HIGH"
                else "원화 강세: 비헤지 ETF 환이익" if lv == "LOW" else "환율 안정")
        lead = f"USD/KRW {krw_v:,.0f}원  " if krw_v is not None else ""
        note = f"{lead}({basis} {v:+.2f}%)  — {tail}"
        score = _clamp(50 + v / (2 * thr) * 50)
    out.append(_sig("Korea FX Risk", lv, col, note, score))

    return out
