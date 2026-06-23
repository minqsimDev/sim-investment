import html as html_lib
import re
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import layout as L  # 반응형(뷰포트 감지 + 모바일 CSS)
from data.loader import load_market_data, batch_close_history
from core.journey import pct_weight  # 비중(%) 정수 기본 포맷(전 화면 공통)
from ui.components.dash_style import (
    inject_css, jj_footer, mark_active_nav, show_skeleton, color_change,
)
from siminvest_theme import DOWN  # 하락=파랑 (벤치마크 막대 음수 처리)
from format import won, currency as _cur  # 금액 표기 단일 출처
from ui.components.mountain_scene import render_mountain
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
    if "etf" in raw or any(name.upper().startswith(prefix) for prefix in _ISSUER_CLASSES):
        return "ETF"
    if "kr" in raw or ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "국내주식"
    if "us" in raw or ticker:
        return "미국주식"
    return "기타"


def _holding_currency(row: dict, ticker: str = "", category: str = "") -> str:
    """보유 1건의 환산·표시 통화(KRW|USD) — 전 화면 '보유→원화' 변환의 단일 출처(SSOT).

    규칙: 명시 currency(KRW/USD) 우선 → 없으면 카테고리로 판정.
    '미국주식'(us_stock)만 USD(×환율 대상), 그 외(국내·ETF·크립토·원자재·현금·기타)는 KRW.
    크립토를 USD 로 보면 국내거래소 원화 평가금액에 ×환율되어 총액이 폭증함(예: 1,200만→184억).
    render()·_render_portfolio_detail() 두 경로가 이 함수 하나만 쓰게 해 결과 불일치를 차단한다."""
    cur = str(_first(row, "currency", "ccy") or "").upper()
    if cur in {"KRW", "USD"}:
        return cur
    cat = category or _category_for_holding(row, ticker)
    return "USD" if cat == "미국주식" else "KRW"


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

        # USD eval_amount는 KRW로 환산
        market_value = direct_market
        if market_value is not None and fx_factor != 1:
            market_value = direct_market * fx_factor
        elif market_value is None and current is not None:
            market_value = qty * current * fx_factor
        cost_basis = direct_cost
        if cost_basis is not None and fx_factor != 1:
            cost_basis = direct_cost * fx_factor
        elif cost_basis is None and avg_price is not None:
            cost_basis = qty * avg_price * fx_factor
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

        market_value_local = (market_value / fx_factor) if (fx_factor != 1 and market_value is not None) else market_value
        gain_loss_local = (gain_loss / fx_factor) if (fx_factor != 1 and gain_loss is not None) else gain_loss
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


@st.cache_data(ttl=3600, show_spinner=False)
def _position_sparklines(tickers: tuple[str, ...]) -> dict[str, list[float]]:
    """보유 종목 1년 스파크라인(주간) — 공용 batch_close_history(→price_source) 경유.
    일봉을 주간 마지막값으로 리샘플(이전 1wk 직접 다운로드 대체)."""
    tickers = tuple(t for t in tickers if t and t not in {"CASH", "KRW", "USD"})
    if not tickers:
        return {}
    hist = batch_close_history(",".join(dict.fromkeys(tickers)), "1y")
    out: dict[str, list[float]] = {}
    for ticker in tickers:
        s = hist.get(ticker)
        if s is None or getattr(s, "empty", True):
            continue
        s = s.dropna().resample("W").last().dropna()
        if len(s) >= 2:
            base = float(s.iloc[0]) or 1
            out[ticker] = [(float(v) / base - 1) * 100 for v in s]
    return out


def _sparkline_svg(values: list[float]) -> str:
    if len(values) < 2:
        return '<div style="color:#7E8694;font-size:10px;font-weight:850;padding-top:8px">차트 데이터 대기</div>'
    width, height, pad = 160, 34, 2
    mn, mx = min(values), max(values)
    span = mx - mn or 0.1
    terminal = float(values[-1])
    color = "#F25560" if terminal > 3 else ("#4D90F0" if terminal < -3 else "#9AA0AD")
    pts = []
    for i, v in enumerate(values):
        x = pad + (i / (len(values) - 1)) * (width - 2 * pad)
        y = (height - pad) - ((v - mn) / span) * (height - 2 * pad)
        pts.append((x, y))
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_d = line_d + f" L {width - pad},{height} L {pad},{height} Z"
    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="{area_d}" fill="{color}" fill-opacity="0.16"/>'
        f'<path d="{line_d}" stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )


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
    return f"{pct_weight(value)}%"


def _target_upside(position: dict, target_prices: dict[str, float]) -> float | None:
    target = target_prices.get(position["ticker"])
    current = position.get("current_price")
    if target and current:
        return (target / current - 1) * 100
    return None


def _target_upside_html(position: dict, target_prices: dict[str, float]) -> str:
    upside = _target_upside(position, target_prices)
    if upside is None:
        return '<span class="pd-neu">데이터 없음</span>'
    cls = _tone(upside)
    return f'<span class="{cls}">{upside:+.1f}%</span>'


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


def _conc_color(rank: int, leader_alarm: bool) -> str:
    """비중 내림차순 rank → 색. 1위는 과집중이면 레드, 아니면 골드. 이후 골드→회색 차등."""
    if rank == 0:
        return _CONC_ALARM if leader_alarm else _CONC_RAMP[0]
    ri = (rank - 1) if leader_alarm else rank   # 레드면 2위가 골드, 골드면 2위가 올리브
    return _CONC_RAMP[min(ri, len(_CONC_RAMP) - 1)]


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


