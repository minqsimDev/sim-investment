"""
시장 분석 — 카테고리별 상위 변동 종목, 애널리스트 노트, 목표가, 스파크라인
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import layout as L  # 반응형(뷰포트 감지 + 모바일 CSS)
from data.loader import load_market_data
from ui.components.dash_style import (
    glossary_expander,
    inject_css, show_skeleton,
    mark_active_nav, mkt_section_header, jj_footer,
)

# ── Category candidate pools ──────────────────────────────────────────────────
# (key, display_name, src)  src: "us"|"kr"|"comm"|"fx"|"crypto"

_CAT_POOLS: dict[str, list[tuple[str, str, str]]] = {
    "AI·반도체":  [
        ("NVDA","엔비디아","us"),("TSM","TSMC","us"),("AMD","AMD","us"),("AVGO","브로드컴","us"),
        ("MU","마이크론","us"),("ASML","ASML","us"),("QCOM","퀄컴","us"),("INTC","인텔","us"),
        ("AMAT","어플라이드 머티리얼즈","us"),("LRCX","램리서치","us"),("KLAC","KLA","us"),("ARM","ARM","us"),
    ],
    "빅테크":     [
        ("MSFT","마이크로소프트","us"),("AAPL","애플","us"),("META","메타","us"),("AMZN","아마존","us"),
        ("GOOGL","알파벳","us"),("TSLA","테슬라","us"),("NFLX","넷플릭스","us"),("ORCL","오라클","us"),
        ("CRM","세일즈포스","us"),("ADBE","어도비","us"),("IBM","IBM","us"),("NOW","서비스나우","us"),
    ],
    "국내주식":   [
        ("005930.KS","삼성전자","kr"),("000660.KS","SK하이닉스","kr"),("207940.KS","삼성바이오로직스","kr"),
        ("005380.KS","현대차","kr"),("000270.KS","기아","kr"),("051910.KS","LG화학","kr"),
        ("006400.KS","삼성SDI","kr"),("035420.KS","NAVER","kr"),("105560.KS","KB금융","kr"),("055550.KS","신한지주","kr"),
        ("373220.KS","LG에너지솔루션","kr"),("005490.KS","POSCO홀딩스","kr"),
    ],
    "원자재":     [
        ("gold","금","comm"),("silver","은","comm"),("copper","구리","comm"),("wti_crude","WTI원유","comm"),
        ("brent_crude","브렌트","comm"),("natural_gas","천연가스","comm"),("platinum","백금","comm"),("palladium","팔라듐","comm"),
        ("corn","옥수수","comm"),("wheat","밀","comm"),("soybeans","대두","comm"),("coffee","커피","comm"),
    ],
    "금리·환율":  [
        ("usd_krw","달러/원","fx"),("jpy_krw","엔/원","fx"),("eur_krw","유로/원","fx"),("usd_jpy","달러/엔","fx"),
        ("dxy","달러지수","fx"),("us10y","미국10년물","fx"),("us5y","미국5년물","fx"),("us30y","미국30년물","fx"),
        ("vix","VIX","fx"),("tlt","미국장기채","fx"),("uup","달러ETF","fx"),("hyg","하이일드","fx"),
    ],
    "크립토":     [
        ("BTC-USD","비트코인","crypto"),("ETH-USD","이더리움","crypto"),("SOL-USD","솔라나","crypto"),("BNB-USD","BNB","crypto"),
        ("XRP-USD","리플","crypto"),("DOGE-USD","도지코인","crypto"),("ADA-USD","카르다노","crypto"),("AVAX-USD","아발란체","crypto"),
        ("LINK-USD","체인링크","crypto"),("BCH-USD","비트코인캐시","crypto"),("LTC-USD","라이트코인","crypto"),("DOT-USD","폴카닷","crypto"),
    ],
}

_INSTRUMENT_SPARK_TICKERS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    "wti_crude": "CL=F",
    "brent_crude": "BZ=F",
    "natural_gas": "NG=F",
    "platinum": "PL=F",
    "palladium": "PA=F",
    "corn": "ZC=F",
    "wheat": "ZW=F",
    "soybeans": "ZS=F",
    "coffee": "KC=F",
    "usd_krw": "USDKRW=X",
    "jpy_krw": "JPYKRW=X",
    "eur_krw": "EURKRW=X",
    "usd_jpy": "USDJPY=X",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
    "us5y": "^FVX",
    "us30y": "^TYX",
    "vix": "^VIX",
    "tlt": "TLT",
    "uup": "UUP",
    "hyg": "HYG",
}

# 테마별 시장 동향 카드 — 본문/배지/순서를 모두 실시세(토스·yfinance)에서 파생한다.
# AI 작문·정적 문구 없음. chip=대표 배지·정렬키(당일 |등락률|), basket=브레드스/리더·러거드 산출용.
_COMM_KOR = {"gold": "금", "silver": "은", "copper": "구리",
             "wti_crude": "WTI", "brent_crude": "브렌트", "natural_gas": "천연가스"}

_THEMES = [
    {"title": "AI 반도체",    "tone": "good",
     "chip": ("반도체", "benchmarks", "ticker", "SOXX"),
     "basket": {"group": "us_stocks", "sectors": ("semiconductor", "ai_semiconductor"),
                "noun": "반도체"}},
    {"title": "금리·달러",    "tone": "warn",
     "chip": ("달러지수", "fx", "pair", "dxy"),
     "rates": True},
    {"title": "원자재",       "tone": "",
     "chip": ("금", "commodities", "name", "gold"),
     "basket": {"group": "commodities", "noun": "원자재", "labels": _COMM_KOR}},
    {"title": "국내 대형주",  "tone": "",
     "chip": ("코스피", "kospi", None, None),
     "basket": {"group": "kr_stocks", "noun": "대형주"}},
    {"title": "크립토·고변동","tone": "alert",
     "chip": ("BTC", "crypto", "ticker", "BTC-USD"),
     "basket": {"group": "crypto", "noun": "코인"}},
]

_MARKET_LOCAL_CSS = """<style>
.mkt-theme-first{margin:2px 0 18px}
.mkt-theme-first .mkt-news-grid{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}

