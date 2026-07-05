import html as html_lib
import math
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import streamlit as st
import pandas as pd
import layout as L  # 반응형(뷰포트 감지 + 모바일 CSS)
from data.loader import load_market_data, batch_close_history
from core.journey import pct_weight  # 비중(%) 정수 기본 포맷(전 화면 공통)
from ui.components.dash_style import (
    inject_css, jj_footer, mark_active_nav, show_skeleton, color_change, mkt_section_header,
)
from ui.components.portfolio_treemap import portfolio_treemap
from siminvest_theme import DOWN  # 하락=파랑 (벤치마크 막대 음수 처리)
from format import won, currency as _cur  # 금액 표기 단일 출처
from ui.components.live_refresh import live_refresh, live_badge_html
from ui.pages.portfolio_guest import _render_guest_portfolio
from ui.pages.portfolio_format import (_parse_price_num, _krw_short, _num, _price,
                                       _pct, _escape, _ticker_key, _issuer_from_name,
                                       _first, _money, _fmt_qty, _tone, _norm_name)
from ui.pages.portfolio_css import (_PORT_CSS, _AJ_CSS, _AT_CSS,
                                    _ASEC_CSS, _PB_CSS, _ONBOARD_CSS)


def _fetch_target_prices() -> dict[str, float]:
    from data.loader import load_target_prices
    return load_target_prices()


@st.cache_data(ttl=86400, show_spinner=False)   # 컨센서스는 일 단위 안정 → 24h
def _consensus_notes(tickers_key: str) -> dict:
    """종목별 컨센서스 팩트 노트 {ticker: note}. DB(배치) 우선 + 라이브 폴백(하드코딩 해설 대체)."""
    from data.loader import load_consensus_targets
    from src.analyst_naver import consensus_notes_from_df
    return consensus_notes_from_df(load_consensus_targets([t for t in tickers_key.split(",") if t]))


_COMM_KOR = {
    "gold": "금",
    "silver": "은",
    "copper": "구리",
    "wti_crude": "WTI 원유",
    "brent_crude": "브렌트",
    "natural_gas": "천연가스",
}

_LOGO_DOMAINS = {
    "TSLA": "tesla.com",
    "AAPL": "apple.com",
    "MSFT": "microsoft.com",
    "NVDA": "nvidia.com",
    "META": "meta.com",
    "AMZN": "amazon.com",
    "GOOGL": "abc.xyz",
    "AVGO": "broadcom.com",
    "ASML": "asml.com",
    "TSM": "tsmc.com",
    "AMD": "amd.com",
    "MU": "micron.com",
    "005930": "samsung.com",
    "000660": "skhynix.com",
    "207940": "samsungbiologics.com",
    "005380": "hyundai.com",
    "000270": "kia.com",
    "051910": "lgchem.com",
    "006400": "samsungsdi.com",
    "035420": "naver.com",
    "105560": "kbfg.com",
    "055550": "shinhangroup.com",
}

_BRAND_CLASSES = {
    "TSLA": "brand-red",
    "AAPL": "brand-dark",
    "MSFT": "brand-blue",
    "NVDA": "brand-green",
    "META": "brand-blue",
    "AMZN": "brand-gold",
    "GOOGL": "brand-violet",
    "005930": "brand-blue",
    "000660": "brand-red",
    "207940": "brand-blue",
    "005380": "brand-blue",
    "000270": "brand-dark",
    "051910": "brand-red",
    "006400": "brand-blue",
    "035420": "brand-green",
    "105560": "brand-gold",
    "055550": "brand-blue",
}

_ISSUER_CLASSES = {
    "TIGER": "issuer-tiger",
    "KODEX": "issuer-kodex",
    "RISE": "issuer-rise",
    "PLUS": "issuer-plus",
    "ACE": "issuer-ace",
}

_METAL_VISUALS = {
    "금": ("Au", "metal-gold"),
    "은": ("Ag", "metal-silver"),
    "구리": ("Cu", "metal-copper"),
    "WTI 원유": ("Oil", "metal-energy"),
    "브렌트": ("Oil", "metal-energy"),
    "천연가스": ("Gas", "metal-energy"),
}

_CRYPTO_VISUALS = {
    "BTC": ("BTC", "coin-btc"),
    "ETH": ("ETH", "coin-eth"),
    "SOL": ("SOL", "coin-sol"),
}

# _PORT_CSS → ui.pages.portfolio_css 로 이동


def _logo_html(item: dict) -> str:
    group = item.get("group", "")
    name = str(item.get("name", ""))
    code = str(item.get("code", ""))

    if group == "ETF":
        issuer = _issuer_from_name(name)
        cls = _ISSUER_CLASSES.get(issuer.upper(), "issuer-etf")
        return f'<div class="hold-logo hold-logo-issuer {cls}"><span>{_escape(issuer.upper())}</span></div>'

    if group == "원자재":
        label, cls = _METAL_VISUALS.get(name, ("Com", "metal-energy"))
        return f'<div class="hold-logo hold-logo-metal {cls}"><span>{_escape(label)}</span></div>'

    if group == "크립토":
        symbol = _ticker_key(code).replace("-USD", "")
        label, cls = _CRYPTO_VISUALS.get(symbol, (symbol[:3] or "COIN", "issuer-etf"))
        return f'<div class="hold-logo hold-logo-issuer {cls}"><span>{_escape(label)}</span></div>'

    key = _ticker_key(code)
    fallback = (key[:4] if group == "미국주식" else name[:2]) or key[:4] or "LOGO"
    cls = _BRAND_CLASSES.get(key, "brand-dark")
    return f'<div class="hold-logo hold-logo-company {cls}"><span>{_escape(fallback)}</span></div>'


_DETAIL_CATEGORY_ORDER = ["미국주식", "ETF", "크립토", "원자재", "국내주식", "현금"]


