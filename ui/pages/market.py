"""
시장 분석 — 카테고리별 상위 변동 종목, 애널리스트 노트, 목표가, 스파크라인
"""
from __future__ import annotations

import html as html_lib
import json

import pandas as pd
import streamlit as st

import layout as L  # 반응형(뷰포트 감지 + 모바일 CSS)
from data.loader import load_market_data, batch_history
from ui.components.dash_style import (
    glossary_expander,
    inject_css, show_skeleton, mkt_stats_chips,
    mark_active_nav, mkt_page_header, mkt_section_header, jj_footer,
)

# ── Category candidate pools ──────────────────────────────────────────────────
# (key, display_name, src)  src: "us"|"kr"|"comm"|"fx"|"crypto"
_MAX_CATEGORY_ITEMS = 12
_POOL_VERSION = "market-top12-v1"

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

_BRAND_CLASSES = {
    "NVDA": "brand-green",
    "TSM": "brand-blue",
    "AMD": "brand-red",
    "AVGO": "brand-red",
    "MU": "brand-violet",
    "ASML": "brand-blue",
    "QCOM": "brand-blue",
    "INTC": "brand-blue",
    "AMAT": "brand-violet",
    "LRCX": "brand-dark",
    "KLAC": "brand-gold",
    "ARM": "brand-blue",
    "MSFT": "brand-blue",
    "AAPL": "brand-dark",
    "META": "brand-blue",
    "AMZN": "brand-gold",
    "GOOGL": "brand-violet",
    "TSLA": "brand-red",
    "NFLX": "brand-red",
    "ORCL": "brand-red",
    "CRM": "brand-blue",
    "ADBE": "brand-red",
    "IBM": "brand-blue",
    "NOW": "brand-green",
    "000660": "brand-red",
    "005930": "brand-blue",
    "207940": "brand-blue",
    "005380": "brand-blue",
    "000270": "brand-dark",
    "051910": "brand-red",
    "006400": "brand-blue",
    "035420": "brand-green",
    "105560": "brand-gold",
    "055550": "brand-blue",
    "373220": "brand-blue",
    "005490": "brand-dark",
}

_METAL_VISUALS = {
    "gold": ("Au", "metal-gold"),
    "silver": ("Ag", "metal-silver"),
    "copper": ("Cu", "metal-copper"),
    "wti_crude": ("Oil", "metal-energy"),
    "brent_crude": ("Oil", "metal-energy"),
    "natural_gas": ("Gas", "metal-energy"),
    "platinum": ("Pt", "metal-silver"),
    "palladium": ("Pd", "metal-silver"),
    "corn": ("Corn", "metal-gold"),
    "wheat": ("Wht", "metal-gold"),
    "soybeans": ("Soy", "metal-green"),
    "coffee": ("Cof", "metal-copper"),
}

_FX_VISUALS = {
    "usd_krw": ("₩/$", "fx-krw"),
    "jpy_krw": ("¥/₩", "fx-krw"),
    "eur_krw": ("€/₩", "fx-dxy"),
    "usd_jpy": ("$/¥", "fx-dxy"),
    "dxy": ("DXY", "fx-dxy"),
    "us10y": ("10Y", "fx-rate"),
    "us5y": ("5Y", "fx-rate"),
    "us30y": ("30Y", "fx-rate"),
    "vix": ("VIX", "fx-rate"),
    "tlt": ("TLT", "fx-dxy"),
    "uup": ("UUP", "fx-dxy"),
    "hyg": ("HYG", "fx-rate"),
}