/* '한눈에 요약 / 전체 비교' 뷰 토글 = 미국/한국 ETF 라디오와 동일 양식(전역 radiogroup 골드칩) + 우측 정렬(period_radio 와 동일) */
[data-testid="stElementContainer"]:has(>[data-testid="stRadio"]){width:100%!important}
[data-testid="stRadio"]{display:flex!important;width:100%!important;justify-content:flex-end!important}
[data-testid="stRadio"] div[role="radiogroup"]{justify-content:flex-end!important;flex-wrap:wrap}
/* ── 레짐 슬림 바 + 근거 신호 스트립 ─────────────────────────────────────────── */
.rg-slim{display:flex;align-items:center;gap:10px;flex-wrap:wrap;border:1px solid #262A33;
  border-radius:999px;padding:9px 16px;margin:2px 0 10px;background:#16181F}
.rg-slim .rg-k{font-size:10.5px;font-weight:800;color:#7E8694;letter-spacing:.04em}
.rg-slim .rg-dir{font-size:15px;font-weight:950;letter-spacing:-.02em}
.rg-slim .rg-note{font-size:11.5px;font-weight:650;color:#9AA0AD}
.rg-good .rg-dir{color:#3DD68C}.rg-watch .rg-dir{color:#C9CDD6}.rg-risk .rg-dir{color:#E8883A}
.rg-good{border-color:rgba(61,214,140,.34)}.rg-risk{border-color:rgba(232,136,58,.40)}
.rg-sigs{display:flex;flex-wrap:wrap;gap:6px}
.rg-sig{font-size:11.5px;font-weight:800;padding:4px 10px;border-radius:999px;border:1px solid #262A33;color:#9AA0AD;background:rgba(255,255,255,.04)}
.rg-high{color:#E8883A;border-color:rgba(232,136,58,.38);background:rgba(232,136,58,.10)}
.rg-mid{color:#D9A441;border-color:rgba(217,164,65,.34);background:rgba(217,164,65,.10)}
.rg-low{color:#9AA0AD}
.rg-bridge{display:inline-flex;align-items:center;margin:8px 0 2px;padding:8px 14px;border-radius:999px;
  font-size:12.5px;font-weight:800;color:#D9A441;background:rgba(217,164,65,.10);
  border:1px solid rgba(217,164,65,.40);text-decoration:none}
.rg-bridge:hover{background:rgba(217,164,65,.18);border-color:#D9A441}
</style>"""


# ── Data helpers ──────────────────────────────────────────────────────────────


def _spark_ticker_for(key: str, src: str) -> str:
    if src in {"us", "kr", "crypto"}:
        return key
    return _INSTRUMENT_SPARK_TICKERS.get(key, key)


# ── HTML builders ─────────────────────────────────────────────────────────────

def _grp_change(data: dict, group: str, col: str | None, val) -> float | None:
    """data[group] DataFrame에서 col==val 행의 change_pct(%) → float|None. group='kospi'는 특수 경로."""
    if group == "kospi":
        try:
            from ui.pages.kr_stocks import _bench_prices as _krb
            return _mkt_num((_krb().get("^KS11") or {}).get("change_pct"))
        except Exception:
            return None
    df = data.get(group, pd.DataFrame())
    if not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
        return None
    r = df[df[col] == val]
    return _mkt_num(r.iloc[0].get("change_pct")) if not r.empty else None


def _usdkrw_level(data: dict) -> str | None:
    """USD/KRW 현재 환율 문자열(예: '1,380') — 금리·달러 카드 본문용."""
    fx = data.get("fx", pd.DataFrame())
    if not isinstance(fx, pd.DataFrame) or fx.empty or "pair" not in fx.columns:
        return None
    r = fx[fx["pair"] == "usd_krw"]
    if r.empty:
        return None
    rate = _mkt_num(r.iloc[0].get("rate"))
    return f"{rate:,.0f}" if rate is not None else None


def _basket_stats(data: dict, spec: dict) -> dict | None:
    """바스켓(자산군 일부)의 브레드스·리더·러거드 산출. {n, up, lead, lag} 또는 None.
    lead/lag = (이름, 등락률%). 전부 실시세 change_pct 기반(작문 없음)."""
    df = data.get(spec["group"], pd.DataFrame())
    if not isinstance(df, pd.DataFrame) or df.empty or "change_pct" not in df.columns:
        return None
    sub = df
    if spec.get("sectors") and "sector" in df.columns:
        sub = df[df["sector"].isin(spec["sectors"])]
    rows = []
    labels = spec.get("labels")
    for _, r in sub.iterrows():
        c = _mkt_num(r.get("change_pct"))
        if c is None:
            continue
        nm = labels.get(r.get("name")) if labels else (r.get("name") or r.get("ticker"))
        rows.append((str(nm), c))
    if not rows:
        return None
    rows.sort(key=lambda x: x[1], reverse=True)
    up = sum(1 for _, c in rows if c > 0)
    return {"n": len(rows), "up": up, "lead": rows[0], "lag": rows[-1]}


def _theme_body(data: dict, theme: dict) -> str:
    """카드 본문 — 실시세 팩트만. 금리·달러는 레벨/방향, 그 외는 브레드스+리더·러거드."""
    if theme.get("rates"):
        dxy = _grp_change(data, "fx", "pair", "dxy")
        tnx = _grp_change(data, "benchmarks", "ticker", "^TNX")
        parts = []
        if dxy is not None:
            parts.append(f"DXY {dxy:+.2f}%")
        krw = _usdkrw_level(data)
        if krw:
            parts.append(f"USD/KRW {krw}원")
        if tnx is not None:
            parts.append(f"美10Y {tnx:+.2f}%")
        return " · ".join(parts) if parts else "환율·금리 데이터 준비 중"
    spec = theme.get("basket") or {}
    s = _basket_stats(data, spec)
    if not s:
        return "데이터 준비 중"
    noun = spec.get("noun", "종목")
    lead_nm, lead_c = s["lead"]
    body = f"{noun} {s['n']}종 중 {s['up']}종 상승 · 리더 {lead_nm} {lead_c:+.1f}%"
    lag_nm, lag_c = s["lag"]
    if s["n"] >= 2 and lag_c < 0:
        body += f" · 러거드 {lag_nm} {lag_c:+.1f}%"
    return body


def _mkt_num(v):
    try:
        x = float(v)
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return None


_MG_CSS = """<style>
.mg-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:2px 0 14px}
@media(max-width:760px){.mg-row{grid-template-columns:1fr}}
.mg-card{display:block;background:#16181F;border:1px solid #262A33;border-radius:16px;padding:14px 16px;
  box-shadow:0 6px 18px rgba(0,0,0,.25);text-decoration:none !important;transition:border-color .15s,transform .1s}
.mg-card:hover{border-color:#D9A441;transform:translateY(-1px)}
.mg-region{font-size:10px;font-weight:900;color:#7E8694;letter-spacing:.06em;text-transform:uppercase;
  margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.mg-go{font-size:10px;font-weight:800;color:#7E8694;text-transform:none}
.mg-card:hover .mg-go{color:#D9A441}
.mg-rep{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.mg-replbl{font-size:11px;font-weight:750;color:#7E8694}
.mg-pct{font-size:20px;font-weight:950;font-family:'SF Mono',ui-monospace,monospace}
.mg-pct.pos{color:#F25560}.mg-pct.neg{color:#4D90F0}.mg-pct.flat{color:#9AA0AD}
.mg-br{font-size:11.5px;font-weight:750;color:#9AA0AD;margin-top:8px;font-variant-numeric:tabular-nums}
.mg-br .up{color:#F25560}.mg-br .dn{color:#4D90F0}
.mg-lead{font-size:11px;font-weight:700;color:#7E8694;margin-top:4px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-theme-chip{font-size:10.5px;font-weight:850;border-radius:999px;padding:2px 8px;margin-left:8px;
  font-variant-numeric:tabular-nums;vertical-align:middle}
.mkt-theme-chip.pos{background:rgba(242,85,96,.13);color:#F25560}
.mkt-theme-chip.neg{background:rgba(77,144,240,.13);color:#4D90F0}
.mg-mini{display:flex;gap:5px;margin-top:8px;flex-wrap:wrap}
.mg-mini span{font-size:10px;font-weight:850;padding:2px 8px;border-radius:999px;
  border:1px solid #262A33;color:#9AA0AD;font-variant-numeric:tabular-nums}
.mg-mini .up{color:#F25560}.mg-mini .dn{color:#4D90F0}
</style>"""


def _market_glance_html(data: dict, suffix: str = "") -> str:
    """시장 한눈 3카드(미국·한국·매크로): 대표지수 등락 + breadth + 리더 — data에서 자동 산출.
    카드 클릭 시 쿼리파라미터로 해당 서브탭 이동."""
    _slug = {"미국": "us", "한국": "kr", "원자재": "commodities"}
    def _stats(chgs, names):
        pairs = [(n, _mkt_num(c)) for n, c in zip(names, chgs) if _mkt_num(c) is not None]
        up = sum(1 for _, c in pairs if c > 0)
        dn = sum(1 for _, c in pairs if c < 0)
        leader = max(pairs, key=lambda x: x[1]) if pairs else (None, None)
        return up, dn, leader[0], leader[1]

    bm = data.get("benchmarks", pd.DataFrame())
    us = data.get("us_stocks", pd.DataFrame())
    kr = data.get("kr_stocks", pd.DataFrame())
    cm = data.get("commodities", pd.DataFrame())

    def _bmchg(tk):
        if bm.empty: return None
        r = bm[bm["ticker"] == tk]
        return _mkt_num(r.iloc[0].get("change_pct")) if not r.empty else None

    rows = []
    # 미국
    u_up, u_dn, u_ln, u_lc = _stats(
        us["change_pct"].tolist() if not us.empty else [],
        us["name"].tolist() if (not us.empty and "name" in us.columns) else [])
    rows.append(("미국", "나스닥100", _bmchg("QQQ"), u_up, u_dn, u_ln, u_lc))
    # 한국
    try:
        from ui.pages.kr_stocks import _bench_prices as _krb
        kospi = _mkt_num((_krb().get("^KS11") or {}).get("change_pct"))
    except Exception:
        kospi = None
    k_up, k_dn, k_ln, k_lc = _stats(
        kr["change_pct"].tolist() if not kr.empty else [],
        kr["name"].tolist() if (not kr.empty and "name" in kr.columns) else [])
    rows.append(("한국", "코스피", kospi, k_up, k_dn, k_ln, k_lc))
    # 매크로
    try:
        from ui.pages.commodities import _META as _CMETA
    except Exception:
        _CMETA = {}
    gold = None
    if not cm.empty:
        r = cm[cm["name"] == "gold"]
        gold = _mkt_num(r.iloc[0].get("change_pct")) if not r.empty else None
    cnames = [_CMETA.get(n, (n,))[0] for n in cm["name"].tolist()] if not cm.empty else []
    c_up, c_dn, c_ln, c_lc = _stats(cm["change_pct"].tolist() if not cm.empty else [], cnames)
    rows.append(("원자재", "금", gold, c_up, c_dn, c_ln, c_lc))

    # 카드별 미니칩 — 구 '오늘의 핵심 지표' 펄스칩을 해당 시장 카드에 흡수(별도 섹션 제거)
    minis = {
        "미국": [("S&P500", _grp_change(data, "benchmarks", "ticker", "SPY")),
                 ("반도체", _grp_change(data, "benchmarks", "ticker", "SOXX"))],
        "한국": [("USD/KRW", _grp_change(data, "fx", "pair", "usd_krw"))],
        "원자재": [("BTC", _grp_change(data, "crypto", "ticker", "BTC-USD"))],
    }

    html = ""
    for region, lbl, rep, up, dn, ln, lc in rows:
        cls = "pos" if (rep or 0) > 0 else ("neg" if (rep or 0) < 0 else "flat")
        rep_s = f"{rep:+.2f}%" if rep is not None else "—"
        lead = f"리더 {ln} {lc:+.1f}%" if ln and lc is not None else "리더 —"
        href = f"?market_tab={_slug.get(region, 'summary')}{suffix}"
        mini_html = ""
        chips = [(n, v) for n, v in minis.get(region, []) if v is not None]
        if chips:
            mini_html = '<div class="mg-mini">' + "".join(
                f'<span>{n} <span class="{"up" if v > 0 else ("dn" if v < 0 else "")}">{v:+.2f}%</span></span>'
                for n, v in chips) + '</div>'
        title = "원자재·크립토" if region == "원자재" else region
        html += (f'<a class="mg-card" href="{href}" data-mkt-tab="{region}" target="_self">'
                 f'<div class="mg-region">{title} <span class="mg-go">자세히 →</span></div>'
                 f'<div class="mg-rep"><span class="mg-replbl">{lbl}</span>'
                 f'<span class="mg-pct {cls}">{rep_s}</span></div>'
                 f'<div class="mg-br"><span class="up">상승 {up}</span> · <span class="dn">하락 {dn}</span></div>'
                 f'<div class="mg-lead">{lead}</div>{mini_html}</a>')
    return _MG_CSS + f'<div class="mg-row">{html}</div>'


def _build_news_grid(data: dict) -> str:
    """테마 카드 — 본문·배지·순서 모두 실시세 파생. 당일 |대표 등락률| 큰 테마부터 노출."""
    built = []
    for theme in _THEMES:
        lbl, group, col, val = theme["chip"]
        chg = _grp_change(data, group, col, val)
        built.append({"theme": theme, "chip_lbl": lbl, "chip": chg,
                      "body": _theme_body(data, theme)})
    # 노출 순서: 당일 |등락률| 큰 순(값 없는 테마는 뒤로) — 상위 3개만(나머지는 '전체 비교'가 담당)
    built.sort(key=lambda b: abs(b["chip"]) if b["chip"] is not None else -1.0, reverse=True)
    built = built[:3]

    cards_html = ""
    for b in built:
        cls = {"alert": "alert-card", "good": "good-card", "warn": "warn-card"}.get(b["theme"]["tone"], "")
        chip_html = ""
        if b["chip"] is not None:
            v = b["chip"]
            ccls = "pos" if v > 0 else ("neg" if v < 0 else "")
            chip_html = f'<span class="mkt-theme-chip {ccls}">{b["chip_lbl"]} {v:+.2f}%</span>'
        cards_html += (
            f'<div class="mkt-news-card {cls}">'
            f'<h4>{b["theme"]["title"]}{chip_html}</h4>'
            f'<p>{b["body"]}</p>'
            f'</div>'
        )
    return f'<div class="mkt-news-grid">{cards_html}</div>'


# ── 레짐 헤드라인 + 근거 신호 스트립 HTML 빌더 ───────────────────────────────

_REGIME_TONE = {"good": "rg-good", "watch": "rg-watch", "risk": "rg-risk"}


def _regime_headline_html(direction: str, note: str, tone: str) -> str:
    """한 줄 슬림 바 — 큰 카드는 전체현황 다이제스트와 중복이라 축약(방향+한줄 노트만)."""
    from html import escape
    cls = _REGIME_TONE.get(tone, "rg-watch")
    return (
        f'<div class="rg-slim {cls}">'
        f'<span class="rg-k">오늘 시장</span>'
        f'<span class="rg-dir">{escape(direction)}</span>'
        f'<span class="rg-note">{escape(note)}</span>'
        f'</div>'
    )


def _regime_signals_strip_html(signals: list[dict]) -> str:
    """판정 근거 신호 칩 — expander 내부용(제목은 expander 라벨이 담당)."""
    from ui.pages.risk_signals import _SIG_KOR
    order = {"high": 0, "mid": 1, "low": 2, "na": 3}
    lab = {"high": "위험", "mid": "주의", "low": "완충", "na": "중립"}
    sigs = sorted(signals, key=lambda s: order.get(s.get("col", "na"), 3))
    chips = "".join(
        f'<span class="rg-sig rg-{s.get("col","na")}">'
        f'{_SIG_KOR.get(s["signal"], s["signal"])} · {lab.get(s.get("col","na"),"중립")}</span>'
        for s in sigs
    )
    return f'<div class="rg-sigs">{chips}</div>'


def _exposure_bridge_html(suffix: str) -> str:
    """이 국면이 내 노출에 뭘 의미? — 로그인 시만 노출되는 가벼운 링크 1줄(시장=general 유지)."""
    if st.session_state.get("auth_role") == "guest" or not st.session_state.get("username"):
        return ""
    qs = ("?" + suffix.removeprefix("&")) if suffix else ""
    href = f"/risk{qs}"
    return (
        f'<a class="rg-bridge" href="{href}" target="_self">'
        f'이 국면에서 내 노출은? · 리스크 진단 →</a>'
    )


# ── Main render ───────────────────────────────────────────────────────────────

def _live_section(suffix: str = "") -> None:
    # 스파크라인·목표주가 병렬 로드 제거 — 소비처(카테고리 블록)가 사라진 뒤 로딩 비용만 유발했음
    ph = show_skeleton()
    data = load_market_data()
    ph.empty()

    # ── 레짐 슬림 바 + 근거 expander (전체현황 다이제스트와 중복 → 한 줄 축약) ──────
    from ui.components.regime import regime_verdict
    _rg = regime_verdict(data)
    st.markdown(_regime_headline_html(_rg["direction"], _rg["note"], _rg["tone"]), unsafe_allow_html=True)
    if _rg.get("signals"):
        with st.expander("왜 — 판정 근거", expanded=False):
            st.markdown(_regime_signals_strip_html(_rg["signals"]), unsafe_allow_html=True)

    # ── 시장 한눈 3카드 — 대표 등락·breadth·리더 + 핵심지표 미니칩(구 펄스칩 흡수) ────
    st.markdown(mkt_section_header("시장 한눈", "핵심 3개 시장 — 대표 등락·breadth·리더·핵심지표 · 클릭 시 이동"),
                unsafe_allow_html=True)
    st.markdown(_market_glance_html(data, suffix), unsafe_allow_html=True)

    # ── 테마별 시장 동향 — 실시세 파생, 당일 |등락률| 상위 3개만 ─────────────────────
    st.markdown(mkt_section_header("테마별 시장 동향", "오늘 등락 큰 테마 3개"), unsafe_allow_html=True)
    st.markdown(
        f'<div class="mkt-card mkt-theme-first">{_build_news_grid(data)}</div>',
        unsafe_allow_html=True,
    )

    # '카테고리별 시장 분석'(TOP12 순환)은 '전체' 탭과 중복 → 무버는 '전체' 탭 단일 소스로 통합.
    # 개별 종목 애널리스트 노트는 미국/한국/매크로 탭의 '애널리스트 전망'에서 확인.
    # (전체 비교 안내는 상단 뷰 토글로 일원화 — 중복 링크·캡션 제거)

    # ── 로그인 전용 '내 노출' 브리지 — 시장은 general 유지, 단 1줄 ─────────────────
    st.markdown(_exposure_bridge_html(suffix), unsafe_allow_html=True)


# ── 쿼리파라미터 기반 서브탭 (딥링크·카드 클릭 이동 지원) ──────────────────────
# 자산군 7개만 일반 탭으로. '요약/전체'는 탭이 아니라 진입 기본 화면 + 뷰 토글로 흡수.
_MARKET_TABS = [
    ("미국", "us"), ("한국", "kr"), ("ETF", "etf"), ("원자재", "commodities"),
    ("크립토", "crypto"), ("외환", "fx"), ("채권·금리", "rates"),
]
def _market_suffix() -> str:
    """탭 링크에 세션(로그인/게스트) 유지용 파라미터 부착."""
    role = st.session_state.get("auth_role")
    user = st.session_state.get("username", "")
    if role == "guest":
        return "&_auth=guest"
    if user:
        from core.auth_token import user_param
        return f"&{user_param(user)}"
    return ""


@st.fragment
def _market_summary_all(suffix: str, initial_view: str) -> None:
    """요약 ⇄ 전체 비교 — 토글 위젯+뷰를 한 fragment 로 묶어 누를 때 이 섹션만 부분 렌더
    (페이지 전체 재실행·CSS 재주입·스크롤 점프 제거). 초기값은 쿼리파라미터(딥링크 진입)."""
    from ui.pages import major_movers
    # 미국 ETF / 한국 ETF 와 동일 양식 — st.radio horizontal(전역 radiogroup 골드칩 스타일 공유) + 우측 정렬
    _idx = 1 if initial_view == "all" else 0
    _sel = st.radio(
        "시장 뷰", ["한눈에 요약", "전체 비교"], index=_idx, horizontal=True,
        key="mkt_view_radio", label_visibility="collapsed",
    ) or "한눈에 요약"
    if _sel == "전체 비교":
        from ui.components.all_markets import all_markets_html
        st.markdown(all_markets_html(load_market_data(), suffix), unsafe_allow_html=True)
        # 전 자산군 급등·급락 순위 상세는 기본 접힘(토글)
        if st.toggle("급등·급락 순위 전체 보기 (전 자산군 상세)", key="all_movers_detail", value=False):
            major_movers.render(embedded=True)
    else:
        _live_section(suffix)


def render() -> None:
    L.viewport_width()          # 폭 먼저 확정 → 모바일 리플로우 최소화
    L.inject_responsive_css()   # 페이지당 1회 (시장 탭 전체 공통)
    inject_css()
    mark_active_nav("/market")
    st.markdown(_MARKET_LOCAL_CSS, unsafe_allow_html=True)
    st.html("""
<script>
(function(){
  if (window.__siminvestMarketWheelBound) return;
  window.__siminvestMarketWheelBound = true;
  window.addEventListener("message", function(event){
    if (!event.data || event.data.type !== "siminvest:marketWheel") return;
    var scroller = document.querySelector("section.main") || document.scrollingElement || document.documentElement;
    if (scroller && typeof event.data.deltaY === "number") {
      scroller.scrollBy({top:event.data.deltaY, left:0, behavior:"auto"});
    }
  });
})();
</script>
""")

    # 최상위 '시장' 배너는 제거 — 제목은 상단 네비와 중복, 부제(전 자산군)는 바로 아래 탭과 중복.
    # (서브탭별 배너 us_stocks/kr_stocks 등은 탭 식별용이라 유지)

    from ui.pages import us_stocks, kr_stocks, commodities, fx_rates, crypto, etf  # major_movers 는 _market_summary_all fragment 내부에서 import

    # 자산군 탭 — 클라이언트사이드 st.radio(인세션 리런). 과거 <a href=?market_tab=> 하드네비는
    # 리버스 프록시 뒤에서 /market 풀로드가 홈으로 오라우팅돼 멈췄다(Streamlit 멀티페이지 딥링크 한계).
    # 라디오는 풀 리로드 없이 이 세션에서 다시 그려 정상 동작. 요약/전체비교 토글과 동일 양식.
    _asset_tabs = {s for _, s in _MARKET_TABS}
    _tab_labels = ["요약"] + [l for l, _ in _MARKET_TABS]
    _tab_slugs  = [""]     + [s for _, s in _MARKET_TABS]
    _entry = st.query_params.get("market_tab", "")     # 딥링크 진입(가능 시)용 초기값
    _idx = _tab_slugs.index(_entry) if _entry in _tab_slugs else 0
    _sel = st.radio(
        "시장 자산군", _tab_labels, index=_idx, horizontal=True,
        key="mkt_asset_tab", label_visibility="collapsed",
    ) or "요약"
    active = _tab_slugs[_tab_labels.index(_sel)]
    # 사용률 계측(세션당 탭 1회, best-effort) — 시장 탭 가지치기 판단용
    from core.usage_log import log_tab_view
    log_tab_view("market", active or "summary")
    suffix = _market_suffix()

    # 시장한눈 카드(.mg-card)의 '자세히' 클릭을 위 라디오 선택으로 위임(하드네비 풀리로드 회피).
    # 카드 data-mkt-tab(미국/한국/원자재) == 라디오 라벨 텍스트라 그대로 매칭해 클릭.
    import streamlit.components.v1 as _components
    _components.html(
        """
<script>
(function(){
  var pdoc=window.parent.document, pwin=window.parent;
  if(pwin.__svMktCardBridge) return; pwin.__svMktCardBridge=true;
  pdoc.addEventListener('click', function(e){
    var card=e.target.closest('.mg-card[data-mkt-tab]');
    if(!card) return;
    if(e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey) return;
    e.preventDefault(); e.stopPropagation();
    var tab=card.getAttribute('data-mkt-tab');
    var rg=pdoc.querySelector('[role=radiogroup]');
    if(!rg) return;
    var lbl=[].slice.call(rg.querySelectorAll('label')).filter(function(l){return l.textContent.trim()===tab;})[0];
    if(lbl) lbl.click();
  }, true);
})();
</script>
""",
        height=0,
    )

    if active in _asset_tabs:
        # 자산군 7개 탭
        if active == "us":
            us_stocks.render(embedded=True)
        elif active == "kr":
            kr_stocks.render(embedded=True)
        elif active == "crypto":
            crypto.render(embedded=True)
        elif active == "etf":
            etf.render(embedded=True)
        elif active == "commodities":
            commodities.render(embedded=True)
        elif active == "fx":
            fx_rates.render(embedded=True, section="fx")
        elif active == "rates":
            fx_rates.render_rates(embedded=True)
    else:
        # 진입 기본 화면 = 요약/전체. 토글은 fragment 안의 위젯 — 누르면 페이지 전체가 아니라
        # 이 섹션만 다시 그린다(하드 nav·CSS 재주입·스크롤 점프 제거). 초기값은 쿼리파라미터(딥링크).
        _market_summary_all(suffix, "all" if active == "all" else "summary")

    glossary_expander("MA20 이격", "breadth", "추세", "상승여력", "감지 임계값")
    st.markdown(jj_footer(), unsafe_allow_html=True)