def _records_from_holdings(raw) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, pd.DataFrame):
        return raw.to_dict("records")
    if isinstance(raw, list):
        return [dict(x) for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        for key in ("items", "holdings", "positions"):
            if isinstance(raw.get(key), list):
                return [dict(x) for x in raw[key] if isinstance(x, dict)]
    return []


def _market_price_maps(data: dict) -> dict[str, dict]:
    maps: dict[str, dict] = {}
    for table_name, key_col in [
        ("us_stocks", "ticker"),
        ("kr_stocks", "ticker"),
        ("my_etfs", "ticker"),
        ("crypto", "ticker"),
        ("commodities", "ticker"),
    ]:
        df = data.get(table_name, pd.DataFrame())
        if df is not None and not df.empty and key_col in df.columns:
            for _, row in df.iterrows():
                maps[str(row.get(key_col, "")).upper()] = dict(row)
    return maps


def _is_kr_listed(ticker: str, name: str = "") -> bool:
    """한국 상장 여부 — 판정 로직은 인제스트 게이트(core.holdings_ingest)와 단일 출처 공유."""
    from core.holdings_ingest import is_kr_listed
    return is_kr_listed(ticker, name)


def _quote_ticker(ticker: str, category: str) -> str:
    """보유 티커 → 시세 조회용 티커. 크립토는 -USD 접미사, 한국 6자리 코드는 .KS 부착
    (국내 ETF/주식이 코드만으로 저장돼도 토스/yfinance 조회 가능하게)."""
    t = ticker.upper().strip()
    if category == "크립토" and t and not t.endswith("-USD"):
        return f"{t}-USD"
    if re.fullmatch(r"\d{6}", t):
        return f"{t}.KS"
    return t


def _holding_ident(h: dict) -> str:
    """보유 1건 식별자 — 삭제 링크·매칭 공용(티커 우선, 없으면 이름)."""
    return str(h.get("ticker") or h.get("name") or "")


def _price_currency(position: dict) -> str:
    """현재가(시세) 표시 통화 — 미국주식은 USD. 평가액 환산통화(_holding_currency)와 별개이며,
    잘못 저장된 currency='KRW'(구 파싱 버그)에 휘둘리지 않게 카테고리 기준."""
    return "USD" if position.get("category") == "미국주식" else \
        _holding_currency(position, position.get("ticker", ""), position.get("category", ""))


def _cached_bulk_quotes(tickers: tuple[str, ...]) -> dict:
    """보유 보강 시세 — DB(quotes) 우선 → 미존재만 라이브 + 자가 적재. data.loader.batch_quotes 위임
    (DB·소스 오케스트레이션은 로더 계층 단일화, 60초 캐시도 그쪽). 키=정렬된 티커 튜플."""
    from data.loader import batch_quotes
    return batch_quotes(",".join(tickers))


def _supplement_holding_quotes(raw_records: list[dict], price_maps: dict[str, dict]) -> None:
    """워치리스트(_market_price_maps)에 없는 보유 종목(PLTR·크립토 등)의 오늘 변동·현재가를
    개별 시세(fetch_prices_bulk)로 보강. 원본 보유 티커 키로 price_maps 에 추가(동일 형식)."""
    need: dict[str, str] = {}   # 원본티커(UPPER) -> 조회티커
    for row in raw_records:
        tk = str(_first(row, "ticker", "symbol", "code") or "").upper().strip()
        if not tk or tk in price_maps:                      # 현금·이미 워치리스트 커버는 스킵
            continue
        cat = _category_for_holding(row, tk)
        if cat == "현금":
            continue
        need[tk] = _quote_ticker(tk, cat)
    if not need:
        return
    try:
        quotes = _cached_bulk_quotes(tuple(sorted(set(need.values()))))   # 60초 캐시(렌더마다 네트워크 X)
    except Exception:                                       # 조회 실패해도 화면은 떠야 함(오늘값만 빔)
        return
    for orig, qtk in need.items():
        q = quotes.get(qtk)
        if q:
            price_maps[orig] = dict(q)


def _position_eval(category, qty, current, fx_factor, direct_market,
                   direct_cost, avg_price, direct_gain, direct_gain_pct, direct_today, change, fx=1):
    """수량 보유 1건의 (평가금액, 평가금액_현지, 원가, 평가손익, 평가손익_현지, 손익률, 오늘변동금액).

    **평가금액 = 보유수량 × 라이브 현재가**(종가/장중 실시간) → 시세 변동 반영(스냅샷 고정 X).
    **매입금액(원가)·매입단가는 고정**(스냅샷 direct_cost/avg_price). 수익률 = (평가−매입)/매입.

    fx_factor = 이 보유의 USD→원화 환산계수(USD=환율, 원화권=1). _holding_currency 가 티커/카테고리로
    USD 여부를 robust 판정하므로(파서 currency 오태깅 무관) **평가금액·매입금액에 동일 fx_factor 일관 적용**
    → 둘이 어긋나 수익률 폭발하던 버그 제거. 라이브 현재가 없으면 스냅샷 평가금액 폴백. 크립토는 스냅샷."""
    # 소수점 누락(파서 OCR 자릿수 오류) 자동 보정: 매입금액 '27,543.519'를 27543519처럼 ×10ⁿ 부풀려
    # 읽으면 수익률이 -99.9%로 폭발. 스냅샷 평가금액 vs 라이브 평가액(수량×현재가)의 배율로 자릿수 k를
    # 추정해 스냅샷 금액들(매입·평가·손익)을 되돌린다. 라이브 평가금액(수량×현재가)은 영향 없음.
    # 가드: 주식만(현재가·평가금액 동일 통화) + 증권사 수익률 -90% 미만(실제 폭락)이면 보정 안 함.
    # (크립토는 현재가=BTC-USD·평가금액=원화로 통화가 달라 배율이 자릿수 오류가 아니므로 제외.)
    if (category in ("미국주식", "국내주식") and direct_market and qty and current and current > 0
            and (direct_gain_pct is None or direct_gain_pct > -90)):
        _r = direct_market / (qty * current)
        if _r > 50:                                  # 스냅샷이 라이브의 50배 초과 = 자릿수 누락
            _k = 10 ** round(math.log10(_r))
            if _k >= 10:
                direct_market /= _k
                if direct_cost is not None: direct_cost /= _k
                if direct_gain is not None: direct_gain /= _k
                if direct_today is not None: direct_today /= _k

    live = category in ("미국주식", "국내주식") and bool(qty) and current is not None and current > 0

    cost_basis = direct_cost   # 매입금액(원가)은 시세와 무관 — 고정(USD면 ×환율)
    if cost_basis is not None and fx_factor != 1:
        cost_basis = direct_cost * fx_factor
    elif cost_basis is None and avg_price is not None:
        cost_basis = qty * avg_price * fx_factor

    if live:
        market_value = qty * current * fx_factor   # 평가금액·매입금액 동일 환산(일관)
        gain_loss = (market_value - cost_basis) if cost_basis is not None else None
        gain_pct = (gain_loss / cost_basis * 100) if (gain_loss is not None and cost_basis) else None
        today_amount = (qty * change * fx_factor) if change is not None else None
        local_fx = fx_factor
    else:
        market_value = direct_market
        if market_value is not None and fx_factor != 1:
            market_value = direct_market * fx_factor
        elif market_value is None and current is not None:
            market_value = qty * current * fx_factor
        gain_loss = direct_gain
        if gain_loss is not None and fx_factor != 1:
            gain_loss = direct_gain * fx_factor
        elif gain_loss is None and market_value is not None and cost_basis is not None:
            gain_loss = market_value - cost_basis
        gain_pct = direct_gain_pct
        if gain_pct is None and gain_loss is not None and cost_basis:
            gain_pct = gain_loss / cost_basis * 100
        today_amount = direct_today
        if today_amount is not None and fx_factor != 1:
            today_amount = direct_today * fx_factor
        elif today_amount is None and change is not None:
            today_amount = qty * change * fx_factor
        local_fx = fx_factor

    market_value_local = (market_value / local_fx) if (local_fx != 1 and market_value is not None) else market_value
    gain_loss_local = (gain_loss / local_fx) if (local_fx != 1 and gain_loss is not None) else gain_loss
    return market_value, market_value_local, cost_basis, gain_loss, gain_loss_local, gain_pct, today_amount


def _today_label(quote_ticker: str, opens: dict[str, bool]) -> str:
    """오늘 변동 라벨 — 해당 시장 개장 중이면 '오늘', 마감이면 '전일'(마지막 세션 종가 기준).
    시장은 canonical market_of(티커)로 판정(크립토 24h·US/KR 세션). 미국장 마감 시 간밤 세션을
    '오늘'로 오인하지 않게 구분. ETF는 카테고리로는 시장이 모호해 티커 기준이 정확(.KS→KR, US ETF→US)."""
    from core.market_hours import market_of
    return "오늘" if opens.get(market_of(quote_ticker), opens["US"]) else "전일"


# USD/KRW 환율은 data/fx.py 단일 출처에 위임(이전엔 이 UI 파일 안에 자체 HTTP 호출이 박혀
# 있었음). _usdkrw·_FX_FALLBACK 은 기존 호출부(`_usdkrw(data) or _FX_FALLBACK`) 호환 별칭.
from data.fx import usdkrw as _usdkrw, FX_FALLBACK as _FX_FALLBACK


def _category_for_holding(row: dict, ticker: str) -> str:
    raw = str(_first(row, "asset_class", "assetType", "type", "category", "group") or "").lower()
    name = str(_first(row, "name", "asset_name", "display_name") or "")
    if "cash" in raw or "현금" in raw or ticker.upper() in {"CASH", "KRW", "USD"}:
        return "현금"
    if "crypto" in raw or ticker.upper().endswith("-USD"):
        return "크립토"
    if "commodity" in raw or "원자재" in raw:
        return "원자재"
    # ETF 판정: 이름에 'ETF' 표기 OR 국내 ETF 발행사 접두 OR (asset_class=etf & 한국 티커).
    # 파서(vision)가 개별 미국주식을 'etf'로 오분류하는 경우(예: SPCX/스페이스X)를 거른다 —
    # 비한국 티커는 이름이 ETF가 아니면 미국주식으로(통화/수익률은 이미 티커 기준이라 무관, 라벨만 보정).
    name_u = name.upper()
    if ("ETF" in name_u or any(name_u.startswith(prefix) for prefix in _ISSUER_CLASSES)
            or ("etf" in raw and (ticker.endswith(".KS") or ticker.endswith(".KQ")))):
        return "ETF"
    if "kr" in raw or ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "국내주식"
    if "us" in raw or ticker:
        return "미국주식"
    return "기타"


def _holding_currency(row: dict, ticker: str = "", category: str = "") -> str:
    """보유 1건의 환산·표시 통화(KRW|USD) — 전 화면 '보유→원화' 변환의 단일 출처(SSOT).

    판정은 **티커/카테고리 기준**(스크린샷 파서의 currency·asset_class 가 자주 틀려서 — 미국주식을
    'KRW'로 오태깅하거나, 미국주식을 ETF로 오분류 → 환율 미적용으로 수익률 폭발). 따라서:
    - 원화권: 국내주식·크립토(국내거래소 원화)·현금·원자재, 또는 .KS/.KQ 티커 → KRW.
    - 그 외 해외 상장(미국주식·해외 ETF·기타, 비한국 티커) → USD(×환율). 저장 currency 태그에 안 휘둘림.
    크립토를 USD로 보면 국내거래소 원화 평가금액에 ×환율되어 총액 폭증(예: 1,200만→184억)이라 KRW 고정."""
    cat = category or _category_for_holding(row, ticker)
    t = (ticker or "").upper()
    _nm = str(_first(row, "name", "asset_name", "display_name") or "")
    # 국내 상장(코드 6자리·발행사 접두 포함) — 국내 ETF가 .KS 없이 와도 USD 오판 금지(평가액 ×환율 폭증 방지)
    if cat in ("국내주식", "크립토", "현금", "원자재") or _is_kr_listed(t, _nm):
        return "KRW"
    if cat in ("미국주식", "ETF", "기타"):   # 해외 상장(비한국 티커) — 매입·평가금액이 USD
        return "USD"
    cur = str(_first(row, "currency", "ccy") or "").upper()   # 분류 불가 시 명시 태그, 기본 KRW
    return cur if cur in ("KRW", "USD") else "KRW"


def _display_currency(row: dict, ticker: str, category: str) -> str:
    return _holding_currency(row, ticker, category)  # 하위호환 별칭 — 단일 출처 위임


def _name_ticker_map(price_maps: dict[str, dict]) -> dict[str, str]:
    """라이브 시세 표(my_etfs 등)의 name→ticker 맵. 티커 없는 보유(스크린샷 ETF) 시세 해소용."""
    out: dict[str, str] = {}
    for tk, mrow in price_maps.items():
        nm = str(mrow.get("name") or "").strip()
        if nm:
            out.setdefault(_norm_name(nm), tk)
    return out


def _normalize_holdings(data: dict) -> tuple[list[dict], dict]:
    raw_records = _records_from_holdings(data.get("holdings"))
    price_maps = _market_price_maps(data)
    _supplement_holding_quotes(raw_records, price_maps)  # 워치리스트 밖 보유(PLTR·크립토)도 오늘 변동 채움
    name_to_ticker = _name_ticker_map(price_maps)  # 이름→티커(스크린샷 ETF 등 티커 없는 보유 해소)
    fx = _usdkrw(data) or _FX_FALLBACK   # 환율 실패 시 폴백 — 미국 종목이 안 빠지게
    positions: list[dict] = []
    cash_balance = _num(data.get("cash_balance"))
    cash_from_rows = 0.0

    for idx, row in enumerate(raw_records):
        ticker = str(_first(row, "ticker", "symbol", "code") or "").upper()
        name = str(_first(row, "name", "asset_name", "display_name") or ticker or "현금")
        if not ticker and name:  # 티커 없으면 이름으로 라이브 시세 매칭(ETF 오늘자 반영)
            ticker = name_to_ticker.get(_norm_name(name), "")
        category = _category_for_holding(row, ticker)
        currency = _display_currency(row, ticker, category)
        market_row = price_maps.get(ticker, {})
        qty = _num(_first(row, "quantity", "qty", "shares", "units", "보유수량"))
        current = _num(_first(row, "current_price", "last_price", "price", "현재가"))
        if current is None:
            current = _num(market_row.get("price"))
        prev_close = _num(_first(row, "prev_close", "previous_close"))
        if prev_close is None:
            prev_close = _num(market_row.get("prev_close"))
        change = _num(_first(row, "change", "day_change"))
        if change is None:
            change = _num(market_row.get("change"))
        change_pct = _num(_first(row, "change_pct", "today_change_percent", "day_change_percent"))
        if change_pct is None:
            change_pct = _num(market_row.get("change_pct"))
        avg_price = _num(_first(row, "average_price", "avg_price", "avg_cost", "average_cost", "평균단가"))
        direct_market = _num(_first(row, "market_value", "marketValue", "평가금액", "position_value", "value"))
        direct_cost = _num(_first(row, "cost_basis", "total_cost", "purchase_amount", "매입금액"))
        direct_gain = _num(_first(row, "gain_loss", "unrealized_pnl", "pnl", "평가손익"))
        direct_gain_pct = _num(_first(row, "gain_loss_percent", "pnl_percent", "return_pct", "수익률"))
        direct_today = _num(_first(row, "today_change_amount", "day_change_amount", "오늘변동금액"))

        if category == "현금":
            cash_value = direct_market or _num(_first(row, "cash_balance", "balance", "amount")) or 0
            if cash_value <= 0:
                continue
            cash_from_rows += cash_value
            positions.append({
                "id": ticker or f"CASH-{idx}",
                "category": "현금",
                "name": name or "현금/예수금",
                "ticker": ticker or "CASH",
                "currency": "KRW",
                "quantity": None,
                "current_price": None,
                "avg_price": None,
                "market_value": cash_value,
                "cost_basis": cash_value,
                "gain_loss": 0,
                "gain_loss_pct": 0,
                "today_change_amount": 0,
                "today_change_pct": 0,
                "source_row": row,
            })
            continue

        fx_factor = fx if currency == "USD" and fx else 1

        # ETF/qty-없는 종목: eval_amount로 포지션 생성
        if qty is None or qty <= 0:
            if direct_market and direct_market > 0:
                cost_basis = direct_cost or direct_market
                gain_loss = direct_gain or (direct_market - cost_basis if cost_basis else None)
                gain_pct = direct_gain_pct or (gain_loss / cost_basis * 100 if gain_loss and cost_basis else None)
                market_value_local = (direct_market / fx_factor) if fx_factor != 1 else direct_market
                gain_loss_local = (gain_loss / fx_factor) if (fx_factor != 1 and gain_loss is not None) else gain_loss
                # 오늘 변동금액 — 스크린샷에 없으면 라이브 오늘% × 평가액으로 추정(ETF 오늘자 반영)
                today_amt = direct_today
                if today_amt is None and change_pct is not None:
                    today_amt = direct_market * change_pct / 100
                # 수량 추정 — 보유주수 미상이면 평가액(현지통화) ÷ 현재가
                est_qty = None
                if current and current > 0 and market_value_local:
                    est_qty = market_value_local / current
                positions.append({
                    "id": ticker or name or f"HOLDING-{idx}",
                    "category": category,
                    "name": name,
                    "ticker": ticker,
                    "currency": currency,
                    "quantity": est_qty,
                    "quantity_est": est_qty is not None,
                    "current_price": current,
                    "avg_price": avg_price,
                    "market_value": direct_market,
                    "market_value_local": market_value_local,
                    "cost_basis": cost_basis,
                    "gain_loss": gain_loss,
                    "gain_loss_local": gain_loss_local,
                    "gain_loss_pct": gain_pct,
                    "today_change_amount": today_amt,
                    "today_change_pct": change_pct,
                    "source_row": row,
                })
            continue

        # 평가금액·손익·오늘변동 — 주식은 라이브 재계산(스냅샷 평가금액 대체), 크립토 등은 스냅샷 유지.
        market_value, market_value_local, cost_basis, gain_loss, gain_loss_local, gain_pct, today_amount = \
            _position_eval(category, qty, current, fx_factor, direct_market, direct_cost,
                           avg_price, direct_gain, direct_gain_pct, direct_today, change)
        positions.append({
            "id": ticker or f"HOLDING-{idx}",
            "category": category,
            "name": name,
            "ticker": ticker,
            "currency": currency,
            "quantity": qty,
            "current_price": current,
            "avg_price": avg_price,
            "market_value": market_value,
            "market_value_local": market_value_local,
            "cost_basis": cost_basis,
            "gain_loss": gain_loss,
            "gain_loss_local": gain_loss_local,
            "gain_loss_pct": gain_pct,
            "today_change_amount": today_amount,
            "today_change_pct": change_pct,
            "source_row": row,
        })

    if cash_balance and cash_balance > 0 and not any(p["category"] == "현금" for p in positions):
        positions.append({
            "id": "CASH",
            "category": "현금",
            "name": "현금/예수금",
            "ticker": "CASH",
            "currency": "KRW",
            "quantity": None,
            "current_price": None,
            "avg_price": None,
            "market_value": cash_balance,
            "cost_basis": cash_balance,
            "gain_loss": 0,
            "gain_loss_pct": 0,
            "today_change_amount": 0,
            "today_change_pct": 0,
            "source_row": {"source": "cash_balance"},
        })

    total_value = sum(p["market_value"] or 0 for p in positions)
    for p in positions:
        p["weight"] = (p["market_value"] or 0) / total_value * 100 if total_value > 0 else 0

    positions.sort(key=lambda x: x.get("market_value") or 0, reverse=True)
    meta = {
        "raw_count": len(raw_records),
        "cash_balance": cash_balance if cash_balance is not None else (cash_from_rows if cash_from_rows > 0 else None),
        "fx_usdkrw": fx,
        "has_holdings_source": "holdings" in data,
    }
    return positions, meta


def _portfolio_summary(positions: list[dict], meta: dict) -> dict:
    if not positions:
        return {
            "has_data": False,
            "total_market_value": None,
            "total_cost_basis": None,
            "total_gain_loss": None,
            "total_gain_loss_pct": None,
            "today_change_amount": None,
            "today_change_pct": None,
            "largest_position": None,
            "top_gain_contributor": None,
            "cash_balance": meta.get("cash_balance"),
            "fx_usdkrw": meta.get("fx_usdkrw"),
        }
    total = sum(p["market_value"] or 0 for p in positions)
    cost = sum(p["cost_basis"] or 0 for p in positions)
    gain = sum(p["gain_loss"] or 0 for p in positions)
    today = sum(p["today_change_amount"] or 0 for p in positions)
    gain_pct = gain / cost * 100 if cost else None
    today_pct = today / total * 100 if total else None
    gainers = [p for p in positions if p.get("gain_loss") is not None]
    return {
        "has_data": True,
        "total_market_value": total,
        "total_cost_basis": cost,
        "total_gain_loss": gain,
        "total_gain_loss_pct": gain_pct,
        "today_change_amount": today,
        "today_change_pct": today_pct,
        "largest_position": positions[0] if positions else None,
        "top_gain_contributor": max(gainers, key=lambda x: x.get("gain_loss") or 0) if gainers else None,
        "cash_balance": meta.get("cash_balance"),
        "fx_usdkrw": meta.get("fx_usdkrw"),
    }


def _positions_by_category(positions: list[dict], show_empty: bool = False) -> list[dict]:
    total = sum(p["market_value"] or 0 for p in positions)
    grouped: list[dict] = []
    categories = _DETAIL_CATEGORY_ORDER + sorted({p["category"] for p in positions} - set(_DETAIL_CATEGORY_ORDER))
    for category in categories:
        items = [p for p in positions if p["category"] == category]
        if not items and not show_empty:
            continue
        value = sum(p["market_value"] or 0 for p in items)
        cost = sum(p["cost_basis"] or 0 for p in items)
        gain = sum(p["gain_loss"] or 0 for p in items)
        today = sum(p["today_change_amount"] or 0 for p in items)
        grouped.append({
            "id": category,
            "name": category,
            "count": len(items),
            "items": items,
            "total_market_value": value,
            "weight": value / total * 100 if total else 0,
            "total_gain_loss": gain if items else None,
            "total_gain_loss_pct": gain / cost * 100 if cost else None,
            "today_change_amount": today if items else None,
            "top_by_value": items[:3],
        })
    return grouped


def _summary_card(label: str, value: str, sub: str = "", cls: str = "") -> str:
    return (
        '<div class="pd-summary-card">'
        f'<span>{_escape(label)}</span>'
        f'<b class="{cls}">{_escape(value)}</b>'
        f'<small>{_escape(sub)}</small>'
        '</div>'
    )


def _portfolio_today_state(summary: dict) -> tuple[str, str, str, str]:
    amount = summary.get("today_change_amount")
    pct = summary.get("today_change_pct")
    total = summary.get("total_market_value") or 0
    if amount is None or pct is None:
        return "데이터 대기", "전일가 연결 필요", "pd-neu", "normal"
    if abs(pct) > 50 or (total > 0 and abs(amount) > total * 0.5):
        return "데이터 확인 필요", "수량·통화·전일가 중 하나가 비정상일 수 있습니다", "pd-warn", "outlier"
    return _money(amount, "KRW", signed=True, compact=True), f"오늘 변동률 {pct:+.2f}%", _tone(amount), "normal"


def _format_weight(value: float | None) -> str:
    if value is None:
        return "0%"
    if 0 < value < 0.1:          # 반올림 0%가 '데이터 없음'처럼 보이는 것 방지
        return "<0.1%"
    return f"{pct_weight(value)}%"


def _target_upside(position: dict, target_prices: dict[str, float]) -> float | None:
    target = target_prices.get(position["ticker"])
    current = position.get("current_price")
    if target and current:
        return (target / current - 1) * 100
    return None


def _position_value_pair(position: dict, compact: bool = False) -> tuple[str, str]:
    primary = _money(position.get("market_value"), "KRW", compact=compact)
    currency = position.get("currency", "KRW")
    local = position.get("market_value_local")
    if currency == "USD" and local is not None:
        return primary, f"≈ {_money(local, 'USD')}"
    return primary, currency


def _portfolio_overview_html(summary: dict, positions: list[dict], categories: list[dict]) -> str:
    if not summary["has_data"]:
        return (
            '<div class="pd-overview">'
            '<div class="pd-hero"><span>원화 환산 총액</span><b>API 데이터 없음</b>'
            '<small>보유 수량과 평가금액이 연결되면 요약을 표시합니다.</small></div>'
            '</div>'
        )

    total = summary.get("total_market_value")
    gain = summary.get("total_gain_loss")
    gain_pct = summary.get("total_gain_loss_pct")
    today_value, today_sub, today_cls, today_state = _portfolio_today_state(summary)
    cash = summary.get("cash_balance")
    fx = summary.get("fx_usdkrw")
    today_chip_cls = "warn" if today_state == "outlier" else ""
    gain_sub = f"평가 수익률 {gain_pct:+.2f}%" if gain_pct is not None else "원가 데이터 대기"
    fx_text = _cur(fx, "KRW") if fx else "데이터 대기"
    # 집중도·USD 노출 수치는 위험 카드와 진단 탭에 한 곳씩만(single source of truth, Track W).
    # 히어로 칩은 데이터 이상 '플래그'만 남긴다(중복 제거).
    chips = [
        f'<span class="pd-chip {today_chip_cls}">{_escape(today_value)}</span>' if today_state == "outlier" else "",
    ]
    # D1: 핵심 성과 3카드(총액·총손익·오늘)만. 참조값(현금·환율)은 총액 카드 보조 줄로 흡수(빈 카드 제거).
    cash_disp = _money(cash, "KRW", compact=True) if cash is not None else "데이터 없음"
    hero_sub = f"보유 {len(positions)}개 · 현금 {cash_disp} · USD/KRW {fx_text}"
    return (
        '<div class="pd-overview">'
        '<div class="pd-hero">'
        '<div><span>원화 환산 총액</span>'
        f'<b>{_money(total, "KRW", compact=True)}</b>'
        f'<small>{_escape(hero_sub)}</small></div>'
        f'<div class="pd-hero-chips">{"".join(chips)}</div>'
        '</div>'
        f'<div class="pd-metric"><span>총 손익</span><b class="{_tone(gain)}">{_money(gain, "KRW", signed=True, compact=True)}</b>'
        f'<small>{_escape(gain_sub)}</small></div>'
        f'<div class="pd-metric"><span>오늘 변동</span><b class="{today_cls}">{_escape(today_value)}</b><small>{_escape(today_sub)}</small></div>'
        '</div>'
        '<div class="pd-overview-note">최대 비중·상위 3개 집중도와 USD 노출 상세는 '
        '아래 <b>위험 카드</b>와 <b>진단</b> 탭에서 한 곳으로 모아 보여줍니다.</div>'
    )


# 집중도 색 팔레트 — 색 = 비중 차등(등락색 회피). 최대 집중만 레드 경고, 이후 골드→올리브→회색.
_CONC_ALARM = "#E2683C"                                              # 최대 집중(과집중 위험) — 주황(경고 채널)
_CONC_RAMP  = ["#C99A3C", "#8C7A3E", "#5A5F52", "#3E4450", "#2E333B"]  # 비중순 골드→회색
_CONC_ETC   = "#23272F"                                              # 기타(가장 짙은 회색)
_CONC_ALARM_MIN = 50.0   # 최대 종목이 이 비중↑이면 주황 위험 경고(=PB '위험' 기준). 미만이면 골드(비중)

# 종목 집중도 바 = 각 종목 고유 브랜드 색(구성을 색으로 직관적으로 읽게). 브랜드 그라데이션의 대표 솔리드.
_BRAND_SOLID = {
    "brand-red": "#D74333", "brand-dark": "#6F7C84", "brand-blue": "#3B82C4",
    "brand-green": "#3AA384", "brand-violet": "#7B6FD6", "brand-gold": "#D6A23A",
}
_STOCK_FALLBACK = ["#5E6573", "#4A515E", "#3E4450", "#33383F", "#2A2E36"]  # 브랜드 미상 종목(중립 회색)
# 코인 고유색(배지 .coin-* 그라데이션의 대표 솔리드) — 집중도 바도 같은 색을 쓰게.
_COIN_SOLID = {
    "BTC": "#F7931A", "ETH": "#627EEA", "SOL": "#14F195", "ADA": "#0033AD",
    "XRP": "#23A5DE", "DOGE": "#C2A633", "USDT": "#26A17B", "USDC": "#2775CA",
}


def _stock_bar_color(pos, idx: int) -> str:
    """종목 → 고유 브랜드/코인 색. 크립토는 코인 고유색, 그 외 브랜드 미상은 중립 회색 차등."""
    ticker = str((pos.get("ticker", "") if isinstance(pos, dict) else pos) or "")
    key = _ticker_key(ticker)
    cls = _BRAND_CLASSES.get(key, "")
    if cls:
        return _BRAND_SOLID.get(cls, _STOCK_FALLBACK[min(idx, len(_STOCK_FALLBACK) - 1)])
    if isinstance(pos, dict):
        ac = str(pos.get("asset_class") or "").lower()
        if pos.get("category") == "크립토" or "crypto" in ac:
            return _COIN_SOLID.get(key.replace("-USD", ""), _CAT_COLOR.get("크립토", "#F0A030"))
    return _STOCK_FALLBACK[min(idx, len(_STOCK_FALLBACK) - 1)]


# 자산군 = 카테고리 상징색. 미국/한국은 국기 색을 '실제 면적 비율'로 가중 혼합한 대표색.
_CAT_COLOR = {
    "미국주식": "#8A2B48",   # 성조기 혼합(흰 제외): 빨강 66% + 파랑 34% → 와인/자주
    "국내주식": "#563460",   # 태극기 혼합(흰 제외): 빨·파 각 44% + 검 12% → 짙은 플럼/남보라
    "ETF": "#7E6BD6",        # 혼합 바스켓 = 바이올렛
    "크립토": "#F0A030",     # 코인 앰버
    "원자재": "#9E7B3B",     # 금속/원자재 = 브론즈
    "현금": "#3FB27F",       # 현금 = 머니 그린
}
_CAT_FALLBACK = "#5A6270"


def _mini_allocation_html(categories: list[dict]) -> str:
    # 자산군 = 카테고리 상징색(미국·한국은 국기 면적비율 혼합색). 비중 내림차순 정렬.
    active = sorted(
        [c for c in categories if c["count"] > 0 and c["weight"] > 0],
        key=lambda c: c["weight"], reverse=True,
    )
    if not active:
        return '<div class="pd-empty"><b>자산군 비중 데이터 없음</b><p>보유 자산군 데이터가 연결되면 표시합니다.</p></div>'
    bars = []
    legends = []
    for idx, cat in enumerate(active):
        color = _CAT_COLOR.get(cat["name"], _CAT_FALLBACK)
        width = min(100, max(0, cat["weight"]))
        bars.append(f'<i style="width:{width:.1f}%;background:{color}" title="{_escape(cat["name"])} {pct_weight(cat["weight"])}%"></i>')
        legends.append(
            f'<span><i class="pd-mini-dot" style="background:{color}"></i>{_escape(cat["name"])} {pct_weight(cat["weight"])}%</span>'
        )
    return '<div class="pd-mini-alloc">' + "".join(bars) + '</div><div class="pd-mini-legend">' + "".join(legends) + '</div>'


def _holdings_concentration_html(positions: list[dict]) -> str:
    """종목 집중도 시각화 — 종목별 색 스택 바(막대만 봐도 구성이 읽히게).

    색 = 각 종목 고유 브랜드 색(테슬라·애플·엔비디아 등). 과집중 '위험' 경고는 위험 카드(주황)가 담당.
    종목 多(>5)면 상위 5개만 브랜드색 + 기타 회색.
    """
    colored = [p for p in positions[:5] if p.get("weight", 0) > 0]
    if not colored:
        return ""
    shown = sum(p.get("weight", 0) for p in colored)
    etc = max(0.0, 100.0 - shown)
    bars, legends = [], []
    for i, p in enumerate(colored):
        w = p.get("weight", 0)
        c = _stock_bar_color(p, i)
        nm = _escape(p.get("name", ""))
        bars.append(f'<i style="width:{w:.1f}%;background:{c}" title="{nm} {pct_weight(w)}%"></i>')
        legends.append(f'<span><i class="pd-mini-dot" style="background:{c}"></i>{nm} {pct_weight(w)}%</span>')
    if etc > 0.5:
        bars.append(f'<i style="width:{etc:.1f}%;background:{_CONC_ETC}"></i>')
        legends.append(f'<span><i class="pd-mini-dot" style="background:{_CONC_ETC}"></i>기타 {pct_weight(etc)}%</span>')
    return (
        '<div class="pd-conc-label">종목 집중도 <span>종목별 고유색 · 비중순</span></div>'
        '<div class="pd-mini-alloc">' + "".join(bars) + '</div>'
        '<div class="pd-mini-legend">' + "".join(legends) + '</div>'
    )


def _greed_bar_html(g: dict) -> str:
    """탐욕 지수 바(D1) — 종목 집중도 바와 같은 양식(라벨+12px 바)으로 바로 아래 한 쌍.
    색은 회색→골드 그라데이션(파랑=하락 충돌 회피) + 흰 마커 + 공포/중립/탐욕 라벨로 읽게 한다(A+C)."""
    score = max(0, min(100, int(g["score"])))
    tone = ("과열 구간 — 점검 권장" if score >= 60 else
            "균형 구간" if score >= 45 else "방어적 구간")
    return (
        '<div class="gd-block">'   # 위 자산군 바와 구분되게 약간의 간격+옅은 구분선
        f'<div class="pd-conc-label">내 계좌 탐욕 지수 '
        f'<span>{_escape(g["label"])} {score} · {tone} · 집중도·현금 기반(시장 아님)</span></div>'
        f'<div class="gd-track"><i class="gd-marker" style="left:{score}%"></i></div>'
        '<div class="gd-scale"><span>공포</span><span>중립</span><span>탐욕</span></div>'
        '</div>'
    )


def _portfolio_diagnosis_html(positions: list[dict], categories: list[dict], summary: dict,
                              actions: str = "", extra_html: str = "") -> str:
    if not positions:
        return (
            '<div class="pd-diagnosis"><div class="pd-diagnosis-head"><b>포트폴리오 진단</b>'
            '<span>데이터 대기</span></div><div class="pd-diagnosis-grid">'
            '<div class="pd-diagnosis-item"><strong>계산 대기</strong><span>보유 수량과 평가금액이 연결되면 집중도와 환율 노출을 계산합니다.</span></div>'
            '</div></div>'
        )
    largest = positions[0]
    top3_weight = sum(p.get("weight", 0) for p in positions[:3])
    fx_weight = sum(p.get("weight", 0) for p in positions if p.get("currency") == "USD")
    active_cats = [c for c in categories if c["count"] > 0]
    largest_cat = max(active_cats, key=lambda c: c["weight"]) if active_cats else None
    today_value, today_sub, _, today_state = _portfolio_today_state(summary)
    largest_w = largest.get("weight", 0)
    # 카드 좌측 바 색 = 집중도 막대 색 매칭: 최대 집중(과집중)=레드, 아니면 골드 / 상위3=골드 / USD·자산군=올리브
    leader_alarm = largest_w >= _CONC_ALARM_MIN
    single_sev = "danger" if leader_alarm else "gold"
    single_body = (
        "단일 종목 비중이 과도합니다. 개별 악재 시 총 평가액이 크게 흔들릴 수 있어 분할 매도·분산을 우선 검토하세요."
        if largest_w >= 50 else
        "단일 종목 비중이 높아 해당 종목 뉴스가 총 평가액에 크게 반영됩니다."
    )
    items = [
        # 비중 수치는 바로 위 '종목 집중도' 바에 표시 → 진단 항목은 종목명 + 액션만(중복 제거)
        # sev 클래스 = 막대 색과 매칭(danger 레드 / gold 골드 / olive 올리브)
        (f'{largest["name"]} 집중', single_body, single_sev),
        (f"상위 3개 {_format_weight(top3_weight)}", "상위 포지션 중심입니다. 리밸런싱 시 먼저 볼 구간입니다.", "gold"),
        (f"USD 노출 {_format_weight(fx_weight)}", "원/달러 변동이 원화 평가금액에 직접 반영됩니다.", "olive"),
    ]
    if largest_cat:
        items.append((f'{largest_cat["name"]} {_format_weight(largest_cat.get("weight"))}', "자산군 분산 상태를 함께 확인하세요.", "olive"))
    if today_state == "outlier":
        items.append((today_value, today_sub, ""))
    return (
        '<div class="pd-diagnosis">'
        '<div class="pd-diagnosis-head"><b>포트폴리오 진단</b>'
        '<div class="pd-head-right"><span>한눈에 판단할 핵심 원인</span>' + actions + '</div></div>'
        + _holdings_concentration_html(positions)   # 종목 집중 시각화(핵심)
        + _mini_allocation_html(categories)          # 자산군 분산(보조)
        + extra_html                                  # 탐욕 바 — 자산군 바 아래로(위치 스왑)
        + '<div class="pd-diagnosis-grid">'
        + "".join(f'<div class="pd-diagnosis-item {sev}"><strong>{_escape(title)}</strong><span>{_escape(body)}</span></div>' for title, body, sev in items[:4])
        + '</div>'
        + '</div>'
    )


def _sort_positions(positions: list[dict], target_prices: dict[str, float], sort_key: str) -> list[dict]:
    if sort_key == "수익률순":
        return sorted(positions, key=lambda p: p.get("gain_loss_pct") if p.get("gain_loss_pct") is not None else -999999, reverse=True)
    if sort_key == "오늘 변동순":
        return sorted(positions, key=lambda p: abs(p.get("today_change_pct") or 0), reverse=True)
    if sort_key == "목표여력순":
        return sorted(positions, key=lambda p: _target_upside(p, target_prices) if _target_upside(p, target_prices) is not None else -999999, reverse=True)
    return sorted(positions, key=lambda p: p.get("weight") or 0, reverse=True)


# 쓰레기통 아이콘 — 이모지(🗑)는 폰트에 따라 두부(□)로 깨져서 인라인 SVG 사용.
_TRASH_SVG = ('<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
              '<path d="M10 11v6M14 11v6"/></svg>')


def _holdings_table_html(positions: list[dict], target_prices: dict[str, float], limit: int | None = None,
                         editable: bool = False, sfx: str = "") -> str:
    visible = positions[:limit] if limit else positions
    if not visible:
        return '<div class="pd-empty"><b>표시할 보유종목이 없습니다</b><p>포트폴리오 데이터가 연결되면 여기에 종목 리스트가 표시됩니다.</p></div>'
    max_w = max((p.get("weight") or 0 for p in visible), default=0)
    from core.market_hours import is_open
    _opens = {"US": is_open("US"), "KR": is_open("KR"), "CRYPTO": True, "FX": is_open("FX")}  # '오늘/전일' 라벨용
    rows = []
    for position in visible:
        w = position.get("weight") or 0
        gain_cls = _tone(position.get("gain_loss_pct"))
        day_cls = _tone(position.get("today_change_pct"), 0.05)
        primary_value, secondary_value = _position_value_pair(position)
        target, _, _ = _target_info(position, target_prices)
        upside = _target_upside(position, target_prices)
        upside_label = f"{upside:+.1f}%" if upside is not None else "데이터 없음"
        upside_cls = _tone(upside)
        _cur_disp = _price_currency(position)   # 현재가 표시통화(미국주식→USD) — 평가액 환산통화와 별개
        logo_item = {"group": position["category"], "name": position["name"], "code": position["ticker"]}
        shares = _fmt_qty(position.get("quantity"), position.get("quantity_est", False))
        # 비중 바: 최대 비중만 주황(집중 위험 — 경고 채널), 나머지 회색. 손익 빨강과 분리
        bar_color = "#E2683C" if (max_w > 0 and w >= max_w) else "#5A5F52"
        # 손익률·금액·오늘 — 한 줄, 색 적용(12.5px)
        # C2: 점(·) 대신 간격으로 손익률 / 금액 / 오늘 구분(빽빽함 해소)
        if position.get("gain_loss_pct") is not None:
            ret = (f'<span class="hl-ret-pct {gain_cls}">{position["gain_loss_pct"]:+.1f}%</span>'
                   f'<span class="hl-ret-amt {gain_cls}">{_money(position.get("gain_loss"), "KRW", signed=True, compact=True)}</span>')
        else:
            ret = '<span class="pd-neu">손익 대기</span>'
        _tlabel = _today_label(_quote_ticker(position.get("ticker", ""), position["category"]), _opens)  # 미국장 마감 시 '전일'
        today = (f'<span class="hl-ret-today">{_tlabel} <b class="{day_cls}">{position["today_change_pct"]:+.2f}%</b></span>'
                 if position.get("today_change_pct") is not None
                 else f'<span class="hl-ret-today">{_tlabel} —</span>')   # 미제공도 자리 유지(스캔성)
        # 행 전체(summary)를 클릭하면 아래로 상세가 펼쳐짐. 🗑은 summary 바깥(맨 우측 거터)에 둬 클릭 충돌 방지.
        hid = quote(_holding_ident(position))
        trash = (f'<a class="hl-trash" href="?pf=holdings&hdel={hid}{sfx}" target="_self" '
                 f'title="삭제" aria-label="삭제">{_TRASH_SVG}</a>') if editable else ''
        rows.append(
            f'<div class="hl-rowwrap{" editable" if editable else ""}">'
            '<details class="hl-exp" name="hold-acc">'
            '<summary class="hl-srow" aria-label="상세 보기">'
            '<div class="hl-main">'
            f'{_logo_html(logo_item)}'
            '<div class="hl-info">'
            f'<b class="hl-name">{_escape(position["name"])}</b>'
            f'<span class="hl-sub"><b class="hl-w">비중 {_format_weight(w)}</b> · {_escape(position["category"])} · {_escape(shares)}</span>'
            f'<div class="hl-wbar"><i style="width:{min(w,100):.0f}%;background:{bar_color}"></i></div>'
            '</div></div>'
            '<div class="hl-vals">'
            f'<b class="hl-val">{_escape(primary_value)}</b>'
            f'<span class="hl-ret">{ret}{today}</span>'
            '</div>'
            '</summary>'
            '<div class="hl-detail">'
            f'<div class="hl-d-note">{_insight_text(position, target_prices)}</div>'
            '<div class="hl-d-facts">'
            f'<div><span>현재가</span><b>{_price(position.get("current_price"), _cur_disp)}</b></div>'
            f'<div><span>평가액</span><b>{_escape(primary_value)}</b><em>{_escape(secondary_value)}</em></div>'
            f'<div><span>목표가</span><b>{_escape(target)}</b></div>'
            f'<div><span>여력</span><b class="{upside_cls}">{_escape(upside_label)}</b></div>'
            '</div></div>'
            '</details>'
            f'{trash}'
            '</div>'
        )
    return '<div class="pd-table-card hl-card">' + "".join(rows) + '</div>'


_CONTRIB_CSS = """<style>
.pc-card{background:#16181F;border:1px solid #262A33;border-radius:14px;padding:6px 14px 10px;margin:2px 0 14px}
.pc-row{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,2fr) auto;align-items:center;
  gap:10px;padding:8px 2px;border-bottom:1px solid rgba(38,42,51,.6)}
.pc-row:last-of-type{border-bottom:none}
.pc-nm{font-size:12px;font-weight:900;color:#E7E9EE;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pc-nm small{display:block;font-size:9.5px;color:#7E8694;font-weight:800}
.pc-bar{position:relative;height:14px}
.pc-bar .pc-zero{position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:#262A33}
.pc-bar i{position:absolute;top:2px;bottom:2px;border-radius:3px}
.pc-bar i.p{left:50%;background:linear-gradient(90deg,rgba(242,85,96,.9),rgba(242,85,96,.45))}
.pc-bar i.n{right:50%;background:linear-gradient(270deg,rgba(77,144,240,.9),rgba(77,144,240,.45))}
.pc-amt{font-size:12px;font-weight:900;font-family:'SF Mono',ui-monospace,monospace;
  font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.pc-amt.pos{color:#F25560}.pc-amt.neg{color:#4D90F0}
.pc-amt small{display:block;font-size:9px;color:#7E8694;font-weight:700}
.pc-sum{font-size:10.5px;color:#7E8694;font-weight:750;margin-top:8px;line-height:1.55}
.pc-sum b{color:#E7E9EE}
@media(max-width:640px){.pc-row{grid-template-columns:minmax(0,1fr) minmax(0,1.4fr) auto;gap:7px}}
</style>"""


def _contribution_html(positions: list[dict], summary: dict, mode: str = "오늘") -> str:
    """'누가 계좌를 움직였나' — 손익 기여 랭킹(상승·하락 상위 2 + 요약 한 줄).
    기여 %p = 금액 ÷ 기준값(오늘=현재총액, 누적=총원금) × 100. 기존 포지션 데이터만 사용(신규 호출 없음)."""
    key = "today_change_amount" if mode == "오늘" else "gain_loss"
    base = (summary.get("total_market_value") if mode == "오늘"
            else summary.get("total_cost_basis")) or 0
    # 표기상 0.00%p 로 반올림되는 미미한 기여는 노이즈 → 제외
    rows = [p for p in positions
            if p.get("category") != "현금"
            and abs((p.get(key) or 0) / base * 100 if base else 0) >= 0.005]
    if not rows or not base:
        return ""
    ups = sorted((p for p in rows if (p.get(key) or 0) > 0), key=lambda p: p[key], reverse=True)[:2]
    dns = sorted((p for p in rows if (p.get(key) or 0) < 0), key=lambda p: p[key])[:2]
    picks = ups + dns
    max_abs = max(abs(p[key]) for p in picks)

    def _row(p: dict) -> str:
        v = p[key]
        pp = v / base * 100
        width = abs(v) / max_abs * 46 if max_abs else 0
        sign, cls, bar = ("+", "pos", "p") if v > 0 else ("−", "neg", "n")
        code = _escape(str(p.get("ticker") or ""))
        return (
            '<div class="pc-row">'
            f'<div class="pc-nm">{_escape(p.get("name") or code)}'
            f'<small>{code} · 비중 {p.get("weight", 0):.0f}%</small></div>'
            f'<div class="pc-bar"><span class="pc-zero"></span><i class="{bar}" style="width:{width:.1f}%"></i></div>'
            f'<div class="pc-amt {cls}">{sign}₩{abs(v):,.0f}<small>{pp:+.2f}%p</small></div>'
            '</div>'
        )

    up_pp = sum((p.get(key) or 0) for p in rows if (p.get(key) or 0) > 0) / base * 100
    dn_pp = sum((p.get(key) or 0) for p in rows if (p.get(key) or 0) < 0) / base * 100
    mover = max(rows, key=lambda p: abs(p.get(key) or 0))
    mover_dir = "끌어올림" if (mover.get(key) or 0) > 0 else "끌어내림"
    _nm = str(mover.get("name") or "")
    # 이/가 조사 — 한글 종성 유무로 선택, 비한글 끝 글자는 '가'
    mover_josa = "이" if _nm and "가" <= _nm[-1] <= "힣" and (ord(_nm[-1]) - 0xAC00) % 28 else "가"
    net_pct = summary.get("today_change_pct") if mode == "오늘" else summary.get("total_gain_loss_pct")
    net_s = f"{net_pct:+.2f}%" if net_pct is not None else "—"
    label = "오늘 계좌 변동" if mode == "오늘" else "누적 수익률"
    summary_line = (
        f'<div class="pc-sum">{label} <b>{net_s}</b> 중 상승 기여 {up_pp:+.2f}%p · '
        f'하락 기여 {dn_pp:+.2f}%p — <b>{_escape(_nm)}</b>{mover_josa} 가장 크게 {mover_dir}</div>'
    )
    return _CONTRIB_CSS + '<div class="pc-card">' + "".join(_row(p) for p in picks) + summary_line + '</div>'


def _holdings_panel_html(
    title: str,
    subtitle: str,
    positions: list[dict],
    target_prices: dict[str, float],
    limit: int | None = None,
    action: str = "",
    editable: bool = False,
    sfx: str = "",
) -> str:
    return (
        '<div class="pd-list-panel">'
        f'<div class="pd-list-head"><b>{_escape(title)}</b>'
        f'<div class="pd-head-right"><span>{_escape(subtitle)}</span>{action}</div></div>'
        + _holdings_table_html(positions, target_prices, limit=limit, editable=editable, sfx=sfx)
        + '</div>'
    )


def _rebalance_html(positions: list[dict], summary: dict,
                    cap: float = 25.0, threshold: float = 5.0) -> str:
    """균형형(SAA + 임계 리밸런싱) 조정 표. cap=단일 종목 상한, threshold=±%p 임계 밴드."""
    if not positions:
        return '<div class="pd-empty"><b>리밸런싱 계산 대기</b><p>보유종목 데이터가 연결되면 집중도 완화 시나리오를 계산합니다.</p></div>'
    largest = positions[0]
    total = summary.get("total_market_value") or 0
    current_weight = largest.get("weight") or 0
    trim_amount = max(0, (largest.get("market_value") or 0) - total * (cap / 100))
    top3_weight = sum(p.get("weight", 0) for p in positions[:3])
    fx_weight = sum(p.get("weight", 0) for p in positions if p.get("currency") == "USD")

    # ── 종목별 조정 표: 단일 종목 상한(cap%) + ±threshold%p 임계 리밸런싱. 금액 자동 산출 ──
    from core.pb import friction_krw
    rows = []
    freed = 0.0
    freed_fee = 0.0       # 매도 실행 마찰비용(거래세·수수료·환전) 개략 추정
    freed_has_us = False
    for p in positions[:8]:
        w = p.get("weight", 0) or 0
        tgt = min(w, cap)
        delta = tgt - w                       # 음수 = 매도, 양수 = 매수
        amt = delta / 100 * total
        if abs(delta) < 0.05:
            adj_html = '<span class="rb-keep">유지</span>'
            amt_html = '<span class="rb-keep rb-num">—</span>'
        elif abs(delta) < threshold:          # 임계 밴드 이내 → 거래 안 함(과잉 매매 방지)
            adj_html = '<span class="rb-keep rb-num">유지 · 임계 이내</span>'
            amt_html = '<span class="rb-keep rb-num">—</span>'
        else:
            cls = "rb-sell" if delta < 0 else "rb-buy"   # 매도=블루 / 매수=레드(한국식)
            word = "매도" if delta < 0 else "매수"
            adj_html = f'<span class="{cls} rb-num">{delta:+.1f}%p {word}</span>'
            amt_html = f'<span class="{cls} rb-num">{_money(amt, "KRW", signed=True, compact=True)}</span>'
            if delta < 0:
                _is_us = p.get("currency") == "USD"
                freed += -amt
                freed_fee += friction_krw(-amt, is_us=_is_us)
                freed_has_us = freed_has_us or _is_us
        rows.append(
            '<div class="rb-trow">'
            f'<span class="rb-nm">{_escape(p.get("name", ""))}</span>'
            f'<span class="rb-cur">{pct_weight(w)}%</span>'
            f'<span class="rb-tgt">{pct_weight(tgt)}%</span>'
            f'{adj_html}{amt_html}</div>'
        )
    foot = (
        f'매도 재원 약 <b style="color:#4D90F0">{_money(freed, "KRW", compact=True)}</b>은 '
        f'현금 비중 확대·다른 자산군 분산 매수에 배분하는 시나리오입니다. '
        f'(단일 종목 상한 {pct_weight(cap)}% · ±{pct_weight(threshold)}%p 임계)<br>'
        f'<span style="color:#7E8694">실행 비용 약 {_money(freed_fee, "KRW", compact=True)} 차감 시 '
        f'순재원 약 {_money(max(freed - freed_fee, 0), "KRW", compact=True)} '
        f'— 거래세·수수료{"·환전" if freed_has_us else ""} 추정'
        f'{" · 해외 양도세는 실현손익에 따라 별도" if freed_has_us else ""}.</span>'
        if freed > 0 else
        f'단일 종목 상한 {pct_weight(cap)}% · ±{pct_weight(threshold)}%p 임계 이내 — 즉시 조정할 과집중 종목은 없습니다.'
    )
    table = (
        '<div class="pd-diagnosis">'
        '<div class="pd-diagnosis-head"><b>종목별 조정</b><span>현재 → 목표(상한) · 금액 자동 산출</span></div>'
        '<div class="rb-tbl">'
        '<div class="rb-thead"><span>종목</span><span>현재</span><span>목표</span>'
        '<span class="rb-num">조정</span><span class="rb-num">금액(원화)</span></div>'
        + "".join(rows)
        + f'<div class="rb-foot">{foot}</div>'
        '</div></div>'
    )

    # ── 매도 자금 이동처(자산군 수준) — 목표 배분에서 부족한 칸 채우기. 종목·상품 추천 금지 ──
    cash = summary.get("cash_balance") or 0
    cash_now = (cash / total * 100) if total else 0
    div_now = sum((p.get("weight") or 0) for p in positions
                  if p.get("category") in ("ETF", "원자재", "채권", "크립토"))
    freed_pct = (freed / total * 100) if total else 0
    cash_target = 10.0                                   # 현금 완충 목표(균형형 룰)
    cash_move = min(freed_pct, max(0.0, cash_target - cash_now))   # 현금 부족분 우선 채움
    div_move = max(0.0, freed_pct - cash_move)           # 나머지는 분산 자산군으로
    dest = [
        ("현금 완충", cash_now, cash_now + cash_move, cash_move),
        ("분산 자산군 (ETF·채권 등 저상관)", div_now, div_now + div_move, div_move),
    ]
    drows = ""
    for nm, cur, tgt, mv in dest:
        if mv > 0.05:
            mv_html = (f'<span class="rb-move rb-num">+{mv:.1f}%p</span>'
                       f'<span class="rb-move rb-num">+{_money(mv / 100 * total, "KRW", compact=True)}</span>')
        else:
            mv_html = '<span class="rb-keep rb-num">유지</span><span class="rb-keep rb-num">—</span>'
        drows += (
            '<div class="rb-trow">'
            f'<span class="rb-nm">{_escape(nm)}</span>'
            f'<span class="rb-cur">{pct_weight(cur)}%</span>'
            f'<span class="rb-tgt">{pct_weight(tgt)}%</span>'
            f'{mv_html}</div>'
        )
    dest_block = (
        '<div class="pd-diagnosis">'
        '<div class="pd-diagnosis-head"><b>매도 자금 이동처</b><span>자산군 수준 · 종목·상품 추천 아님</span></div>'
        '<div class="rb-tbl">'
        '<div class="rb-thead"><span>자산군</span><span>현재</span><span>목표</span>'
        '<span class="rb-num">이동</span><span class="rb-num">금액(원화)</span></div>'
        + drows
        + '<div class="rb-foot">이동처는 <b style="color:#C99A3C">자산군 분산 방향</b>이며 특정 종목·상품(예: 개별 주식·ETF 티커) 추천이 아닙니다. '
          '구체 상품 선택과 최종 책임은 본인에게 있습니다.</div>'
        '</div></div>'
    ) if freed_pct > 0.05 else ""

    # ── '앱이 돕는 것' vs '사용자가 정하는 것' 역할 분리 ──
    reduction = max(0.0, current_weight - min(current_weight, cap))
    roles_block = (
        '<div class="rb-split">'
        '<div class="rb-role app"><div class="rb-role-k">앱이 돕는 것</div>'
        '<ul><li>부족한 자산군 식별(현금·분산)</li>'
        '<li>균형까지 필요한 배분 금액 자동 산출</li>'
        f'<li>집중 위험 감소폭: {pct_weight(current_weight)}% → {pct_weight(min(current_weight, cap))}% '
        f'(−{reduction:.1f}%p)</li></ul></div>'
        '<div class="rb-role user"><div class="rb-role-k">사용자가 정하는 것</div>'
        '<ul><li>구체 종목·상품 선택</li><li>매수 타이밍</li><li>분할 매수 횟수</li></ul></div>'
        '</div>'
    )
    return (
        '<div class="pd-rebalance-grid">'
        '<div class="pd-rebalance-card">'
        f'<b>{_escape(largest["name"])} {pct_weight(cap)}% 시나리오</b>'
        f'<p>현재 비중 {pct_weight(current_weight)}%에서 {pct_weight(cap)}%로 낮추려면 원화 기준 약 {_money(trim_amount, "KRW", compact=True)} 규모를 다른 자산군으로 옮기는 시나리오를 검토할 수 있습니다.</p>'
        '</div>'
        '<div class="pd-rebalance-card">'
        '<b>우선순위</b>'
        f'<p>상위 3개 비중 {pct_weight(top3_weight)}%, USD 노출 {pct_weight(fx_weight)}%입니다. 신규 매수 전에는 단일 종목과 환율 노출을 먼저 낮추는 선택지가 더 직접적입니다.</p>'
        '</div></div>'
        + table + dest_block + roles_block
    )


# ── 운용 방식(철학) 레이어 — 근거 출처 명시, 균형형만 실제 계산 구현 ──────────────
_REBAL_METHODS = {
    "균형형": {
        "rec": True,
        "desc": "전략적 목표비중(SAA)에 ±5%p 임계 리밸런싱 · 단일 종목 상한 25%.",
        "src": "Vanguard·CFA 임계 · 골드만 SAA",
        "rule": "SAA(전략적 자산배분)",
        "when": "목표비중 ±5%p 이탈 시",
        "fit": "대부분의 장기 투자자",
        "engine": True,
    },
    "정량 최적화형": {
        "rec": False,
        "desc": "목표·위험성향을 입력해 수리 최적화로 배분을 도출.",
        "src": "골드만 ISG robust optimization",
        "rule": "목표·위험성향 → 최적화",
        "when": "주기적 재최적화",
        "fit": "수치 모델을 신뢰하는 투자자",
        "engine": False,
    },
    "집중형": {
        "rec": False,
        "desc": "소수 확신 종목에 집중·장기 보유. 통상 단일 종목 ≤25%.",
        "src": "버핏 / 버크셔 주주서한",
        "rule": "확신 종목 집중",
        "when": "투자 논리 훼손 시",
        "fit": "깊은 리서치·고위험 감내",
        "engine": False,
    },
}


def _rebal_method_layer_html(selected: str, top_w: float) -> str:
    """방식 3카드(추천 골드 테두리·출처 라벨) + '내게 적합' 진단."""
    if top_w > 25:
        diag = (f"최대 종목 {pct_weight(top_w)}%는 집중형 상한(25%)도 초과 — "
                f"집중도부터 낮추는 <b>균형형</b>을 추천합니다.")
    else:
        diag = (f"최대 종목 {pct_weight(top_w)}% · 집중도는 양호합니다 — "
                f"목적에 맞게 선택하세요(기본 <b>균형형</b>).")
    cards = ""
    for name, m in _REBAL_METHODS.items():
        cls = "rbm-card" + (" rec" if m["rec"] else "") + (" sel" if name == selected else "")
        badge = '<span class="rbm-badge">추천</span>' if m["rec"] else ""
        impl = "" if m["engine"] else '<span class="rbm-soon">설명 제공 · 엔진 예정</span>'
        cards += (
            f'<div class="{cls}">'
            f'<div class="rbm-h">{name}{badge}</div>'
            f'<div class="rbm-d">{m["desc"]}</div>'
            f'<div class="rbm-src">근거 · {_escape(m["src"])}{impl}</div>'
            f'</div>'
        )
    return (
        f'<div class="rbm-diag"><span class="rbm-diag-k">내게 적합</span>{diag}</div>'
        f'<div class="rbm-grid">{cards}</div>'
    )


def _rebal_pending_html(method: str) -> str:
    """엔진 미구현 방식 — 설명만(과구현 방지)."""
    m = _REBAL_METHODS.get(method, {})
    return (
        '<div class="pd-diagnosis rbm-pending">'
        f'<div class="pd-diagnosis-head"><b>{_escape(method)}</b><span>설명 · 엔진은 추후 확장</span></div>'
        f'<p class="rbm-pending-p">{_escape(m.get("desc", ""))}<br>'
        f'목표비중: {_escape(m.get("rule", ""))} · 조정 시점: {_escape(m.get("when", ""))} · '
        f'적합: {_escape(m.get("fit", ""))}</p>'
        f'<p class="rbm-pending-note">자동 조정 표는 현재 <b>균형형</b>만 계산합니다. '
        f'이 방식은 선택지·설명으로 제공되며 계산 엔진은 추후 추가됩니다.</p>'
        f'<div class="rbm-src">근거 · {_escape(m.get("src", ""))}</div>'
        '</div>'
    )


def _rebal_compare_sources_html() -> str:
    """방식별 차이 표 + 정직성 문구 + 참고 출처."""
    rows = ""
    for name, m in _REBAL_METHODS.items():
        rec = ' <span class="rbm-badge sm">추천</span>' if m["rec"] else ""
        rows += (
            '<div class="rbm-trow">'
            f'<span class="rbm-tnm">{name}{rec}</span>'
            f'<span>{_escape(m["rule"])}</span>'
            f'<span>{_escape(m["when"])}</span>'
            f'<span>{_escape(m["fit"])}</span>'
            '</div>'
        )
    return (
        '<div class="pd-diagnosis">'
        '<div class="pd-diagnosis-head"><b>방식별 차이</b><span>정답 없음 · 목적에 맞게 선택</span></div>'
        '<div class="rbm-tbl">'
        '<div class="rbm-thead"><span>방식</span><span>목표비중 정하는 법</span>'
        '<span>조정 시점</span><span>적합 대상</span></div>'
        + rows
        + '</div>'
        '<div class="rbm-honest">리밸런싱은 <b>리스크 관리</b> 목적이며 수익을 보장하지 않습니다. '
        '운용 방식에 정답은 없고, 목적·성향에 맞게 선택하는 것입니다.</div>'
        '<div class="rbm-refs">참고 · 골드만 ISG · Morgan Stanley PWM · Vanguard·CFA · 버크셔 주주서한</div>'
        '</div>'
    )


def _risk_summary_html(positions: list[dict], categories: list[dict]) -> str:
    if not positions:
        return (
            '<div class="pd-card">'
            '<div class="pd-section-title"><b>리스크·집중도</b><span>애널리스트 관점</span></div>'
            '<div class="pd-risk-list">'
            '<div class="pd-risk-item"><b>계산 대기</b><span>실제 holdings 수량과 평가금액이 연결되면 최대 비중, 상위 3개 집중도, 환율 노출을 계산합니다.</span></div>'
            '</div></div>'
        )
    top3_weight = sum(p.get("weight", 0) for p in positions[:3])
    largest = positions[0]
    active_cats = [c for c in categories if c["count"] > 0]
    largest_cat = max(active_cats, key=lambda c: c["weight"]) if active_cats else None
    fx_weight = sum(p.get("weight", 0) for p in positions if p.get("currency") == "USD")
    items = [
        ("최대 비중 종목", f"{largest['name']} 비중 {pct_weight(largest.get('weight', 0))}%. 해당 종목 변동성이 전체 평가액에 반영될 수 있습니다."),
        ("상위 3개 종목 비중", f"상위 3개 포지션 합산 {pct_weight(top3_weight)}%. 집중도가 높을수록 개별 이슈 민감도가 커질 수 있습니다."),
        ("자산군 집중도", f"{largest_cat['name']} 비중 {pct_weight(largest_cat['weight'])}%." if largest_cat else "자산군 데이터 대기"),
        ("환율 영향", f"USD 표시 자산 비중 {pct_weight(fx_weight)}%. USD/KRW 변동이 원화 평가액에 반영될 수 있습니다."),
    ]
    return (
        '<div class="pd-card">'
        '<div class="pd-section-title"><b>리스크·집중도</b></div>'
        '<div class="pd-risk-list">'
        + "".join(f'<div class="pd-risk-item"><b>{_escape(title)}</b><span>{_escape(body)}</span></div>' for title, body in items)
        + '</div></div>'
    )


def _target_info(position: dict, target_prices: dict[str, float]) -> tuple[str, str, str]:
    target = target_prices.get(position["ticker"])
    current = position.get("current_price")
    if target and current:
        upside = (target / current - 1) * 100
        cls = _tone(upside)
        return f"${target:,.0f}", f"{upside:+.1f}%", cls
    return "미제공", "데이터 없음", "pd-neu"


def _insight_text(position: dict, target_prices: dict[str, float]) -> str:
    # 목표가/여력은 아래 사실 요약줄에 한 번만 표기 — 여기선 중복 제거. 영향도는 비중 기반 구체값으로.
    tk = str(position["ticker"])
    note = (_consensus_notes(tk).get(tk)
            or "네이버 컨센서스 미연결 종목 · 가격, 비중, 손익 변화를 함께 확인하세요.")
    w = float(position.get("weight") or 0)
    impact = (f"이 종목이 20% 하락하면 계좌 평가액은 약 {w * 0.2:.1f}% 영향을 받습니다."
              if w > 0 else "비중 정보가 없어 영향도를 계산할 수 없습니다.")
    return (
        f"<b>주요 이슈</b>: {_escape(note)}<br>"
        f"<b>영향도</b>: {_escape(impact)}<br>"
        "<b>체크포인트</b>: 실적 가이던스, 금리·환율, 업종 모멘텀, 포트폴리오 내 비중 변화"
    )


def _journey_chart_svg(progress_pct: float, current: float, target: float,
                       checkpoints: list[float]) -> str:
    from core.journey import krw_compact
    W, H, PL, PR, BY = 1000, 150, 70, 70, 82
    span = W - PL - PR
    cur_p = max(0.0, min(100.0, progress_pct))

    def x(pct: float) -> float:
        return PL + pct / 100 * span

    xc = x(cur_p)
    # 경로: 걸어온 길=골드 실선, 남은 길=무채색 점선
    svg = (
        f'<line x1="{PL}" y1="{BY}" x2="{xc:.1f}" y2="{BY}" stroke="#D9A441" '
        f'stroke-width="4" stroke-linecap="round"/>'
        f'<line x1="{xc:.1f}" y1="{BY}" x2="{x(100):.1f}" y2="{BY}" stroke="#3A4150" '
        f'stroke-width="2" stroke-dasharray="3 6" stroke-linecap="round"/>'
    )
    # 체크포인트 (1/3, 2/3, 목표)
    cps = [(100.0 * (i + 1) / len(checkpoints), amt) for i, amt in enumerate(checkpoints)]
    next_idx = next((i for i, (_, amt) in enumerate(cps) if amt > current + 1), len(cps) - 1)
    for i, (cp, amt) in enumerate(cps):
        cx = x(cp)
        is_target = (i == len(cps) - 1)
        achieved = amt <= current + 1
        if is_target:
            svg += (f'<circle cx="{cx:.1f}" cy="{BY}" r="9" fill="#16181F" '
                    f'stroke="#D9A441" stroke-width="3"/>'
                    f'<circle cx="{cx:.1f}" cy="{BY}" r="3.5" fill="#E7E9EE"/>')
            label = "목표"
        elif achieved:
            svg += f'<circle cx="{cx:.1f}" cy="{BY}" r="7" fill="#D9A441"/>'
            label = krw_compact(amt)
        elif i == next_idx:
            svg += (f'<circle cx="{cx:.1f}" cy="{BY}" r="8" fill="#16181F" '
                    f'stroke="#D9A441" stroke-width="2.5"/>')
            label = krw_compact(amt)
        else:
            svg += (f'<circle cx="{cx:.1f}" cy="{BY}" r="6" fill="#16181F" '
                    f'stroke="#3A4150" stroke-width="2"/>')
            label = krw_compact(amt)
        svg += (f'<text x="{cx:.1f}" y="{BY + 26}" text-anchor="middle" '
                f'fill="#7E8694" font-size="13" font-weight="700">{label}</text>')
    # 현재 위치 마커 (숫자 중복 금지 → "현재"만)
    svg += (
        f'<line x1="{xc:.1f}" y1="{BY - 20}" x2="{xc:.1f}" y2="{BY + 12}" '
        f'stroke="#D9A441" stroke-width="2"/>'
        f'<circle cx="{xc:.1f}" cy="{BY}" r="5" fill="#D9A441" stroke="#16181F" stroke-width="2"/>'
        f'<rect x="{xc - 26:.1f}" y="{BY - 44}" width="52" height="20" rx="10" '
        f'fill="rgba(217,164,65,0.14)" stroke="rgba(217,164,65,0.4)"/>'
        f'<text x="{xc:.1f}" y="{BY - 30}" text-anchor="middle" fill="#D9A441" '
        f'font-size="12" font-weight="800">현재</text>'
    )
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'preserveAspectRatio="none" style="width:100%;height:auto;display:block">{svg}</svg>')