_CRYPTO_VISUALS = {
    "BTC-USD": ("BTC", "coin-btc"),
    "ETH-USD": ("ETH", "coin-eth"),
    "SOL-USD": ("SOL", "coin-sol"),
    "BNB-USD": ("BNB", "coin-btc"),
    "XRP-USD": ("XRP", "coin-sol"),
    "DOGE-USD": ("DOGE", "coin-btc"),
    "ADA-USD": ("ADA", "coin-eth"),
    "AVAX-USD": ("AVAX", "coin-sol"),
    "LINK-USD": ("LINK", "coin-eth"),
    "BCH-USD": ("BCH", "coin-btc"),
    "LTC-USD": ("LTC", "coin-eth"),
    "DOT-USD": ("DOT", "coin-sol"),
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
.mkt-cat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.mkt-cat-block{
  background:rgba(22,24,31,0.60);border:1px solid rgba(38,42,51,0.85);border-radius:20px;
  padding:0;overflow:hidden;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  box-shadow:0 4px 18px rgba(0,0,0,0.30);position:relative}
.mkt-cat-head{display:flex;justify-content:space-between;align-items:center;
  padding:13px 16px 10px;position:relative;z-index:2}
.mkt-cat-head h4{margin:0;color:#E7E9EE;font-size:14px;font-weight:900;letter-spacing:-0.02em}
.mkt-cat-head .cat-dir{font-size:11px;font-weight:800;display:flex;align-items:center;gap:4px}
.cat-dir.pos{color:#F25560}.cat-dir.neg{color:#4D90F0}.cat-dir.neu{color:#7E8694}
.mkt-cat-rows{padding:0 10px 10px;display:grid;gap:6px;position:relative;z-index:2}

/* detail row */
details.mkt-det{border-radius:12px;overflow:hidden}
details.mkt-det summary{
  position:relative;list-style:none;display:grid;
  grid-template-columns:auto minmax(0,1fr) auto auto auto;
  align-items:center;gap:9px;overflow:hidden;
  padding:9px 11px;border-radius:12px;cursor:pointer;
  border:1px solid rgba(38,42,51,0.8);
  backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
  transition:filter 0.12s}
details.mkt-det summary > *{position:relative;z-index:1}
details.mkt-det summary::-webkit-details-marker{display:none}
details.mkt-det summary:hover{filter:brightness(1.18)}
details.mkt-det[open] summary{border-radius:12px 12px 0 0;border-bottom:none}
.mkt-det-main{min-width:0}
.mkt-det-name{display:block;font-size:12px;font-weight:900;color:#E7E9EE;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-det-code{display:block;margin-top:1px;color:#7E8694;font-size:9.5px;font-weight:800;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-det-chg{font-size:13px;font-weight:850;font-family:'SF Mono',ui-monospace,monospace;
  white-space:nowrap;flex-shrink:0}
.mkt-det-chg.pos{color:#F25560}.mkt-det-chg.neg{color:#4D90F0}.mkt-det-chg.neu{color:#7E8694}
.mkt-det-tp{font-size:10px;font-weight:700;color:#7E8694;white-space:nowrap;flex-shrink:0}
.mkt-det-arrow{font-size:13px;color:#7E8694;transition:transform 0.18s;flex-shrink:0}
details.mkt-det[open] .mkt-det-arrow{transform:rotate(90deg)}
.mkt-det-spark{position:absolute!important;z-index:0!important;right:8px;top:2px;bottom:2px;
  width:50%;display:flex;align-items:center;justify-content:flex-end;opacity:0.24;pointer-events:none}
.mkt-det-spark svg{width:100%;height:100%}
.mkt-logo{position:relative;z-index:1;flex:0 0 32px;width:32px;height:32px;border-radius:8px;overflow:hidden;
  display:grid;place-items:center;background:#1E2029;border:1px solid #262A33;color:#E7E9EE;
  font-size:9.5px;font-weight:950;text-align:center;line-height:1}
.brand-red{background:linear-gradient(135deg,#d74333,#f2a15c);color:#fff}
.brand-dark{background:linear-gradient(135deg,#222831,#6f7c84);color:#fff}
.brand-blue{background:linear-gradient(135deg,#1f5fae,#61b4dc);color:#fff}
.brand-green{background:linear-gradient(135deg,#186c5f,#8acb91);color:#fff}
.brand-violet{background:linear-gradient(135deg,#4942a4,#b65bcf);color:#fff}
.brand-gold{background:linear-gradient(135deg,#9b6a16,#e6b84d);color:#251607}
.mkt-logo-metal{border-radius:50%;border:0;font-size:11px;box-shadow:inset 0 2px 8px rgba(255,255,255,0.48),inset 0 -6px 10px rgba(0,0,0,0.14)}
.metal-gold{background:radial-gradient(circle at 31% 28%,#fff6b8,#e6ac2f 54%,#9a6617);color:#4a2b0b}
.metal-silver{background:radial-gradient(circle at 31% 28%,#ffffff,#cdd8de 55%,#758590);color:#293842}
.metal-copper{background:radial-gradient(circle at 31% 28%,#ffd7b0,#bd6c36 56%,#6d351d);color:#38180b}
.metal-green{background:radial-gradient(circle at 31% 28%,#e8ffd8,#88b95a 56%,#4a6e2e);color:#1f3515}
.metal-energy{background:radial-gradient(circle at 31% 28%,#d7f1ff,#376f8a 58%,#16394d);color:#f8fbfa}
.fx-krw{background:linear-gradient(135deg,#214f70,#9fcbd3);color:#fff}
.fx-dxy{background:linear-gradient(135deg,#34404a,#95a5a6);color:#fff}
.fx-rate{background:linear-gradient(135deg,#9b3f39,#e8892f);color:#fff}
.coin-btc{background:linear-gradient(135deg,#f7931a,#ffca68);color:#3b2100}
.coin-eth{background:linear-gradient(135deg,#627eea,#9fb2ff);color:#111a3a}
.coin-sol{background:linear-gradient(135deg,#14f195,#9945ff);color:#10131f}

/* row background tints */
summary.pos-bg{background:rgba(242,85,96,0.12);border-color:rgba(242,85,96,0.28)!important}
summary.neg-bg{background:rgba(77,144,240,0.11);border-color:rgba(77,144,240,0.26)!important}
summary.neu-bg{background:rgba(255,255,255,0.04);border-color:rgba(38,42,51,0.7)!important}

/* expanded body */
.mkt-det-body{background:rgba(14,15,19,0.92);border:1px solid rgba(38,42,51,0.7);
  border-top:none;border-radius:0 0 12px 12px;padding:11px 13px}
.mkt-det-note{font-size:12px;color:#9AA0AD;line-height:1.65;font-weight:650}

.mkt-theme-first{margin:2px 0 18px}
.mkt-theme-first .mkt-news-grid{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}

/* interactive category analysis */
.mkt-category-root{display:grid;gap:16px}
.mkt-summary-panel{
  border:1px solid rgba(38,42,51,0.9);border-radius:20px;padding:14px 16px;
  background:linear-gradient(135deg,rgba(22,24,31,0.95),rgba(30,32,41,0.85));
  box-shadow:0 3px 14px rgba(0,0,0,0.25)
}
.mkt-summary-title{font-size:12px;font-weight:950;color:#E7E9EE;margin-bottom:7px}
.mkt-summary-body{margin:0;color:#9AA0AD;font-size:12px;line-height:1.62;font-weight:700}
.mkt-summary-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.mkt-summary-chip{display:inline-flex;align-items:center;gap:4px;padding:5px 8px;border-radius:999px;
  border:1px solid rgba(38,42,51,0.95);background:rgba(255,255,255,0.05);font-size:10px;font-weight:900;color:#9AA0AD}
.mkt-summary-chip.pos{color:#F25560;background:rgba(242,85,96,0.10);border-color:rgba(242,85,96,0.24)}
.mkt-summary-chip.neg{color:#4D90F0;background:rgba(77,144,240,0.10);border-color:rgba(77,144,240,0.24)}
.mkt-summary-chip.warn{color:#D9A441;background:rgba(217,164,65,0.12);border-color:rgba(217,164,65,0.28)}
.mkt-category-root .mkt-cat-grid{grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
.mkt-category-root .mkt-cat-block{min-height:354px;background:rgba(22,24,31,0.68)}
.mkt-category-root .mkt-cat-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;
  align-items:start;padding:13px 14px 6px}
.mkt-head-main{min-width:0}.mkt-head-line{display:flex;align-items:center;gap:8px;min-width:0}
.mkt-head-line h4{margin:0;color:#E7E9EE;font-size:14px;font-weight:950;letter-spacing:-0.01em}
.mkt-status{display:inline-flex;align-items:center;padding:4px 7px;border-radius:999px;font-size:10px;font-weight:950;
  border:1px solid rgba(38,42,51,0.95);background:rgba(255,255,255,0.04);color:#7E8694}
.mkt-status.pos{background:rgba(242,85,96,0.10);color:#F25560;border-color:rgba(242,85,96,0.24)}
.mkt-status.neg{background:rgba(77,144,240,0.10);color:#4D90F0;border-color:rgba(77,144,240,0.24)}
.mkt-status.warn{background:rgba(217,164,65,0.12);color:#D9A441;border-color:rgba(217,164,65,0.28)}
.mkt-cat-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}
.cat-range,.cat-avg{font-size:10px;font-weight:900;border-radius:999px;padding:4px 7px;border:1px solid rgba(38,42,51,0.9);
  background:rgba(255,255,255,0.04);color:#7E8694}
.cat-avg.pos{color:#F25560;background:rgba(242,85,96,0.10);border-color:rgba(242,85,96,0.2)}
.cat-avg.neg{color:#4D90F0;background:rgba(77,144,240,0.10);border-color:rgba(77,144,240,0.2)}
.cat-avg.neu{color:#7E8694}
.mkt-cat-controls{display:flex;gap:5px;align-items:center;padding-top:1px}
.mkt-rot-btn{width:28px;height:28px;border-radius:10px;border:1px solid rgba(38,42,51,0.95);
  background:rgba(255,255,255,0.05);color:#9AA0AD;font-size:17px;font-weight:900;line-height:1;cursor:pointer}
.mkt-rot-btn:hover{background:rgba(255,255,255,0.1);color:#E7E9EE}
.mkt-cat-block[data-rotation="off"] .mkt-rot-btn{opacity:.32;pointer-events:none}
.mkt-cat-rows{padding:0 12px 9px;display:grid;grid-auto-rows:min-content;align-content:start;gap:7px;min-height:207px}
.mkt-cat-rows.is-changing{opacity:.48;transform:translateY(2px);transition:opacity .16s ease,transform .16s ease}
.mkt-mover-row{
  appearance:none;border:1px solid rgba(38,42,51,0.9);border-radius:14px;background:rgba(255,255,255,0.04);
  min-height:62px;width:100%;display:grid;grid-template-columns:32px minmax(0,1fr) 84px 102px 12px;
  align-items:center;gap:8px;padding:8px 9px;position:relative;overflow:hidden;text-align:left;cursor:pointer;
  box-shadow:0 2px 9px rgba(0,0,0,0.20);transition:background .14s ease,border-color .14s ease,transform .14s ease}
.mkt-mover-row:before{content:"";position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:0 4px 4px 0;background:transparent}
.mkt-mover-row:hover{background:rgba(255,255,255,0.07);transform:translateY(-1px)}
.mkt-mover-row.selected{background:rgba(217,164,65,0.10);border-color:rgba(217,164,65,0.30)}
.mkt-mover-row.selected:before{background:#D9A441}
.mkt-mover-row.pos-bg{background:rgba(242,85,96,0.09)}
.mkt-mover-row.neg-bg{background:rgba(77,144,240,0.09)}
.mkt-mover-row .mkt-logo{width:32px;height:32px;border-radius:9px;z-index:2}
.mkt-row-main{min-width:0;z-index:2}
.mkt-row-name{display:block;font-size:12px;font-weight:950;color:#E7E9EE;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-row-code{display:block;margin-top:2px;color:#7E8694;font-size:9.5px;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-price{z-index:2;min-width:0}.mkt-price span,.mkt-row-metric span{display:block;color:#7E8694;font-size:9px;font-weight:900;line-height:1.15}
.mkt-price b{display:block;margin-top:3px;color:#E7E9EE;font-size:11px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-price em{display:block;margin-top:2px;font-style:normal;font-size:10px;font-weight:950;font-family:'SF Mono',ui-monospace,monospace}
.mkt-price em.pos{color:#F25560}.mkt-price em.neg{color:#4D90F0}.mkt-price em.neu{color:#7E8694}
.mkt-row-metric{position:relative;min-height:43px;display:flex;flex-direction:column;justify-content:center;align-items:flex-end;
  text-align:right;overflow:hidden;z-index:1}
.mkt-row-metric b{position:relative;z-index:2;margin-top:2px;max-width:100%;color:#9AA0AD;font-size:10.5px;font-weight:950;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-row-metric em{position:relative;z-index:2;margin-top:2px;max-width:100%;font-style:normal;color:#7E8694;font-size:9.5px;
  font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mkt-row-metric.pos b,.mkt-row-metric.pos em{color:#F25560}
.mkt-row-metric.neg b,.mkt-row-metric.neg em{color:#4D90F0}
.mkt-row-metric.warn b,.mkt-row-metric.warn em{color:#D9A441}
.mkt-row-chart{position:absolute;inset:1px -8px 0 auto;width:94px;height:44px;opacity:.25;z-index:1;display:flex;align-items:center;justify-content:flex-end}
.mkt-row-chart svg{width:94px;height:44px}.mkt-row-chevron{color:#7E8694;font-size:15px;font-weight:950;z-index:2}
.mkt-note-panel{margin:0 12px 12px;min-height:83px;border-radius:15px;border:1px solid rgba(38,42,51,0.9);
  background:linear-gradient(135deg,rgba(30,32,41,0.96),rgba(22,24,31,0.9));padding:11px 12px;box-shadow:inset 0 1px 0 rgba(255,255,255,0.04)}
.mkt-note-panel[data-empty="true"]{display:flex;align-items:center;color:#7E8694;font-size:11px;font-weight:850}
.mkt-note-top{display:flex;justify-content:space-between;gap:8px;align-items:start;margin-bottom:5px}
.mkt-note-title{font-size:11px;font-weight:950;color:#E7E9EE}
.mkt-note-close{border:0;background:rgba(255,255,255,0.06);width:22px;height:22px;border-radius:8px;color:#9AA0AD;
  font-size:15px;font-weight:950;cursor:pointer;line-height:1}
.mkt-note-text{margin:0;color:#9AA0AD;font-size:11px;line-height:1.55;font-weight:720;display:-webkit-box;-webkit-line-clamp:3;
  -webkit-box-orient:vertical;overflow:hidden}
@media(max-width:920px){
  details.mkt-det summary{grid-template-columns:auto minmax(0,1fr) auto auto;gap:8px}
  .mkt-det-tp{display:none}
  .mkt-det-spark{width:58%;opacity:0.18}
  .mkt-category-root .mkt-cat-grid{grid-template-columns:1fr}
  .mkt-mover-row{grid-template-columns:32px minmax(0,1fr) 78px 94px 12px}
}
@media(max-width:640px){
  .mkt-summary-panel{padding:14px 15px;border-radius:18px}
  .mkt-summary-title{font-size:15px}
  .mkt-summary-body{font-size:12px;line-height:1.55}
  .mkt-category-root .mkt-cat-grid{grid-template-columns:minmax(0,1fr);gap:10px}
  .mkt-category-root .mkt-cat-block{min-height:0;border-radius:17px}
  .mkt-category-root .mkt-cat-head{grid-template-columns:1fr;gap:7px;padding:12px 12px 6px}
  .mkt-cat-controls{justify-content:flex-start}
  .mkt-cat-rows{padding:0 10px 8px;gap:6px;min-height:0}
  .mkt-mover-row{grid-template-columns:30px minmax(0,1fr) 68px 10px;min-height:56px;gap:7px;padding:7px}
  .mkt-price{display:none}
  .mkt-row-metric{min-height:38px}
  .mkt-row-metric b{font-size:10px}
  .mkt-row-metric em{font-size:9px}
  .mkt-row-chart{width:72px;height:38px;opacity:.16}
  .mkt-row-chart svg{width:72px;height:38px}
  .mkt-note-panel{margin:0 10px 10px;min-height:0;padding:10px}
  .mkt-note-text{-webkit-line-clamp:4}
}
/* '한눈에 요약 / 전체 비교' 뷰 토글 = 미국/한국 ETF 라디오와 동일 양식(전역 radiogroup 골드칩) + 우측 정렬(period_radio 와 동일) */
[data-testid="stElementContainer"]:has(>[data-testid="stRadio"]){width:100%!important}
[data-testid="stRadio"]{display:flex!important;width:100%!important;justify-content:flex-end!important}
[data-testid="stRadio"] div[role="radiogroup"]{justify-content:flex-end!important;flex-wrap:wrap}
div[data-testid="stButtonGroup"] button[data-testid^="stBaseButton-segmented_control"]{
  background:transparent!important;border:none!important;border-radius:0!important;box-shadow:none!important;
  border-bottom:2px solid transparent!important;color:#9AA0AD!important;
  font-size:14px!important;font-weight:700!important;padding:8px 2px!important;margin:0!important}
div[data-testid="stButtonGroup"] button[data-testid^="stBaseButton-segmented_control"]:hover{color:#E7E9EE!important}
div[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"]{
  color:#E7E9EE!important;border-bottom-color:#D9A441!important}
</style>"""


# ── Data helpers ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _instrument_data(pool_version: str = _POOL_VERSION) -> tuple[dict[str, list[float]], dict[str, dict]]:
    """풀 전 티커 1년 히스토리 1회 배치 → (스파크라인, 시세). price_source 단일 진입점(batch_history) 경유."""
    key_to_ticker: dict[str, str] = {}
    for pool in _CAT_POOLS.values():
        for key, _, src in pool:
            key_to_ticker[key] = _spark_ticker_for(key, src)
    tickers = list(dict.fromkeys(key_to_ticker.values()))
    hist = batch_history(",".join(tickers), "1y")
    if not hist:
        return {}, {}

    sparks: dict[str, list[float]] = {}
    quotes: dict[str, dict] = {}
    for key, tk in key_to_ticker.items():
        df = hist.get(tk)
        if df is None:
            continue
        series = df["Close"].dropna()
        if len(series) < 2:
            continue
        weekly = series.resample("W").last().dropna()
        if len(weekly) >= 2:
            base = float(weekly.iloc[0]) or 1.0
            sparks[key] = [(float(v) / base - 1) * 100 for v in weekly]
        price = float(series.iloc[-1])
        prev  = float(series.iloc[-2])
        chg   = price - prev
        quotes[key] = {
            "ticker": tk, "price": price, "prev_close": prev,
            "change": chg, "change_pct": chg / prev * 100 if prev else 0.0,
        }
    return sparks, quotes


def _instrument_sparklines(pool_version: str = _POOL_VERSION) -> dict[str, list[float]]:
    sparks, _ = _instrument_data(pool_version)
    return sparks


def _market_pool_quotes(pool_version: str = _POOL_VERSION) -> dict[str, dict]:
    _, quotes = _instrument_data(pool_version)
    return quotes


def _fetch_target_prices(pool_version: str = _POOL_VERSION) -> dict[str, float]:
    from data.loader import load_target_prices
    return load_target_prices()


def _escape(value) -> str:
    return html_lib.escape(str(value or ""))


def _ticker_key(code: str) -> str:
    return str(code or "").replace(".KS", "").replace(".KQ", "").upper()


def _spark_ticker_for(key: str, src: str) -> str:
    if src in {"us", "kr", "crypto"}:
        return key
    return _INSTRUMENT_SPARK_TICKERS.get(key, key)


def _market_logo_html(item: dict) -> str:
    key = str(item.get("key", ""))
    src = str(item.get("src", ""))
    name = str(item.get("name", ""))

    if src == "comm":
        label, cls = _METAL_VISUALS.get(key, ("Com", "metal-energy"))
        return f'<span class="mkt-logo mkt-logo-metal {cls}">{_escape(label)}</span>'

    if src == "fx":
        label, cls = _FX_VISUALS.get(key, (key[:3].upper() or "FX", "fx-dxy"))
        return f'<span class="mkt-logo {cls}">{_escape(label)}</span>'

    if src == "crypto":
        label, cls = _CRYPTO_VISUALS.get(key, (_ticker_key(key)[:3] or "COIN", "coin-btc"))
        return f'<span class="mkt-logo {cls}">{_escape(label)}</span>'

    ticker = _ticker_key(key)
    cls = _BRAND_CLASSES.get(ticker, "brand-dark")
    fallback = (ticker[:4] if src == "us" else name[:2]) or ticker[:4] or "LOGO"
    return f'<span class="mkt-logo {cls}">{_escape(fallback)}</span>'


def _fmt_chg(v) -> tuple[str, str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—", "neu"
    if isinstance(v, str) and v.strip().upper() in {"", "N/A", "NA", "NONE", "—", "-"}:
        return "—", "neu"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v), "neu"
    sign = "+" if f >= 0 else ""
    cls = "pos" if f > 0.05 else ("neg" if f < -0.05 else "neu")
    return f"{sign}{f:.2f}%", cls


def _get_chg(maps: dict, key: str, src: str):
    """Return (change_pct, price) from data maps."""
    row = _get_row(maps, key, src)
    if row is None:
        return None, None
    if src == "fx":
        return row.get("change_pct"), row.get("rate")
    return row.get("change_pct"), row.get("price")


def _get_row(maps: dict, key: str, src: str):
    if src == "comm":
        return maps.get("comm", {}).get(key)
    if src == "fx":
        return maps.get("fx", {}).get(key)
    return maps.get(src, {}).get(key)


def _mini_sparkline_svg(values: list[float], width: int = 90, height: int = 36) -> str:
    """Safe SVG sparkline using only <path> elements."""
    if len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    span = mx - mn or 0.1
    terminal = float(values[-1])
    if terminal > 3:
        color = "#F25560"
    elif terminal < -3:
        color = "#4D90F0"
    else:
        color = "#5f7f86"
    pad = 2

    pts = []
    for i, v in enumerate(values):
        x = pad + (i / (len(values) - 1)) * (width - 2 * pad)
        y = (height - pad) - ((v - mn) / span) * (height - 2 * pad)
        pts.append((x, y))

    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = line_d + f" L {width - pad},{height} L {pad},{height} Z"
    last_x, last_y = pts[-1]

    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<path d="{area_d}" fill="{color}" fill-opacity="0.24"/>'
        f'<path d="{line_d}" stroke="{color}" stroke-width="2.1" fill="none" stroke-opacity="0.92" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.1" fill="{color}" fill-opacity="0.86"/>'
        f'</svg>'
    )


# ── HTML builders ─────────────────────────────────────────────────────────────

def _build_maps(data: dict) -> dict[str, dict]:
    maps: dict[str, dict] = {}
    for src, col, id_col in [
        ("us", "us_stocks", "ticker"),
        ("kr", "kr_stocks", "ticker"),
        ("crypto", "crypto", "ticker"),
    ]:
        df = data.get(col, pd.DataFrame())
        if not df.empty and id_col in df.columns:
            maps[src] = {r[id_col]: dict(r) for _, r in df.iterrows()}

    comm_df = data.get("commodities", pd.DataFrame())
    if not comm_df.empty and "name" in comm_df.columns:
        maps["comm"] = {r["name"]: dict(r) for _, r in comm_df.iterrows()}

    fx_df = data.get("fx", pd.DataFrame())
    if not fx_df.empty and "pair" in fx_df.columns:
        maps["fx"] = {r["pair"]: dict(r) for _, r in fx_df.iterrows()}

    return maps


def _num(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.replace(",", "").strip()
        if text.upper() in {"", "N/A", "NA", "NONE", "—", "-"}:
            return None
        value = text
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _macro_value(data: dict, key: str) -> float | None:
    df = data.get("macro", pd.DataFrame())
    if df is None or df.empty or "key" not in df.columns:
        return None
    row = df[df["key"] == key]
    if row.empty:
        return None
    return _num(row.iloc[0].get("value"))


def _normalize_price(value, key: str) -> float | None:
    f = _num(value)
    if f is None:
        return None
    # Yahoo rate indices such as ^TNX/^FVX/^TYX are often yield x 10.
    if key in {"us10y", "us5y", "us30y"} and f > 20:
        return f / 10
    return f


def _fmt_price(value, src: str, key: str) -> str:
    f = _normalize_price(value, key)
    if f is None:
        return "가격 데이터 대기"
    if key in {"us10y", "us5y", "us30y"}:
        return f"{f:.2f}%"
    if key in {"usd_krw", "jpy_krw", "eur_krw"}:
        return f"{f:,.0f}원"
    if key == "usd_jpy":
        return f"{f:,.2f}엔"
    if key in {"tlt", "uup", "hyg"}:
        return f"${f:,.2f}"
    if src == "fx":
        return f"{f:,.2f}"
    if src == "kr":
        return f"{f:,.0f}원"
    if src == "crypto":
        return f"${f:,.0f}" if abs(f) >= 1000 else f"${f:,.2f}"
    if src == "comm":
        return f"${f:,.2f}"
    return f"${f:,.2f}"


def _trend_metric(values: list[float]) -> tuple[str, str]:
    if not values:
        return "1년 추세 대기", "neu"
    terminal = float(values[-1])
    sign = "+" if terminal >= 0 else ""
    cls = "pos" if terminal > 3 else ("neg" if terminal < -3 else "neu")
    return f"1년 추세 {sign}{terminal:.1f}%", cls


def _pressure_state(key: str, price: float | None) -> tuple[str, str, str]:
    if price is None:
        return "상태 확인 중", "지표 대기", "neu"
    if key == "usd_krw":
        if price >= 1450:
            return "환율 부담 높음", "원화 변동성 확인", "warn"
        if price >= 1350:
            return "환율 부담 중간", "수급 영향 관찰", "warn"
        return "환율 부담 낮음", "완충 요인", "pos"
    if key == "dxy":
        if price >= 104:
            return "달러 강세 부담", "신흥국 압력", "warn"
        if price >= 100:
            return "달러 강세 중립", "방향 확인", "neu"
        return "달러 약세 완충", "원자재 우호", "pos"
    if key in {"us10y", "us5y", "us30y"}:
        if price >= 4.5:
            return "금리 부담 높음", "성장주 압력", "warn"
        if price >= 3.8:
            return "금리 부담 중간", "밸류에이션 확인", "warn"
        return "금리 부담 낮음", "위험선호 완충", "pos"
    if key == "vix":
        if price >= 25:
            return "변동성 부담 높음", "위험회피 확인", "warn"
        if price >= 18:
            return "변동성 중간", "시장 민감도 관찰", "warn"
        return "변동성 안정", "위험선호 완충", "pos"
    if key == "tlt":
        return "장기채 흐름", "금리 방향 참고", "neu"
    if key == "uup":
        return "달러 ETF", "달러 압력 참고", "neu"
    if key == "hyg":
        return "신용스프레드 참고", "위험선호 확인", "neu"
    return "상태 확인 중", "지표 대기", "neu"


def _asset_metric(item: dict, target_prices: dict[str, float] | None, sparks: dict[str, list[float]]) -> tuple[str, str, str, str]:
    key = str(item["key"])
    src = str(item["src"])
    price = _normalize_price(item.get("price"), key)

    if src in {"us", "kr"}:
        target = _num((target_prices or {}).get(key))
        if target and price and price > 0:
            upside = (target / price - 1) * 100
            sign = "+" if upside >= 0 else ""
            currency = "$" if src == "us" else ""
            suffix = "" if src == "us" else "원"
            tone = "pos" if upside > 0 else "neg"
            return "목표가", f"{currency}{target:,.0f}{suffix}", f"여력 {sign}{upside:.1f}%", tone
        if src == "kr":
            return "목표가", "컨센서스 없음", "수급 확인", "neu"
        return "목표가", "미제공", "추정치 확인", "neu"

    if src == "fx":
        state, sub, tone = _pressure_state(key, price)
        return "상태", state, sub, tone

    trend, tone = _trend_metric(sparks.get(key, []))
    if src == "comm":
        return "기준", "선물 가격", trend, tone
    if src == "crypto":
        return "상태", "최근 흐름", trend, tone
    return "상태", "확인 필요", "데이터 대기", "neu"


@st.cache_data(ttl=86400, show_spinner=False)   # 컨센서스는 일 단위 안정 → 24h
def _consensus_notes(tickers_key: str) -> dict:
    """종목별 컨센서스 팩트 노트 {ticker: note}. DB(배치) 우선 + 라이브 폴백. 주식(us/kr)만 값이 있다."""
    from data.loader import load_consensus_targets
    from src.analyst_naver import consensus_notes_from_df
    return consensus_notes_from_df(load_consensus_targets([t for t in tickers_key.split(",") if t]))


def _item_note(item: dict, notes: dict) -> str:
    """카드 노트 — 주식은 네이버 컨센서스(투자의견·목표가·기준일), 그 외는 중립 가이드.
    하드코딩/작문 해설은 쓰지 않는다."""
    note = notes.get(str(item["key"]))
    if note:
        return note
    if item["src"] in ("comm", "fx", "crypto"):
        return "애널리스트 컨센서스 미제공 자산 · 가격·달러·금리 흐름과 함께 확인하세요."
    return "네이버 컨센서스 미연결 · 가격·거래량·업종 모멘텀을 함께 확인하세요."


def _category_payload(data: dict, sparks: dict[str, list[float]], target_prices: dict[str, float] | None = None) -> list[dict]:
    maps = _build_maps(data)
    quote_fallbacks = _market_pool_quotes(_POOL_VERSION)
    categories: list[dict] = []

    # 주식(us/kr) 종목만 네이버 컨센서스 노트 — 비주식(원자재·환율·크립토)엔 컨센서스 없음
    _stock_tks = sorted({k for pool in _CAT_POOLS.values() for (k, _n, s) in pool if s in ("us", "kr")})
    notes = _consensus_notes(",".join(_stock_tks))

    for cat, pool in _CAT_POOLS.items():
        raw_items = []
        for key, dname, src in pool:
            chg, price = _get_chg(maps, key, src)
            quote = quote_fallbacks.get(key, {})
            if _normalize_price(price, key) is None:
                price = quote.get("price")
            if _num(chg) is None:
                chg = quote.get("change_pct")
            if key == "us10y" and _normalize_price(price, key) is None:
                price = _macro_value(data, "us_10y")
            row = _get_row(maps, key, src) or {}
            ticker = row.get("ticker") or quote.get("ticker") or _spark_ticker_for(key, src)
            price_num = _normalize_price(price, key)
            chg_num = _num(chg)
            chg_txt, chg_cls = _fmt_chg(chg)
            metric_label, metric_value, metric_sub, metric_tone = _asset_metric(
                {"key": key, "src": src, "price": price}, target_prices, sparks
            )
            spark_html = _mini_sparkline_svg(sparks.get(key, []), width=130, height=46)
            raw_items.append({
                "id": key,
                "key": key,
                "name": dname,
                "src": src,
                "ticker": ticker,
                "priceValue": price_num,
                "priceLabel": _fmt_price(price, src, key),
                "changeValue": chg_num,
                "changeLabel": chg_txt,
                "changeClass": chg_cls,
                "metricLabel": metric_label,
                "metricValue": metric_value,
                "metricSub": metric_sub,
                "metricTone": metric_tone,
                "logoHtml": _market_logo_html({"key": key, "src": src, "name": dname}),
                "sparkHtml": spark_html,
                "note": _item_note({"key": key, "src": src, "name": dname}, notes),
            })

        raw_items.sort(key=lambda x: abs(x["changeValue"] or 0), reverse=True)
        raw_items = raw_items[:_MAX_CATEGORY_ITEMS]
        for idx, item in enumerate(raw_items, start=1):
            item["rank"] = idx

        top3 = raw_items[:3]
        valid = [x["changeValue"] for x in top3 if x["changeValue"] is not None]
        avg = sum(valid) / len(valid) if valid else 0
        if cat == "금리·환율":
            pressure_items = [x for x in raw_items if x["metricTone"] == "warn"]
            if len(pressure_items) >= 2:
                status, status_cls = "압력", "warn"
            elif pressure_items:
                status, status_cls = "중립", "warn"
            else:
                status, status_cls = "완충", "pos"
        elif avg > 0.35:
            status, status_cls = "강세", "pos"
        elif avg < -0.35:
            status, status_cls = "약세", "neg"
        else:
            status, status_cls = "혼조", "neu"

        categories.append({
            "name": cat,
            "status": status,
            "statusClass": status_cls,
            "topAverage": avg,
            "rotationEnabled": len(raw_items) > 3,
            "items": raw_items,
        })

    return categories


def _market_summary_html(categories: list[dict]) -> str:
    if not categories:
        return ""
    strong = [c for c in categories if c.get("topAverage", 0) > 0.35 and c["name"] != "금리·환율"]
    weak = [c for c in categories if c.get("topAverage", 0) < -0.35 and c["name"] != "금리·환율"]
    strong.sort(key=lambda x: x.get("topAverage", 0), reverse=True)
    weak.sort(key=lambda x: x.get("topAverage", 0))
    strong_txt = ", ".join(c["name"] for c in strong[:2]) or "뚜렷한 강세 없음"
    weak_txt = ", ".join(c["name"] for c in weak[:2]) or "뚜렷한 약세 없음"

    fx = next((c for c in categories if c["name"] == "금리·환율"), None)
    pressure = "금리·환율 지표는 중립권에서 방향 확인이 필요합니다."
    if fx:
        warn_items = [i["name"] for i in fx["items"] if i.get("metricTone") == "warn"]
        if warn_items:
            pressure = f"{', '.join(warn_items[:2])} 흐름은 성장주와 원화자산 변동성에 부담 요인으로 볼 수 있습니다."

    body = (
        f"강세 축은 {strong_txt}, 약세 축은 {weak_txt}입니다. "
        f"{pressure} 각 카테고리의 변동 상위 종목과 현재가격, 목표가 또는 대체 지표를 함께 확인하세요."
    )
    chips = [
        ("강세", strong_txt, "pos"),
        ("약세", weak_txt, "neg"),
        ("압력", pressure.replace(" 흐름은 성장주와 원화자산 변동성에 부담 요인으로 볼 수 있습니다.", ""), "warn"),
    ]
    chip_html = "".join(
        f'<span class="mkt-summary-chip {cls}">{_escape(label)} · {_escape(text)}</span>'
        for label, text, cls in chips
    )
    return (
        '<div class="mkt-summary-panel">'
        '<div class="mkt-summary-title">오늘의 시장 요약</div>'
        f'<p class="mkt-summary-body">{_escape(body)}</p>'
        f'<div class="mkt-summary-chips">{chip_html}</div>'
        '</div>'
    )


def _build_category_blocks(data: dict, sparks: dict[str, list[float]], target_prices: dict[str, float] | None = None) -> str:
    categories = _category_payload(data, sparks, target_prices)
    if not categories:
        return ""

    payload = json.dumps(categories, ensure_ascii=False).replace("</", "<\\/")
    payload_attr = html_lib.escape(payload, quote=True)
    blocks = ""
    for idx, category in enumerate(categories):
        rotation = "on" if category["rotationEnabled"] else "off"
        blocks += (
            f'<section class="mkt-cat-block" data-cat-index="{idx}" data-rotation="{rotation}">'
            '<div class="mkt-cat-head">'
            '<div class="mkt-head-main">'
            '<div class="mkt-head-line">'
            f'<h4>{_escape(category["name"])}</h4>'
            f'<span class="mkt-status {category["statusClass"]}">{_escape(category["status"])}</span>'
            '</div>'
            '<div class="mkt-cat-meta">'
            '<span class="cat-range">상위 변동 1–3 / -</span>'
            '<span class="cat-avg neu">현재 표시 종목 평균 —</span>'
            '</div>'
            '</div>'
            '<div class="mkt-cat-controls">'
            '<button class="mkt-rot-btn" type="button" data-dir="-1" aria-label="이전 순위">‹</button>'
            '<button class="mkt-rot-btn" type="button" data-dir="1" aria-label="다음 순위">›</button>'
            '</div>'
            '</div>'
            '<div class="mkt-cat-rows"><div style="color:#879497;font-size:11px;font-weight:850;padding:12px">시장 데이터 정리 중...</div></div>'
            '<div class="mkt-note-panel" data-empty="true">종목을 선택하면 분석 노트가 여기에 표시됩니다.</div>'
            '</section>'
        )

    return (
        f'<div id="mkt-category-root" class="mkt-category-root" data-categories="{payload_attr}">'
        f'{_market_summary_html(categories)}'
        f'<div class="mkt-cat-grid">{blocks}</div>'
        '</div>'
    )


def _category_interaction_script() -> str:
    return """
<script>
(function(){
  if (window.__simMktTimers) {
    window.__simMktTimers.forEach(function(id){ clearTimeout(id); });
  }
  window.__simMktTimers = [];

  function later(fn, ms) {
    var id = setTimeout(fn, ms);
    window.__simMktTimers.push(id);
    return id;
  }
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function(ch) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[ch];
    });
  }
  function pct(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    var n = Number(value);
    return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
  }
  function avgClass(value) {
    if (value > 0.05) return "pos";
    if (value < -0.05) return "neg";
    return "neu";
  }
  function rowBg(changeClass) {
    if (changeClass === "pos") return "pos-bg";
    if (changeClass === "neg") return "neg-bg";
    return "neu-bg";
  }

  function init() {
    var root = document.getElementById("mkt-category-root");
    if (!root) {
      later(init, 80);
      return;
    }
    if (root.dataset.bound === "true") return;
    root.dataset.bound = "true";

    var categories = [];
    try {
      categories = JSON.parse(root.getAttribute("data-categories") || "[]");
    } catch (err) {
      return;
    }

    var PAGE_SIZE = 3;
    var INITIAL_DELAY = 5000;
    var INTERVAL = 10000;
    var controllers = [];

    function closeOthers(active) {
      controllers.forEach(function(ctrl) {
        if (ctrl !== active) ctrl.closeNote(true);
      });
    }

    root.querySelectorAll(".mkt-cat-block").forEach(function(card) {
      var index = Number(card.getAttribute("data-cat-index"));
      var category = categories[index];
      if (!category) return;

      var rowsEl = card.querySelector(".mkt-cat-rows");
      var rangeEl = card.querySelector(".cat-range");
      var avgEl = card.querySelector(".cat-avg");
      var noteEl = card.querySelector(".mkt-note-panel");
      var buttons = card.querySelectorAll(".mkt-rot-btn");
      var items = category.items || [];
      var pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
      var state = { page: 0, selectedId: null, hover: false, timer: null };

      function stop() {
        if (state.timer) clearTimeout(state.timer);
        state.timer = null;
      }
      function canRotate() {
        return category.rotationEnabled && pages > 1 && !state.hover && !state.selectedId;
      }
      function schedule(ms) {
        stop();
        if (!category.rotationEnabled || pages <= 1) return;
        state.timer = later(function() {
          if (!canRotate()) {
            schedule(1000);
            return;
          }
          state.page = (state.page + 1) % pages;
          render(true);
          schedule(INTERVAL);
        }, ms);
      }
      function visibleItems() {
        var start = state.page * PAGE_SIZE;
        return items.slice(start, start + PAGE_SIZE);
      }
      function updateMeta(slice) {
        var start = state.page * PAGE_SIZE + 1;
        var end = Math.min(items.length, state.page * PAGE_SIZE + slice.length);
        rangeEl.textContent = "상위 변동 " + start + "–" + end + " / " + items.length;
        var valid = slice.map(function(item){ return item.changeValue; })
          .filter(function(v){ return v != null && !Number.isNaN(Number(v)); });
        var avg = valid.length ? valid.reduce(function(a,b){ return a + Number(b); }, 0) / valid.length : null;
        avgEl.className = "cat-avg " + avgClass(avg || 0);
        avgEl.textContent = "현재 표시 종목 평균 " + pct(avg);
      }
      function renderNote(item) {
        if (!item) {
          noteEl.setAttribute("data-empty", "true");
          noteEl.innerHTML = "종목을 선택하면 분석 노트가 여기에 표시됩니다.";
          return;
        }
        noteEl.removeAttribute("data-empty");
        noteEl.innerHTML = [
          '<div class="mkt-note-top">',
          '<div class="mkt-note-title">선택 종목 분석 · ', esc(item.name), '</div>',
          '<button class="mkt-note-close" type="button" aria-label="분석 닫기">×</button>',
          '</div>',
          '<p class="mkt-note-text">', esc(item.note), '</p>'
        ].join("");
        var closeBtn = noteEl.querySelector(".mkt-note-close");
        if (closeBtn) {
          closeBtn.addEventListener("click", function(event) {
            event.stopPropagation();
            state.selectedId = null;
            render(false);
            schedule(10000);
          });
        }
      }
      function render(soft) {
        var slice = visibleItems();
        if (state.selectedId && !slice.some(function(item){ return item.id === state.selectedId; })) {
          state.selectedId = null;
        }
        updateMeta(slice);
        if (soft) {
          rowsEl.classList.add("is-changing");
          later(function(){ rowsEl.classList.remove("is-changing"); }, 160);
        }
        rowsEl.innerHTML = slice.map(function(item) {
          var selected = item.id === state.selectedId ? " selected" : "";
          var spark = item.sparkHtml || '<span style="color:#9fadb0;font-size:9px;font-weight:900">차트 대기</span>';
          return [
            '<button class="mkt-mover-row ', rowBg(item.changeClass), selected, '" type="button" data-id="', esc(item.id), '">',
            item.logoHtml || "",
            '<span class="mkt-row-main">',
            '<span class="mkt-row-name">', esc(item.name), '</span>',
            '<span class="mkt-row-code">', esc(item.ticker), '</span>',
            '</span>',
            '<span class="mkt-price">',
            '<span>현재가</span>',
            '<b>', esc(item.priceLabel), '</b>',
            '<em class="', esc(item.changeClass), '">', esc(item.changeLabel), '</em>',
            '</span>',
            '<span class="mkt-row-metric ', esc(item.metricTone), '">',
            '<span>', esc(item.metricLabel), '</span>',
            '<b>', esc(item.metricValue), '</b>',
            '<em>', esc(item.metricSub), '</em>',
            '<span class="mkt-row-chart">', spark, '</span>',
            '</span>',
            '<span class="mkt-row-chevron">›</span>',
            '</button>'
          ].join("");
        }).join("");
        rowsEl.querySelectorAll(".mkt-mover-row").forEach(function(row) {
          row.addEventListener("click", function() {
            var id = row.getAttribute("data-id");
            var item = items.find(function(x){ return x.id === id; });
            if (!item) return;
            if (state.selectedId === id) {
              state.selectedId = null;
              render(false);
              schedule(10000);
              return;
            }
            closeOthers(controller);
            stop();
            state.selectedId = id;
            render(false);
            renderNote(item);
          });
        });
        var selected = items.find(function(x){ return x.id === state.selectedId; });
        renderNote(selected || null);
      }
      function go(delta) {
        if (pages <= 1) return;
        state.selectedId = null;
        state.page = (state.page + delta + pages) % pages;
        render(true);
        schedule(INTERVAL);
      }
      function closeNote(resume) {
        if (!state.selectedId) return;
        state.selectedId = null;
        render(false);
        if (resume) schedule(10000);
      }

      var controller = { closeNote: closeNote };
      controllers.push(controller);

      buttons.forEach(function(btn) {
        btn.addEventListener("click", function(event) {
          event.stopPropagation();
          go(Number(btn.getAttribute("data-dir") || 1));
        });
      });
      card.addEventListener("mouseenter", function() {
        state.hover = true;
        stop();
      });
      card.addEventListener("mouseleave", function() {
        state.hover = false;
        if (!state.selectedId) schedule(INTERVAL);
      });

      render(false);
      schedule(INITIAL_DELAY);
    });
  }

  init();
})();
</script>
"""


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

    html = ""
    for region, lbl, rep, up, dn, ln, lc in rows:
        cls = "pos" if (rep or 0) > 0 else ("neg" if (rep or 0) < 0 else "flat")
        rep_s = f"{rep:+.2f}%" if rep is not None else "—"
        lead = f"리더 {ln} {lc:+.1f}%" if ln and lc is not None else "리더 —"
        href = f"?market_tab={_slug.get(region, 'summary')}{suffix}"
        html += (f'<a class="mg-card" href="{href}" target="_self">'
                 f'<div class="mg-region">{region} <span class="mg-go">자세히 →</span></div>'
                 f'<div class="mg-rep"><span class="mg-replbl">{lbl}</span>'
                 f'<span class="mg-pct {cls}">{rep_s}</span></div>'
                 f'<div class="mg-br"><span class="up">상승 {up}</span> · <span class="dn">하락 {dn}</span></div>'
                 f'<div class="mg-lead">{lead}</div></a>')
    return _MG_CSS + f'<div class="mg-row">{html}</div>'


def _build_news_grid(data: dict) -> str:
    """테마 카드 — 본문·배지·순서 모두 실시세 파생. 당일 |대표 등락률| 큰 테마부터 노출."""
    built = []
    for theme in _THEMES:
        lbl, group, col, val = theme["chip"]
        chg = _grp_change(data, group, col, val)
        built.append({"theme": theme, "chip_lbl": lbl, "chip": chg,
                      "body": _theme_body(data, theme)})
    # 노출 순서: 당일 |등락률| 큰 순(값 없는 테마는 뒤로)
    built.sort(key=lambda b: abs(b["chip"]) if b["chip"] is not None else -1.0, reverse=True)

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


# ── Main render ───────────────────────────────────────────────────────────────

def _pulse_chips(data: dict) -> str:
    """요약 상단 — 대표 지수/환율/원자재/크립토 1D 변동 칩.
    (HTML 문자열만 반환하는 순수 함수 — 렌더를 안 하므로 @st.fragment 는 무의미해 제거.
     덕분에 요약/전체 토글을 fragment 로 감싸도 중첩 크래시가 없음.)"""
    def _chg(key, col, val):
        df = data.get(key, pd.DataFrame())
        if not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
            return None
        r = df[df[col] == val]
        if r.empty:
            return None
        c = r.iloc[0].get("change_pct")
        return float(c) if isinstance(c, (int, float)) and not pd.isna(c) else None

    specs = [
        ("나스닥100", "benchmarks", "ticker", "QQQ"),
        ("S&P500",   "benchmarks", "ticker", "SPY"),
        ("반도체",    "benchmarks", "ticker", "SOXX"),
        ("USD/KRW",  "fx",          "pair",   "usd_krw"),
        ("금",        "commodities", "name",   "gold"),
        ("비트코인",  "crypto",      "ticker", "BTC-USD"),
    ]
    items = []
    for label, key, col, val in specs:
        c = _chg(key, col, val)
        if c is None:
            continue
        sign = "+" if c >= 0 else ""
        items.append({"label": label, "value": f"{sign}{c:.2f}%",
                      "cls": "pos" if c > 0 else ("neg" if c < 0 else "neu")})
    return mkt_stats_chips(items) if items else ""


def _live_section(suffix: str = "") -> None:
    from concurrent.futures import ThreadPoolExecutor as _TPE
    ph = show_skeleton()
    with _TPE(max_workers=3) as _ex:
        _fd = _ex.submit(load_market_data)
        _fs = _ex.submit(_instrument_sparklines, _POOL_VERSION)
        _ft = _ex.submit(_fetch_target_prices, _POOL_VERSION)
        data = _fd.result()
        sparks = _fs.result()
        target_prices = _ft.result()
    ph.empty()

    # 오늘의 핵심 지표 펄스 (요약 상단 — 지수·환율·원자재·크립토 1D)
    pulse = _pulse_chips(data)
    if pulse:
        st.markdown(mkt_section_header("오늘의 핵심 지표", "지수 · 환율 · 원자재 · 크립토 · 1D"), unsafe_allow_html=True)
        st.markdown(pulse, unsafe_allow_html=True)

    # ── 시장 한눈 3카드 (핵심 3개 시장) — 빠른 브리핑. 전 자산군 상세는 '전체' 탭 ──────
    st.markdown(mkt_section_header("시장 한눈", "핵심 3개 시장(미국·한국·원자재) — 대표 등락·breadth·리더 · 클릭 시 이동"),
                unsafe_allow_html=True)
    st.markdown(_market_glance_html(data, suffix), unsafe_allow_html=True)

    # ── 테마별 시장 동향 — 본문·배지·순서 모두 실시세 파생(당일 |등락률| 큰 순) ──────
    st.markdown(mkt_section_header("테마별 시장 동향", "오늘 먼저 볼 흐름 · 등락 큰 순"), unsafe_allow_html=True)
    st.markdown(
        f'<div class="mkt-card mkt-theme-first">{_build_news_grid(data)}</div>',
        unsafe_allow_html=True,
    )

    # '카테고리별 시장 분석'(TOP12 순환)은 '전체' 탭과 중복 → 무버는 '전체' 탭 단일 소스로 통합.
    # 개별 종목 애널리스트 노트는 미국/한국/매크로 탭의 '애널리스트 전망'에서 확인.
    # (전체 비교 안내는 상단 뷰 토글로 일원화 — 중복 링크·캡션 제거)


# ── 쿼리파라미터 기반 서브탭 (딥링크·카드 클릭 이동 지원) ──────────────────────
# 자산군 7개만 일반 탭으로. '요약/전체'는 탭이 아니라 진입 기본 화면 + 뷰 토글로 흡수.
_MARKET_TABS = [
    ("미국", "us"), ("한국", "kr"), ("ETF", "etf"), ("원자재", "commodities"),
    ("크립토", "crypto"), ("외환", "fx"), ("채권·금리", "rates"),
]
_TABBAR_CSS = """<style>
.mkt-tabbar{display:flex;gap:16px;border-bottom:1px solid #262A33;margin:2px 0 16px;flex-wrap:wrap}
.mkt-tabbar a{font-size:14px;font-weight:700;color:#9AA0AD;text-decoration:none !important;
  padding:8px 2px;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .15s,border-color .15s;white-space:nowrap}
.mkt-tabbar a:hover{color:#E7E9EE}
.mkt-tabbar a.active{color:#E7E9EE;border-bottom-color:#D9A441}
/* 개요(요약·전체) | 자산군 그룹 구분선 */
.mkt-tab-div{width:1px;align-self:center;height:15px;background:#262A33;margin:0 2px}
/* 좁은 화면: 줄바꿈 대신 가로 스크롤(한 줄 유지) */
@media(max-width:760px){
  .mkt-tabbar{flex-wrap:nowrap;overflow-x:auto;gap:14px;-webkit-overflow-scrolling:touch}
  .mkt-tabbar::-webkit-scrollbar{height:0}
}
</style>"""


def _market_suffix() -> str:
    """탭 링크에 세션(로그인/게스트) 유지용 파라미터 부착."""
    role = st.session_state.get("auth_role")
    user = st.session_state.get("username", "")
    if role == "guest":
        return "&_auth=guest"
    if user:
        return f"&_user={user}"
    return ""


def _market_tab_bar(active: str, suffix: str) -> str:
    parts = []
    for label, slug in _MARKET_TABS:
        parts.append(
            f'<a class="{"active" if slug == active else ""}" '
            f'href="?market_tab={slug}{suffix}" target="_self">{label}</a>'
        )
    return _TABBAR_CSS + f'<div class="mkt-tabbar">{"".join(parts)}</div>'


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

    st.markdown(
        mkt_page_header("📊", "시장", "전 자산군 — 미국 · 한국 · ETF · 원자재 · 크립토 · 외환 · 채권/금리"),
        unsafe_allow_html=True,
    )

    from ui.pages import us_stocks, kr_stocks, commodities, fx_rates, crypto, etf  # major_movers 는 _market_summary_all fragment 내부에서 import

    # 쿼리파라미터 기반 서브탭 — st.tabs 대신(딥링크·시장 한눈 카드 클릭 이동 지원)
    _asset_tabs = {s for _, s in _MARKET_TABS}
    active = st.query_params.get("market_tab", "")
    suffix = _market_suffix()
    st.markdown(_market_tab_bar(active, suffix), unsafe_allow_html=True)

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
