"""
Market Overview — Bloomberg-lite institutional monitoring dashboard.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf

from data.fetcher import fetch_all
from core.config_loader import load_config
from src.risk import compute_regime_signals
from src.database import load_latest_indicator_summary, DEFAULT_DB
from ui.components.dash_style import (
    inject_css, section_header, timestamp_bar,
    numeric, csv_bytes, excel_bytes,
)

# ── Performance chart tickers ─────────────────────────────────────────────────
_PERF_TICKERS = {
    "QQQ":      "QQQ",
    "SPY":      "SPY",
    "SOXX":     "SOXX",
    "GLD":      "GLD",
    "SLV":      "SLV",
    "TLT":      "TLT",
    "구리":     "HG=F",
    "USD/KRW":  "USDKRW=X",
    "DXY":      "DX-Y.NYB",
    "미국10Y":  "^TNX",
    "KWEB":     "KWEB",
    "비트코인": "BTC-USD",
}

_PERF_COLORS = {
    "QQQ":      "#1C2B3A", "SPY":     "#4A6FA5", "SOXX":    "#E07B39",
    "GLD":      "#C9A84C", "SLV":     "#8CA0B3", "TLT":     "#5A7D9A",
    "구리":     "#B87333", "USD/KRW": "#6B7A8D", "DXY":     "#5E7C8B",
    "미국10Y":  "#D64E4E", "KWEB":    "#E53935", "비트코인": "#F7931A",
}

_PERF_DEFAULTS = ["QQQ", "SOXX", "GLD", "비트코인", "USD/KRW"]
_PERIOD_MAP    = {"1M": "1mo", "3M": "3mo", "6M": "6mo"}

# ── ETF Driver Heatmap ────────────────────────────────────────────────────────
_HM_ETFS = [
    "TIGER 나스닥100",      "RISE S&P500",
    "KODEX 빅테크10(H)",    "PLUS 나스닥테크",
    "TIGER 반도체나스닥",    "TIGER 반도체레버리지",
    "KODEX AI테크TOP10",    "KODEX AI커버드콜",
    "KODEX 배당커버드콜",
    "ACE KRX금현물",        "TIGER KRX금현물",
    "KODEX 은선물(H)",      "TIGER 구리실물",
    "TIGER 차이나휴머노이드", "KODEX 차이나휴머노이드",
]
_HM_DRIVERS = ["금리", "달러", "USD/KRW", "AI", "반도체", "금", "은", "구리", "중국"]

# Exposure matrix [Rate, Dollar, FX, AI, Semi, Gold, Silver, Copper, China]
_HM_Z = [
    [2, 0, 1, 2, 1, 0, 0, 0, 0],  # TIGER 나스닥100
    [1, 0, 1, 1, 1, 0, 0, 0, 0],  # RISE S&P500
    [2, 0, 0, 2, 1, 0, 0, 0, 0],  # KODEX 빅테크10(H) hedged
    [2, 0, 1, 2, 1, 0, 0, 0, 0],  # PLUS 나스닥테크
    [2, 0, 1, 1, 2, 0, 0, 1, 0],  # TIGER 반도체나스닥
    [2, 0, 1, 1, 2, 0, 0, 1, 0],  # TIGER 반도체레버리지
    [2, 0, 1, 2, 1, 0, 0, 0, 0],  # KODEX AI테크TOP10
    [1, 0, 1, 2, 1, 0, 0, 0, 0],  # KODEX AI커버드콜
    [1, 0, 1, 0, 0, 0, 0, 0, 0],  # KODEX 배당커버드콜
    [0, 2, 1, 0, 0, 2, 0, 0, 0],  # ACE KRX금현물
    [0, 2, 1, 0, 0, 2, 0, 0, 0],  # TIGER KRX금현물
    [0, 1, 0, 0, 1, 0, 2, 0, 0],  # KODEX 은선물(H)
    [0, 1, 1, 0, 1, 0, 0, 2, 1],  # TIGER 구리실물
    [1, 1, 1, 1, 1, 0, 0, 1, 2],  # TIGER 차이나휴머노이드
    [1, 1, 1, 1, 1, 0, 0, 1, 2],  # KODEX 차이나휴머노이드
]

# Signal → heatmap column index
_SIG_COL = {
    "Rate Pressure":          0,
    "Dollar Strength":        1,
    "Korea FX Risk":          2,
    "Tech Momentum":          3,
    "Semiconductor Momentum": 4,
}

_LEVEL_KOR = {
    "NEUTRAL": "중립", "MEDIUM": "중간", "HIGH": "높음", "LOW": "낮음",
    "RISING": "상승", "FALLING": "하락", "FLAT": "보합",
    "RISK-ON": "위험선호", "RISK-OFF": "위험회피",
    "BULLISH": "상승", "BEARISH": "하락", "STRONG": "강세", "WEAK": "약세",
}

# Signal English → Korean display names
_SIG_KOR = {
    "Risk-on / Risk-off":      "위험선호 지수",
    "Dollar Strength":         "달러 강도",
    "Rate Pressure":           "금리 압력",
    "Tech Momentum":           "기술주 모멘텀",
    "Semiconductor Momentum":  "반도체 모멘텀",
    "Commodity Momentum":      "원자재 모멘텀",
    "Korea FX Risk":           "원화 환율 리스크",
}

_ETF   = {"name":"종목명","ticker":"티커","price":"현재가","change":"전일대비",
          "change_pct":"등락률(%)","benchmark":"벤치마크","hedged":"환헤지"}
_BENCH = {"ticker":"티커","name":"종목명","price":"현재가","change_pct":"등락률(%)"}
_STOCK = {"ticker":"티커","name":"종목명","sector":"섹터","price":"현재가","change_pct":"등락률(%)"}
_COMM  = {"name":"원자재","price":"현재가","change_pct":"등락률(%)"}
_FX    = {"pair":"통화쌍","rate":"환율","change_pct":"등락률(%)","priority":"중요도"}
_MAC   = {"key":"지표","series_id":"FRED코드","value":"값","date":"기준일"}


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load():
    return fetch_all()


@st.cache_data(ttl=1800)
def _multi_history(period: str) -> pd.DataFrame:
    """Normalized (base=100) price history for all perf tickers."""
    yf_period = _PERIOD_MAP.get(period, "3mo")
    ticker_list = list(_PERF_TICKERS.values())
    try:
        raw = yf.download(ticker_list, period=yf_period, interval="1d",
                          progress=False, auto_adjust=True)
        if raw.empty:
            return pd.DataFrame()
        # yf returns MultiIndex (price_type, ticker) when multiple tickers
        closes = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
        result = {}
        for label, tk in _PERF_TICKERS.items():
            try:
                if tk in closes.columns:
                    s = closes[tk].dropna()
                    if len(s) > 1:
                        result[label] = (s / s.iloc[0]) * 100
            except Exception:
                continue
        return pd.DataFrame(result) if result else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ── Chart builders ────────────────────────────────────────────────────────────

def _perf_chart(period: str, selected: list[str]) -> go.Figure:
    df = _multi_history(period)
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(text="데이터 없음", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
    else:
        for name in selected:
            if name not in df.columns:
                continue
            s   = df[name].dropna()
            pct = s.iloc[-1] - 100
            sign = "+" if pct >= 0 else ""
            fig.add_trace(go.Scatter(
                x=s.index, y=s,
                name=f"{name}  {sign}{pct:.1f}%",
                line=dict(color=_PERF_COLORS.get(name, "#888"), width=1.5),
                mode="lines",
                hovertemplate="%{y:.1f}<extra>" + name + "</extra>",
            ))
        fig.add_hline(y=100, line_width=1, line_dash="dot", line_color="#CBD5E0")

    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0), height=300,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
        xaxis=dict(showgrid=False, showline=True, linecolor="#E2E8F0",
                   tickfont=dict(size=9, color="#718096")),
        yaxis=dict(showgrid=True, gridcolor="#F0F4F8", showline=True,
                   linecolor="#E2E8F0", tickfont=dict(size=9, color="#718096"),
                   side="right"),
        legend=dict(font=dict(size=8.5), orientation="h",
                    yanchor="bottom", y=1.01, xanchor="left", x=0,
                    bgcolor="rgba(255,255,255,0)"),
        hovermode="x unified",
        showlegend=True,
    )
    return fig


def _rotation_chart(period: str) -> go.Figure:
    df = _multi_history(period)
    fig = go.Figure()
    if df.empty:
        return fig
    returns = {}
    for col in df.columns:
        s = df[col].dropna()
        if not s.empty and not pd.isna(s.iloc[-1]):
            returns[col] = round(s.iloc[-1] - 100, 2)
    if not returns:
        return fig
    sorted_items = sorted(returns.items(), key=lambda x: x[1])
    names  = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    colors = ["#276749" if v >= 0 else "#9B2335" for v in values]
    texts  = [f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%" for v in values]

    fig.add_trace(go.Bar(
        x=values, y=names, orientation="h",
        marker_color=colors, marker_opacity=0.72,
        text=texts, textposition="outside",
        textfont=dict(size=8.5, color="#4A5568"),
        cliponaxis=False,
    ))
    fig.update_layout(
        margin=dict(l=0, r=60, t=8, b=0), height=320,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
        xaxis=dict(showgrid=True, gridcolor="#F0F4F8",
                   zeroline=True, zerolinecolor="#CBD5E0", zerolinewidth=1,
                   tickformat="+.1f", ticksuffix="%",
                   tickfont=dict(size=9, color="#718096")),
        yaxis=dict(tickfont=dict(size=9, color="#2D3748"), showgrid=False),
        showlegend=False,
    )
    return fig


def _regime_bar(signals: list[dict]) -> go.Figure:
    _COL = {"low": "#38A169", "mid": "#D69E2E", "high": "#9B2335", "na": "#A0AEC0"}
    names  = [_SIG_KOR.get(s["signal"], s["signal"]) for s in signals]
    scores = [s.get("score", 50) for s in signals]
    colors = [_COL.get(s["col"], "#A0AEC0") for s in signals]

    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker_color=colors, marker_opacity=0.65,
        text=[f"{sc}" for sc in scores],
        textposition="outside",
        textfont=dict(size=9, color="#4A5568"),
        cliponaxis=False,
        hovertemplate="%{y}: %{x}/100<extra></extra>",
    ))
    fig.add_vline(x=50, line_width=1, line_dash="dot", line_color="#CBD5E0")
    fig.update_layout(
        title=dict(text="신호 강도  (0 = 약세/위험회피  ·  100 = 강세/위험선호)",
                   font=dict(size=10, color="#718096"), x=0, xanchor="left"),
        margin=dict(l=0, r=50, t=30, b=0), height=240,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
        xaxis=dict(range=[0, 115], showgrid=True, gridcolor="#F0F4F8",
                   tickfont=dict(size=9, color="#718096")),
        yaxis=dict(tickfont=dict(size=9, color="#2D3748"), showgrid=False),
        showlegend=False,
    )
    return fig


def _etf_heatmap(signals: list[dict]) -> go.Figure:
    # Build annotated driver labels with current signal level
    sig_level = {s["signal"]: s["lv"] for s in signals}
    driver_labels = list(_HM_DRIVERS)
    for sig_name, col_idx in _SIG_COL.items():
        lv = sig_level.get(sig_name, "")
        if lv and lv != "N/A":
            lv_kor = _LEVEL_KOR.get(lv.upper(), lv)
            driver_labels[col_idx] = f"{_HM_DRIVERS[col_idx]}<br><sub>{lv_kor}</sub>"

    colorscale = [
        [0.0, "#F7F8FA"],
        [0.5, "#FEEBC8"],
        [1.0, "#F6AD55"],
    ]

    fig = go.Figure(go.Heatmap(
        z=_HM_Z,
        x=_HM_DRIVERS,
        y=_HM_ETFS,
        colorscale=colorscale,
        zmin=0, zmax=2,
        showscale=False,
        hovertemplate="<b>%{y}</b><br>%{x}: 노출도 %{z}/2<extra></extra>",
        xgap=2, ygap=2,
    ))

    # Dot annotations for non-zero cells
    dot_map = {0: "", 1: "·", 2: "●"}
    for i, row in enumerate(_HM_Z):
        for j, val in enumerate(row):
            if val > 0:
                fig.add_annotation(
                    x=_HM_DRIVERS[j], y=_HM_ETFS[i],
                    text=dot_map[val], showarrow=False,
                    font=dict(size=10, color="#744210" if val == 2 else "#92400E"),
                )

    fig.update_layout(
        title=dict(text="ETF 드라이버 노출도  (● 높음  ·  중간  □ 없음)",
                   font=dict(size=10, color="#718096"), x=0, xanchor="left"),
        margin=dict(l=0, r=0, t=30, b=0), height=440,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        xaxis=dict(side="top", tickfont=dict(size=9, color="#2D3748"),
                   tickangle=0, showgrid=False),
        yaxis=dict(tickfont=dict(size=8.5, color="#2D3748"),
                   autorange="reversed", showgrid=False),
    )
    return fig


# ── HTML helpers (unchanged) ──────────────────────────────────────────────────

def _badge(chg):
    if not isinstance(chg, (int, float)): return '<span class="neut">—</span>'
    if chg >  0.3: return '<span class="bull">↑</span>'
    if chg < -0.3: return '<span class="bear">↓</span>'
    return '<span class="neut">→</span>'


def _pct(v):
    if not isinstance(v, (int, float)): return "N/A", "neu"
    cls = "pos" if v > 0.005 else ("neg" if v < -0.005 else "neu")
    return f"{'+'if v>=0 else ''}{v:.2f}%", cls


def _snapshot_html(data: dict) -> str:
    bm   = data["benchmarks"]
    comm = data["commodities"]
    fxd  = data["fx"]
    mac  = data["macro"]

    def _bv(df, id_col, id_val, price_col, fmt):
        r = df[df[id_col] == id_val]
        if r.empty: return "N/A", None
        p = r.iloc[0][price_col]; c = r.iloc[0].get("change_pct")
        return (format(float(p), fmt) if isinstance(p, (int, float)) else "N/A",
                float(c) if isinstance(c, (int, float)) else None)

    spy_v,  spy_c   = _bv(bm,   "ticker", "SPY",     "price", ",.2f")
    qqq_v,  qqq_c   = _bv(bm,   "ticker", "QQQ",     "price", ",.2f")
    soxx_v, soxx_c  = _bv(bm,   "ticker", "SOXX",    "price", ",.2f")
    krw_v,  krw_c   = _bv(fxd,  "pair",   "usd_krw", "rate",  ",.1f")
    dxy_v,  dxy_c   = _bv(fxd,  "pair",   "dxy",     "rate",  ".2f")
    gld_v,  gld_c   = _bv(comm, "name",   "gold",    "price", ",.2f")
    slv_v,  slv_c   = _bv(comm, "name",   "silver",  "price", ".2f")
    cop_v,  cop_c   = _bv(comm, "name",   "copper",  "price", ".3f")

    us10y = "N/A"
    if mac is not None and not mac.empty:
        r = mac[mac["key"] == "us_10y"]
        if not r.empty and isinstance(r.iloc[0]["value"], (int, float)):
            us10y = f"{float(r.iloc[0]['value']):.2f}%"

    def row(sym, name, val, chg, sep=False):
        pct_s, cls = _pct(chg)
        sep_cls = ' class="sep"' if sep else ""
        return (f'<tr{sep_cls}><td class="sym">{sym}</td><td class="nm">{name}</td>'
                f'<td class="r">{val}</td><td class="r {cls}">{pct_s}</td>'
                f'<td class="r">{_badge(chg)}</td></tr>')

    def _u(val, prefix="$"):
        return f"{prefix}{val}" if val != "N/A" else val

    thead = ('<thead><tr><th>종목</th><th>자산명</th>'
             '<th class="r">현재가</th><th class="r">1D %</th><th class="r">방향</th></tr></thead>')

    def row6(sym, name, val, unit, chg, sep=False):
        pct_s, cls = _pct(chg)
        sep_cls = ' class="sep"' if sep else ""
        val_cell = (f'{val}&nbsp;<span style="color:#718096;font-size:9px">{unit}</span>'
                    if val != "N/A" else "N/A")
        return (f'<tr{sep_cls}><td class="sym">{sym}</td><td class="nm">{name}</td>'
                f'<td class="r">{val_cell}</td>'
                f'<td class="r {cls}">{pct_s}</td>'
                f'<td class="r">{_badge(chg)}</td></tr>')

    rows = [
        row6("SPY",     "S&P 500",         spy_v,   "USD",    spy_c),
        row6("QQQ",     "나스닥 100",       qqq_v,   "USD",    qqq_c),
        row6("SOXX",    "반도체 ETF",       soxx_v,  "USD",    soxx_c),
        row6("USD/KRW", "달러 / 원화",      krw_v,   "원/달러", krw_c,  sep=True),
        row6("DXY",     "달러 인덱스",      dxy_v,   "index",  dxy_c),
        row6("US 10Y",  "미국 10년 국채",   us10y,   "%",      None),
        row6("금",      "금 선물",          gld_v,   "$/oz",   gld_c,  sep=True),
        row6("은",      "은 선물",          slv_v,   "$/oz",   slv_c),
        row6("구리",    "구리 선물",        cop_v,   "$/lb",   cop_c),
    ]
    return f'<div class="fin-t"><table>{thead}<tbody>{"".join(rows)}</tbody></table></div>'


def _snapshot_bar(data: dict) -> go.Figure:
    bm   = data["benchmarks"]
    comm = data["commodities"]
    fxd  = data["fx"]

    def _c(df, id_col, id_val):
        r = df[df[id_col] == id_val]
        if r.empty: return None
        v = r.iloc[0].get("change_pct")
        return float(v) if isinstance(v, (int, float)) else None

    assets = [
        ("구리",     _c(comm, "name",   "copper")),
        ("은",       _c(comm, "name",   "silver")),
        ("금",       _c(comm, "name",   "gold")),
        ("DXY",      _c(fxd,  "pair",   "dxy")),
        ("USD/KRW",  _c(fxd,  "pair",   "usd_krw")),
        ("SOXX",     _c(bm,   "ticker", "SOXX")),
        ("QQQ",      _c(bm,   "ticker", "QQQ")),
        ("SPY",      _c(bm,   "ticker", "SPY")),
    ]
    labels = [a[0] for a in assets if a[1] is not None]
    values = [a[1] for a in assets if a[1] is not None]
    colors = ["#276749" if v >= 0 else "#9B2335" for v in values]
    texts  = [f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%" for v in values]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors, marker_opacity=0.72,
        text=texts, textposition="outside",
        textfont=dict(size=9, color="#4A5568"),
        cliponaxis=False,
    ))
    fig.update_layout(
        margin=dict(l=0, r=60, t=4, b=0), height=180,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#F7F8FA",
        xaxis=dict(showgrid=True, gridcolor="#F0F4F8",
                   zeroline=True, zerolinecolor="#CBD5E0", zerolinewidth=1,
                   tickformat="+.2f", ticksuffix="%",
                   tickfont=dict(size=9, color="#718096")),
        yaxis=dict(tickfont=dict(size=10, color="#2D3748",
                   family="'SF Mono',ui-monospace,monospace"), showgrid=False),
        showlegend=False,
    )
    return fig


def _regime_html(signals: list[dict]) -> str:
    thead = '<thead><tr><th>신호</th><th>단계</th><th>설명</th></tr></thead>'
    rows = [
        f'<tr><td class="sig">{_SIG_KOR.get(s["signal"], s["signal"])}</td>'
        f'<td><span class="rl-{s["col"]}">{_LEVEL_KOR.get(s["lv"].upper(), s["lv"])}</span></td>'
        f'<td class="cmt">{s["note"]}</td></tr>'
        for s in signals
    ]
    return f'<div class="fin-t"><table>{thead}<tbody>{"".join(rows)}</tbody></table></div>'


def _etf_impact(config: dict, data: dict) -> pd.DataFrame:
    bm_df  = data["benchmarks"]
    co_df  = data["commodities"]
    fx_df  = data["fx"]
    st_df  = data["us_stocks"]
    mac    = data["macro"]

    def _chg(df, id_col, id_val):
        r = df[df[id_col] == id_val]
        if r.empty: return None
        v = r.iloc[0].get("change_pct")
        return float(v) if isinstance(v, (int, float)) else None

    def _lookup(drv: str):
        v = _chg(bm_df, "ticker", drv)
        if v is None: v = _chg(st_df, "ticker", drv)
        if v is None: v = _chg(co_df, "name", drv.lower())
        if v is None:
            pair = drv.lower().replace("/", "_").replace(" ", "_")
            v = _chg(fx_df, "pair", pair)
        return v

    def _top(drivers: list) -> str:
        best_d, best_a = None, 0.0
        for d in drivers:
            v = _lookup(d)
            if v is not None and abs(v) > best_a:
                best_d, best_a = d, abs(v)
        if best_d is None: return "N/A"
        v = _lookup(best_d)
        return f"{best_d}  {'+'if v>=0 else ''}{v:.2f}%"

    us10y = None
    if mac is not None and not mac.empty:
        r = mac[mac["key"] == "us_10y"]
        if not r.empty and isinstance(r.iloc[0]["value"], (int, float)):
            us10y = float(r.iloc[0]["value"])

    krw_c = _chg(fx_df, "pair", "usd_krw")
    rows = []
    for etf in config["my_etfs"]:
        bm_t   = etf.get("benchmark", "")
        bm_c   = _chg(bm_df, "ticker", bm_t)
        hedged = etf.get("hedged", False)
        if hedged:
            note = "환헤지 — FX 영향 차단"
        elif krw_c is not None:
            if   krw_c > 0.3:  note = "원화 약세 → 환손실 주의"
            elif krw_c < -0.3: note = "원화 강세 → 환이익"
            else:               note = "환율 안정"
        else:
            note = ""
        rows.append({
            "ETF":        etf["name"],
            "분류":       etf.get("category", "—"),
            "주요 드라이버": _top(etf.get("drivers", [])),
            "BM":         bm_t,
            "BM 1D%":     bm_c,
            "FX 1D%":     krw_c,
            "10Y 금리":   f"{us10y:.2f}%" if us10y is not None else "N/A",
            "FX 영향":    note,
        })
    return numeric(pd.DataFrame(rows), ["BM 1D%", "FX 1D%"])


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    inject_css()

    c1, c2 = st.columns([9, 1])
    c1.markdown("## 시장 전체 현황")
    c1.caption("글로벌 시장 스냅샷  ·  투자 참고용, 매매 권유 아님")
    if c2.button("↻ 새로고침", use_container_width=True):
        _load.clear()
        _multi_history.clear()

    with st.spinner(""):
        data   = _load()
        config = load_config()

    ts = data["fetched_at"][:19].replace("T", " ")
    st.markdown(timestamp_bar(ts), unsafe_allow_html=True)

    signals = compute_regime_signals(data)

    # ── 1. Market Snapshot ───────────────────────────────────────────────────
    st.markdown(section_header("시장 스냅샷", "주요 지표 한눈에 보기"),
                unsafe_allow_html=True)
    st.markdown(_snapshot_html(data), unsafe_allow_html=True)
    st.plotly_chart(_snapshot_bar(data), use_container_width=True,
                    config={"displayModeBar": False})

    # ── 2. Normalized Performance ────────────────────────────────────────────
    st.markdown(section_header("성과 비교", "기간 시작일 기준 정규화 100"),
                unsafe_allow_html=True)

    p_col, a_col = st.columns([1, 3])
    with p_col:
        period = st.radio("기간", ["1M", "3M", "6M"], index=1, horizontal=True,
                          label_visibility="collapsed")
    with a_col:
        selected = st.multiselect(
            "자산 선택",
            list(_PERF_TICKERS.keys()),
            default=_PERF_DEFAULTS,
            label_visibility="collapsed",
        )

    st.plotly_chart(_perf_chart(period, selected or _PERF_DEFAULTS),
                    use_container_width=True, config={"displayModeBar": False})

    # ── 3. Asset Rotation ────────────────────────────────────────────────────
    st.markdown(section_header("자산 순환 흐름", "기간별 수익률 비교"),
                unsafe_allow_html=True)
    st.plotly_chart(_rotation_chart(period), use_container_width=True,
                    config={"displayModeBar": False})

    # ── 4. Market Regime + Signal Bar ────────────────────────────────────────
    st.markdown(section_header("시장 국면", "신호 기반 현재 상태"),
                unsafe_allow_html=True)
    r_left, r_right = st.columns([1, 1])
    with r_left:
        st.markdown(_regime_html(signals), unsafe_allow_html=True)
    with r_right:
        st.plotly_chart(_regime_bar(signals), use_container_width=True,
                        config={"displayModeBar": False})

    # ── 5. ETF Driver Heatmap ────────────────────────────────────────────────
    st.markdown(section_header("ETF 드라이버 노출도",
                               "노출도: ● 높음  ·  중간  □ 없음"),
                unsafe_allow_html=True)
    st.plotly_chart(_etf_heatmap(signals), use_container_width=True,
                    config={"displayModeBar": False})

    # ── 6. My ETF Impact ─────────────────────────────────────────────────────
    st.markdown(section_header("내 ETF — 드라이버 영향",
                               "주요 드라이버의 보유 자산 당일 영향"),
                unsafe_allow_html=True)
    impact_df = _etf_impact(config, data)

    def _cell(v):
        if not isinstance(v, (int, float)) or pd.isna(v): return ""
        if v > 0.005:  return "background-color:#F0FFF6;color:#276749;font-weight:600"
        if v < -0.005: return "background-color:#FFF5F5;color:#9B2335;font-weight:600"
        return ""

    st.dataframe(
        impact_df.style.map(_cell, subset=["BM 1D%", "FX 1D%"]),
        column_config={
            "BM 1D%": st.column_config.NumberColumn(format="%.2f%%"),
            "FX 1D%": st.column_config.NumberColumn(format="%.2f%%"),
        },
        use_container_width=True, hide_index=True,
    )

    # ── 7. Export ─────────────────────────────────────────────────────────────
    with st.expander("데이터 내보내기", expanded=False):
        mac  = data["macro"]
        comm = data["commodities"]
        fx   = data["fx"]
        today = ts[:10]
        sheets = {
            "보유ETF":  data["my_etfs"].rename(columns=_ETF),
            "벤치마크": data["benchmarks"].rename(columns=_BENCH),
            "미국주식": data["us_stocks"].rename(columns=_STOCK),
            "원자재":   comm.rename(columns=_COMM),
            "환율":     fx.rename(columns=_FX),
        }
        if mac is not None and not mac.empty:
            sheets["매크로"] = mac.rename(columns=_MAC)
        dl1, dl2, _ = st.columns([1, 1, 6])
        dl1.download_button("↓ 전체 Excel", excel_bytes(sheets),
                            f"SIMvest_{today}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
        dl2.download_button("↓ ETF CSV",
                            csv_bytes(sheets["보유ETF"]),
                            f"SIMvest_etf_{today}.csv",
                            "text/csv", use_container_width=True)