# ── B3: 계좌 시계열 스냅샷 + 자산 추이 ────────────────────────────────────────
def _record_today_snapshot(username: str | None, summary: dict, positions: list[dict]) -> None:
    """오늘 자산 스냅샷 기록 — 로그인 유저·세션당 1회(잦은 파일쓰기 방지)."""
    if not username:
        return
    from datetime import date as _d
    today = _d.today().isoformat()
    flag = f"_snap_done_{username}_{today}"
    if st.session_state.get(flag):
        return
    top = positions[0] if positions else {}
    try:
        from core.accounts import record_snapshot
        record_snapshot(username, {
            "date": today,
            "total": summary.get("total_market_value") or 0,
            "gain_pct": summary.get("total_gain_loss_pct"),
            "today_pct": summary.get("today_change_pct"),
            "top_name": top.get("name"),
            "top_weight": top.get("weight"),
            "cash": summary.get("cash_balance") or 0,
        })
        st.session_state[flag] = True
    except Exception:
        pass


# _AT_CSS → ui.pages.portfolio_css 로 이동


def _yf_history_symbol(ticker: str, currency, category) -> tuple[str, object]:
    """yfinance 가격 이력용 심볼·통화 정규화.

    크립토는 'BTC' → 'BTC-USD'(USD결제)로 바꾼다. bare 'BTC'/'ETH'는 yfinance에서
    동명의 엉뚱한 주식($27 등)으로 잡혀 추이 총액이 망가지던 버그(끝값 24원)의 원인.
    이미 -USD/.KS/=X/=F/^ 등 정규 심볼이거나 크립토가 아니면 그대로 둔다.
    """
    t = (ticker or "").upper()
    if t.endswith(("-USD", ".KS", ".KQ", "=X", "=F")) or t.startswith("^"):
        return ticker, currency
    if category == "크립토" or t in _COIN_SOLID:
        return f"{t}-USD", "USD"
    return ticker, currency