def _holdings_table_html(positions: list[dict], target_prices: dict[str, float], limit: int | None = None) -> str:
    visible = positions[:limit] if limit else positions
    if not visible:
        return '<div class="pd-empty"><b>표시할 보유종목이 없습니다</b><p>포트폴리오 데이터가 연결되면 여기에 종목 리스트가 표시됩니다.</p></div>'
    max_w = max((p.get("weight") or 0 for p in visible), default=0)
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
        today = (f'<span class="hl-ret-today">오늘 <b class="{day_cls}">{position["today_change_pct"]:+.2f}%</b></span>'
                 if position.get("today_change_pct") is not None else '')
        rows.append(
            '<div class="hl-row">'
            '<div class="hl-main">'
            f'{_logo_html(logo_item)}'
            '<div class="hl-info">'
            f'<b class="hl-name">{_escape(position["name"])}</b>'
            f'<span class="hl-sub">{_escape(position["category"])} · {_escape(shares)} · 비중 {_format_weight(w)}</span>'
            f'<div class="hl-wbar"><i style="width:{min(w,100):.0f}%;background:{bar_color}"></i></div>'
            '</div></div>'
            '<div class="hl-vals">'
            f'<b class="hl-val">{_escape(primary_value)}</b>'
            f'<span class="hl-ret">{ret}{today}</span>'
            '</div>'
            '<details class="hl-exp" name="hold-acc"><summary aria-label="상세 보기"><span class="hl-caret">▾</span></summary>'
            f'<div class="hl-detail">{_insight_text(position, target_prices)}<br>'
            f'<b>현재가</b> {_price(position.get("current_price"), position.get("currency", "KRW"))} · '
            f'<b>평가액</b> {_escape(primary_value)} ({_escape(secondary_value)}) · '
            f'<b>목표가</b> {_escape(target)} · <b>여력</b> <span class="{upside_cls}">{_escape(upside_label)}</span></div>'
            '</details>'
            '</div>'
        )
    return '<div class="pd-table-card hl-card">' + "".join(rows) + '</div>'


def _holdings_panel_html(
    title: str,
    subtitle: str,
    positions: list[dict],
    target_prices: dict[str, float],
    limit: int | None = None,
    action: str = "",
) -> str:
    return (
        '<div class="pd-list-panel">'
        f'<div class="pd-list-head"><b>{_escape(title)}</b>'
        f'<div class="pd-head-right"><span>{_escape(subtitle)}</span>{action}</div></div>'
        + _holdings_table_html(positions, target_prices, limit=limit)
        + '</div>'
    )


def _holdings_card_grid_html(
    positions: list[dict],
    target_prices: dict[str, float],
    sparks: dict[str, list[float]],
) -> str:
    if not positions:
        return '<div class="pd-empty"><b>표시할 보유종목이 없습니다</b></div>'
    cards = []
    for position in positions:
        ret_cls = _tone(position.get("gain_loss_pct"))
        day_cls = _tone(position.get("today_change_pct"), 0.05)
        _, upside, upside_cls = _target_info(position, target_prices)
        logo_item = {"group": position["category"], "name": position["name"], "code": position["ticker"]}
        currency = position.get("currency", "KRW")
        qty = position.get("quantity")
        local = position.get("market_value_local")

        # value sub-line: USD equiv + qty
        sub_parts: list[str] = []
        if currency == "USD" and local is not None:
            sub_parts.append(f"= ${local:,.0f}")
        if qty is not None:
            sub_parts.append(f"{_fmt_qty(qty)}주")
        val_sub = " · ".join(sub_parts) if sub_parts else ""

        # return pill
        if position.get("gain_loss_pct") is not None:
            ret_val = f'{position["gain_loss_pct"]:+.2f}%'
            ret_sub = _money(position.get("gain_loss"), "KRW", signed=True, compact=True)
        else:
            ret_val, ret_sub = "—", ""

        # today pill
        if position.get("today_change_pct") is not None:
            day_val = f'{position["today_change_pct"]:+.2f}%'
            day_sub = _money(position.get("today_change_amount"), "KRW", signed=True, compact=True) if position.get("today_change_amount") else ""
        else:
            day_val, day_sub, day_cls = "대기", "", "pd-neu"

        cur_price = _price(position.get("current_price"), currency)
        upside_str = upside if upside and upside != "—" else "데이터 없음"
        qty_str = _fmt_qty(qty) if qty is not None else "—"
        spark_svg = _sparkline_svg(sparks.get(position.get("ticker") or "", []))

        cards.append(
            '<article class="hcv-card">'
            '<div class="hcv-head">'
            f'{_logo_html(logo_item)}'
            '<div class="hcv-info">'
            f'<b>{_escape(position["name"])}</b>'
            f'<span>{_escape(position.get("ticker") or "—")} · {_escape(position["category"])}</span>'
            '</div>'
            f'<div class="hcv-wt">{pct_weight(position.get("weight", 0))}%</div>'
            '</div>'
            '<div class="hcv-val">'
            f'<div class="hcv-val-num">{_money(position.get("market_value"), "KRW")}</div>'
            f'<div class="hcv-val-sub">{_escape(val_sub)}</div>'
            '</div>'
            '<div class="hcv-pills">'
            f'<div class="hcv-pill"><span>수익률</span><b class="{ret_cls}">{_escape(ret_val)}</b>'
            f'<small>{_escape(ret_sub)}</small></div>'
            f'<div class="hcv-pill"><span>오늘</span><b class="{day_cls}">{_escape(day_val)}</b>'
            f'<small>{_escape(day_sub)}</small></div>'
            '</div>'
            '<div class="hcv-stats">'
            f'<div class="hcv-st"><span>현재가</span><b>{_escape(cur_price)}</b></div>'
            f'<div class="hcv-st"><span>목표 여력</span><b class="{upside_cls}">{_escape(upside_str)}</b></div>'
            f'<div class="hcv-st"><span>수량</span><b>{_escape(qty_str)}</b></div>'
            '</div>'
            f'<div class="hcv-spark">{spark_svg}</div>'
            '</article>'
        )
    return '<div class="hcv-grid">' + "".join(cards) + '</div>'


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


