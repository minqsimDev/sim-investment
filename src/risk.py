"""
Market regime signal computation.
Used by risk_signals.py (live display) and main.py (DB storage).

신호 산출 3단(우선순위):
  1) 백분위 보정(B): 모멘텀 신호는 '최근 20거래일 수익률'을, 달러는 'DXY 레벨'을 **자기 1년 분포의
     백분위**로 판정(상위 25% 강함 / 하위 25% 약함). 고정 임계값의 자의성 제거 — 자기 보정.
  2) 추세 폴백(A): 1년 표본이 부족하면 20일 수익률을 고정 임계값으로.
  3) 1D 폴백: 종가 히스토리가 없으면 1일 변동%로.
종가는 price_history(DB) 1년치(_fetch_regime_closes→batch_close_history). 레벨 신호 중 금리(US10Y,
FRED)는 경제적 앵커(4.5/3.5%)가 의미 있어 고정 유지.
"""
import pandas as pd

_PCT_HI, _PCT_LO = 75.0, 25.0     # 백분위 밴드(상/하위 25%)
_MIN_SAMPLE = 60                  # 백분위 산출 최소 표본(~3개월)


def _fetch_regime_closes(data: dict) -> dict:
    """추세·백분위 산출용 1년 종가 — 벤치마크·원자재·환율 티커를 DB-우선(batch_close_history)으로.
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
        hist = batch_close_history(",".join(dict.fromkeys(want.values())), "1y")
    except Exception:
        return {}
    return {k: hist.get(tk) for k, tk in want.items() if hist.get(tk) is not None}


def compute_regime_signals(data: dict, closes: dict | None = None) -> list[dict]:
    """Returns list of signal dicts: signal, lv (level label), col (low/mid/high/na), note, score.
    closes: {key: Close Series} (1년). None 이면 DB에서 조회, 빈 dict 면 1D 폴백."""
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

    def _clamp(v, lo=0, hi=100):
        return max(lo, min(hi, v))

    def _sig(signal, lv, col, note, score=50):
        return {"signal": signal, "lv": lv, "col": col, "note": note, "score": round(_clamp(score))}

    def _ret20_series(key):
        """{key} 종가의 20거래일 수익률(%) 시계열 — 부족하면 None."""
        s = closes.get(key)
        if s is None:
            return None
        try:
            s = s.dropna()
        except Exception:
            return None
        if len(s) < 21:
            return None
        return ((s / s.shift(20) - 1) * 100).dropna()

    def _pctile(value, dist):
        """value 가 dist(과거 분포) 내 백분위(0-100) — 표본 부족이면 None."""
        if value is None or dist is None or len(dist) < _MIN_SAMPLE:
            return None
        return float((dist < value).sum()) / len(dist) * 100

    def _eval_mom(key, d1, t_thr, d_thr):
        """모멘텀 신호 판정 → (band, value, basis, pct, score).
        band: high/low/mid/None. basis: '1개월'|'1D'. pct: 백분위 또는 None."""
        r = _ret20_series(key)
        cur = float(r.iloc[-1]) if r is not None else None
        pct = _pctile(cur, r)
        if pct is not None:                                   # 1) 백분위 보정
            band = "high" if pct >= _PCT_HI else "low" if pct <= _PCT_LO else "mid"
            return band, cur, "1개월", pct, pct
        if cur is not None:                                   # 2) 추세(고정 임계값)
            band = "high" if cur > t_thr else "low" if cur < -t_thr else "mid"
            return band, cur, "1개월", None, _clamp(50 + cur / (2 * t_thr) * 50)
        if d1 is not None:                                    # 3) 1D 폴백
            band = "high" if d1 > d_thr else "low" if d1 < -d_thr else "mid"
            return band, d1, "1D", None, _clamp(50 + d1 / (2 * d_thr) * 50)
        return None, None, None, None, 50

    def _pctword(pct):
        """백분위를 직관적 문구로 — 상단이면 '상위 X%', 하단이면 '하위 X%'."""
        return f"최근1년 상위 {100 - pct:.0f}%" if pct >= 50 else f"최근1년 하위 {pct:.0f}%"

    def _mom_note(sym, v, basis, pct):
        if v is None:
            return "데이터 없음"
        if basis == "1D":
            return f"{sym} 1D {v:+.2f}%"
        s = f"{sym} 1개월 {v:+.1f}%"
        if pct is not None:
            s += f" · {_pctword(pct)}"
        return s

    out = []

    # ── Risk sentiment (SPY) ────────────────────────────────────────────────────
    band, v, basis, pct, score = _eval_mom("SPY", _bc("SPY"), 2.0, 0.5)
    if band is None:
        out.append(_sig("Risk-on / Risk-off", "N/A", "na", "데이터 없음", 50))
    else:
        lv, col = {"high": ("RISK-ON", "low"), "low": ("RISK-OFF", "high"),
                   "mid": ("NEUTRAL", "mid")}[band]
        note = _mom_note("SPY", v, basis, pct)
        if lv == "RISK-ON":    note += "  — 위험선호 우세"
        elif lv == "RISK-OFF": note += "  — 안전자산 선호"
        tlt_c = _bc("TLT")
        if tlt_c is not None:  note += f"  ·  TLT 1D {tlt_c:+.2f}%"
        out.append(_sig("Risk-on / Risk-off", lv, col, note, score))

    # ── Dollar strength (DXY 레벨 백분위) ───────────────────────────────────────
    dxy_v, dxy_c = _fv("dxy", "rate"), _fv("dxy", "change_pct")
    dxy_hist = None
    try:
        _s = closes.get("dxy")
        dxy_hist = _s.dropna() if _s is not None else None
    except Exception:
        dxy_hist = None
    dxy_pct = _pctile(dxy_v, dxy_hist)
    if dxy_pct is not None:
        if dxy_pct >= _PCT_HI:   lv, col, tail = "STRONG", "high", "  — 강달러: EM 헤드윈드"
        elif dxy_pct <= _PCT_LO: lv, col, tail = "WEAK",   "low",  "  — 약달러: EM 우호적"
        else:                     lv, col, tail = "NEUTRAL", "mid", ""
        note = f"DXY {dxy_v:.2f} · {_pctword(dxy_pct)}{tail}"
        score = dxy_pct
    elif dxy_v is not None:                                   # 폴백: 고정 레벨
        if dxy_v > 103:   lv, col = "STRONG",  "high"
        elif dxy_v > 98:  lv, col = "NEUTRAL", "mid"
        else:              lv, col = "WEAK",    "low"
        note = f"DXY {dxy_v:.2f}" + (f"  (1D {dxy_c:+.2f}%)" if dxy_c is not None else "")
        score = _clamp((dxy_v - 90) / 20 * 100)
    else:
        lv, col, note, score = "N/A", "na", "데이터 없음", 50
    out.append(_sig("Dollar Strength", lv, col, note, score))

    # ── Rate pressure (US 10Y 레벨, FRED — 경제적 앵커 고정) ─────────────────────
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

    # ── Tech / Semiconductor momentum ───────────────────────────────────────────
    for name, key, sym, t_thr in [("Tech Momentum", "QQQ", "QQQ", 3.0),
                                   ("Semiconductor Momentum", "SOXX", "SOXX", 5.0)]:
        band, v, basis, pct, score = _eval_mom(key, _bc(key), t_thr, 1.0 if key == "QQQ" else 1.5)
        if band is None:
            out.append(_sig(name, "N/A", "na", "데이터 없음", 50))
        else:
            lv, col = {"high": ("BULLISH", "low"), "low": ("BEARISH", "high"),
                       "mid": ("NEUTRAL", "mid")}[band]
            out.append(_sig(name, lv, col, _mom_note(sym, v, basis, pct), score))

    # ── Commodity momentum (금·은·동 20일수익률 평균의 백분위) ───────────────────
    rets, curs = [], []
    for nm in ("gold", "silver", "copper"):
        r = _ret20_series(nm)
        if r is not None:
            rets.append(r); curs.append(float(r.iloc[-1]))
    if curs:
        cur = sum(curs) / len(curs)
        dist = pd.concat(rets, axis=1).mean(axis=1).dropna() if rets else None
        pct = _pctile(cur, dist)
        if pct is not None:
            band = "high" if pct >= _PCT_HI else "low" if pct <= _PCT_LO else "mid"
            note = f"1개월 평균 {cur:+.1f}% · {_pctword(pct)}"
            score = pct
        else:
            band = "high" if cur > 3 else "low" if cur < -3 else "mid"
            note, score = f"1개월 평균 {cur:+.1f}%", _clamp(50 + cur / 6 * 50)
    else:                                                     # 1D 폴백
        ds = [_cc(n) for n in ("gold", "silver", "copper") if _cc(n) is not None]
        if ds:
            avg = sum(ds) / len(ds)
            band = "high" if avg > 0.5 else "low" if avg < -0.5 else "mid"
            note, score = f"1D 평균 {avg:+.1f}%", _clamp(50 + avg / 1.0 * 50)
        else:
            band, note, score = None, "데이터 없음", 50
    if band is None:
        out.append(_sig("Commodity Momentum", "N/A", "na", note, 50))
    else:
        lv, col = {"high": ("RISING", "mid"), "low": ("FALLING", "low"),
                   "mid": ("FLAT", "mid")}[band]
        out.append(_sig("Commodity Momentum", lv, col, note, score))

    # ── Korea FX risk (USD/KRW) ─────────────────────────────────────────────────
    krw_v = _fv("usd_krw", "rate")
    band, v, basis, pct, score = _eval_mom("usd_krw", _fv("usd_krw", "change_pct"), 1.5, 0.5)
    if band is None:
        out.append(_sig("Korea FX Risk", "N/A", "na", "데이터 없음", 50))
    else:
        lv, col = {"high": ("HIGH", "high"), "low": ("LOW", "low"), "mid": ("MEDIUM", "mid")}[band]
        tail = ("원화 약세: 비헤지 ETF 환손실" if lv == "HIGH"
                else "원화 강세: 비헤지 ETF 환이익" if lv == "LOW" else "환율 안정")
        lead = f"USD/KRW {krw_v:,.0f}원 · " if krw_v is not None else ""
        body = _mom_note("", v, basis, pct).lstrip()
        out.append(_sig("Korea FX Risk", lv, col, f"{lead}{body} — {tail}", score))

    return out