def _portfolio_value_series(positions: list[dict], period: str, fx: float, start: str | None = None):
    """보유 × 기간 일별 종가 → 일별 총 평가액(원화) 시계열. 현재 수량을 기간 내 보유했다고 가정(추세 근사).

    start(YYYY-MM-DD)가 주어지면 그 날짜~현재 구간으로 받는다('전체=투자 시작일~현재'용). 없으면 period 사용.
    """
    import pandas as pd
    from data.session import cached_download
    holds = []
    for p in positions:
        if not p.get("ticker") or not ((p.get("quantity") or 0) > 0):
            continue
        sym, cur = _yf_history_symbol(p["ticker"], p.get("currency"), p.get("category"))
        holds.append((sym, float(p.get("quantity") or 0), cur))
    if not holds:
        return None
    tickers = [t for t, _, _ in holds]
    try:
        if start:
            raw = cached_download(tickers, start=start, interval="1d", progress=False, auto_adjust=True)
        else:
            raw = cached_download(tickers, period=period, interval="1d", progress=False, auto_adjust=True)
    except Exception:
        return None
    if raw is None or raw.empty:
        return None
    multi = len(tickers) > 1
    frames = []
    for tk, qty, cur in holds:
        try:
            closes = (raw["Close"][tk] if multi else raw["Close"]).dropna()
        except Exception:
            continue
        if closes.empty:
            continue
        v = closes * qty * (fx if cur == "USD" else 1.0)
        v.name = tk
        frames.append(v)
    if not frames:
        return None
    return pd.concat(frames, axis=1).sort_index().ffill().sum(axis=1).dropna()