def _portfolio_summary_html(summary: dict) -> str:
    if not summary["has_data"]:
        return (
            '<div class="pd-summary-grid">'
            + _summary_card("총 평가금액", "API 데이터 없음", "holdings 수량/평가금액 연결 필요")
            + _summary_card("총 평가손익", "데이터 대기", "실제 보유 원가 기준")
            + _summary_card("오늘 변동", "데이터 대기", "실제 보유 수량 기준")
            + _summary_card("최대 비중", "데이터 대기", "보유 포지션 연결 후 계산")
            + '</div>'
        )
    gain_cls = _tone(summary["total_gain_loss"])
    today_cls = _tone(summary["today_change_amount"])
    largest = summary["largest_position"]
    contributor = summary["top_gain_contributor"]
    gain_pct = summary["total_gain_loss_pct"]
    today_pct = summary["today_change_pct"]
    cards = [
        _summary_card("총 평가금액", _money(summary["total_market_value"], "KRW", compact=True), "실제 holdings 평가 기준"),
        _summary_card(
            "총 평가손익",
            _money(summary["total_gain_loss"], "KRW", signed=True, compact=True),
            f"평가 수익률 {gain_pct:+.2f}%" if gain_pct is not None else "원가 데이터 대기",
            gain_cls,
        ),
        _summary_card(
            "오늘 변동",
            _money(summary["today_change_amount"], "KRW", signed=True, compact=True),
            f"오늘 변동률 {today_pct:+.2f}%" if today_pct is not None else "전일가 데이터 대기",
            today_cls,
        ),
        _summary_card(
            "최대 비중 종목",
            largest["name"] if largest else "데이터 대기",
            f"{pct_weight(largest.get('weight', 0))}% · {_money(largest.get('market_value'), 'KRW', compact=True)}" if largest else "",
        ),
        _summary_card(
            "최대 손익 기여",
            contributor["name"] if contributor else "데이터 대기",
            _money(contributor.get("gain_loss"), "KRW", signed=True, compact=True) if contributor else "손익 데이터 대기",
            _tone(contributor.get("gain_loss") if contributor else None),
        ),
        _summary_card(
            "현금/예수금",
            _money(summary.get("cash_balance"), "KRW", compact=True) if summary.get("cash_balance") is not None else "데이터 없음",
            "API cashBalance 기준",
        ),
        _summary_card(
            "USD/KRW",
            _cur(summary["fx_usdkrw"], "KRW") if summary.get("fx_usdkrw") else "데이터 대기",
            "해외자산 원화 환산 기준",
        ),
    ]
    return '<div class="pd-summary-grid">' + "".join(cards) + '</div>'


