"""
Market regime signal computation.
Used by overview.py (live display) and main.py (DB storage).
"""
import pandas as pd


def compute_regime_signals(data: dict) -> list[dict]:
    """
    Returns list of signal dicts with keys:
      signal, lv (level label), col (low/mid/high/na), note
    """
    bm   = data.get("benchmarks",  pd.DataFrame())
    comm = data.get("commodities", pd.DataFrame())
    fxd  = data.get("fx",          pd.DataFrame())
    mac  = data.get("macro",       pd.DataFrame())

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

    spy_c  = _bc("SPY");  tlt_c  = _bc("TLT")
    qqq_c  = _bc("QQQ");  soxx_c = _bc("SOXX")
    gld_c  = _cc("gold"); slv_c  = _cc("silver"); cop_c = _cc("copper")
    dxy_v  = _fv("dxy", "rate");     dxy_c  = _fv("dxy", "change_pct")
    krw_v  = _fv("usd_krw", "rate"); krw_c  = _fv("usd_krw", "change_pct")
    us10y  = _mv("us_10y")

    def _clamp(v, lo=0, hi=100):
        return max(lo, min(hi, v))

    def _sig(signal, lv, col, note, score=50):
        return {"signal": signal, "lv": lv, "col": col, "note": note, "score": round(_clamp(score))}

    out = []

    # ── Risk sentiment ────────────────────────────────────────────────────────
    if spy_c is not None:
        if spy_c > 0.5:    lv, col = "RISK-ON",  "low"
        elif spy_c < -0.5: lv, col = "RISK-OFF", "high"
        else:               lv, col = "NEUTRAL",  "mid"
        note = f"SPY {spy_c:+.2f}%"
        if tlt_c is not None: note += f"  ·  TLT {tlt_c:+.2f}%"
        if spy_c > 0.5:    note += "  — 위험선호 우세"
        elif spy_c < -0.5: note += "  — 안전자산 선호"
    else:
        lv, col, note = "N/A", "na", "데이터 없음"
    score = _clamp((spy_c + 2) / 4 * 100) if spy_c is not None else 50
    out.append(_sig("Risk-on / Risk-off", lv, col, note, score))

    # ── Dollar strength ───────────────────────────────────────────────────────
    if dxy_v is not None:
        if dxy_v > 103:   lv, col = "STRONG",  "high"
        elif dxy_v > 98:  lv, col = "NEUTRAL", "mid"
        else:              lv, col = "WEAK",    "low"
        note = f"DXY {dxy_v:.2f}"
        if dxy_c is not None: note += f"  (1D {dxy_c:+.2f}%)"
        if dxy_v > 103:   note += "  — 강달러: EM 헤드윈드"
        elif dxy_v < 98:  note += "  — 약달러: EM 우호적"
    else:
        lv, col, note = "N/A", "na", "데이터 없음"
    score = _clamp((dxy_v - 90) / 20 * 100) if dxy_v is not None else 50
    out.append(_sig("Dollar Strength", lv, col, note, score))

    # ── Rate pressure (US 10Y) ────────────────────────────────────────────────
    if us10y is not None:
        if us10y > 4.5:   lv, col = "HIGH",   "high"
        elif us10y > 3.5: lv, col = "MEDIUM", "mid"
        else:              lv, col = "LOW",    "low"
        tail = ("고금리: 성장주 밸류에이션 압박" if us10y > 4.5
                else "저금리: 성장주 우호" if us10y <= 3.5 else "중립적 수준")
        note = f"US 10Y {us10y:.2f}%  — {tail}"
    else:
        lv, col, note = "N/A", "na", "FRED 데이터 없음"
    score = _clamp((us10y - 1.0) / 5.0 * 100) if us10y is not None else 50
    out.append(_sig("Rate Pressure", lv, col, note, score))

    # ── Tech momentum ─────────────────────────────────────────────────────────
    if qqq_c is not None:
        if qqq_c > 1.0:    lv, col = "BULLISH", "low"
        elif qqq_c < -1.0: lv, col = "BEARISH", "high"
        else:               lv, col = "NEUTRAL", "mid"
        note = f"QQQ {qqq_c:+.2f}%"
    else:
        lv, col, note = "N/A", "na", "데이터 없음"
    score = _clamp((qqq_c + 2.0) / 4.0 * 100) if qqq_c is not None else 50
    out.append(_sig("Tech Momentum", lv, col, note, score))

    # ── Semiconductor momentum ────────────────────────────────────────────────
    if soxx_c is not None:
        if soxx_c > 1.5:    lv, col = "BULLISH", "low"
        elif soxx_c < -1.5: lv, col = "BEARISH", "high"
        else:                lv, col = "NEUTRAL", "mid"
        note = f"SOXX {soxx_c:+.2f}%"
    else:
        lv, col, note = "N/A", "na", "데이터 없음"
    score = _clamp((soxx_c + 3.0) / 6.0 * 100) if soxx_c is not None else 50
    out.append(_sig("Semiconductor Momentum", lv, col, note, score))

    # ── Commodity momentum ────────────────────────────────────────────────────
    cc_vals = [(n, c) for n, c in [("Gold", gld_c), ("Silver", slv_c), ("Copper", cop_c)]
               if c is not None]
    if cc_vals:
        avg = sum(v for _, v in cc_vals) / len(cc_vals)
        if avg > 0.5:   lv, col = "RISING",  "mid"
        elif avg < -0.5: lv, col = "FALLING", "low"
        else:            lv, col = "FLAT",    "mid"
        note = "  ·  ".join(f"{n} {v:+.1f}%" for n, v in cc_vals)
    else:
        lv, col, note = "N/A", "na", "데이터 없음"
    score = _clamp((avg + 2.0) / 4.0 * 100) if cc_vals else 50
    out.append(_sig("Commodity Momentum", lv, col, note, score))

    # ── Korea FX risk ─────────────────────────────────────────────────────────
    if krw_c is not None and krw_v is not None:
        if krw_c > 0.5:    lv, col = "HIGH",   "high"
        elif krw_c < -0.5: lv, col = "LOW",    "low"
        else:               lv, col = "MEDIUM", "mid"
        tail = ("원화 약세: 비헤지 ETF 환손실" if krw_c > 0.5
                else "원화 강세: 비헤지 ETF 환이익" if krw_c < -0.5 else "환율 안정")
        note = f"USD/KRW {krw_v:,.0f}원  (1D {krw_c:+.2f}%)  — {tail}"
    else:
        lv, col, note = "N/A", "na", "데이터 없음"
    score = _clamp((krw_c + 1.0) / 2.0 * 100) if krw_c is not None else 50
    out.append(_sig("Korea FX Risk", lv, col, note, score))

    return out