def _asset_trend_svg(series) -> str:
    """자산 추이를 자산 여정 바와 '동일한 슬롯(viewBox 1000x150)'에 그리는 인라인 SVG.
    Catmull-Rom 곡선(부드러움) + 골드 영역 채움 + 시작·현재 값 라벨. 바 자리에서 in-place 교체용."""
    from core.journey import krw_compact
    if series is None or len(series) < 2:
        return ('<div style="height:103px;display:grid;place-items:center;color:#7E8694;'
                'font-size:12px;font-weight:700">추이 데이터 대기</div>')
    ys = [float(v) for v in series.values]
    n = len(ys)
    W, H, PL, PR, PT, PB = 1000, 150, 12, 12, 18, 26
    span, lo, hi = W - PL - PR, min(ys), max(ys)
    rng = (hi - lo) or 1.0
    pts = [(PL + (i / (n - 1)) * span, PT + (1 - (ys[i] - lo) / rng) * (H - PT - PB)) for i in range(n)]
    # Catmull-Rom → cubic bezier 로 부드러운 path
    d = f'M {pts[0][0]:.1f} {pts[0][1]:.1f}'
    for i in range(n - 1):
        p0, p1, p2 = pts[i - 1] if i > 0 else pts[0], pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[-1]
        c1x, c1y = p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6
        c2x, c2y = p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6
        d += f' C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {p2[0]:.1f} {p2[1]:.1f}'
    base = H - PB
    area = d + f' L {pts[-1][0]:.1f} {base:.1f} L {pts[0][0]:.1f} {base:.1f} Z'
    col = "#D9A441"
    svg = (
        f'<defs><linearGradient id="atg" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{col}" stop-opacity="0.30"/>'
        f'<stop offset="1" stop-color="{col}" stop-opacity="0.02"/></linearGradient></defs>'
        f'<path d="{area}" fill="url(#atg)"/>'
        f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{pts[0][0]:.1f}" cy="{pts[0][1]:.1f}" r="3.5" fill="#16181F" stroke="{col}" stroke-width="2"/>'
        f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="4.5" fill="{col}" stroke="#16181F" stroke-width="2"/>'
        f'<text x="{pts[0][0]:.1f}" y="{base + 18:.1f}" text-anchor="start" fill="#7E8694" font-size="12" font-weight="700">{krw_compact(ys[0])}</text>'
        f'<text x="{pts[-1][0]:.1f}" y="{base + 18:.1f}" text-anchor="end" fill="#E7E9EE" font-size="12" font-weight="800">{krw_compact(ys[-1])}</text>'
    )
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'preserveAspectRatio="none" style="width:100%;height:auto;display:block">{svg}</svg>')


def _journey_eta_display(m: dict, current: float, target: float) -> str:
    """예상 기간 라벨. 이미 목표 도달이면 '목표 도달',
    연 성장률(CAGR)이 0 이하면 현재 추세로는 닿지 못하므로 '투자 실패',
    그 외에는 'N년 M개월'."""
    from core.journey import eta_label
    if target > 0 and current >= target:
        return "목표 도달"
    if m.get("cagr_pct", 0) <= 0:
        return "투자 실패"
    return eta_label(m.get("years_to_goal"))


_AJ_BAND, _AJ_BIG = 5.0, 20.0   # 순항(±5%p) / 크게(±20%p) 임계 — 벤치마크 대비 격차(%p)


def _journey_bench_badge_html(positions: list[dict] | None, current: float,
                              start_value: float, start_date) -> str:
    """상태 배지 — '같은 기간 시장(내 카테고리 벤치마크 비중블렌드) 대비' 단일 평가.
    내 수익률 > 벤치=상회(골드) / ≈벤치=순항(중립) / < 벤치=하회(주황). 격차 ±N.N%p 병기.
    데이터/커버리지 부족 시 빈 문자열(배지 숨김)."""
    if not positions or not start_value:
        return ""
    try:
        from core.pb import blended_benchmark_return
        b = blended_benchmark_return(positions, start_date)
    except Exception:
        return ""
    if b["coverage"] < 0.5:
        return ""
    excess = ((current / start_value - 1) - b["blended"]) * 100   # %p
    if excess >= _AJ_BIG:
        cls, txt = "ahead", f'시장 크게 상회 +{excess:.1f}%p'
    elif excess >= _AJ_BAND:
        cls, txt = "ahead", f'시장 상회 +{excess:.1f}%p'
    elif excess > -_AJ_BAND:
        cls, txt = "ontrack", "순항 · 시장 수준"
    elif excess > -_AJ_BIG:
        cls, txt = "behind", f'시장 하회 −{abs(excess):.1f}%p'      # 벤치마크 대비(목표 대비 아님) — 명칭 혼동 방지
    else:
        cls, txt = "behind", f'시장 크게 하회 −{abs(excess):.1f}%p'
    return f'<div class="aj-badgewrap"><span class="aj-pace {cls}">{txt}</span></div>'


def _journey_cards_html(current: float, m: dict, target: float = 0.0) -> str:
    from core.journey import krw_compact
    eta = _journey_eta_display(m, current, target)
    unreachable = eta == "투자 실패"
    eta_cls = ' style="color:%s"' % _CONC_ALARM if unreachable else ''   # 위험경고=주황
    cagr = m["cagr_pct"]
    cagr_html = (f'<span style="color:{DOWN}">{cagr:.1f}%</span>'    # 음수 성장률=파랑
                 if cagr < 0 else f'{cagr:.1f}%')
    return (
        f'<div class="aj-card"><div class="k">목표까지</div>'
        f'<div class="v">{krw_compact(m["remaining"])}</div></div>'
        f'<div class="aj-card"><div class="k">예상 기간 <span class="aj-auto">자동</span></div>'
        f'<div class="v"{eta_cls}>{eta}</div></div>'
        f'<div class="aj-card"><div class="k">연 성장률 <span class="aj-auto">자동</span></div>'
        f'<div class="v">{cagr_html}</div></div>'
        f'<div class="aj-card"><div class="k">현재 자산</div>'
        f'<div class="v">{krw_compact(current)}</div></div>'
    )


def _journey_leftcell_html(current: float, target: float, m: dict, chart_svg: str | None = None,
                           headline_label: str | None = None, headline_val_html: str | None = None,
                           clickable: bool = False) -> str:
    """헤드라인 + 차트(진행률 바 또는 추이 SVG). clickable 이면 바 클릭 힌트 표시(오버레이 버튼이 위에 겹침)."""
    from core.journey import milestones
    hl_label = headline_label or "목표 도달률"
    hl_val = headline_val_html if headline_val_html is not None else f'{m["progress_pct"]:.1f}%'
    if chart_svg is not None:
        # in-place 교체: 바와 같은 .aj-chart 슬롯에 추이 SVG(동일 위치·크기) + 바닥에서 차오르는 애니메이션
        hint = '<div class="aj-chart-hint">여정으로 ⤢</div>' if clickable else ''
        chart_html = f'<div class="aj-chart aj-chart-trend">{chart_svg}{hint}</div>'
    else:
        chart = _journey_chart_svg(m["progress_pct"], current, target, milestones(target))
        hint = '<div class="aj-chart-hint">지나온 경로 보기 ⤢</div>' if clickable else ''
        chart_html = f'<div class="aj-chart">{chart}{hint}</div>'
    return (f'<div class="aj-headline"><span class="lbl">{hl_label}</span>'
            f'<span class="val">{hl_val}</span></div>{chart_html}')


def _journey_block_html(current: float, target: float, m: dict, chart_svg: str | None = None,
                        headline_label: str | None = None, headline_val_html: str | None = None) -> str:
    # 단일 그리드(클릭 없음, 게스트 등) — 좌(헤드라인+차트) | 우(카드)
    left = _journey_leftcell_html(current, target, m, chart_svg, headline_label, headline_val_html, clickable=False)
    return (_AJ_CSS + '<div class="aj-grid"><div>' + left + '</div>'
            f'<div class="aj-cards">{_journey_cards_html(current, m, target)}</div></div>')


def _journey_get(key, username, is_guest, default):
    """여정 설정값 조회 — 로그인 유저는 DB, 게스트는 세션."""
    if username and not is_guest:
        from core.accounts import get_setting
        v = get_setting(username, key, None)
        if v is not None:
            return v
    return st.session_state.get(f"journey_{key}", default)


def _journey_set(key, value, username, is_guest) -> None:
    st.session_state[f"journey_{key}"] = value
    if username and not is_guest:
        from core.accounts import set_setting
        set_setting(username, key, value)


def _estimate_start_value(positions: list[dict] | None, total: float) -> float:
    """초기 투자금(원가) 추정 — 매입금액이 없어도 보유 수익률(gain_loss_pct)로 평가금액에서
    역산해 실제 수익률이 반영되게(원가 = 평가금액 / (1+수익률/100)). 데이터 없으면 0.62×현재 폴백.
    이전엔 무조건 0.62×현재라, 손실 포트폴리오도 '수익률 +61.3%'(=1/0.62-1)로 잘못 표기됐음."""
    cost, ok = 0.0, False
    for p in (positions or []):
        mv = p.get("market_value")
        if mv is None:
            continue
        gp = p.get("gain_loss_pct")
        if gp is not None and (1 + gp / 100) > 0.01:
            cost += mv / (1 + gp / 100); ok = True
        else:
            cost += mv
    return cost if (ok and cost > 0) else max(1.0, total * 0.62)


def _journey_settings_panel(target: int, start_date, username: str | None, is_guest: bool) -> None:
    """여정 설정(목표 금액·시작일) — 인라인 expander(전폭). 기존 st.popover는 모바일에서 톱니가
    배지 아래로 떨어지고 열고닫을 때 화면이 떨려서 안정적인 expander 로 교체."""
    from datetime import date as _date
    # 카드와 간격 + 차분한 우측 칩 톤다운(아래 expander 를 CSS 형제 선택자로 스타일).
    st.markdown(_AJ_CSS + '<div class="aj-set-anchor"></div>', unsafe_allow_html=True)
    with st.expander("⚙️ 목표·시작일 설정", expanded=False):
        # 목표 금액(억원). 초기투자금은 보유 원가로 자동 산출(stale 세션값 오염 방지).
        _TGT_MIN, _EOK_MAX = 0.1, 2000.0
        _target_eok = min(_EOK_MAX, max(_TGT_MIN, round(target / 1e8, 1)))
        new_target_eok = st.number_input(
            "목표 금액 (억원)", min_value=_TGT_MIN, max_value=_EOK_MAX,
            value=_target_eok, step=0.5, format="%.1f", key="aj_target_eok",
        )
        new_start_date = st.date_input(
            "투자 시작일", value=start_date, max_value=_date.today(), key="aj_start_date",
        )
        # 목표 기한 — 목표 엔진의 필요수익률(연복리) 역산 분모. 기본 5년 뒤.
        _td = _journey_target_date(username, is_guest)
        new_target_date = st.date_input(
            "목표 기한", value=_td, min_value=_date.today() + timedelta(days=30), key="aj_target_date",
        )
        st.caption("초기 투자금은 보유 원가로 자동 산출 · 시작일로 연 성장률(CAGR)·예상 기간을 계산합니다.")
        new_target = int(round(new_target_eok * 1e8))
        changed = False
        if new_target_eok != _target_eok:
            _journey_set("target_value", new_target, username, is_guest); changed = True
        if new_start_date.isoformat() != start_date.isoformat():
            _journey_set("start_date", new_start_date.isoformat(), username, is_guest); changed = True
        if new_target_date.isoformat() != _td.isoformat():
            _journey_set("target_date", new_target_date.isoformat(), username, is_guest); changed = True
        if changed:
            st.rerun()  # 전체 리런 — 벤치마크 비교·PB 진단도 새 시작일 반영


def _journey_target_date(username: str | None, is_guest: bool):
    """목표 기한 조회(기본 5년 뒤) — 설정 패널·목표 엔진 공용."""
    from datetime import date as _date
    raw = _journey_get("target_date", username, is_guest,
                       (_date.today() + timedelta(days=365 * 5)).isoformat())
    return _date.fromisoformat(raw) if isinstance(raw, str) else raw


_GOAL_CSS = """<style>
.ge-head{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline;background:#16181F;
  border:1px solid #262A33;border-radius:14px;padding:12px 16px;margin:12px 0 0}
.ge-prog-row{flex-basis:100%;display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.ge-prog-k{font-size:11.5px;font-weight:800;color:#9AA0AD}
.ge-prog-k b{color:#E7E9EE;font-size:14px}
.ge-prog{flex-basis:100%;display:block;height:7px;border-radius:99px;background:rgba(255,255,255,.07);overflow:hidden;margin:2px 0 6px}
.ge-prog i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,rgba(217,164,65,.55),#D9A441)}
.ge-prog-row .aj-badgewrap{margin:0}
@media(max-width:768px){.ge-prog-k{font-size:12.5px!important}.ge-prog-k b{font-size:15px!important}}
.ge-req{font-size:15px;font-weight:950;color:#E7E9EE}
.ge-req b{color:#D9A441}
.ge-act{font-size:12px;font-weight:800;color:#9AA0AD}
.ge-act b.pos{color:#F25560}.ge-act b.neg{color:#4D90F0}
.ge-eta{flex-basis:100%;font-size:11.5px;color:#9AA0AD;font-weight:750}
.ge-eta b{color:#E7E9EE}.ge-eta .late{color:#E8883A;font-weight:900}.ge-eta .early{color:#3DD68C;font-weight:900}
.ge-split{flex-basis:100%;font-size:10.5px;color:#7E8694;font-weight:750}
.ge-split b{color:#D9A441}
.ge-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
@media(max-width:760px){.ge-grid{grid-template-columns:1fr}}
.ge-card{background:#16181F;border:1px solid #262A33;border-radius:14px;padding:11px 13px}
.ge-card .t{font-size:11px;font-weight:900;color:#E7E9EE}
.ge-card .v{font-size:14px;font-weight:950;margin:4px 0 2px;font-variant-numeric:tabular-nums}
.ge-card .v.gold{color:#D9A441}.ge-card .v.warn{color:#E8883A}.ge-card .v.good{color:#3DD68C}
.ge-card .s{font-size:10px;color:#7E8694;font-weight:750;line-height:1.55}
.ge-card .s b{color:#E7E9EE}
.ge-shock{display:inline-flex;align-items:center;margin-top:10px;font-size:11px;font-weight:800;
  padding:6px 12px;border-radius:999px;color:#E8883A;background:rgba(232,136,58,.10);
  border:1px solid rgba(232,136,58,.38)}
</style>"""


def _goal_engine_block(current: float, target: int, start_value: float, m: dict,
                       positions: list[dict], username: str | None,
                       badge_html: str = "") -> None:
    """자산 여정(통합) — 진행률·필요수익률 vs 실제 페이스·3레버·충격 지연·입금 기록.
    H: 구 여정 카드 4개를 흡수해 한 섹션·한 벌의 숫자로(기간 표현도 '도달 예상일' 단일화).
    페이스는 journey_metrics 의 원가 기준 CAGR(입금이 수익으로 잡히지 않음)."""
    from datetime import date as _date
    from core.goal_engine import (years_to_target, required_cagr, monthly_topup_needed,
                                  shock_delay_years, monthly_avg_deposit)
    from core.journey import krw_compact

    today = _date.today()
    target_date = _journey_target_date(username, False)
    t_goal = (target_date - today).days / 365.25
    r_act = (m.get("cagr_pct") or 0) / 100
    r_req = required_cagr(current, target, t_goal)
    if r_req is None:
        st.markdown(_GOAL_CSS + '<div class="ge-head"><span class="ge-act">'
                    '목표 기한이 지났어요 — ⚙️ 설정에서 기한을 다시 잡아주세요.</span></div>',
                    unsafe_allow_html=True)
        return

    deposits = _journey_get("deposits", username, False, []) or []
    avg_dep = monthly_avg_deposit(deposits)

    # 도달 예상(현행 페이스, 적립 미반영 보수 추정)
    eta_y = years_to_target(current, target, r_act)
    if eta_y is not None:
        eta = today + timedelta(days=eta_y * 365.25)
        dy = eta_y - t_goal
        gap_html = (f'목표({target_date.year}년 {target_date.month}월)보다 '
                    + (f'<span class="late">+{dy:.1f}년 늦음</span>' if dy > 0.05
                       else f'<span class="early">{abs(dy):.1f}년 여유</span>' if dy < -0.05 else '<b>정확히 페이스</b>'))
        eta_html = f'이 페이스면 <b>{eta.year}년 {eta.month}월</b> 도달 — {gap_html}'
    else:
        eta_html = '현행 페이스(≤0%)로는 도달 불가 — 아래 레버를 확인하세요'

    profit = current - start_value
    split_html = (f'원금(투입) {krw_compact(start_value)} + 수익 <b>{"+" if profit >= 0 else ""}'
                  f'{krw_compact(profit)}</b> = 현재 {krw_compact(current)}')

    # 진행률 행(구 여정 카드의 도달률·목표까지 흡수) + 벤치마크 배지
    _prog = max(0.0, min(100.0, m.get("progress_pct") or 0))
    prog_row = (f'<span class="ge-prog-row"><span class="ge-prog-k">도달률 <b>{_prog:.1f}%</b> · '
                f'목표까지 {krw_compact(m.get("remaining") or 0)}</span>{badge_html}</span>'
                f'<span class="ge-prog"><i style="width:{max(2.0, _prog):.1f}%"></i></span>')

    act_cls = "pos" if r_act >= r_req else "neg"
    head = (f'<div class="ge-head">'
            f'{prog_row}'
            f'<span class="ge-req">필요 연 <b>{r_req * 100:+.1f}%</b></span>'
            f'<span class="ge-act">실제 페이스 <b class="{act_cls}">{r_act * 100:+.1f}%</b> (원가 기준 · 입금 제외)</span>'
            f'<span class="ge-eta">{eta_html}</span>'
            f'<span class="ge-split">{split_html}</span>'
            f'</div>')

    # ── 3레버 — 갭을 메우는 선택지(리스크 증폭이 아닌 적립·기간 먼저) ────────────
    topup = monthly_topup_needed(current, target, r_act, t_goal) or 0.0
    extra = max(0.0, topup - avg_dep)
    if topup <= 0:
        l1v, l1s = ('<div class="v good">추가 적립 불필요</div>',
                    '현행 페이스만으로 기한 내 도달')
    else:
        l1v = f'<div class="v gold">월 +{krw_compact(extra if avg_dep else topup)}</div>'
        l1s = (f'필요 월 적립 <b>{krw_compact(topup)}</b>'
               + (f' (현 월평균 {krw_compact(avg_dep)} 반영)' if avg_dep else ' · 현행 수익률 유지 가정'))

    if eta_y is not None and eta_y - t_goal > 0.05:
        l2v = f'<div class="v">+{eta_y - t_goal:.1f}년</div>'
        l2s = f'기한을 <b>{eta.year}년 {eta.month}월</b>로 늦추면 필요수익률이 연 {r_act * 100:.0f}%로 내려옴'
    elif eta_y is None:
        l2v, l2s = '<div class="v warn">—</div>', '페이스가 0 이하 — 기간 연장만으론 부족'
    else:
        l2v, l2s = '<div class="v good">연장 불필요</div>', '현행 페이스가 기한을 앞섬'

    r_next = required_cagr(current * (1 + r_act), target, t_goal - 1) if t_goal > 1 else None
    if r_act >= r_req:
        l3v, l3s = ('<div class="v good">여유</div>',
                    f'페이스가 필요수익률을 {(r_act - r_req) * 100:.1f}%p 웃돎 — 유지가 곧 전략')
    else:
        l3v = f'<div class="v warn">필요 연 {r_req * 100:.0f}%↑</div>'
        l3s = ('페이스 유지 시 1년 뒤 필요수익률 <b>연 '
               + (f'{r_next * 100:.0f}%' if r_next is not None else '—') + '</b>로 상승 — 갭은 적립·기간으로')

    grid = (f'<div class="ge-grid">'
            f'<div class="ge-card"><div class="t">① 적립 늘리기</div>{l1v}<div class="s">{l1s}</div></div>'
            f'<div class="ge-card"><div class="t">② 기간 늘리기</div>{l2v}<div class="s">{l2s}</div></div>'
            f'<div class="ge-card"><div class="t">③ 현행 유지</div>{l3v}<div class="s">{l3s}</div></div>'
            f'</div>')

    # ── 충격 → 도달 지연 환산 — 집중 경고를 '목표 언어'로 번역 ───────────────────
    shock_html = ""
    nc = [p for p in positions if p.get("category") != "현금" and (p.get("weight") or 0) > 0]
    if nc and r_act > 0:
        top = max(nc, key=lambda p: p.get("weight") or 0)
        delay = shock_delay_years(r_act, top.get("weight") or 0)
        if delay is not None and delay >= 0.1:
            shock_html = (f'<span class="ge-shock">⚠ 최대종목 {_escape(top.get("name") or "")} '
                          f'({top.get("weight", 0):.0f}%) −30% 충격 시 도달 <b>&nbsp;+{delay:.1f}년 지연</b></span>')

    st.markdown(mkt_section_header("자산 여정", f"목표 {krw_compact(target)} · 기한 {target_date.year}년 {target_date.month}월 · 입금 분리 페이스"),
                unsafe_allow_html=True)
    st.markdown(_GOAL_CSS + head + grid + shock_html, unsafe_allow_html=True)

    # ── 입금 기록 — 페이스 왜곡 방지(원금·수익 분리)의 데이터 원천 + 레버① 실측 ────
    _dep_label = f"💰 입금 기록 — 월평균 {krw_compact(avg_dep)} (최근 6개월)" if avg_dep else "💰 입금 기록"
    with st.expander(_dep_label, expanded=False):
        c1, c2, c3 = st.columns([1.2, 1.2, 0.8], vertical_alignment="bottom")
        with c1:
            amt_man = st.number_input("금액 (만원)", min_value=1.0, value=100.0, step=10.0,
                                      format="%.0f", key="ge_dep_amt")
        with c2:
            dep_date = st.date_input("입금일", value=today, max_value=today, key="ge_dep_date")
        with c3:
            if st.button("기록", key="ge_dep_add", use_container_width=True):
                deposits = list(deposits) + [{"date": dep_date.isoformat(),
                                              "amount": int(amt_man * 10_000)}]
                _journey_set("deposits", deposits, username, False)
                st.rerun(scope="fragment")
        if deposits:
            recent = sorted(deposits, key=lambda d: str(d.get("date", "")), reverse=True)[:5]
            st.caption("최근: " + " · ".join(f"{d['date']} +{krw_compact(d['amount'])}" for d in recent))
        st.caption("입금은 수익과 분리 기록됩니다 — 페이스(CAGR)는 원가 기준이라 입금이 수익으로 잡히지 않아요.")