def _allocation_html(categories: list[dict]) -> str:
    active = [c for c in categories if c["count"] > 0 and c["weight"] > 0]
    if not active:
        return '<div class="pd-empty"><b>자산군 비중 데이터 없음</b><p>실제 holdings 데이터가 연결되면 보유 자산군만 표시합니다. 0% 자산군은 기본적으로 숨깁니다.</p></div>'
    rows = []
    for cat in active:
        rows.append(
            '<div class="pd-alloc-row">'
            f'<div class="pd-alloc-name">{_escape(cat["name"])}</div>'
            '<div class="pd-alloc-track">'
            f'<div class="pd-alloc-fill" style="width:{min(100, max(0, cat["weight"])):.1f}%"></div>'
            '</div>'
            f'<div class="pd-alloc-pct">{pct_weight(cat["weight"])}%</div>'
            '</div>'
        )
    return (
        '<div class="pd-card">'
        '<div class="pd-section-title"><b>자산군 비중</b><span>실제 보유 자산군만</span></div>'
        f'<div class="pd-alloc-list">{"".join(rows)}</div>'
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
    tk = str(position["ticker"])
    note = (_consensus_notes(tk).get(tk)
            or "네이버 컨센서스 미연결 종목 · 가격, 비중, 손익 변화를 함께 확인하세요.")
    target, upside, _ = _target_info(position, target_prices)
    impact = (
        f"내 포지션 기준 영향: 현재 비중 {pct_weight(position.get('weight', 0))}%로,"
        "해당 종목 변동성이 포트폴리오 평가액에 일부 반영될 수 있습니다."
    )
    return (
        f"<b>주요 이슈</b>: {_escape(note)}<br>"
        f"<b>목표가</b>: {_escape(target)} · <b>목표가 대비 여력</b>: {_escape(upside)}<br>"
        f"<b>{_escape(impact)}</b><br>"
        "<b>체크포인트</b>: 실적 가이던스, 금리·환율, 업종 모멘텀, 포트폴리오 내 비중 변화"
    )


def _holding_card_html(position: dict, target_prices: dict[str, float], sparks: dict[str, list[float]]) -> str:
    gain_cls = _tone(position.get("gain_loss"))
    ret_cls = _tone(position.get("gain_loss_pct"))
    day_cls = _tone(position.get("today_change_pct"), 0.05)
    target, upside, upside_cls = _target_info(position, target_prices)
    logo_item = {"group": position["category"], "name": position["name"], "code": position["ticker"]}

    if position.get("today_change_pct") is not None:
        day_html = f'<div class="pd-day"><span>오늘</span><b class="{day_cls}">{position.get("today_change_pct"):+.2f}%</b></div>'
    else:
        day_html = '<div class="pd-day"><span>오늘</span><b class="pd-neu">대기</b></div>'

    if position.get("gain_loss_pct") is not None:
        ret_html = f'<div class="pd-stat"><span>수익률</span><b class="{ret_cls}">{position.get("gain_loss_pct"):+.2f}%</b></div>'
    else:
        ret_html = '<div class="pd-stat"><span>수익률</span><b class="pd-neu">데이터 대기</b></div>'

    return (
        '<article class="pd-holding-card">'
        '<div class="pd-holding-top">'
        f'{_logo_html(logo_item)}'
        f'<div class="pd-holding-name"><b>{_escape(position["name"])}</b><span>{_escape(position["ticker"])}</span></div>'
        f'<div class="pd-weight">{pct_weight(position.get("weight", 0))}%</div>'
        '</div>'
        '<div class="pd-value-row">'
        f'<div class="pd-value-main"><span>평가금액 (원화)</span><b>{_money(position.get("market_value"), "KRW")}</b></div>'
        + day_html +
        '</div>'
        '<div class="pd-stat-grid">'
        f'<div class="pd-stat"><span>평가손익</span><b class="{gain_cls}">{_money(position.get("gain_loss"), "KRW", signed=True)}</b></div>'
        + ret_html +
        f'<div class="pd-stat"><span>현재가</span><b>{_price(position.get("current_price"), position.get("currency", "KRW"))}</b></div>'
        f'<div class="pd-stat"><span>평균단가</span><b>{_price(position.get("avg_price"), position.get("currency", "KRW"))}</b></div>'
        f'<div class="pd-stat"><span>보유수량</span><b>{_fmt_qty(position.get("quantity"), position.get("quantity_est", False))}</b></div>'
        f'<div class="pd-stat"><span>목표가</span><b>{_escape(target)}</b></div>'
        f'<div class="pd-stat"><span>목표 여력</span><b class="{upside_cls}">{_escape(upside)}</b></div>'
        '</div>'
        f'<div class="pd-spark">{_sparkline_svg(sparks.get(position["ticker"], []))}</div>'
        '<details class="pd-insight">'
        '<summary>애널리스트 인사이트 보기</summary>'
        f'<div class="pd-insight-body">{_insight_text(position, target_prices)}</div>'
        '</details>'
        '</article>'
    )


def _empty_category_html(name: str) -> str:
    return (
        '<div class="pd-empty">'
        f'<b>{_escape(name)} 보유 없음</b>'
        f'<p>현재 API 기준 보유 중인 {name} 자산이 없습니다. 관심 종목과 시장 모니터링 종목은 시장 분석 탭에서 확인할 수 있습니다.</p>'
        '</div>'
    )


def _holdings_categories_html(categories: list[dict], target_prices: dict[str, float], sparks: dict[str, list[float]]) -> str:
    parts: list[str] = []
    for category in categories:
        if category["count"] == 0:
            parts.append(_empty_category_html(category["name"]))
            continue
        leaders = " · ".join(p["name"] for p in category["top_by_value"])
        parts.append(
            '<section class="pd-cat-section">'
            '<div class="pd-cat-head">'
            f'<h4>{_escape(category["name"])} {category["count"]}개 · 평가금액 상위: {_escape(leaders)}</h4>'
            f'<span>{_money(category["total_market_value"], "KRW")} · {pct_weight(category["weight"])}%</span>'
            '</div>'
            '<div class="pd-holding-grid">'
            + "".join(_holding_card_html(p, target_prices, sparks) for p in category["items"])
            + '</div></section>'
        )
    return "".join(parts)


# _AJ_CSS → ui.pages.portfolio_css 로 이동


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


def _render_asset_trend(username: str | None, positions: list[dict], fx: float,
                        start_date=None) -> None:
    """자산 추이 — 보유 × 기간 가격 이력으로 일별 총 평가액 추세.

    기본은 '전체'(투자 시작일~현재) — 여정의 '지나온 경로'와 직결되는 구간. 1M~1Y는 짧은 범위 확대용.
    전환(여정↔추이)은 상위 _render_asset_section 의 스트립 토글이 담당(리로드 없는 fragment 부분 리런).
    """
    import plotly.graph_objects as go
    from core.journey import krw_compact
    _AP = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
    _start_iso = start_date.isoformat() if hasattr(start_date, "isoformat") else (start_date or None)
    opts = (["전체"] if _start_iso else []) + list(_AP.keys())
    period = st.radio("추이 기간", opts, index=0, horizontal=True,
                      label_visibility="collapsed", key="trend_range")
    _smooth = 0.6
    if period == "전체":
        s = _portfolio_value_series(positions, "", fx, start=_start_iso)
        range_label = "투자 시작 이후"
        # 장기 구간은 일봉이 너무 빽빽 → 주봉 다운샘플로 더 매끈하게(스플라인 평활도도 ↑)
        if s is not None and len(s) > 180:
            s = s.resample("W").last().dropna()
            _smooth = 1.0
    else:
        s = _portfolio_value_series(positions, _AP.get(period, "3mo"), fx)
        range_label = period
    if s is None or len(s) < 2:
        st.caption("자산 추이 — 보유 종목 가격 이력이 모이면 기간별 총 평가액 추세가 표시됩니다.")
        return
    first, last = float(s.iloc[0]), float(s.iloc[-1])
    chg = (last / first - 1) * 100 if first else 0
    cls = "up" if chg >= 0 else "down"
    sign = "+" if chg >= 0 else ""
    st.markdown(
        _AT_CSS + f'<div class="at-head"><b>자산 추이</b>'
        f'<span>{range_label} · {krw_compact(first)} → {krw_compact(last)} '
        f'<b class="{cls}">{sign}{chg:.1f}%</b></span></div>',
        unsafe_allow_html=True)
    # 자연스러운 영역 차트 — 스플라인 곡선 + 골드 그라데이션 채움. 0이 아닌 min 근처로 줌(추세 강조).
    ymin, ymax = float(s.min()), float(s.max())
    pad = (ymax - ymin) * 0.14 or max(ymax * 0.02, 1.0)
    fig = go.Figure(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        line=dict(color="#D9A441", width=2, shape="spline", smoothing=_smooth),
        fill="tozeroy", fillcolor="rgba(217,164,65,0.12)",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f}원<extra></extra>",
    ))
    fig.update_layout(
        height=160, margin=dict(l=0, r=0, t=4, b=0),          # 바그래프 크기로 컴팩트
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showline=False, zeroline=False, nticks=5,
                   tickfont=dict(size=9, color="#7E8694")),
        yaxis=dict(visible=False, range=[ymin - pad, ymax + pad]),  # 축 숨김 → 컴팩트, 추세만
        showlegend=False, hovermode="x",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key="asset_trend_chart")


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
    from core.journey import journey_metrics, krw_compact, stage_label

    username = st.session_state.get("username")
    target = int(_journey_get("target_value", username, is_guest, 1_500_000_000))
    # 초기 투자금은 보유 수익률 역산 원가(=실제 투자원금)로 자동 산출 — 벤치마크 수익률과 동일 기준.
    # (이전엔 게어의 수동 입력값을 저장·사용했는데, 키 위젯의 stale 세션값이 재저장돼 손실인데도
    #  연 성장률이 +로 나오는 오류가 반복됨. 자동 원가로 단일화해 벤치마크와 일관성 확보.)
    start_value = _estimate_start_value(positions, current_value)
    sd_raw = _journey_get("start_date", username, is_guest, (_date.today() - timedelta(days=730)).isoformat())
    start_date = _date.fromisoformat(sd_raw) if isinstance(sd_raw, str) else sd_raw

    # ── 자산 여정: 카드(border) 없이 플랫 — 헤더(제목 좌 / [순항중·페이스·목표수정] 우측 한 줄) + 그리드 ──
    with st.container(border=False):
        st.markdown('<div class="aj-marker"></div>', unsafe_allow_html=True)
        title_col, badge_col, gear_col = st.columns([6.2, 2.6, 0.7], gap="small")

        target_date = st.session_state.get("portfolio_target_date") or (_date.today() + timedelta(days=365 * 5))
        m = journey_metrics(start_date, start_value, current_value, target, target_date)
        pace = m["pace_months"]
        # 페이스 배지(평가) — 앞섬=골드 / 부합=중립회색 / 뒤처짐=주황 경고. 12개월↑은 정성 평가.
        if pace is None:
            pace_html = ""
        elif pace >= 12:
            pace_html = '<span class="aj-pace ahead">목표 페이스 크게 상회</span>'
        elif pace > 0:
            pace_html = f'<span class="aj-pace ahead">예정보다 {pace}개월 빠름</span>'
        elif pace == 0:
            pace_html = '<span class="aj-pace ontrack">예정 페이스에 부합</span>'
        elif pace > -12:
            pace_html = f'<span class="aj-pace behind">예정보다 {abs(pace)}개월 늦음</span>'
        else:
            pace_html = '<span class="aj-pace behind">목표 페이스 크게 하회</span>'

        # 단계 배지(정보) — 진행 phase 별 초록 계열(초반=중립 → 순항=초록 → 막바지=진초록 → 도달=초록 강조)
        _stage = stage_label(m["progress_pct"])
        _stage_cls = {"초반 구간": "s-early", "순항 중": "s-cruise",
                      "막바지 구간": "s-final", "목표 도달": "s-reached"}.get(_stage, "s-cruise")

        with title_col:
            st.markdown(_AJ_CSS + '<div class="aj-top aj-top-row"><h3>자산 여정</h3></div>',
                        unsafe_allow_html=True)
        with badge_col:
            # [순항 중][페이스] 우측 정렬, 단계↔페이스 간격 = 컬럼 간격(=페이스↔톱니)과 맞춰 3개 등간격
            st.markdown(
                f'<div class="aj-badgewrap"><span class="aj-stage {_stage_cls}">{_escape(_stage)}</span>'
                f'{pace_html}</div>', unsafe_allow_html=True)
        with gear_col:
            # 목표수정: 톱니 아이콘만(헤더 제자리라 '설정'으로 직관적). 높이는 배지와 통일(28px)
            with st.popover(":material/settings:", use_container_width=False, help="목표 수정"):
                st.markdown("<div class='aj-pop-t'>여정 설정</div>", unsafe_allow_html=True)
                # 목표 금액(억원, 작은 포트폴리오 대비 value clamp). 초기투자금은 보유 원가로 자동
                # 산출하므로 입력 제거(키 위젯 stale 세션값이 재저장돼 연 성장률이 잘못 나오던 오염원).
                _TGT_MIN, _EOK_MAX = 0.1, 2000.0
                _target_eok = min(_EOK_MAX, max(_TGT_MIN, round(target / 1e8, 1)))
                new_target_eok = st.number_input(
                    "목표 금액 (억원)", min_value=_TGT_MIN, max_value=_EOK_MAX,
                    value=_target_eok, step=0.5, format="%.1f", key="aj_target_eok",
                )
                new_start_date = st.date_input(
                    "투자 시작일", value=start_date, max_value=_date.today(), key="aj_start_date",
                )
                st.caption("초기 투자금은 보유 원가로 자동 산출 · 시작일로 연 성장률(CAGR)·예상 기간을 계산합니다.")

                new_target = int(round(new_target_eok * 1e8))
                changed = False
                # 사용자가 입력값을 실제로 변경했을 때만 저장(표시된 기본값과 비교).
                if new_target_eok != _target_eok:
                    _journey_set("target_value", new_target, username, is_guest); changed = True
                if new_start_date.isoformat() != start_date.isoformat():
                    _journey_set("start_date", new_start_date.isoformat(), username, is_guest); changed = True
                if changed:
                    st.rerun()  # 전체 리런 — 벤치마크 비교·PB 진단도 새 시작일 반영
        # 진행률 바 ↔ 자산 추이 in-place 교체(같은 .aj-chart 슬롯 = 동일 위치·크기). positions 있을 때만.
        open_ = bool(st.session_state.get("journey_trend_open", False)) and positions is not None
        chart_svg = _hl_label = _hl_val = None
        if open_:
            _si = start_date.isoformat() if hasattr(start_date, "isoformat") else start_date
            _s = _portfolio_value_series(positions, "", fx, start=_si)
            if _s is not None and len(_s) > 180:
                _s = _s.resample("W").last().dropna()   # 주봉 다운샘플 → 더 매끈
            chart_svg = _asset_trend_svg(_s)
            # 추이 표시 중엔 헤드라인을 '투자 시작 이후 +N%'(상승=빨강/하락=파랑)로 교체
            if _s is not None and len(_s) >= 2 and float(_s.iloc[0]):
                _tp = (float(_s.iloc[-1]) / float(_s.iloc[0]) - 1) * 100
                _cls = "aj-val-up" if _tp >= 0 else "aj-val-down"
                _hl_label = "투자 시작 이후"
                _hl_val = f'<span class="{_cls}">{"+" if _tp >= 0 else ""}{_tp:.1f}%</span>'
        if positions is None:
            # 게스트 등 — 클릭 없이 단일 그리드
            st.markdown(_journey_block_html(current_value, target, m, chart_svg=chart_svg,
                        headline_label=_hl_label, headline_val_html=_hl_val), unsafe_allow_html=True)
        else:
            # 바 자체 클릭으로 전환 — 차트 셀(좌) 위에 투명 오버레이 버튼을 겹쳐 '바 클릭'을 토글로
            _lc, _rc = st.columns([1.5, 1], gap="medium")
            with _lc:
                st.markdown(_AJ_CSS + _journey_leftcell_html(current_value, target, m, chart_svg=chart_svg,
                            headline_label=_hl_label, headline_val_html=_hl_val, clickable=True),
                            unsafe_allow_html=True)
                st.markdown('<span class="aj-barclick-anchor"></span>', unsafe_allow_html=True)
                if st.button(" ", key="journey_trend_toggle", use_container_width=True):
                    st.session_state["journey_trend_open"] = not open_
                    st.rerun(scope="fragment")
            with _rc:
                st.markdown(_AJ_CSS + f'<div class="aj-cards">{_journey_cards_html(current_value, m, target)}</div>',
                            unsafe_allow_html=True)


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


def _pb_risk_summary_html(d: dict) -> str:
    """전체현황(다이제스트)용 한 줄 요약 — 헤드라인 + 핵심 한 줄.
    풀 카드(지표 그리드·재배분·벤치마크)는 포트폴리오/리스크에만 두어 100% 복제를 제거한다.
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
    sub = (f'최대 종목 −20% 시 계좌 {d["shock_pct"]:.1f}% · 현금 {pct_weight(d["cash_pct"])}% · '
           f'USD {pct_weight(d["usd_w"])}%')
    return (
        f'<div class="pb-card pb-{lv_cls} pb-compact">'
        f'<span class="pb-sev">{sev_html}</span>'
        f'<div class="pb-head">{_escape(head)}</div>'
        f'<div class="pb-bench">{_escape(sub)}</div>'
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


def _delete_holding(holdings: list[dict], index: int) -> list[dict]:
    """holdings 에서 index 항목을 뺀 새 리스트 반환. 범위 밖이면 원본 복사본 그대로(원본 비변형)."""
    if index < 0 or index >= len(holdings):
        return list(holdings)
    return [h for i, h in enumerate(holdings) if i != index]


def _persist_holdings(holdings: list[dict]) -> None:
    """세션 + 계정 저장소에 보유를 반영. 로그인 유저만 영속화(스크린샷 적용 경로와 동일 패턴)."""
    st.session_state["brokerage_holdings"] = holdings
    _uname = st.session_state.get("username")
    if st.session_state.get("auth_role") == "user" and _uname:
        from core.accounts import get_portfolios, save_portfolio
        _ex = get_portfolios(_uname)
        _pf_name = _ex[0]["name"] if _ex else "내 포트폴리오"
        save_portfolio(_uname, holdings, name=_pf_name,
                       cash=st.session_state.get("brokerage_cash_balance", 0.0))


def _render_holdings_editor() -> None:
    """편집 모드 — 원본 brokerage_holdings 를 순서대로 보여주고 행별 삭제(2단계 확인)."""
    holdings = st.session_state.get("brokerage_holdings") or []
    if not holdings:
        st.info("보유 종목이 없습니다.")
        return
    _last_note = " · 마지막 한 종목을 지우면 온보딩 화면으로 돌아갑니다." if len(holdings) == 1 else ""
    st.caption(f"삭제할 종목의 🗑 버튼을 누르세요.{_last_note}")

    pending = st.session_state.get("_pending_delete_holding")
    for i, h in enumerate(holdings):
        name = h.get("name", "—")
        amt = _cur(float(h.get("평가금액") or h.get("eval_amount") or 0), "KRW")
        c_info, c_act = st.columns([4, 2])
        with c_info:
            st.markdown(f"**{name}**  ·  {amt}")
        with c_act:
            if pending == i:
                cc1, cc2 = st.columns(2)
                if cc1.button("삭제 확정", key=f"del_confirm_{i}", type="primary",
                              use_container_width=True):
                    _persist_holdings(_delete_holding(holdings, i))
                    st.session_state.pop("_pending_delete_holding", None)
                    st.rerun()
                if cc2.button("취소", key=f"del_cancel_{i}", use_container_width=True):
                    st.session_state.pop("_pending_delete_holding", None)
                    st.rerun()
            else:
                if st.button("🗑 삭제", key=f"del_{i}", use_container_width=True):
                    st.session_state["_pending_delete_holding"] = i
                    st.rerun()


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
        f'{live_badge_html(["US", "KR", "CRYPTO"], compact=True)}</div></div>',
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
    _auth = "_auth=guest" if _role == "guest" else (f"_user={_u}" if _u else "")
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
        edit_mode = st.toggle("편집 — 종목 삭제", key="holdings_edit_mode")
        if edit_mode:
            _render_holdings_editor()
        else:
            sort_key = st.radio(
                "보유종목 정렬", ["비중순", "수익률순", "오늘 변동순", "목표여력순"],
                index=0, key="portfolio_holding_sort", label_visibility="collapsed", horizontal=True,
            ) or "비중순"
            sorted_positions = _sort_positions(positions, target_prices, sort_key)
            st.markdown(
                _holdings_panel_html("전체 보유종목", f"{sort_key} · 비교형 리스트", sorted_positions, target_prices),
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
        st.markdown(
            _holdings_panel_html("핵심 보유종목", "비중 상위 5종목 · 상세는 펼쳐보기", sorted_by_weight,
                                 target_prices, limit=5, action=_hold_action),
            unsafe_allow_html=True,
        )
        # 자산 여정 ↔ 자산 추이 — segmented control 토글(fragment 부분 리런, 전체 리로드 없음)
        if journey:
            _render_asset_section(journey["current_asset"], _uname, positions,
                                  _usdkrw(data) or _FX_FALLBACK)


def _holding_items(
    us_held: pd.DataFrame,
    kr_stocks: pd.DataFrame,
    etfs: pd.DataFrame,
    commodities: pd.DataFrame,
    crypto_df: pd.DataFrame,
) -> list[dict]:
    items: list[dict] = []

    def _sort_value(row, fallback: int, currency: str) -> float:
        for col in ("market_value", "holding_value", "position_value", "amount", "value", "평가액", "보유금액"):
            if col in row and _num(row.get(col)) is not None:
                return float(_num(row.get(col)) or 0)
        return max(0, 1000 - fallback)

    def _add(group: str, name: str, code: str, price: str, chg, meta1: str, meta2: str, sort_value: float) -> None:
        pct_s, pct_cls = _pct(chg)
        items.append(
            {
                "group": group,
                "name": str(name or ""),
                "code": str(code or ""),
                "price": price,
                "pct": pct_s,
                "pct_cls": pct_cls,
                "meta1": str(meta1 or ""),
                "meta2": str(meta2 or ""),
                "sort_value": sort_value,
            }
        )

    if not us_held.empty:
        for idx, (_, r) in enumerate(us_held.iterrows()):
            _add(
                    "미국주식",
                    r.get("name", r.get("ticker", "")),
                    r.get("ticker", ""),
                    _price(r.get("price"), "USD"),
                    r.get("change_pct"),
                    str(r.get("sector", "")).replace("_", " "),
                    "직접 보유",
                    _sort_value(r, idx, "USD") + 4000,
            )

    if not kr_stocks.empty:
        for idx, (_, r) in enumerate(kr_stocks.iterrows()):
            role = "직접 보유" if r.get("role") == "actual_holding" else "모니터링"
            _add(
                    "국내주식",
                    r.get("name", r.get("ticker", "")),
                    r.get("ticker", ""),
                    _price(r.get("price"), "KRW"),
                    r.get("change_pct"),
                    str(r.get("sector", "")).replace("_", " "),
                    role,
                    _sort_value(r, idx, "KRW") + 1000,
            )

    if not etfs.empty:
        for idx, (_, r) in enumerate(etfs.iterrows()):
            hedge = "환헤지" if r.get("hedged") is True else "환노출"
            _add(
                    "ETF",
                    r.get("name", r.get("ticker", "")),
                    r.get("ticker", ""),
                    _price(r.get("price"), "KRW"),
                    r.get("change_pct"),
                    hedge,
                    f"BM {r.get('benchmark', '-')}",
                    _sort_value(r, idx, "KRW") + 5000,
            )

    if not commodities.empty:
        for idx, (_, r) in enumerate(commodities.iterrows()):
            key = r.get("name", "")
            _add(
                    "원자재",
                    _COMM_KOR.get(key, str(key).title()),
                    r.get("ticker", ""),
                    _price(r.get("price"), "USD"),
                    r.get("change_pct"),
                    "실시간 시세",
                    "시장 노출 관리",
                    _sort_value(r, idx, "USD") + 2000,
            )

    if not crypto_df.empty:
        for idx, (_, r) in enumerate(crypto_df.iterrows()):
            _add(
                    "크립토",
                    r.get("name", r.get("ticker", "")),
                    r.get("symbol", r.get("ticker", "")),
                    _price(r.get("price"), "USD"),
                    r.get("change_pct"),
                    str(r.get("category", "")).replace("_", " "),
                    "직접 보유",
                    _sort_value(r, idx, "USD") + 3000,
            )

    return sorted(items, key=lambda item: item["sort_value"], reverse=True)


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


def _holding_rows_html(items: list[dict]) -> str:
    rows: list[str] = []
    for idx, item in enumerate(items, 1):
        rows.append(
            '<div class="hold-row">'
            f'<div class="hold-rank">{idx:02d}</div>'
            f'<div class="hold-main"><b>{_escape(item["name"])}</b><span>{_escape(item["code"])}</span></div>'
            f'<div class="hold-cat">{_escape(item["group"])}</div>'
            f'<div class="hold-row-price">{_escape(item["price"])}</div>'
            f'<div class="hold-row-chg {item["pct_cls"]}">{_escape(item["pct"])}</div>'
            f'<div class="hold-row-note">{_escape(item["meta2"])}</div>'
            '</div>'
        )
    return '<div class="hold-list">' + "".join(rows) + '</div>'


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


def _holding_grouped_html(items: list[dict]) -> str:
    if not items:
        return '<div class="hold-empty">등록된 자산이 없습니다.</div>'
    order = ["미국주식", "국내주식", "ETF", "원자재", "크립토"]
    groups = {group: [item for item in items if item["group"] == group] for group in order}
    extra_groups = sorted({item["group"] for item in items} - set(order))
    html_parts: list[str] = []
    for group in order + extra_groups:
        group_items = groups.get(group) if group in groups else [item for item in items if item["group"] == group]
        if not group_items:
            continue
        leaders = " · ".join(_escape(item["name"]) for item in group_items[:3])
        html_parts.append(
            '<section class="hold-cat-section">'
            f'<div class="hold-cat-title"><b>{_escape(group)}</b><span>{len(group_items)}개 · 보유 큰 순</span></div>'
            f'<div class="hold-cat-summary"><span>상위: {leaders}</span></div>'
            f'{_holding_cards_html(group_items)}'
            '</section>'
        )
    return "".join(html_parts)


def _render_holding_expander(items: list[dict], target_prices: dict[str, float]) -> None:
    st.markdown(
        '<div class="port-detail-head"><h3>보유 포트폴리오 상세</h3>'
        '<span>카테고리별 접기/펼치기</span></div>',
        unsafe_allow_html=True,
    )
    if not items:
        st.markdown(_holding_summary_html(items), unsafe_allow_html=True)
        return

    order = ["미국주식", "국내주식", "ETF", "원자재", "크립토"]
    groups = {group: [item for item in items if item["group"] == group] for group in order}
    extra_groups = sorted({item["group"] for item in items} - set(order))

    for group in order + extra_groups:
        group_items = groups.get(group) if group in groups else [item for item in items if item["group"] == group]
        if not group_items:
            continue
        leaders = " · ".join(item["name"] for item in group_items[:3])
        with st.expander(f"{group} {len(group_items)}개 · 상위 {leaders}", expanded=False):
            st.markdown(_holding_cards_html(group_items), unsafe_allow_html=True)
            issues = _analyst_issues_html(group_items, target_prices)
            if issues:
                st.markdown(issues, unsafe_allow_html=True)


# _ONBOARD_CSS → ui.pages.portfolio_css 로 이동


def _render_onboarding() -> None:
    """첫 사용 온보딩 — 보유 0건(미연결 포함). 환영 + 핵심 개념 1분 안내 + 스크린샷 올리기 CTA."""
    st.markdown(_ONBOARD_CSS, unsafe_allow_html=True)
    _suf = ("?_user=" + st.session_state["username"]) if st.session_state.get("username") else ""
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
        k = (str(h.get("name", "")).strip(), str(h.get("ticker", "")).strip())
        if k == ("", ""):
            continue
        if k not in best:
            best[k] = h
            order.append(k)
        elif _amt(h) > _amt(best[k]):
            best[k] = h
    return [best[k] for k in order]


def _render_screenshot_upload(key: str = "screenshot_upload", show_header: bool = True) -> None:
    from core.vision_parser import parse_portfolio_image
    from ui.pages.login import _filter_valid_holdings

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
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,   # 여러 장(스크롤 캡처·계좌 분할 등) 한 번에 분석
        key=f"{key}_{st.session_state.get(nonce_key, 0)}",
        label_visibility="collapsed",
    )
    st.markdown(
        '<div class="scr-priv"><span>🔒 이미지는 <b>저장하지 않아요</b> · 여러 장을 한 번에 분석 후 '
        '보유 정보만 내 계정에 로컬 저장 · 거래 기능 없음</span></div>',
        unsafe_allow_html=True,
    )

    if not uploaded:   # None 또는 빈 리스트
        return

    # 파일 집합(이름·크기) 기준 캐시 키 — 같은 집합이면 재분석 안 함
    sig = "|".join(f"{u.name}:{u.size}" for u in uploaded)
    cache_key = f"_screenshot_parsed_{key}_{abs(hash(sig))}"
    if cache_key not in st.session_state:
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
                st.session_state[cache_key] = {
                    "holdings": deduped, "cash_balance": 0.0, "n_img": _n_img,
                    "raw_count": len(merged),
                }
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
    preview_rows = [
        {
            "종목명": h.get("name", ""),
            "코드": h.get("ticker", ""),
            "평가금액": _cur(_amt(h), "KRW"),
            "수익률": f"{float(h.get('수익률') or h.get('profit_loss_pct') or 0):+.2f}%",
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

    col_apply, col_cancel = st.columns([2, 1])
    with col_apply:
        if st.button("이 데이터로 포트폴리오 적용", use_container_width=True, key=f"btn_apply_{key}"):
            st.session_state["brokerage_holdings"] = holdings
            st.session_state["brokerage_cash_balance"] = cash
            st.session_state["brokerage_debug"] = result.get("_debug", {})
            st.session_state["brokerage_provider"] = "screenshot"
            # 로그인 유저는 계정 저장소에도 영속화 — 안 하면 하드 nav(?_user=) 후
            # app.py 세션 복원이 옛 보유로 되돌려 "업데이트가 안 되는" 것처럼 보임(login.py 저장 경로와 동일).
            _uname = st.session_state.get("username")
            if st.session_state.get("auth_role") == "user" and _uname:
                from core.accounts import get_portfolios, save_portfolio
                _existing = get_portfolios(_uname)
                _pf_name = _existing[0]["name"] if _existing else "내 포트폴리오"
                save_portfolio(_uname, holdings, name=_pf_name, cash=cash)
            st.session_state.pop(cache_key, None)
            st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1  # 업로더 비우기
            st.rerun()
    with col_cancel:
        if st.button("취소", use_container_width=True, key=f"btn_cancel_{key}"):
            st.session_state.pop(cache_key, None)
            st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1  # 업로더 비우기
            st.rerun()


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
        # USD eval_amount → KRW 환산 후 합산 (환율 실패 시 폴백 — 미국 종목이 안 빠지게)
        _fx = _usdkrw(data) or _FX_FALLBACK
        def _to_krw(h: dict, field: str) -> float:
            val = float(h.get(field) or 0)
            if val and _holding_currency(h, str(h.get("ticker") or "")) == "USD":  # 단일 출처
                val *= _fx
            return val
        live_holdings_total = sum(_to_krw(h, "평가금액") for h in brokerage_holdings)
        live_total = live_holdings_total + cash_balance
        live_cost = sum(_to_krw(h, "매입금액") for h in brokerage_holdings)
        live_gain = sum(_to_krw(h, "평가손익") for h in brokerage_holdings)
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

    # 스크린샷 업로더 — 요약 뷰에서 드롭존을 바로 노출(클릭 1스텝, 사용자 선호).
    # 기존 사용자에겐 온보딩 3단계 가이드 대신 간결한 섹션 타이틀만(맥락 제공·중복 제거).
    # (첫 사용자(보유 0건)는 위 _render_onboarding 에서 3단계 가이드로 노출.)
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

    # 푸터는 전 페이지 동일하게 jj_footer() 1개로 통일(포트폴리오 전용 데이터 캡션 제거).
    st.markdown(jj_footer(), unsafe_allow_html=True)