# NOTE: @st.fragment 제거 — 로그인 경로는 상위 _render_asset_section(fragment) 안에서 호출돼
# fragment 중첩이 됐고, 그 탓에 st.rerun(scope="fragment")가 "can only be specified from
# within a fragment"로 깨졌다. 외부 _render_asset_section 의 fragment scope 를 쓰면 정상.
# (게스트 경로는 positions=None 이라 scope="fragment" 분기에 도달하지 않음.)
def _render_asset_journey(current_value: float, *, is_guest: bool = False,
                          positions: list[dict] | None = None, fx: float | None = None) -> None:
    """자산 여정 — fragment 라서 설정 변경 시 이 블록만 갱신(전체 리로드 X).

    positions/fx 가 주어지면 진행률 바 자리에서 '자산 추이'로 in-place 교체(같은 위치·크기) 토글을 제공.
    """
    from datetime import date as _date
    from core.journey import journey_metrics

    username = st.session_state.get("username")
    target = int(_journey_get("target_value", username, is_guest, 1_500_000_000))
    # 초기 투자금은 보유 수익률 역산 원가(=실제 투자원금)로 자동 산출 — 벤치마크 수익률과 동일 기준.
    # (이전엔 게어의 수동 입력값을 저장·사용했는데, 키 위젯의 stale 세션값이 재저장돼 손실인데도
    #  연 성장률이 +로 나오는 오류가 반복됨. 자동 원가로 단일화해 벤치마크와 일관성 확보.)
    start_value = _estimate_start_value(positions, current_value)
    sd_raw = _journey_get("start_date", username, is_guest, (_date.today() - timedelta(days=730)).isoformat())
    start_date = _date.fromisoformat(sd_raw) if isinstance(sd_raw, str) else sd_raw

    # ── 자산 여정 ──────────────────────────────────────────────────────────────
    with st.container(border=False):
        st.markdown('<div class="aj-marker"></div>', unsafe_allow_html=True)
        target_date = _journey_target_date(username, is_guest)   # 설정 패널과 동일 키(목표 엔진 공용)
        m = journey_metrics(start_date, start_value, current_value, target, target_date)
        # 상태 배지 = '같은 기간 시장(내 카테고리 벤치마크 비중블렌드) 대비' 단일 평가.
        _badge_html = _journey_bench_badge_html(positions, current_value, start_value, start_date)

        if positions is None or is_guest or not username:
            # 게스트 — 종전 헤더+그리드 유지(엔진은 로그인 가치)
            title_col, badge_col, _gear = st.columns([6.2, 2.6, 0.7], gap="small")
            with title_col:
                st.markdown(_AJ_CSS + '<div class="aj-top aj-top-row"><h3>자산 여정</h3></div>',
                            unsafe_allow_html=True)
            with badge_col:
                st.markdown(_badge_html, unsafe_allow_html=True)
            st.markdown(_journey_block_html(current_value, target, m), unsafe_allow_html=True)
        else:
            # H: 여정+목표엔진 통합 — 여정 카드 4개(목표까지·예상기간·연성장률·현재자산)와
            # "예상 14년 5개월" 식 이중 기간표현을 제거하고, 진행률·페이스·레버를 한 벌의 숫자로.
            _goal_engine_block(current_value, target, start_value, m, positions, username,
                               badge_html=_badge_html)
        # 목표·시작일 설정 — 전폭 인라인 expander(헤더 톱니 popover 대체: 모바일 위치/떨림 해결)
        _journey_settings_panel(target, start_date, username, is_guest)


# _ASEC_CSS → ui.pages.portfolio_css 로 이동


@st.fragment
def _render_asset_section(current_value: float, username: str | None,
                          positions: list[dict], fx: float) -> None:
    """자산 여정 — 진행률 바 자리에서 '자산 추이'로 in-place 교체(같은 위치·크기) 토글 제공.

    D2: 추이를 아래에 따로 펼치지 않고, 바와 동일한 .aj-chart 슬롯에 추이 SVG 를 그려 그 자리에서 교체한다.
    토글·렌더는 _render_asset_journey 가 담당(session_state + fragment 부분 리런, 리로드 없음).
    """
    st.markdown(_ASEC_CSS, unsafe_allow_html=True)
    # 바 자리에서 추이로 in-place 교체(같은 위치·크기) — 토글·렌더는 journey 가 담당
    _render_asset_journey(current_value, is_guest=False, positions=positions, fx=fx)


# _PB_CSS → ui.pages.portfolio_css 로 이동


@st.cache_data(ttl=3600, show_spinner=False)
def _get_bench_returns(start_iso: str) -> dict:
    from datetime import date as _d
    from core.pb import bench_returns as _br
    try:
        return _br(_d.fromisoformat(start_iso))
    except Exception:
        return {}


def _account_diag(positions: list[dict], total: float, cash: float,
                  uname: str | None, is_guest: bool = False) -> dict:
    """A2 단일 출처 — 전체현황·포트폴리오가 같은 입력으로 같은 diag/bench를 받게 한다.
    (총수익·KOSPI 대비·벤치마크 등이 화면마다 달라지던 문제 해소. bench 는 캐시 래퍼 하나로 통일.)"""
    from datetime import date as _date
    from core.pb import holdings_for_pb, pb_diagnostics
    # 벤치마크 '내 포트폴리오 수익률'은 실제 원가(수익률 역산) 기준 — 여정의 초기투자금 설정값
    # (사용자가 임의 설정/과거 기본값 저장 가능)에 묶이면 손실 종목도 +로 나오는 오류가 났음.
    cost_basis = _estimate_start_value(positions, total)
    sval = float(_journey_get("start_value", uname, is_guest, cost_basis))  # 여정 표시·설정용(저장값 우선)
    sd_raw = _journey_get("start_date", uname, is_guest,
                          (_date.today() - timedelta(days=730)).isoformat())
    sd = _date.fromisoformat(sd_raw) if isinstance(sd_raw, str) else sd_raw
    bench = _get_bench_returns(sd.isoformat())            # 두 화면 동일한 캐시 소스
    diag = pb_diagnostics(holdings_for_pb(positions), total, cash, sd, cost_basis, bench)
    return {"diag": diag, "bench": bench, "start": sd, "start_value": sval}


def _pb_sev_parts(lv: str) -> tuple[str, str]:
    """위험 카드 제목 접두·배지 라벨(A+C). 색이 아니라 좌측 빨강 바·배지 라벨로 위험을 읽게 한다.
    반환: (제목 앞 접두, 배지 HTML)."""
    if lv == "위험":
        return "", "위험 · 즉시 점검"
    if lv == "주의":
        return "", "주의 · 점검 권장"
    return "", "양호"


def _pb_risk_card_html(d: dict) -> str:
    from core.journey import krw_compact, pct_weight
    from core.pb import friction_krw
    lv = d["level"]
    lv_cls = {"위험": "danger", "주의": "warn", "양호": "safe"}.get(lv, "warn")
    head_icon, sev_html = _pb_sev_parts(lv)
    pct = d["top_w"] * 100
    pct_s = pct_weight(pct)
    if lv == "위험":
        head = f'{head_icon}{d["top_name"]} 1종목 {pct_s}% 집중 — 분산이 아니라 베팅입니다'
    elif lv == "주의":
        head = f'{d["top_name"]} {pct_s}% 집중 — 분산 점검이 필요합니다'
    else:
        head = f'{d["top_name"]} {pct_s}% — 집중도는 양호합니다'
    cash_txt = "방어 여력 없음" if d["cash_pct"] < 1 else "방어 여력 일부"
    excess = d["excess_vs_best"]
    bench_cap = (
        f'시작 이후 수익률 {d["my_return"]:+.1f}%'
        + (f' — {d["best_bench"]} 대비 {excess:+.1f}%p, {"초과수익(알파) 확인 권장" if excess > 0 else "벤치마크 하회 — 점검 필요"}'
           if d["best_bench"] else " — 벤치마크 비교 데이터 대기")
    )
    return (
        f'<div class="pb-card pb-{lv_cls}">'
        f'<span class="pb-sev">{sev_html}</span>'
        f'<div class="pb-head">{_escape(head)}</div>'
        '<div class="pb-scen">'
        f'<div class="pb-s"><span>최대 종목 −20% 충격</span><b>계좌 {d["shock_pct"]:.1f}% · {krw_compact(d["shock_krw"])}</b></div>'
        f'<div class="pb-s"><span>현금 완충</span><b>{pct_weight(d["cash_pct"])}% · {cash_txt}</b></div>'
        f'<div class="pb-s"><span>USD 노출</span><b>{pct_weight(d["usd_w"])}% · 환헤지 없음</b></div>'
        '</div>'
        f'<div class="pb-action">{_escape(d["top_name"])} {pct_s}% → 40% 축소 = <b>약 {krw_compact(d["rebal_to_40"])} 재배분</b>'
        + (f'<span class="pb-cost">실행 비용 약 {krw_compact(friction_krw(d["rebal_to_40"], is_us=d.get("top_cur") == "USD"))} '
           f'(거래세·수수료{"·환전" if d.get("top_cur") == "USD" else ""} 추정'
           f'{" · 해외 양도세 별도" if d.get("top_cur") == "USD" else ""})</span>'
           if d["rebal_to_40"] > 0 else '')
        + '</div>'
        f'<div class="pb-bench">{_escape(bench_cap)}</div>'
        '</div>'
    )


def _pb_risk_summary_html(d: dict, footer: str = "") -> str:
    """전체현황(다이제스트)용 한 줄 요약 — 헤드라인 + 핵심 한 줄.
    풀 카드(지표 그리드·재배분·벤치마크)는 포트폴리오/리스크에만 두어 100% 복제를 제거한다.
    footer: 카드 하단에 끼울 HTML(예: 상세 링크) — 비면 미표시.
    """
    from core.journey import pct_weight
    lv = d["level"]
    lv_cls = {"위험": "danger", "주의": "warn", "양호": "safe"}.get(lv, "warn")
    head_icon, sev_html = _pb_sev_parts(lv)
    pct_s = pct_weight(d["top_w"] * 100)
    if lv == "위험":
        head = f'{head_icon}{d["top_name"]} 1종목 {pct_s}% 집중 — 분산이 아니라 베팅입니다'
    elif lv == "주의":
        head = f'{d["top_name"]} {pct_s}% 집중 — 분산 점검이 필요합니다'
    else:
        head = f'{d["top_name"]} {pct_s}% — 집중도는 양호합니다'
    # USD 노출은 2단 '오늘 할 일 — 내 노출'과 중복이라 여기선 제외(집중/노출은 2단으로 일원화).
    # 1단은 '집중도 한 줄 진단 + 충격 시나리오(완충=현금)'에 집중.
    sub = f'최대 종목 −20% 시 계좌 {d["shock_pct"]:.1f}% · 현금 {pct_weight(d["cash_pct"])}%'
    return (
        f'<div class="pb-card pb-{lv_cls} pb-compact">'
        f'<span class="pb-sev">{sev_html}</span>'
        f'<div class="pb-head">{_escape(head)}</div>'
        f'<div class="pb-bench">{_escape(sub)}</div>'
        f'{footer}'
        '</div>'
    )


def _benchmark_compare_html(d: dict, bench: dict) -> str:
    if not bench:
        return ""
    rows = [("내 포트폴리오", d["my_return"], True)] + [(k, v * 100, False) for k, v in bench.items()]
    rows.sort(key=lambda r: r[1], reverse=True)   # A1: 값 큰 순(최댓값=KOSPI 위로). 내 포트폴리오는 mine 강조 유지
    # 막대 길이는 최대 절대값 기준 정규화(값 ∝ 길이). 0 분모 방지.
    max_abs = max((abs(r[1]) for r in rows), default=1) or 1
    bars = ""
    for label, val, mine in rows:
        w = abs(val) / max_abs * 100
        sign = "+" if val >= 0 else "−"
        # 음수(손실)는 '오른쪽→왼쪽' 채움(margin-left:auto)으로 양수와 반대 방향 → 채워진 막대가
        # +처럼 보이던 문제 해소. 색도 하락=파랑(한국식)으로.
        if mine and val < 0:
            bar = f'<i style="width:{w:.0f}%;background:{DOWN};margin-left:auto"></i>'
            valspan = f'<span class="bm-val mine" style="color:{DOWN}">−{abs(val):.1f}%</span>'
        elif mine:
            # 내 포트폴리오(이익·강조) = 골드
            bar = f'<i class="bm-mine" style="width:{w:.0f}%"></i>'
            valspan = f'<span class="bm-val mine">+{val:.1f}%</span>'
        elif val < 0:
            # 벤치마크 손실: 하락=파랑 + 오른쪽 채움
            bar = f'<i style="width:{w:.0f}%;background:{DOWN};margin-left:auto"></i>'
            valspan = f'<span class="bm-val" style="color:{DOWN}">−{abs(val):.1f}%</span>'
        else:
            bar = f'<i class="bm-other" style="width:{w:.0f}%"></i>'
            valspan = f'<span class="bm-val">+{val:.1f}%</span>'
        bars += (
            f'<div class="bm-row"><span class="bm-lbl {"mine" if mine else ""}">{_escape(label)}</span>'
            f'<div class="bm-track">{bar}</div>{valspan}</div>'
        )
    return (
        '<div class="bm-card"><div class="bm-title">내 수익률, 무엇 대비? · 투자 시작 이후 동일 기간</div>'
        + bars
        + '<div class="bm-cap">벤치마크 대비 초과분은 레버리지·집중의 베타 증폭일 수 있습니다. 샤프지수로 알파를 검증하세요.</div></div>'
    )


def _persist_holdings(holdings: list[dict]) -> None:
    """세션 + 계정 저장소에 보유를 반영. 로그인 유저만 영속화(스크린샷 적용 경로와 동일 패턴).
    저장 전 인제스트 게이트로 티커·통화·자산군을 표준형으로 확정(모든 저장 경로의 단일 관문)."""
    from core.holdings_ingest import canonicalize_holdings
    holdings, _ = canonicalize_holdings(holdings)
    st.session_state["brokerage_holdings"] = holdings
    _uname = st.session_state.get("username")
    if st.session_state.get("auth_role") == "user" and _uname:
        from core.accounts import get_portfolios, save_portfolio
        _ex = get_portfolios(_uname)
        _pf_name = _ex[0]["name"] if _ex else "내 포트폴리오"
        save_portfolio(_uname, holdings, name=_pf_name,
                       cash=st.session_state.get("brokerage_cash_balance", 0.0))


def _render_portfolio_detail(data: dict, journey: dict | None = None) -> None:
    st.markdown(_PB_CSS, unsafe_allow_html=True)

    positions, meta = _normalize_holdings(data)
    summary = _portfolio_summary(positions, meta)
    categories = _positions_by_category(positions, show_empty=False)

    # 헤더 — '내 투자' + 부제 옆에 출처/종목수 배지(별도 바 대신 통합)
    _prov = {"kiwoom": "키움증권", "kis": "한국투자증권", "screenshot": "스크린샷"}.get(
        st.session_state.get("brokerage_provider", ""), "증권사")
    _cnt = len(st.session_state.get("brokerage_holdings") or positions)
    st.markdown(
        '<div class="pd-header"><h3>내 투자</h3>'
        '<div class="pd-header-sub"><p>가장 큰 리스크부터 — 총액·집중·대응</p>'
        f'<span class="bk-badge">{_escape(_prov)} 실계좌</span>'
        f'<span class="bk-badge">{_cnt}종목</span>'
        f'{live_badge_html(["US", "KR"], compact=True)}</div></div>',   # 배지는 주식장(US/KR) 기준 — 크립토 24h 때문에 '장중' 상시표시 방지(갱신은 아래 live_refresh가 CRYPTO 포함 유지)
        unsafe_allow_html=True,
    )

    target_prices = _fetch_target_prices() if positions else {}

    if not positions:
        st.markdown(_portfolio_overview_html(summary, positions, categories), unsafe_allow_html=True)
        st.markdown(
            '<div class="pd-empty"><b>보유 종목 없음</b>'
            '<p>스크린샷을 다시 업로드하거나 증권사 API를 연결해 보유 종목을 불러오세요.</p></div>',
            unsafe_allow_html=True,
        )
        return

    # ── A. PB 리스크-우선 진단 (최상단) — 전체현황과 동일한 단일 출처(_account_diag, A2) ──
    from core.pb import holdings_for_pb
    _uname = st.session_state.get("username")
    _total = summary.get("total_market_value") or 0
    _cash = summary.get("cash_balance") or 0
    _b = _account_diag(positions, _total, _cash, _uname, is_guest=False)
    _diag, _bench, _start = _b["diag"], _b["bench"], _b["start"]
    # 인증 suffix(세션 보존용 ?_user=/_auth=)를 먼저 계산 — 위험카드 아래 E1 링크에서도 사용
    _role = st.session_state.get("auth_role")
    _u = st.session_state.get("username", "")
    from core.auth_token import user_param as _user_param
    _auth = "_auth=guest" if _role == "guest" else _user_param(_u)
    _sfx = f"&{_auth}" if _auth else ""
    _home = f"?{_auth}" if _auth else "?"
    if _diag:
        st.markdown(_pb_risk_card_html(_diag), unsafe_allow_html=True)
        # '리밸런싱 보기' 버튼 제거 — 아래 탭/리밸런싱 섹션과 중복
        # E1: 재배분 조언 → 행동 연결. 리밸런싱에서 '실행 예정'으로 표시했으면 위험카드 바로 아래에 노출.
        if _journey_get("rebal_planned", _uname, False, False):
            _rb_memo = _escape(_journey_get("rebal_memo", _uname, False, "") or "")
            st.markdown(
                '<div class="pb-plan">✓ 리밸런싱 <b>실행 예정</b>으로 표시됨'
                + (f' — {_rb_memo}' if _rb_memo else "")
                + ' <a class="pb-plan-link" href="?pf=rebal{sfx}" target="_self">조정 표 보기 →</a></div>'.format(sfx=_sfx),
                unsafe_allow_html=True,
            )

    # ── 총액·변동·집중 요약 (hero) ───────────────────────────────────────────────
    st.markdown(_portfolio_overview_html(summary, positions, categories), unsafe_allow_html=True)

    # ── 뷰 라우팅 — 라디오 대신 섹션 헤더 링크(query param ?pf=)로 전환 ──
    #   요약(기본) / holdings(전체 보유종목) / detail(상세 진단) / rebal(리밸런싱)
    #   (_role/_u/_auth/_sfx/_home 은 위 위험카드 블록 앞에서 계산됨)
    pf = st.query_params.get("pf", "")
    sorted_by_weight = _sort_positions(positions, target_prices, "비중순")

    # 진단 헤더(우측) 점프 링크 — 상세 진단 · 리밸런싱
    _diag_actions = (
        f'<a class="pd-jump" href="?pf=detail{_sfx}" target="_self">상세 진단</a>'
        f'<a class="pd-jump" href="?pf=rebal{_sfx}" target="_self">리밸런싱</a>'
    )
    _hold_action = f'<a class="pd-jump" href="?pf=holdings{_sfx}" target="_self">전체 {len(sorted_by_weight)}종목 →</a>'
    _back = f'<a class="pd-back" href="{_home}" target="_self">← 요약으로</a>'

    if pf == "holdings":
        st.markdown(_back, unsafe_allow_html=True)

        # 인라인 삭제 — 통짜 HTML 리스트엔 네이티브 버튼을 못 넣으므로 🗑을 쿼리파라미터 링크로 처리.
        #   🗑 클릭 → ?hdel=<id> (상단 확인 배너) → '삭제' → ?hdelok=<id> (실제 삭제·영속화).
        _raw = st.session_state.get("brokerage_holdings") or []
        _hdelok = st.query_params.get("hdelok", "")
        if _hdelok:
            _kept = [h for h in _raw if _holding_ident(h) != _hdelok]
            if len(_kept) != len(_raw):
                _persist_holdings(_kept)
            st.query_params.pop("hdelok", None)
            st.query_params.pop("hdel", None)
            st.query_params["pf"] = "holdings"
            st.rerun()
        _hdel = st.query_params.get("hdel", "")
        if _hdel:
            _nm = next((h.get("name") or _hdel for h in _raw if _holding_ident(h) == _hdel), _hdel)
            st.markdown(
                f'<div class="hl-delbar"><span>‘{_escape(str(_nm))}’ 종목을 삭제할까요?</span>'
                f'<a class="hl-del-yes" href="?pf=holdings&hdelok={quote(_hdel)}{_sfx}" target="_self">삭제</a>'
                f'<a class="hl-del-no" href="?pf=holdings{_sfx}" target="_self">취소</a></div>',
                unsafe_allow_html=True,
            )

        # 정렬 = 드롭다운(우측 플러시). 4지선다 가로 라디오는 모바일에서 폭 부족으로 깨져 selectbox 로 교체.
        # 모바일은 컬럼이 세로로 쌓여 자동 전체폭(반응형).
        _ctrl_l, _ctrl_r = st.columns([3, 1])
        with _ctrl_r:
            sort_key = st.selectbox(
                "보유종목 정렬", ["비중순", "수익률순", "오늘 변동순", "목표여력순"],
                index=0, key="portfolio_holding_sort", label_visibility="collapsed",
            ) or "비중순"
        sorted_positions = _sort_positions(positions, target_prices, sort_key)
        st.markdown(  # 부제의 정렬 에코 제거(컨트롤이 이미 표시) → 종목수로 대체. 행 클릭=상세, 🗑=삭제.
            _holdings_panel_html("전체 보유종목", f"{len(sorted_positions)}종목 · 행 클릭 시 상세",
                                 sorted_positions, target_prices, editable=True, sfx=_sfx),
            unsafe_allow_html=True,
        )
    elif pf == "detail":
        st.markdown(_back, unsafe_allow_html=True)
        st.markdown(_portfolio_diagnosis_html(sorted_by_weight, categories, summary), unsafe_allow_html=True)
        st.markdown(_risk_summary_html(sorted_by_weight, categories), unsafe_allow_html=True)
    elif pf == "rebal":
        st.markdown(_back, unsafe_allow_html=True)
        _top_w = sorted_by_weight[0].get("weight", 0) if sorted_by_weight else 0
        method = st.radio(
            "운용 방식", ["균형형", "정량 최적화형", "집중형"], index=0,
            key="rebal_method", label_visibility="collapsed", horizontal=True,
        ) or "균형형"
        st.markdown(_rebal_method_layer_html(method, _top_w), unsafe_allow_html=True)
        if method == "균형형":
            cap = st.slider("단일 종목 상한 (균형형 기본 25%)", min_value=15, max_value=40,
                            value=25, step=5, key="rebal_cap",
                            help="이 비중을 넘는 종목을 상한까지 줄이는 조정 표를 자동 계산합니다(±5%p 임계).")
            st.markdown(_rebalance_html(sorted_by_weight, summary, float(cap), 5.0), unsafe_allow_html=True)
        else:
            st.markdown(_rebal_pending_html(method), unsafe_allow_html=True)
        st.markdown(_rebal_compare_sources_html(), unsafe_allow_html=True)

        # E1: 조언 → 행동 연결. 실행 예정 체크 + 메모(다음 행동 캡처) → 설정 저장, 요약 위험카드 아래 노출.
        _planned0 = bool(_journey_get("rebal_planned", _uname, False, False))
        _memo0 = _journey_get("rebal_memo", _uname, False, "") or ""
        with st.container(border=True):
            st.markdown("**실행 계획** — 조언을 다음 행동으로 연결")
            _chk = st.checkbox("이 리밸런싱을 실행 예정으로 표시", value=_planned0, key="rebal_planned_chk")
            _memo = st.text_input("메모 (선택)", value=_memo0, key="rebal_memo_input",
                                  placeholder="예: 테슬라 3회 분할 매도, 목표 비중 40%")
            if _chk != _planned0:
                _journey_set("rebal_planned", _chk, _uname, False)
            if (_memo or "") != _memo0:
                _journey_set("rebal_memo", _memo, _uname, False)
            if _chk:
                st.caption("✓ 요약 화면 위험 카드 아래에 '실행 예정'으로 표시됩니다.")
    else:  # 요약(기본)
        # 섹션 순서(지시서 #3): 진단 → 벤치마크 → 보유종목 → 자산 추이·여정.
        # '무엇이 문제인지' 먼저, '어디로 가는지(투영)'는 아래로.
        _record_today_snapshot(_uname, summary, sorted_by_weight)  # 오늘 스냅샷 기록(세션 1회, 추이용)
        # 탐욕 온도계는 진단 카드 맨 끝 그래프로 통합(별도 박스 제거)
        from core.pb import account_greed
        _greed = account_greed(holdings_for_pb(positions), _total, _cash)
        _greed_html = _greed_bar_html(_greed) if _greed else ""
        # 상세 진단·리밸런싱은 진단 헤더 우측 링크로, 전체 보유종목은 핵심 보유종목 헤더 링크로 통합
        st.markdown(_portfolio_diagnosis_html(sorted_by_weight, categories, summary,
                    actions=_diag_actions, extra_html=_greed_html), unsafe_allow_html=True)
        _bm = _benchmark_compare_html(_diag, _bench) if _diag else ""
        if _bm:
            st.markdown(_bm, unsafe_allow_html=True)

        # ── 계좌를 움직인 종목 — 손익 기여 랭킹(오늘/누적, 히트맵의 '누가 얼마나' 즉답) ──
        st.markdown(mkt_section_header("계좌를 움직인 종목", "손익 기여 = 비중 × 등락 · 상승·하락 상위"),
                    unsafe_allow_html=True)
        # st.radio horizontal — 전역 골드칩 세그먼트 스타일(시장 탭과 동일 위치·색)
        _cmode = st.radio(
            "기여도 기간", ["오늘", "누적"], key="pf_contrib_mode",
            horizontal=True, label_visibility="collapsed",
        ) or "오늘"
        _contrib = _contribution_html(sorted_by_weight, summary, _cmode)
        if _contrib:
            st.markdown(_contrib, unsafe_allow_html=True)
        else:
            st.caption("아직 오늘 변동 데이터가 없어요 (장 시작 전)" if _cmode == "오늘" else "누적 손익 데이터가 없어요")

        st.markdown(
            _holdings_panel_html("핵심 보유종목", "비중 상위 5종목 · 상세는 펼쳐보기", sorted_by_weight,
                                 target_prices, limit=5, action=_hold_action),
            unsafe_allow_html=True,
        )
        # 보유 히트맵 — 전종목을 비중×손익으로 한눈에(타일=평가금액, 색=수익률, 자산군 그룹)
        st.markdown(mkt_section_header("보유 히트맵", "전종목 · 비중 × 손익 한눈에"), unsafe_allow_html=True)
        portfolio_treemap(positions, key="holdings")

        # 자산 여정 ↔ 자산 추이 — segmented control 토글(fragment 부분 리런, 전체 리로드 없음)
        if journey:
            _render_asset_section(journey["current_asset"], _uname, positions,
                                  _usdkrw(data) or _FX_FALLBACK)


def _holding_summary_html(items: list[dict]) -> str:
    if not items:
        return '<div class="hold-empty">등록된 자산이 없습니다.</div>'
    groups = sorted({item["group"] for item in items})
    leaders = ", ".join(item["name"] for item in items[:3])
    return (
        '<div class="hold-summary-line">'
        f'<span class="hold-summary-pill">{len(items)}개 자산</span>'
        f'<span class="hold-summary-pill">{len(groups)}개 카테고리</span>'
        f'<span>상위 보유 후보: {_escape(leaders)}</span>'
        '</div>'
    )


def _analyst_issues_html(group_items: list[dict], target_prices: dict[str, float]) -> str:
    _tks = ",".join(sorted({str(it["code"]) for it in group_items if it.get("code")}))
    notes = _consensus_notes(_tks)
    rows = []
    for item in group_items:
        note = notes.get(str(item.get("code")), "")
        if not note:
            continue

        tp = target_prices.get(item["code"])
        if tp is None:
            tp_html = '<span class="issue-no-tp">목표가 없음</span>'
        else:
            current = _parse_price_num(item["price"])
            if current and current > 0:
                upside = (tp / current - 1) * 100
                upside_cls = "pos" if upside > 0 else ("neg" if upside < 0 else "neu")
                sign = "+" if upside >= 0 else ""
                tp_html = (
                    f'<span class="issue-tp">목표가 ${tp:,.0f}</span>'
                    f'<span class="issue-upside {upside_cls}">{sign}{upside:.1f}%</span>'
                )
            else:
                tp_html = f'<span class="issue-tp">목표가 ${tp:,.0f}</span>'

        rows.append(
            '<div class="issue-row">'
            f'<div><div class="issue-name">{_escape(item["name"])}</div>'
            f'<div class="issue-note">{_escape(note)}</div></div>'
            f'<div class="issue-tp-block">{tp_html}</div>'
            '</div>'
        )

    if not rows:
        return ""
    return (
        '<div class="issue-section">'
        '<div class="issue-head">애널리스트 컨센서스 · 네이버 금융</div>'
        + "".join(rows) +
        '</div>'
    )


def _holding_cards_html(items: list[dict]) -> str:
    cards: list[str] = []
    for item in items:
        bg_cls = (
            "hold-pos-bg" if item["pct_cls"] == "pct-pos"
            else ("hold-neg-bg" if item["pct_cls"] == "pct-neg" else "hold-neu-bg")
        )
        cards.append(
            '<details class="hold-det">'
            f'<summary class="{bg_cls}">'
            f'{_logo_html(item)}'
            '<div class="hold-det-main">'
            f'<b>{_escape(item["name"])}</b>'
            f'<span>{_escape(item["code"])}</span>'
            '</div>'
            f'<span class="hold-det-price">{_escape(item["price"])}</span>'
            f'<span class="hold-det-chg {item["pct_cls"]}">{_escape(item["pct"])}</span>'
            '<span class="hold-det-arrow">▾</span>'
            '</summary>'
            '<div class="hold-det-body">'
            f'<div class="hold-det-note">{_escape(item["meta2"])}</div>'
            '<div class="hold-det-meta">'
            f'<span>현재가 {_escape(item["price"])}</span>'
            f'<span>{_escape(item["meta1"])}</span>'
            f'<span>1D {_escape(item["pct"])}</span>'
            '</div>'
            '</div>'
            '</details>'
        )
    return '<div class="hold-det-stack">' + "".join(cards) + '</div>'


# _ONBOARD_CSS → ui.pages.portfolio_css 로 이동


def _render_onboarding() -> None:
    """첫 사용 온보딩 — 보유 0건(미연결 포함). 환영 + 핵심 개념 1분 안내 + 스크린샷 올리기 CTA."""
    st.markdown(_ONBOARD_CSS, unsafe_allow_html=True)
    from core.auth_token import user_param as _user_param
    _suf = ("?" + _user_param(st.session_state["username"])) if st.session_state.get("username") else ""
    st.markdown(
        '<div class="ob-hero"><h2>SIM에 오신 걸 환영합니다 👋</h2>'
        '<p>내 계좌를 올리면 <b style="color:#E7E9EE">가장 큰 리스크부터</b> 짚어드립니다. '
        '거래가 아니라 <b style="color:#E7E9EE">해석</b>에 집중하는 투자 코치예요.</p>'
        '<div class="ob-steps"><span class="ob-step"><b>1</b> 증권사 앱 보유 화면 캡쳐</span>'
        '<span class="ob-step"><b>2</b> 아래에 올리기</span>'
        '<span class="ob-step"><b>3</b> 집중·노출·시나리오 자동 분석</span></div></div>',
        unsafe_allow_html=True,
    )
    # 핵심 개념 1분 안내
    st.markdown(
        '<div class="ob-grid">'
        '<div class="ob-c"><span class="ic">🎯</span><b>위험 점수</b>'
        '<span>시장 신호를 0–100으로 요약. 70+면 위험 구간. 산식은 펼쳐 볼 수 있어요.</span></div>'
        '<div class="ob-c"><span class="ic">📊</span><b>집중도</b>'
        '<span>한 종목·상위 3개 비중. 높을수록 개별 악재에 크게 흔들립니다.</span></div>'
        '<div class="ob-c"><span class="ic">💱</span><b>노출</b>'
        '<span>USD·반도체 등 특정 위험에 묶인 정도 → 내 계좌 영향 금액으로 환산.</span></div>'
        '<div class="ob-c"><span class="ic">🧪</span><b>시나리오</b>'
        '<span>"시장 −10%면 내 계좌 약 ○○ 영향" 같은 가정별 예상 낙폭.</span></div>'
        '</div>', unsafe_allow_html=True,
    )
    _render_screenshot_upload(key="onboarding_upload")
    st.markdown(
        f'<a class="ob-explore" href="/overview{_suf}" target="_self">샘플 화면 먼저 둘러보기 →</a>',
        unsafe_allow_html=True,
    )
    st.markdown(jj_footer(), unsafe_allow_html=True)


def _holding_key(h: dict) -> tuple:
    """보유 dedup 키 — (종목명, 코드). 양쪽 빈 값이면 ("","")(드롭 대상)."""
    return (str(h.get("name", "")).strip(), str(h.get("ticker", "")).strip())


def _merge_holdings(holdings: list[dict]) -> list[dict]:
    """여러 스크린샷에서 모은 보유를 (종목명, 코드) 기준으로 병합 — 겹친 캡처 중복 제거.
    같은 종목이 여러 장에 걸치면 평가금액이 큰(=더 완전한) 항목을 남긴다. 입력 순서 보존."""
    def _amt(h: dict) -> float:
        try:
            return float(h.get("평가금액") or h.get("eval_amount") or 0)
        except (TypeError, ValueError):
            return 0.0

    best: dict = {}
    order: list = []
    for h in holdings:
        k = _holding_key(h)
        if k == ("", ""):
            continue
        if k not in best:
            best[k] = h
            order.append(k)
        elif _amt(h) > _amt(best[k]):
            best[k] = h
    return [best[k] for k in order]


def _merge_into_existing(existing: list[dict], new: list[dict]) -> list[dict]:
    """기존 보유에 새 인식분을 합침(업데이트). 같은 (종목명,코드)는 새 값으로 갱신, 없던 건 추가,
    이번 스크린샷에 없는 기존 종목은 유지. dict 순서로 기존 위치 보존 + 신규는 뒤에 추가."""
    merged: dict = {}
    for h in (existing or []):
        merged[_holding_key(h)] = h
    for h in (new or []):
        merged[_holding_key(h)] = h   # 새 인식분 우선(갱신/추가)
    merged.pop(("", ""), None)
    return list(merged.values())


_PENDING_SCR_TTL_MIN = 30


def _pending_scr_get() -> dict | None:
    """계정에 임시 저장된 스크린샷 인식 결과(30분) — 모바일에서 캡처하러 앱을 오가거나 분석 중
    화면이 꺼지면 웹소켓 재연결로 세션이 초기화되는데, 세션에만 있던 결과가 사라져
    '버튼을 눌러도 반영이 안 되는' 문제의 근본 원인이었다. 서버(계정)에 두면 살아남는다."""
    from datetime import datetime, timedelta as _td
    uname = st.session_state.get("username")
    if st.session_state.get("auth_role") != "user" or not uname:
        return None
    from core.accounts import get_setting
    p = get_setting(uname, "pending_screenshot", None)
    if not p or not p.get("holdings"):
        return None
    try:
        ts = datetime.fromisoformat(str(p.get("ts", "")))
    except ValueError:
        return None
    if datetime.now() - ts > _td(minutes=_PENDING_SCR_TTL_MIN):
        return None
    return p


def _pending_scr_set(payload: dict | None) -> None:
    uname = st.session_state.get("username")
    if st.session_state.get("auth_role") != "user" or not uname:
        return
    from core.accounts import set_setting
    set_setting(uname, "pending_screenshot", payload)


def _render_screenshot_upload(key: str = "screenshot_upload", show_header: bool = True) -> None:
    from core.vision_parser import parse_portfolio_image
    from ui.pages.login import _filter_valid_holdings

    # 직전 rerun 에서 적용 완료 → 확인 피드백(반영 여부가 안 보인다는 혼선 방지)
    _applied_n = st.session_state.pop("_scr_applied_n", None)
    if _applied_n:
        st.success(f"✅ 보유 {_applied_n}종목 반영 완료 — 위 목록이 갱신됐어요")

    # 드롭존·프라이버시 스타일은 항상 주입. 헤더는 onboarding(메인 CTA)에서만 — 접는 유틸 안에선 생략(라벨 중복 방지).
    st.markdown("""
<style>
/* 업로드 드롭존을 골드 점선 CTA 로 — 클릭(또는 드래그) 한 번에 업로드 */
[data-testid="stFileUploaderDropzone"]{background:rgba(217,164,65,0.06)!important;
  border:1.5px dashed rgba(217,164,65,0.5)!important;border-radius:16px!important;transition:border-color .15s,background .15s}
[data-testid="stFileUploaderDropzone"]:hover{border-color:#D9A441!important;background:rgba(217,164,65,0.12)!important}
/* D6: 3단계 시각 안내(① 캡처 → ② 끌어놓기 → ③ 자동 인식) */
.scr-steps{display:flex;align-items:stretch;gap:8px;margin:6px 0 12px;flex-wrap:wrap}
.scr-step{display:flex;align-items:center;gap:9px;flex:1;min-width:160px;
  background:#1E2029;border:1px solid #262A33;border-radius:12px;padding:10px 12px}
.scr-step-n{flex:0 0 22px;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;
  background:rgba(217,164,65,.15);color:#D9A441;font-size:12px;font-weight:950}
.scr-step b{display:block;color:#E7E9EE;font-size:13px;font-weight:850}
.scr-step em{display:block;color:#9AA0AD;font-size:12px;font-weight:700;font-style:normal;margin-top:1px}
.scr-step-arr{display:flex;align-items:center;color:#7E8694;font-size:16px;font-weight:900}  /* C5: 저대비 하한(#7E8694) */
@media(max-width:640px){.scr-step-arr{display:none}.scr-step{min-width:0;flex:1 1 100%}}
.scr-priv{display:flex;justify-content:flex-end;text-align:right;margin:9px 2px 2px;color:#7E8694;
  font-size:12px;font-weight:650;line-height:1.5}
.scr-priv b{color:#9AA0AD;font-weight:800}
</style>""", unsafe_allow_html=True)
    if show_header:
        st.markdown("""
<div class="scr-steps">
  <div class="scr-step"><span class="scr-step-n">1</span><div><b>증권사 앱 캡처</b><em>보유 종목 화면을 스크린샷</em></div></div>
  <div class="scr-step-arr">→</div>
  <div class="scr-step"><span class="scr-step-n">2</span><div><b>끌어다 놓기</b><em>아래에 이미지를 드롭</em></div></div>
  <div class="scr-step-arr">→</div>
  <div class="scr-step"><span class="scr-step-n">3</span><div><b>자동 인식</b><em>종목·평가금액 추출</em></div></div>
</div>""", unsafe_allow_html=True)

    # 업로더는 위젯 key 를 바꿔야 비워진다 → nonce 카운터를 붙여 적용/취소 후 리셋(재분석 방지).
    nonce_key = f"_scr_nonce_{key}"
    uploaded = st.file_uploader(
        "보유 종목 화면 스크린샷",
        type=["png", "jpg", "jpeg", "webp", "heic", "heif"],   # 모바일 갤러리/파일 피커 호환(webp·heic 포함)
        accept_multiple_files=True,   # 여러 장(스크롤 캡처·계좌 분할 등) 한 번에 분석
        key=f"{key}_{st.session_state.get(nonce_key, 0)}",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="scr-priv"><span>🔒 이미지는 <b>저장하지 않아요</b> · 여러 장을 한 번에 분석 후 '
        '보유 정보만 내 계정에 로컬 저장 · 거래 기능 없음</span></div>',
        unsafe_allow_html=True,
    )
    # 모바일(안드로이드) 갤러리 피커 바로 뜨게 — 파일 입력 accept를 image/* 로 강제(확장자 기반이면
    # 안드로이드가 '파일' 앱을 열어 갤러리까지 들어가야 함). 서버측 type 검증·MIME 재판정은 그대로 동작.
    import streamlit.components.v1 as _components
    _components.html(
        "<script>(function(){var d=window.parent.document;"
        "function s(){d.querySelectorAll('input[type=file]').forEach(function(i){i.setAttribute('accept','image/*');});}"
        "s();setTimeout(s,300);setTimeout(s,1200);})();</script>",
        height=0,
    )

    if not uploaded:   # None 또는 빈 리스트
        # 세션이 초기화됐어도(모바일 재연결 등) 계정에 남은 최근 인식 결과가 있으면 복원
        pending = _pending_scr_get()
        if not pending:
            return
        cache_key = f"_scr_pending_{key}"
        st.session_state[cache_key] = pending
        st.caption("📌 조금 전 분석한 결과를 불러왔어요 — 연결이 잠시 끊겨도 30분간 유지됩니다")
        _has_upload = False
    else:
        _has_upload = True

    # 파일 집합(이름·크기) 기준 캐시 키 — 같은 집합이면 재분석 안 함
    if _has_upload:
        sig = "|".join(f"{u.name}:{u.size}" for u in uploaded)
        cache_key = f"_screenshot_parsed_{key}_{abs(hash(sig))}"
    if _has_upload and cache_key not in st.session_state:
        from core.vision_parser import VisionBusyError
        import logging
        _n_img = len(uploaded)
        with st.spinner(f"이미지 {_n_img}장 분석 중... (약 10~20초)"):
            try:
                # 여러 장을 단일 API 호출로 한 번에 분석(합산) — 빠르고, 모델이 교차 인식.
                _imgs = [(u.read(), u.type or "image/jpeg") for u in uploaded]
                raw = parse_portfolio_image(_imgs[0][0], _imgs[0][1], extra_images=_imgs[1:])
                merged = _filter_valid_holdings(raw)
                deduped = _merge_holdings(merged)
                # 인제스트 게이트 — 티커/통화/자산군 확정 + 못 읽은 행은 사유와 함께 노출
                from core.holdings_ingest import canonicalize_holdings
                clean, dropped = canonicalize_holdings(deduped)
                st.session_state[cache_key] = {
                    "holdings": clean, "dropped": dropped, "cash_balance": 0.0,
                    "n_img": _n_img, "raw_count": len(merged),
                }
                # 계정에도 임시 저장(30분) — 모바일 세션 리셋에도 결과·버튼이 살아남게
                from datetime import datetime as _dt
                _pending_scr_set({**st.session_state[cache_key], "ts": _dt.now().isoformat()})
            except Exception as e:
                logging.getLogger("siminvest").warning("screenshot parse failed: %s", e)
                if isinstance(e, VisionBusyError):
                    st.warning("지금 AI 분석 요청이 몰려 잠시 지연되고 있어요. 잠시 후 다시 시도해 주세요.")
                else:
                    st.error("이미지를 분석하지 못했어요. 더 선명한 스크린샷으로 다시 시도해 주세요.")
                return

    result = st.session_state[cache_key]
    holdings = result["holdings"]
    cash = result["cash_balance"]

    if not holdings:
        st.warning("종목을 인식하지 못했습니다. 더 선명한 스크린샷을 사용해 보세요.")
        return

    # 한번에 분석한 결과 요약 — 총 종목·총 평가금액(+ 여러 장 통합·중복 제거 안내)
    def _amt(h):
        try:
            return float(h.get("평가금액") or h.get("eval_amount") or 0)
        except (TypeError, ValueError):
            return 0.0
    _total = sum(_amt(h) for h in holdings)
    _n_img = int(result.get("n_img", 1))
    _dups = max(0, int(result.get("raw_count", len(holdings))) - len(holdings))
    _summary = f"**{len(holdings)}개 종목** · 합계 평가금액 **{_cur(_total, 'KRW')}**"
    if _n_img > 1:
        _summary += f" · 이미지 {_n_img}장 통합"
    if _dups:
        _summary += f" · 중복 {_dups}건 병합"
    st.markdown(_summary)
    # 못 읽은 행 — 조용히 버리지 않고 사유를 그대로 노출(무엇이 부족했는지 사용자가 알게)
    for _d in result.get("dropped") or []:
        st.warning(f"**{_d['name']}** 은(는) 반영에서 제외돼요 — {_d['reason']}")
    # 시세 조회 가능 여부 사전 확인 — 반영 후 '현재가 공백'을 미리보기에서 잡아냄
    _chk_tks = tuple(sorted({str(h.get("ticker")) for h in holdings
                             if h.get("ticker") and h.get("asset_class") != "cash"}))
    try:
        _chk_quotes = _cached_bulk_quotes(_chk_tks) if _chk_tks else {}
    except Exception:
        _chk_quotes = {}

    def _quote_ok(h: dict) -> str:
        tk = str(h.get("ticker") or "")
        if not tk:
            return "코드 없음"
        return "✓" if _chk_quotes.get(tk) else "확인 필요"

    preview_rows = [
        {
            "종목명": h.get("name", ""),
            "코드": h.get("ticker", ""),
            "평가금액": _cur(_amt(h), "KRW"),
            "수익률": f"{float(h.get('수익률') or h.get('profit_loss_pct') or 0):+.2f}%",
            "시세": _quote_ok(h),
        }
        for h in holdings
    ]
    _preview_df = pd.DataFrame(preview_rows)
    _pct_cols = [c for c in _preview_df.columns if "%" in str(c)]
    if _pct_cols:
        st.dataframe(_preview_df.style.map(color_change, subset=_pct_cols),
                     use_container_width=True, hide_index=True)
    else:
        st.dataframe(_preview_df, use_container_width=True, hide_index=True)

    def _apply(final_holdings: list[dict], final_cash: float) -> None:
        st.session_state["brokerage_cash_balance"] = final_cash
        st.session_state["brokerage_debug"] = result.get("_debug", {})
        st.session_state["brokerage_provider"] = "screenshot"
        # 세션+계정 영속화는 공통 헬퍼로(하드 nav 후 옛 보유로 복원되는 것 방지). cash 는 위에서 세션에 반영됨.
        _persist_holdings(final_holdings)
        _pending_scr_set(None)                     # 임시 저장 정리(재노출 방지)
        st.session_state["_scr_applied_n"] = len(final_holdings)  # 다음 rerun 에서 완료 피드백
        st.session_state.pop(cache_key, None)
        st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1  # 업로더 비우기
        st.rerun()

    def _clear() -> None:
        _pending_scr_set(None)
        st.session_state.pop(cache_key, None)
        st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1
        st.rerun()

    _existing_h = st.session_state.get("brokerage_holdings") or []
    _existing_cash = _num(st.session_state.get("brokerage_cash_balance")) or 0.0
    if _existing_h:
        # 기존 보유가 있으면 합치기(업데이트) ↔ 전체 교체 선택 — 부분 캡처로 기존이 지워지지 않게.
        c_merge, c_replace, c_cancel = st.columns([2, 2, 1])
        with c_merge:
            if st.button("기존에 합치기", use_container_width=True, key=f"btn_merge_{key}"):
                _apply(_merge_into_existing(_existing_h, holdings), cash or _existing_cash)
        with c_replace:
            if st.button("전체 교체", use_container_width=True, key=f"btn_replace_{key}"):
                _apply(holdings, cash)
        with c_cancel:
            if st.button("취소", use_container_width=True, key=f"btn_cancel_{key}"):
                _clear()
        st.caption("합치기 = 같은 종목 갱신·새 종목 추가·기존 유지(부분 캡처 안전) · 교체 = 이번 인식분으로 전부 대체")
    else:
        col_apply, col_cancel = st.columns([2, 1])
        with col_apply:
            if st.button("이 데이터로 포트폴리오 적용", use_container_width=True, key=f"btn_apply_{key}"):
                _apply(holdings, cash)
        with col_cancel:
            if st.button("취소", use_container_width=True, key=f"btn_cancel_{key}"):
                _clear()


def _is_token_expired() -> bool:
    if st.session_state.get("brokerage_provider") == "screenshot":
        return False
    t = st.session_state.get("brokerage_token_fetched_at")
    return t is None or (datetime.now() - t) > timedelta(hours=23)


# ── Guest portfolio view ──────────────────────────────────────────────────────

def render():
    L.viewport_width()          # 폭 먼저 확정 → 모바일 리플로우 최소화
    L.inject_responsive_css()   # 페이지당 1회 (게스트/로그인 공통)
    # Guest: show sample top-5 view instead of real portfolio
    if st.session_state.get("auth_role") == "guest":
        _render_guest_portfolio()
        return

    inject_css()
    mark_active_nav("/portfolio")
    st.markdown(_PORT_CSS, unsafe_allow_html=True)

    # 텔레그램 위험 알림 연결은 리스크 페이지(risk_signals._telegram_settings)에 전체 UI 가 있어
    # 여기 상단 중복 바로가기는 제거(본문/위험 내용 우선).

    brokerage_holdings = st.session_state.get("brokerage_holdings")
    if not brokerage_holdings:   # None(미연결) 또는 [](0종목) → 첫 사용 온보딩(B1, 토큰 체크보다 우선)
        _render_onboarding()
        return

    if st.session_state.get("auth_role") == "user" and _is_token_expired():
        st.warning("세션이 만료되었습니다. 다시 로그인해 주세요.")
        if st.button("재로그인"):
            for k in ["authenticated", "brokerage_token", "brokerage_holdings", "brokerage_cash_balance"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.stop()

    # 라이브 갱신 배지는 '내 투자' 헤더로 이동(여기선 렌더 안 함, 자동갱신·버킷만)
    bucket = live_refresh(["US", "KR", "CRYPTO"], render=False)
    ph = show_skeleton()
    data = load_market_data(_bucket=bucket)
    ph.empty()

    brokerage_connected = True  # 위에서 보유 존재 확인됨
    if brokerage_connected:
        data = dict(data)
        data["holdings"] = brokerage_holdings
        cash_balance = st.session_state.get("brokerage_cash_balance", 0.0)
        data["cash_balance"] = cash_balance
        # 자산여정 '현재 자산' = 카드와 동일한 보정된 총 평가액(_position_eval 경유: 소수점 누락 보정·
        # USD 환산 일관). 이전엔 raw 평가금액×환율 합산이라 소수점 누락분이 그대로 들어가 총액이
        # 폭증(예: 1,380억) → 목표 도달률·연성장률이 개판. 카드(_normalize_holdings)와 단일 출처로 통일.
        _positions, _meta = _normalize_holdings(data)
        live_total = _portfolio_summary(_positions, _meta).get("total_market_value") or 0
        st.session_state["portfolio_current_asset"] = live_total

        # 출처/종목수 배지는 _render_portfolio_detail 의 '내 투자' 헤더로 통합(중복 바 제거).
        # Debug expander — auto-opens when 0 종목 to help diagnose empty responses
        debug_info = st.session_state.get("brokerage_debug")
        if debug_info:
            with st.expander("🔧 API 응답 디버그", expanded=(len(brokerage_holdings) == 0)):
                st.json(debug_info)

    current_asset = st.session_state.get("portfolio_current_asset", 700_000_000)
    target_asset = st.session_state.get("portfolio_target_asset", 1_500_000_000)
    annual_growth_rate = st.session_state.get("portfolio_annual_growth_rate", 0.20)
    progress = min(1.0, max(0.0, current_asset / max(1, target_asset)))

    # ── 서브탭: 내 보유 / 리스크 진단 (segmented control — 비활성 탭은 미실행) ──
    from ui.pages.risk_signals import render_risk_body
    # keyed 위젯은 값이 세션에 저장되면 default 를 무시한다 → /risk 흡수(_pf_open_risk) 시
    # 세션 키(pf_subtab)를 직접 지정해야 탭이 실제로 전환된다(브리지·같은세션 재방문에도 정확).
    if st.session_state.pop("_pf_open_risk", False):
        st.session_state["pf_subtab"] = "리스크 진단"
    elif "pf_subtab" not in st.session_state:
        # 리로드·모바일 웹소켓 재연결로 세션이 초기화돼도 ?pf=risk 면 리스크 탭 유지
        st.session_state["pf_subtab"] = (
            "리스크 진단" if st.query_params.get("pf") == "risk" else "내 보유"
        )

    def _sync_pf_subtab() -> None:
        # 서브탭 선택을 URL(?pf=risk)에 반영 — 리로드/재연결에도 탭이 살아남게.
        # 서버측 쿼리 갱신은 브라우저 URL 전체를 다시 쓰므로(브리지가 살린 토큰 유실 방지)
        # 인증 suffix(_user/_auth)도 함께 재기입한다.
        if st.session_state.get("pf_subtab") == "리스크 진단":
            st.query_params["pf"] = "risk"
        elif st.query_params.get("pf") == "risk":
            del st.query_params["pf"]
        if st.session_state.get("auth_role") == "guest":
            st.query_params["_auth"] = "guest"
        elif st.session_state.get("username"):
            from core.auth_token import make_token
            st.query_params["_user"] = make_token(st.session_state["username"])

    # st.radio horizontal — 시장 자산군 탭과 동일한 전역 골드칩 세그먼트 스타일·좌측 배치
    _tab = st.radio(
        "포트폴리오 보기", ["내 보유", "리스크 진단"],
        key="pf_subtab", horizontal=True, label_visibility="collapsed",
        on_change=_sync_pf_subtab,
    ) or "내 보유"

    if _tab == "리스크 진단":
        # DRY — 이미 정규화한 _positions/live_total 을 넘겨 리스크 탭의 중복 정규화(load_market_data·
        # _normalize_holdings) 제거. (_positions 는 위 _portfolio_summary 로 weight 부착 완료.)
        from core.pb import holdings_for_pb
        render_risk_body(holdings=holdings_for_pb(_positions), total=live_total, is_guest=False)
    else:
        _render_portfolio_detail(
            data,
            journey={
                "progress": max(0.02, progress),
                "height": 360,
                "current_asset": current_asset,
                "target_asset": target_asset,
                "annual_growth_rate": annual_growth_rate,
            },
        )
        if brokerage_connected and st.query_params.get("pf", "") == "":
            st.markdown(
                '<div style="margin:18px 2px 8px;color:#E7E9EE;font-size:14px;font-weight:850;'
                'font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',sans-serif;">'
                '📷 스크린샷으로 보유 갱신'
                '<span style="display:block;color:#9AA0AD;font-size:12px;font-weight:650;margin-top:2px;">'
                '새 캡처를 올리면 종목·평가금액을 다시 인식해 교체해요</span></div>',
                unsafe_allow_html=True,
            )
            _render_screenshot_upload(key="screenshot_update", show_header=False)

    st.markdown(jj_footer(), unsafe_allow_html=True)
